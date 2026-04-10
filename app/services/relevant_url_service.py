"""Relevant URL finder service — filter SERP results by target domain."""
from __future__ import annotations

from urllib.parse import urlparse


def find_relevant_url(phrase: str, serp_results: list[dict], target_domain: str) -> dict:
    """Find a URL from target_domain in SERP results and identify top competitors.

    Args:
        phrase: keyword phrase searched
        serp_results: list of dicts from xmlproxy_service.search_yandex_sync
            Each dict has: url, position, domain, title, snippet
        target_domain: domain to search for (e.g., "example.ru")

    Returns:
        dict with keys: phrase, url, position, top_competitors
    """
    target = _normalize_domain(target_domain)
    found_url = None
    found_position = None
    competitors: list[str] = []

    for result in serp_results:
        result_domain = _normalize_domain(result.get("domain") or "")

        if result_domain == target or result_domain.endswith("." + target):
            # Found target domain in results — take first match (highest position)
            if found_url is None:
                found_url = result.get("url")
                found_position = result.get("position")
        else:
            # Competing domain — collect unique normalized domains
            if result_domain and result_domain not in competitors:
                competitors.append(result_domain)

    return {
        "phrase": phrase,
        "url": found_url,
        "position": found_position,
        "top_competitors": competitors[:3],
    }


def _normalize_domain(domain: str) -> str:
    """Normalize domain: lowercase, strip scheme, strip www. prefix."""
    d = domain.lower().strip()
    if d.startswith("http://") or d.startswith("https://"):
        d = urlparse(d).netloc
    if d.startswith("www."):
        d = d[4:]
    return d
