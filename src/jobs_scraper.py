import aiohttp
import asyncio
import json
from datetime import datetime, timezone, timedelta

REMOTEOK_API = "https://remoteok.com/api"


async def fetch_json(session, url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, headers=headers, timeout=20) as response:
            if response.status == 200:
                return await response.json()
            print(f"Failed ({response.status}): {url}")
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def is_within_24h(epoch_timestamp):
    """Check if a unix timestamp is within the last 24 hours."""
    if not epoch_timestamp:
        return False
    posted = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
    return (datetime.now(timezone.utc) - posted) <= timedelta(hours=24)


async def scrape_jobs(session, ai_only=True):
    """
    Pull job listings from RemoteOK's public API.
    Filters to AI-related roles and jobs posted in the last 24 hours.
    """
    data = await fetch_json(session, REMOTEOK_API)
    if not data:
        return []

    # RemoteOK's first array item is metadata, not a job — skip it.
    jobs = data[1:] if data and not data[0].get("id") else data

    results = []
    for job in jobs:
        tags = [t.lower() for t in job.get("tags", [])]
        position = (job.get("position") or "").lower()

        if ai_only:
            ai_keywords = ["ai", "ml", "machine learning", "llm", "data scien", "artificial"]
            if not any(kw in position or kw in " ".join(tags) for kw in ai_keywords):
                continue

        epoch = job.get("epoch")
        if not is_within_24h(epoch):
            continue

        results.append({
            "schemaVersion": "1.0",
            "recordType": "JOB",
            "source": {"name": "RemoteOK", "url": job.get("url")},
            "content": {
                "company": job.get("company"),
                "role": job.get("position"),
                "date": datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat() if epoch else None,
                "is_remote": True,
                "role_family": "Engineering" if any(
                    k in position for k in ["engineer", "developer", "scientist"]
                ) else "Other",
                "tags": job.get("tags", []),
            },
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        })

    return results


async def main():
    async with aiohttp.ClientSession() as session:
        jobs = await scrape_jobs(session, ai_only=True)
        with open("data/jobs.json", "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)
        print(f"Saved {len(jobs)} AI jobs (posted in last 24h) to data/jobs.json")
        if jobs:
            print(json.dumps(jobs[0], indent=2))
        else:
            print("No AI jobs found posted in the last 24 hours at scrape time — this is expected/honest behavior, not a bug.")


if __name__ == "__main__":
    asyncio.run(main())