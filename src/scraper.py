import aiohttp
import asyncio
import json
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup

PWC_BASE = "https://paperswithcode.co"
GITHUB_API_BASE = "https://api.github.com/repos"


# ---------------------------------------------------------------------------
# Low-level fetch helpers
# ---------------------------------------------------------------------------

async def fetch_text(session, url):
    """Fetch raw HTML/text from a URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, headers=headers, timeout=15) as response:
            if response.status == 200:
                return await response.text()
            print(f"Failed ({response.status}): {url}")
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


async def fetch_json(session, url):
    """Fetch and parse JSON from a URL. Returns (status, data)."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, headers=headers, timeout=15) as response:
            if response.status == 200:
                return response.status, await response.json()
            return response.status, None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None, None


# ---------------------------------------------------------------------------
# Discovery: walk the listing pages to collect paper IDs
# ---------------------------------------------------------------------------

async def discover_paper_ids(session, max_pages=5):
    """
    Walk the /papers/recent listing (with pagination) and collect paper IDs.
    Each page lists ~100 papers; max_pages controls how many pages we crawl.
    """
    paper_ids = []
    url = f"{PWC_BASE}/papers/recent"

    for page_num in range(1, max_pages + 1):
        html = await fetch_text(session, url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        links = soup.select("main ol li a[href^='/paper/']")

        page_ids = []
        for link in links:
            href = link.get("href", "")
            paper_id = href.replace("/paper/", "").strip("/")
            if paper_id:
                page_ids.append(paper_id)

        paper_ids.extend(page_ids)
        print(f"  Page {page_num}: found {len(page_ids)} paper IDs (total so far: {len(paper_ids)})")

        next_link = soup.find("a", {"rel": "next"})
        if not next_link or not next_link.get("href"):
            print("  No more pages.")
            break

        next_href = next_link["href"]
        url = f"{PWC_BASE}{next_href}" if next_href.startswith("/") else next_href

    return paper_ids


# ---------------------------------------------------------------------------
# Detail extraction: scrape one paper page + enrich with GitHub stars
# ---------------------------------------------------------------------------

def extract_jsonld(html):
    """Pull the ScholarlyArticle block out of the page's JSON-LD script tag."""
    soup = BeautifulSoup(html, "html.parser")
    script_tag = soup.find("script", {"type": "application/ld+json"})
    if not script_tag or not script_tag.string:
        return None

    data = json.loads(script_tag.string)
    graph = data.get("@graph", [])
    for item in graph:
        if item.get("@type") == "ScholarlyArticle":
            return item
    return None


def github_url_to_owner_repo(github_url):
    """Turn 'https://github.com/owner/repo' into ('owner', 'repo')."""
    match = re.search(r"github\.com/([^/]+)/([^/]+)/?$", github_url.rstrip("/"))
    if not match:
        return None, None
    return match.group(1), match.group(2)


async def fetch_github_stars(session, github_url):
    """Query GitHub's public API for a repo's current star count."""
    owner, repo = github_url_to_owner_repo(github_url)
    if not owner or not repo:
        return None

    api_url = f"{GITHUB_API_BASE}/{owner}/{repo}"
    status, data = await fetch_json(session, api_url)

    if status == 403:
        # Unauthenticated GitHub API calls are rate-limited (60/hour per IP).
        print(f"  GitHub rate limit hit for {owner}/{repo}")
        return None
    if data:
        return data.get("stargazers_count")
    return None


async def scrape_paper(session, paper_id):
    """Scrape one paperswithcode.co paper page and enrich with GitHub stars."""
    url = f"{PWC_BASE}/paper/{paper_id}"
    html = await fetch_text(session, url)
    if not html:
        return None

    article = extract_jsonld(html)
    if not article:
        print(f"No structured data found for {paper_id}")
        return None

    code_repos = article.get("codeRepository", [])

    star_tasks = [fetch_github_stars(session, repo) for repo in code_repos]
    star_counts = await asyncio.gather(*star_tasks) if code_repos else []

    repos_with_stars = [
        {"github_url": repo, "github_stars": stars}
        for repo, stars in zip(code_repos, star_counts)
    ]

    primary_github_url = code_repos[0] if code_repos else None
    primary_stars = star_counts[0] if star_counts else None

    return {
        "schemaVersion": "1.0",
        "recordType": "RESEARCH_PAPER",
        "source": {"name": "Papers with Code", "url": url},
        "content": {
            "title": article.get("headline"),
            "authors": article.get("author", []),
            "paper_url": article.get("url"),
            "github_url": primary_github_url,
            "github_stars": primary_stars,
            "all_linked_repos": repos_with_stars,
            "published_date": article.get("datePublished"),
        },
        "collectedAt": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Bulk scrape: discover IDs, then scrape each one (with basic concurrency)
# ---------------------------------------------------------------------------

async def scrape_papers_bulk(session, paper_ids, concurrency=5):
    """Scrape many papers with a concurrency limit so we don't hammer the site."""
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def bounded_scrape(pid):
        async with semaphore:
            return await scrape_paper(session, pid)

    tasks = [bounded_scrape(pid) for pid in paper_ids]
    for i, coro in enumerate(asyncio.as_completed(tasks), start=1):
        result = await coro
        if result:
            results.append(result)
        if i % 10 == 0:
            print(f"  Scraped {i}/{len(paper_ids)} papers...")

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with aiohttp.ClientSession() as session:
        print("Discovering paper IDs...")
        paper_ids = await discover_paper_ids(session, max_pages=2)
        print(f"\nTotal papers discovered: {len(paper_ids)}\n")

        # Adjust this slice to scrape more once you're ready to scale up.
        sample_ids = paper_ids[:3]
        print(f"Scraping {len(sample_ids)} sample papers...\n")

        results = await scrape_papers_bulk(session, sample_ids, concurrency=3)

        with open("data/papers_sample.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        print(f"\nSaved {len(results)} papers to data/papers_sample.json")
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())