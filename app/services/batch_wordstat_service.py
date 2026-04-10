"""Batch Wordstat service — separate from wordstat_service.py (per D-11).

Handles up to 1000 phrases: exact + broad frequency + monthly dynamics.
Each phrase requires two API calls (exact match + broad match).
Monthly dynamics are fetched via a separate API endpoint.
"""
from __future__ import annotations

import time

import httpx
from loguru import logger
from sqlalchemy.orm import Session

WORDSTAT_API_BASE = "https://api.wordstat.yandex.net"

# Delay between API calls to respect rate limits (seconds)
_RATE_LIMIT_DELAY = 0.3


def fetch_wordstat_batch_sync(
    phrases: list[str],
    oauth_token: str,
    region_id: int = 0,
    timeout: int = 30,
) -> list[dict]:
    """Fetch exact, broad frequency and monthly dynamics for a list of phrases.

    Per Pitfall 4: exact match requires quoted phrase `'"phrase"'`; broad match
    sends unquoted `'phrase'`.

    Args:
        phrases: List of keywords to look up (up to 1000).
        oauth_token: Yandex Direct OAuth bearer token.
        region_id: 0 = all Russia, 213 = Moscow. Default 0.
        timeout: HTTP timeout per request in seconds.

    Returns:
        List of dicts:
            {
                "phrase": str,
                "freq_exact": int | None,
                "freq_broad": int | None,
                "monthly": [{"year_month": str, "frequency": int}, ...]
            }
        Phrases with API errors return None values; processing continues.
    """
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Content-Type": "application/json",
    }
    region_payload = [region_id] if region_id else []
    results: list[dict] = []

    with httpx.Client(timeout=timeout) as client:
        for phrase in phrases:
            freq_exact: int | None = None
            freq_broad: int | None = None
            monthly: list[dict] = []

            # --- Call 1: exact match (quoted phrase) ---
            try:
                resp = client.post(
                    f"{WORDSTAT_API_BASE}/v1/topRequests",
                    headers=headers,
                    json={
                        "phrase": f'"{phrase}"',
                        "regionIds": region_payload,
                    },
                )
                if resp.status_code == 429:
                    logger.warning("Wordstat API quota exceeded on exact match for '{}'", phrase)
                else:
                    resp.raise_for_status()
                    data = resp.json()
                    freq_exact = _extract_count(data)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Wordstat HTTP error (exact) for '{}': {}", phrase, exc.response.status_code
                )
            except Exception as exc:
                logger.warning("Wordstat exact fetch failed for '{}': {}", phrase, exc)

            time.sleep(_RATE_LIMIT_DELAY)

            # --- Call 2: broad match (unquoted phrase) ---
            try:
                resp = client.post(
                    f"{WORDSTAT_API_BASE}/v1/topRequests",
                    headers=headers,
                    json={
                        "phrase": phrase,
                        "regionIds": region_payload,
                    },
                )
                if resp.status_code == 429:
                    logger.warning("Wordstat API quota exceeded on broad match for '{}'", phrase)
                else:
                    resp.raise_for_status()
                    data = resp.json()
                    freq_broad = _extract_count(data)
                    monthly = _extract_monthly(data)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Wordstat HTTP error (broad) for '{}': {}", phrase, exc.response.status_code
                )
            except Exception as exc:
                logger.warning("Wordstat broad fetch failed for '{}': {}", phrase, exc)

            time.sleep(_RATE_LIMIT_DELAY)

            results.append(
                {
                    "phrase": phrase,
                    "freq_exact": freq_exact,
                    "freq_broad": freq_broad,
                    "monthly": monthly,
                }
            )

    return results


def check_wordstat_oauth_token(db_session: Session) -> str | None:
    """Load Yandex Direct OAuth token from service_credentials table.

    Args:
        db_session: Synchronous SQLAlchemy session.

    Returns:
        Token string if configured, None otherwise.
    """
    from app.services.service_credential_service import get_credential_sync

    creds = get_credential_sync(db_session, "yandex_direct")
    if not creds:
        return None
    return creds.get("token") or None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_count(data: dict) -> int | None:
    """Extract frequency count from Wordstat API response."""
    count = data.get("count")
    if count is not None:
        try:
            return int(count)
        except (ValueError, TypeError):
            pass
    # Fallback: first entry in topRequests list
    top = data.get("topRequests")
    if isinstance(top, list) and top:
        count = top[0].get("count", 0)
        try:
            return int(count)
        except (ValueError, TypeError):
            pass
    return 0


def _extract_monthly(data: dict) -> list[dict]:
    """Extract monthly dynamics from Wordstat broad response.

    Expected format in 'statByRegions' or 'dynamics' or embedded list.
    Returns list of {"year_month": "YYYY-MM", "frequency": int}.
    """
    monthly: list[dict] = []

    # Try common response shapes: "searchedWith" with period data,
    # or direct "monthlyData" / "dynamics" key
    for key in ("monthlyData", "dynamics", "searchedWith"):
        items = data.get(key)
        if isinstance(items, list):
            for item in items:
                ym = item.get("year_month") or item.get("yearMonth") or item.get("period")
                freq = item.get("frequency") or item.get("count") or item.get("value", 0)
                if ym:
                    # Normalize to "YYYY-MM" format
                    ym_str = str(ym)[:7]
                    try:
                        monthly.append({"year_month": ym_str, "frequency": int(freq or 0)})
                    except (ValueError, TypeError):
                        pass
            if monthly:
                break

    return monthly
