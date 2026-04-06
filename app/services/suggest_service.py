"""Suggest service — sync HTTP fetch functions for Yandex and Google Suggest.

All functions are synchronous for use inside Celery tasks (D-03).
Uses httpx.Client for blocking HTTP calls with proxy support for Yandex.
"""
from __future__ import annotations

from loguru import logger

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

YANDEX_SUGGEST_URL = "https://suggest.yandex.ru/suggest-ya.cgi"
GOOGLE_SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

# Russian alphabet — 33 characters for alphabetic expansion (D-16)
RU_ALPHABET = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"

# Redis cache TTL: 24 hours (D-11, plan requirement)
SUGGEST_CACHE_TTL = 86400


# ---------------------------------------------------------------------------
# Yandex Suggest
# ---------------------------------------------------------------------------

def fetch_yandex_suggest_sync(
    query: str,
    proxy_url: str | None = None,
    timeout: int = 10,
) -> list[str]:
    """Fetch Yandex Suggest results for a single query.

    Returns list of suggestion strings. Returns empty list on any error.
    Proxy is applied to both HTTP and HTTPS connections when provided.

    Args:
        query: The search query / seed keyword with letter suffix.
        proxy_url: Optional proxy URL (http://user:pass@host:port).
        timeout: Request timeout in seconds.

    Returns:
        List of suggestion strings (may be empty on error or empty response).
    """
    params = {
        "part": query,
        "uil": "ru",
        "lr": "213",
        "highlight": "0",
        "v": "4",
        "sn": "5",
        "srv": "suggest_ya_search",
    }
    try:
        with httpx.Client(timeout=timeout, proxy=proxy_url) as client:
            resp = client.get(YANDEX_SUGGEST_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            # Primary format: ["query", ["suggestion1", "suggestion2", ...]]
            if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                return [str(s) for s in data[1]]
            # Alternative format: {"items": [{"value": "..."}, ...]}
            if isinstance(data, dict) and "items" in data:
                return [item["value"] for item in data["items"]]
            return []
    except Exception as exc:
        logger.warning("Yandex Suggest fetch failed for query={!r}: {}", query, exc)
        return []


# ---------------------------------------------------------------------------
# Google Suggest
# ---------------------------------------------------------------------------

def fetch_google_suggest_sync(
    query: str,
    timeout: int = 10,
) -> list[str]:
    """Fetch Google Suggest results for a single query.

    No proxy needed — Google is accessed directly from server (D-07, D-02).
    Returns empty list on any error.

    Args:
        query: The search query / seed keyword with letter suffix.
        timeout: Request timeout in seconds.

    Returns:
        List of suggestion strings (may be empty on error or empty response).
    """
    params = {
        "client": "chrome",
        "q": query,
        "hl": "ru",
        "gl": "ru",
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(GOOGLE_SUGGEST_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            # Response format: ["query", ["suggestion1", "suggestion2", ...], ...]
            return [str(s) for s in data[1]] if len(data) > 1 else []
    except Exception as exc:
        logger.warning("Google Suggest fetch failed for query={!r}: {}", query, exc)
        return []


# ---------------------------------------------------------------------------
# Cache key
# ---------------------------------------------------------------------------

def suggest_cache_key(seed: str, include_google: bool) -> str:
    """Generate a normalized Redis cache key for the given seed + sources combo.

    Key format: "suggest:{sources}:{normalized_seed}"
    Sources: "yg" (Yandex + Google) or "y" (Yandex only).

    Args:
        seed: The seed keyword (will be stripped and lowercased).
        include_google: Whether Google Suggest is included.

    Returns:
        Normalized Redis cache key string.
    """
    normalized = seed.strip().lower()
    sources = "yg" if include_google else "y"
    return f"suggest:{sources}:{normalized}"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate_suggestions(
    yandex_results: list[str],
    google_results: list[str],
) -> list[dict]:
    """Merge and deduplicate Yandex + Google suggestions.

    Yandex results are added first, then Google — duplicates are dropped
    based on normalized (stripped + lowercased) comparison. Empty/whitespace
    strings are filtered out.

    Args:
        yandex_results: Raw suggestion strings from Yandex Suggest.
        google_results: Raw suggestion strings from Google Suggest.

    Returns:
        List of dicts: [{"keyword": str, "source": "yandex"|"google"}, ...]
    """
    seen: set[str] = set()
    result: list[dict] = []

    for kw in yandex_results:
        norm = kw.strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            result.append({"keyword": kw.strip(), "source": "yandex"})

    for kw in google_results:
        norm = kw.strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            result.append({"keyword": kw.strip(), "source": "google"})

    return result


# ---------------------------------------------------------------------------
# Proxy helpers
# ---------------------------------------------------------------------------

def get_active_proxy_urls_sync() -> list[str]:
    """Return URLs of all active proxies from DB (for Yandex Suggest rotation).

    Uses sync DB session since this is called from Celery tasks.

    Returns:
        List of proxy URL strings (may be empty if no active proxies configured).
    """
    from app.database import get_sync_db
    from app.models.proxy import Proxy, ProxyStatus
    from sqlalchemy import select

    with get_sync_db() as db:
        proxies = db.execute(
            select(Proxy.url).where(
                Proxy.status == ProxyStatus.active,
                Proxy.is_active == True,  # noqa: E712
            )
        ).scalars().all()
    return list(proxies)
