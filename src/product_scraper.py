import aiohttp
import asyncio
import json
from datetime import datetime, timezone

# Reuse the YC dataset — each company often has a distinct product,
# so we derive product records from the same source, mapped to a
# different schema (PRODUCT instead of STARTUP).
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


def guess_pricing_model(one_liner, tags):
    """
    Very rough heuristic pricing model guess based on keywords.
    A real implementation would visit the product page; this is a
    fast placeholder classification for the trial.
    """
    text = f"{one_liner or ''} {' '.join(tags or [])}".lower()
    if "enterprise" in text:
        return "ENTERPRISE"
    if "free" in text:
        return "FREE"
    if "open source" in text or "open-source" in text:
        return "FREE"
    return "FREEMIUM"


async def scrape_products(session, limit=1000):
    """Derive product records from the YC companies dataset."""
    data = await fetch_json(session, YC_API_URL)
    if not data:
        return []

    results = []
    for company in data[:limit]:
        results.append({
            "schemaVersion": "1.0",
            "recordType": "PRODUCT",
            "source": {"name": "YC Company Directory", "url": company.get("url", YC_API_URL)},
            "content": {
                "startupName": company.get("name"),
                "productName": company.get("name"),
                "pricingModel": guess_pricing_model(company.get("one_liner"), company.get("tags")),
                "description": company.get("one_liner"),
                "website": company.get("website"),
            },
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        })

    return results


async def main():
    async with aiohttp.ClientSession() as session:
        products = await scrape_products(session, limit=1000)
        with open("data/products.json", "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2)
        print(f"Saved {len(products)} products to data/products.json")
        if products:
            print(json.dumps(products[0], indent=2))


if __name__ == "__main__":
    asyncio.run(main())