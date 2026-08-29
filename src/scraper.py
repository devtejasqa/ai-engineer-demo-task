import aiohttp
import asyncio
from bs4 import BeautifulSoup
import json

async def fetch_page(session, url):
    """Fetch raw HTML from a URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, headers=headers, timeout=15) as response:
            if response.status == 200:
                return await response.text()
            else:
                print(f"Failed ({response.status}): {url}")
                return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

async def scrape_paper(session, url):
    """Scrape a single Papers with Code paper page."""
    html = await fetch_page(session, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Try to grab the title
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "Unknown"

    return {
        "recordType": "RESEARCH_PAPER",
        "content": {
            "title": title,
            "paper_url": url,
        },
        "source": {"name": "Papers with Code", "url": url}
    }

async def main():
    test_urls = [
        "https://paperswithcode.com/paper/attention-is-all-you-need",
    ]

    async with aiohttp.ClientSession() as session:
        results = []
        for url in test_urls:
            result = await scrape_paper(session, url)
            if result:
                results.append(result)

        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(main())