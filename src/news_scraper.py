import aiohttp
import asyncio
import json
from datetime import datetime, timezone, timedelta

HN_TOP_STORIES = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"


async def fetch_json(session, url):
    try:
        async with session.get(url, timeout=15) as response:
            if response.status == 200:
                return await response.json()
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def is_within_24h(epoch_timestamp):
    if not epoch_timestamp:
        return False
    posted = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
    return (datetime.now(timezone.utc) - posted) <= timedelta(hours=24)


async def scrape_news(session, ai_only=True, max_check=200):
    """
    Pull recent AI-related news from Hacker News' public API,
    filtered to stories posted in the last 24 hours.
    """
    story_ids = await fetch_json(session, HN_TOP_STORIES)
    if not story_ids:
        return []

    story_ids = story_ids[:max_check]

    tasks = [fetch_json(session, HN_ITEM_URL.format(sid)) for sid in story_ids]
    items = await asyncio.gather(*tasks)

    results = []
    ai_keywords = ["ai", "llm", "gpt", "openai", "anthropic", "machine learning",
                   "neural", "claude", "gemini", "deepseek", "artificial intelligence"]

    for item in items:
        if not item or item.get("type") != "story":
            continue

        title = (item.get("title") or "").lower()
        if ai_only and not any(kw in title for kw in ai_keywords):
            continue

        epoch = item.get("time")
        if not is_within_24h(epoch):
            continue

        results.append({
            "schemaVersion": "1.0",
            "recordType": "NEWS",
            "source": {"name": "Hacker News", "url": item.get("url") or f"https://news.ycombinator.com/item?id={item.get('id')}"},
            "content": {
                "title": item.get("title"),
                "published_date": datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat() if epoch else None,
                "score": item.get("score"),
                "comments_count": item.get("descendants", 0),
            },
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        })

    return results


async def main():
    async with aiohttp.ClientSession() as session:
        news = await scrape_news(session, ai_only=True, max_check=200)
        with open("data/news.json", "w", encoding="utf-8") as f:
            json.dump(news, f, indent=2)
        print(f"Saved {len(news)} AI news items (posted in last 24h) to data/news.json")
        if news:
            print(json.dumps(news[0], indent=2))
        else:
            print("No matching AI news in the last 24h among checked stories — honest result, not a bug.")


if __name__ == "__main__":
    asyncio.run(main())