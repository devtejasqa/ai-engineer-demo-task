import re
import difflib

# Seed list of known canonical AI startup names.
# Add more as needed — this is intentionally small for the trial.
CANONICAL_STARTUPS = [
    "OpenAI", "Anthropic", "Google DeepMind", "Meta AI", "Microsoft",
    "Mistral AI", "Cohere", "Stability AI", "Hugging Face", "Scale AI",
    "Perplexity AI", "Character.AI", "Inflection AI", "Adept AI",
    "Runway", "ElevenLabs", "Midjourney", "xAI", "Databricks",
    "Together AI", "Groq", "Cerebras", "SambaNova", "Lambda Labs",
    "Replit", "GitHub", "NVIDIA", "AMD", "Amazon", "Apple",
    "Tesla", "IBM", "Salesforce", "Snowflake", "Palantir",
    "Vercel", "LangChain", "LlamaIndex", "Weights & Biases",
    "Pinecone", "Weaviate", "Qdrant", "Chroma", "Modal",
    "Baseten", "Fireworks AI", "DeepSeek", "Alibaba", "ByteDance",
    "Z.ai", "Zhipu AI",
]

# Common suffixes/noise to strip before comparing.
NOISE_PATTERNS = [
    r"\bInc\.?\b", r"\bLLC\b", r"\bLtd\.?\b", r"\bCorp\.?\b",
    r"\bCorporation\b", r"\bCompany\b", r"\bCo\.?\b",
    r"\bGroup\b", r"\bHoldings\b", r"\.com\b",
]


def normalize(name):
    """Lowercase, strip punctuation/legal suffixes, collapse whitespace."""
    if not name:
        return ""
    cleaned = name
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)  # strip punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def resolve_entity(raw_name, canonical_list=CANONICAL_STARTUPS, threshold=0.82):
    """
    Match a raw/messy entity name against the canonical list.
    Returns (canonical_name, confidence) or (raw_name, 0.0) if no match found.
    """
    if not raw_name:
        return raw_name, 0.0

    normalized_raw = normalize(raw_name)
    normalized_lookup = {normalize(c): c for c in canonical_list}

    # Exact match after normalization
    if normalized_raw in normalized_lookup:
        return normalized_lookup[normalized_raw], 1.0

    # Fuzzy match using difflib's sequence matcher
    best_match = None
    best_score = 0.0
    for norm_canonical, original_canonical in normalized_lookup.items():
        score = difflib.SequenceMatcher(None, normalized_raw, norm_canonical).ratio()
        if score > best_score:
            best_score = score
            best_match = original_canonical

    if best_score >= threshold:
        return best_match, round(best_score, 3)

    # No confident match — return the raw name as-is, flagged as unresolved.
    return raw_name, 0.0


def resolve_batch(raw_names, canonical_list=CANONICAL_STARTUPS, threshold=0.82):
    """Resolve a list of raw names, returning a mapping log for each."""
    log = []
    for raw in raw_names:
        canonical, confidence = resolve_entity(raw, canonical_list, threshold)
        log.append({
            "raw_name": raw,
            "canonical_name": canonical,
            "confidence": confidence,
            "resolved": confidence >= threshold,
        })
    return log


if __name__ == "__main__":
    # Quick smoke test
    test_names = [
        "OpenAI, Inc.",
        "Open AI",
        "openai.com",
        "Anthropic PBC",
        "Some Random Startup That Won't Match",
        "Hugging Face Inc",
        "DeepSeek AI",
    ]

    results = resolve_batch(test_names)
    for r in results:
        status = "✓ MATCHED" if r["resolved"] else "✗ unresolved"
        print(f"{status:15} '{r['raw_name']}' -> '{r['canonical_name']}' (confidence: {r['confidence']})")