import asyncio
import json
import os
from datetime import datetime, timezone

from scraper import discover_paper_ids, scrape_papers_bulk
from entity_resolver import resolve_batch
import aiohttp


OUTPUT_DIR = "data"


def save_json(data, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(data) if isinstance(data, list) else 1} record(s) to {path}")


async def run_research_papers_pipeline(session, max_pages=2, sample_size=5):
    """Phase I: discover + scrape research papers."""
    print("\n=== PHASE I: Research Papers ===")
    paper_ids = await discover_paper_ids(session, max_pages=max_pages)
    print(f"Discovered {len(paper_ids)} paper IDs")

    sample_ids = paper_ids[:sample_size]
    papers = await scrape_papers_bulk(session, sample_ids, concurrency=3)
    save_json(papers, "papers.json")
    return papers


def extract_author_names(papers):
    """
    Pull plain author name strings out of scraped papers.
    Handles both raw string authors and JSON-LD style {"name": "..."} objects.
    """
    raw_names = []
    for paper in papers:
        authors = paper.get("content", {}).get("authors", [])
        for author in authors:
            if isinstance(author, dict):
                name = author.get("name")
                if name:
                    raw_names.append(name)
            elif isinstance(author, str):
                raw_names.append(author)
    return raw_names


def run_entity_resolution_pipeline(papers):
    """Phase IV: resolve entity names found across scraped records."""
    print("\n=== PHASE IV: Entity Resolution ===")

    raw_names = extract_author_names(papers)

    if not raw_names:
        print("No entity names found to resolve yet (authors were empty for this source).")
        return []

    resolution_log = resolve_batch(raw_names)
    save_json(resolution_log, "entity_mapping_log.json")
    return resolution_log


async def main():
    print(f"Pipeline run started: {datetime.now(timezone.utc).isoformat()}")

    async with aiohttp.ClientSession() as session:
        papers = await run_research_papers_pipeline(session, max_pages=2, sample_size=5)

    entity_log = run_entity_resolution_pipeline(papers)

    print("\n=== SUMMARY ===")
    print(f"Papers scraped: {len(papers)}")
    print(f"Entity mappings logged: {len(entity_log)}")
    print("\nNext steps not yet wired in: startup/product scraping, "
          "news/jobs freshness pipeline, LLM extraction on raw HTML, "
          "Google Sheets export.")


if __name__ == "__main__":
    asyncio.run(main())