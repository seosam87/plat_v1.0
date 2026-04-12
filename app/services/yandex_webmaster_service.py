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


async def resolve_host_id(user_id: str, domain: str) -> str | None:
    """Find host_id for a domain from user's verified hosts."""
    hosts = await list_hosts(user_id)
    domain_lower = domain.lower().rstrip("/")
    for host in hosts:
        ascii_url = host.get("ascii_host_url", "").lower().rstrip("/")
        # Strip protocol to compare plain domain
        clean = ascii_url.replace("https://", "").replace("http://", "").rstrip("/")
        if clean == domain_lower or ascii_url.endswith(domain_lower):
            return host.get("host_id")
    return None


async def fetch_indexing_errors(user_id: str, host_id: str) -> list[dict]:
    """Fetch indexing error samples (HTTP_4XX, HTTP_5XX, OTHER) from Yandex Webmaster API."""
    url = f"{API_BASE}/user/{user_id}/hosts/{host_id}/indexing/samples"
    params = {"status": ["HTTP_4XX", "HTTP_5XX", "OTHER"], "limit": 100, "offset": 0}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
    return data.get("samples", [])


async def fetch_crawl_errors(user_id: str, host_id: str) -> list[dict]:
    """Fetch broken internal link samples from Yandex Webmaster API."""
    url = f"{API_BASE}/user/{user_id}/hosts/{host_id}/links/internal/broken/samples"
    params = {"indicator": ["SITE_ERROR", "DISALLOWED_BY_USER", "UNSUPPORTED_BY_ROBOT"], "limit": 100, "offset": 0}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
    return data.get("links", [])


async def fetch_sanctions(user_id: str, host_id: str) -> list[dict]:
    """Fetch site problems (FATAL/CRITICAL) from Yandex Webmaster summary as sanction proxy.

    No dedicated sanctions endpoint exists — uses site_problems from /summary.
    """
    url = f"{API_BASE}/user/{user_id}/hosts/{host_id}/summary"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
    problems = data.get("site_problems", {})
    result = []
    for severity in ("FATAL", "CRITICAL"):
        count = problems.get(severity, 0)
        if count > 0:
            result.append({"severity": severity, "count": count})
    return result


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
