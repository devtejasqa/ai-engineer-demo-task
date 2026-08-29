import aiohttp
import asyncio
import json
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup

PWC_BASE = "https://paperswithcode.co"
GITHUB_API_BASE = "https://api.github.com/repos"


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

    # Fetch star counts for each linked GitHub repo concurrently.
    star_tasks = [fetch_github_stars(session, repo) for repo in code_repos]
    star_counts = await asyncio.gather(*star_tasks) if code_repos else []

    repos_with_stars = [
        {"github_url": repo, "github_stars": stars}
        for repo, stars in zip(code_repos, star_counts)
    ]

    # Use the first repo (if any) as the "primary" one for the flat schema field.
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


async def main():
    # paper_id is the numeric slug from the paperswithcode.co URL,
    # e.g. paperswithcode.co/paper/98456 -> "98456"
    test_ids = ["98456"]

    async with aiohttp.ClientSession() as session:
        results = []
        for pid in test_ids:
            result = await scrape_paper(session, pid)
            if result:
                results.append(result)

        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())