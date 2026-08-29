import aiohttp
import asyncio
import json
from datetime import datetime, timezone

YC_API_URL = "https://yc-oss.github.io/api/companies/all.json"


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


async def scrape_startups(session, limit=1000):
    """
    Pull startup records from the YC Open Source companies dataset
    (a public, community-maintained mirror of YC's public company directory).
    """
    data = await fetch_json(session, YC_API_URL)
    if not data:
        return []

    results = []
    for company in data[:limit]:
        results.append({
            "schemaVersion": "1.0",
            "recordType": "STARTUP",
            "source": {"name": "YC Company Directory", "url": company.get("url", YC_API_URL)},
            "content": {
                "entityName": company.get("name"),
                "data": {
                    "employeeCount": company.get("team_size"),
                    "batch": company.get("batch"),
                    "industry": company.get("industry"),
                    "one_liner": company.get("one_liner"),
                    "website": company.get("website"),
                },
            },
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        })

    return results


async def main():
    async with aiohttp.ClientSession() as session:
        startups = await scrape_startups(session, limit=1000)
        with open("data/startups.json", "w", encoding="utf-8") as f:
            json.dump(startups, f, indent=2)
        print(f"Saved {len(startups)} startups to data/startups.json")
        if startups:
            print(json.dumps(startups[0], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
    