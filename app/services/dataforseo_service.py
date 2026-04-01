"""DataForSEO API client.

Primary SERP source. Uses httpx with Basic Auth (login:password from .env).
Endpoints: SERP API (live positions), Keywords Data API (volume/difficulty).
"""
from __future__ import annotations

import base64

import httpx
from loguru import logger

from app.config import settings

API_BASE = "https://api.dataforseo.com/v3"
SERP_ENDPOINT = f"{API_BASE}/serp/google/organic/live/advanced"
KEYWORDS_DATA_ENDPOINT = f"{API_BASE}/keywords_data/google_ads/search_volume/live"
TIMEOUT = 30.0


def _auth_header() -> str:
    creds = f"{settings.DATAFORSEO_LOGIN}:{settings.DATAFORSEO_PASSWORD}"
    token = base64.b64encode(creds.encode()).decode()
    return f"Basic {token}"


def is_configured() -> bool:
    return bool(settings.DATAFORSEO_LOGIN and settings.DATAFORSEO_PASSWORD)


async def fetch_serp(
    keyword: str,
    location_code: int = 2840,  # USA by default
    language_code: str = "en",
    depth: int = 100,
) -> list[dict]:
    """Fetch SERP results for a keyword.

    Returns list of {position, url, title, description, type}.
    """
    if not is_configured():
        logger.warning("DataForSEO not configured")
        return []

    payload = [
        {
            "keyword": keyword,
            "location_code": location_code,
            "language_code": language_code,
            "depth": depth,
        }
    ]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            SERP_ENDPOINT,
            json=payload,
            headers={"Authorization": _auth_header(), "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    tasks = data.get("tasks", [])
    if not tasks:
        return results

    for task in tasks:
        task_result = task.get("result", [])
        for result_item in task_result:
            items = result_item.get("items", [])
            for item in items:
                if item.get("type") != "organic":
                    continue
                results.append({
                    "position": item.get("rank_group"),
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                })

    logger.info("DataForSEO SERP fetched", keyword=keyword, results=len(results))
    return results


async def fetch_serp_batch(
    keywords: list[dict],
) -> list[dict]:
    """Fetch SERP for multiple keywords in one API call.

    Each item in keywords: {"keyword": str, "location_code": int, "language_code": str}.
    Returns list of {keyword, results: [...]}.
    """
    if not is_configured() or not keywords:
        return []

    payload = [
        {
            "keyword": kw["keyword"],
            "location_code": kw.get("location_code", 2840),
            "language_code": kw.get("language_code", "en"),
            "depth": 100,
        }
        for kw in keywords
    ]

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            SERP_ENDPOINT,
            json=payload,
            headers={"Authorization": _auth_header(), "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    output = []
    for task in data.get("tasks", []):
        task_keyword = task.get("data", {}).get("keyword", "")
        items = []
        for result_item in task.get("result", []):
            for item in result_item.get("items", []):
                if item.get("type") != "organic":
                    continue
                items.append({
                    "position": item.get("rank_group"),
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                })
        output.append({"keyword": task_keyword, "results": items})

    return output


async def fetch_search_volume(
    keywords: list[str],
    location_code: int = 2840,
    language_code: str = "en",
) -> list[dict]:
    """Fetch search volume and keyword difficulty from Google Ads data.

    Returns list of {keyword, search_volume, competition, cpc}.
    """
    if not is_configured() or not keywords:
        return []

    payload = [
        {
            "keywords": keywords,
            "location_code": location_code,
            "language_code": language_code,
        }
    ]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            KEYWORDS_DATA_ENDPOINT,
            json=payload,
            headers={"Authorization": _auth_header(), "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for task in data.get("tasks", []):
        for result_item in task.get("result", []):
            results.append({
                "keyword": result_item.get("keyword", ""),
                "search_volume": result_item.get("search_volume"),
                "competition": result_item.get("competition"),
                "cpc": result_item.get("cpc"),
            })

    logger.info("DataForSEO search volume fetched", keywords=len(keywords), results=len(results))
    return results
