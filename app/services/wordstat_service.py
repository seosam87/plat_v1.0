"""Yandex Wordstat API client for keyword frequency lookup.

Uses api.wordstat.yandex.net REST API with OAuth Bearer token.
Per D-15: frequency is fetched on explicit user action, not automatically.
"""
from __future__ import annotations

import httpx
from loguru import logger

WORDSTAT_API_BASE = "https://api.wordstat.yandex.net"


def fetch_wordstat_frequency_sync(
    phrases: list[str],
    oauth_token: str,
    region_id: int = 0,
    batch_size: int = 10,
    timeout: int = 30,
) -> dict[str, int]:
    """Fetch monthly search frequency for a list of phrases.

    Args:
        phrases: Keywords to look up (max ~100 per session recommended).
        oauth_token: Yandex Direct OAuth bearer token.
        region_id: 0 = all Russia, 213 = Moscow. Default 0.
        batch_size: Process N phrases at a time to respect rate limits.
        timeout: HTTP timeout in seconds.

    Returns:
        Dict mapping phrase -> monthly frequency count.
        Missing phrases (API error or not found) are omitted.
    """
    results: dict[str, int] = {}
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=timeout) as client:
        for i in range(0, len(phrases), batch_size):
            batch = phrases[i:i + batch_size]
            for phrase in batch:
                try:
                    resp = client.post(
                        f"{WORDSTAT_API_BASE}/v1/topRequests",
                        headers=headers,
                        json={
                            "phrase": phrase,
                            "regionIds": [region_id] if region_id else [],
                        },
                    )
                    if resp.status_code == 429:
                        logger.warning("Wordstat API quota exceeded, stopping batch")
                        return results
                    resp.raise_for_status()
                    data = resp.json()
                    count = data.get("count", 0)
                    if not count and "topRequests" in data:
                        top = data["topRequests"]
                        if isinstance(top, list) and top:
                            count = top[0].get("count", 0)
                    results[phrase] = int(count) if count else 0
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "Wordstat HTTP error for '{}': {}",
                        phrase,
                        exc.response.status_code,
                    )
                except Exception as exc:
                    logger.warning("Wordstat fetch failed for '{}': {}", phrase, exc)

    return results
