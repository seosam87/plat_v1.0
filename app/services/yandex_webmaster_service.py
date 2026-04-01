"""Yandex Webmaster API client.

Token-based (OAuth token from Yandex OAuth). Fetches search query
statistics (positions, clicks, impressions) for a verified host.
"""
from __future__ import annotations

import httpx
from loguru import logger

from app.config import settings

API_BASE = "https://api.webmaster.yandex.net/v4"
TIMEOUT = 20.0


def is_configured() -> bool:
    return bool(settings.YANDEX_WEBMASTER_TOKEN)


def _headers() -> dict:
    return {"Authorization": f"OAuth {settings.YANDEX_WEBMASTER_TOKEN}"}


async def get_user_id() -> str | None:
    """Get the Yandex user_id for the configured token."""
    if not is_configured():
        return None
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{API_BASE}/user/", headers=_headers())
        resp.raise_for_status()
        return str(resp.json().get("user_id", ""))


async def list_hosts(user_id: str) -> list[dict]:
    """List verified hosts for the user."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{API_BASE}/user/{user_id}/hosts/",
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
    return [
        {
            "host_id": h.get("host_id", ""),
            "ascii_host_url": h.get("ascii_host_url", ""),
            "verified": h.get("verified", False),
        }
        for h in data.get("hosts", [])
    ]


async def fetch_search_queries(
    user_id: str,
    host_id: str,
    date_from: str,
    date_to: str,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    """Fetch search query statistics for a host.

    Returns list of {query, clicks, impressions, ctr, position}.
    """
    url = f"{API_BASE}/user/{user_id}/hosts/{host_id}/search-queries/popular"
    params = {
        "date_from": date_from,
        "date_to": date_to,
        "query_indicator": "TOTAL_SHOWS,TOTAL_CLICKS,AVG_SHOW_POSITION,AVG_CLICK_POSITION",
        "limit": limit,
        "offset": offset,
    }

    all_queries: list[dict] = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        while True:
            resp = await client.get(url, params=params, headers=_headers())
            resp.raise_for_status()
            data = resp.json()
            queries = data.get("queries", [])
            if not queries:
                break

            for q in queries:
                indicators = q.get("indicators", {})
                all_queries.append({
                    "query": q.get("query_text", ""),
                    "clicks": indicators.get("TOTAL_CLICKS", 0),
                    "impressions": indicators.get("TOTAL_SHOWS", 0),
                    "position": indicators.get("AVG_SHOW_POSITION"),
                })

            if len(queries) < limit:
                break
            params["offset"] = params.get("offset", 0) + limit

    logger.info(
        "Yandex Webmaster queries fetched",
        host_id=host_id,
        rows=len(all_queries),
    )
    return all_queries
