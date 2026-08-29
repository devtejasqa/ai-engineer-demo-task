import os
import json
import asyncio
import random
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Rough token estimate: ~4 chars per token. Keep prompts well under
# common context limits to avoid 413 Payload Too Large errors.
MAX_CHARS_PER_CHUNK = 12000

EXTRACTION_SCHEMA_PROMPT = """You are a data extraction engine. Given raw text, extract
structured information and return ONLY valid JSON matching this shape, nothing else:

{
  "entityName": "string or null",
  "entityType": "STARTUP | PRODUCT | RESEARCH_PAPER | JOB | null",
  "summary": "one sentence summary",
  "keyFacts": ["fact1", "fact2"]
}

Text to extract from:
---
{TEXT}
---
"""


def chunk_text(text, max_chars=MAX_CHARS_PER_CHUNK):
    """
    Split text into chunks that stay under a safe character limit,
    breaking on paragraph boundaries where possible to keep chunks
    semantically coherent.
    """
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            # If a single paragraph is itself too long, hard-split it.
            if len(para) > max_chars:
                for i in range(0, len(para), max_chars):
                    chunks.append(para[i:i + max_chars])
                current = ""
            else:
                current = para + "\n\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks


async def call_gemini(prompt):
    """Call Gemini Flash. Raises on failure so the fallback chain can catch it."""
    import google.generativeai as genai

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    response = await asyncio.to_thread(model.generate_content, prompt)
    return response.text


async def call_groq(prompt):
    """Call Groq's Llama 3 endpoint."""
    from groq import Groq

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")

    client = Groq(api_key=GROQ_API_KEY)

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


async def call_deepseek(prompt):
    """Call DeepSeek via its OpenAI-compatible API."""
    from openai import OpenAI

    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


async def call_with_retry(fn, prompt, max_retries=3):
    """
    Call an LLM function with exponential backoff + jitter on failure.
    Used per-provider before falling through to the next one in the chain.
    """
    for attempt in range(max_retries):
        try:
            return await fn(prompt)
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = "429" in err_str or "rate" in err_str
            if attempt == max_retries - 1:
                raise
            base_delay = 2 ** attempt
            jitter = random.uniform(0, 1)
            delay = base_delay + jitter
            reason = "rate limit" if is_rate_limit else "error"
            print(f"    Retry {attempt + 1}/{max_retries} after {reason}: {e} (waiting {delay:.1f}s)")
            await asyncio.sleep(delay)


async def extract_structured_data(raw_text):
    """
    Multi-tier fallback extraction: Gemini Flash -> Groq Llama 3 -> DeepSeek.
    Chunks the input text first to avoid 413 errors, then extracts each chunk.
    """
    chunks = chunk_text(raw_text)
    all_results = []

    providers = [
        ("Gemini Flash", call_gemini),
        ("Groq Llama 3", call_groq),
        ("DeepSeek", call_deepseek),
    ]

    for i, chunk in enumerate(chunks):
        prompt = EXTRACTION_SCHEMA_PROMPT.replace("{TEXT}", chunk)
        result_text = None
        last_error = None

        for provider_name, provider_fn in providers:
            try:
                print(f"  Chunk {i + 1}/{len(chunks)}: trying {provider_name}...")
                result_text = await call_with_retry(provider_fn, prompt)
                print(f"  Chunk {i + 1}/{len(chunks)}: succeeded with {provider_name}")
                break
            except Exception as e:
                last_error = e
                print(f"  Chunk {i + 1}/{len(chunks)}: {provider_name} failed ({e}), falling back...")
                continue

        if result_text is None:
            print(f"  Chunk {i + 1}/{len(chunks)}: ALL providers failed. Last error: {last_error}")
            all_results.append({"error": "all_providers_failed", "chunk_index": i})
            continue

        try:
            cleaned = result_text.strip().removeprefix("```json").removesuffix("```").strip()
            parsed = json.loads(cleaned)
            all_results.append(parsed)
        except json.JSONDecodeError:
            all_results.append({"error": "invalid_json_response", "raw_response": result_text})

    return all_results


if __name__ == "__main__":
    sample_text = """
    OpenAI released GPT-5 today, a major upgrade to its flagship model.
    The company, based in San Francisco, has raised over $10 billion in funding.
    """

    results = asyncio.run(extract_structured_data(sample_text))
    print(json.dumps(results, indent=2))