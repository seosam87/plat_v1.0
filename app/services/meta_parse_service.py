"""Meta tag parsing service — async batch URL fetcher with BeautifulSoup extraction."""
from __future__ import annotations

import asyncio

import httpx
from bs4 import BeautifulSoup


async def _fetch_url(client: httpx.AsyncClient, url: str) -> dict:
    """Fetch a single URL and extract meta tags.

    Args:
        client: shared httpx.AsyncClient with follow_redirects enabled
        url: URL string to fetch

    Returns:
        dict with all meta fields; error field is set on failure
    """
    try:
        resp = await client.get(url, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "lxml")

        # Extract robots meta
        robots_tag = soup.find("meta", attrs={"name": "robots"})
        robots = robots_tag.get("content", "") if robots_tag else None

        return {
            "input_url": url,
            "final_url": str(resp.url),
            "status_code": resp.status_code,
            "title": _safe_text(soup.find("title"), 500),
            "h1": _safe_text(soup.find("h1"), 500),
            "h2_list": [h.get_text(strip=True)[:200] for h in soup.find_all("h2")][:10],
            "meta_description": _safe_attr(soup.find("meta", attrs={"name": "description"}), "content", 1000),
            "canonical": _safe_attr(soup.find("link", attrs={"rel": "canonical"}), "href", 2000),
            "robots": robots,
            "error": None,
        }
    except Exception as e:
        return {
            "input_url": url,
            "final_url": None,
            "status_code": None,
            "title": None,
            "h1": None,
            "h2_list": [],
            "meta_description": None,
            "canonical": None,
            "robots": None,
            "error": str(e)[:200],
        }


def _safe_text(tag, max_len: int) -> str | None:
    """Extract text from a BS4 tag safely."""
    if tag is None:
        return None
    return tag.get_text(strip=True)[:max_len] or None


def _safe_attr(tag, attr: str, max_len: int) -> str | None:
    """Extract an attribute from a BS4 tag safely."""
    if tag is None:
        return None
    val = tag.get(attr, "")
    return val[:max_len] if val else None


async def fetch_and_parse_urls(urls: list[str], concurrency: int = 5) -> list[dict]:
    """Fetch multiple URLs concurrently with a semaphore limit.

    Args:
        urls: list of URL strings to fetch
        concurrency: max concurrent requests (default 5 per ROADMAP META-01)

    Returns:
        list of dicts with meta tag data, one per URL (order preserved)
    """
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        timeout=10,
        follow_redirects=True,
        headers={"User-Agent": "SEOPlatform-MetaParser/1.0"},
    ) as client:
        async def bounded(url: str) -> dict:
            async with sem:
                return await _fetch_url(client, url)

        return list(await asyncio.gather(*[bounded(u) for u in urls]))
