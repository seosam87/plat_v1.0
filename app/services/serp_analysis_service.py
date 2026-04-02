"""SERP analysis service: site type classification, competitor detection from SERP data."""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import SessionSerpResult


# ---- Known domain lists ----

_AGGREGATORS = {
    "avito.ru", "ozon.ru", "wildberries.ru", "yandex.ru", "2gis.ru",
    "zoon.ru", "yell.ru", "cataloxy.ru", "sravni.ru", "banki.ru",
    "irecommend.ru", "otzovik.com", "market.yandex.ru",
}

_INFO_DOMAINS = {
    "wikipedia.org", "habr.com", "vc.ru", "pikabu.ru", "dzen.ru",
    "zen.yandex.ru",
}

_INFO_URL_PATTERNS = ("/blog/", "/wiki/", "/article/", "/novosti/", "/news/", "/journal/", "/magazine/")


# ---- Pure functions ----


def classify_site_type(domain: str, url: str = "") -> str:
    """Classify a domain/URL as commercial, informational, or aggregator."""
    domain_lower = domain.lower().strip(".")

    # Check aggregators
    for agg in _AGGREGATORS:
        if domain_lower == agg or domain_lower.endswith("." + agg):
            return "aggregator"

    # Check info domains
    for info in _INFO_DOMAINS:
        if domain_lower == info or domain_lower.endswith("." + info):
            return "informational"

    # Check URL patterns
    url_lower = url.lower()
    if any(p in url_lower for p in _INFO_URL_PATTERNS):
        return "informational"

    return "commercial"


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().removeprefix("www.")
    except Exception:
        return url


def analyze_serp_results(serp_data: list[dict], our_domain: str = "") -> dict:
    """Analyze SERP data across multiple keywords.

    serp_data: [{keyword_phrase, results: [{position, url, domain, title}]}]

    Returns {top_competitors, site_type_distribution, total_keywords}.
    """
    domain_counter: Counter = Counter()
    domain_positions: dict[str, list[int]] = {}
    domain_types: dict[str, str] = {}
    type_counter: Counter = Counter()

    our_domain_lower = our_domain.lower().removeprefix("www.")

    for kw_data in serp_data:
        results = kw_data.get("results", [])
        seen_domains: set[str] = set()
        for r in results:
            domain = r.get("domain", extract_domain(r.get("url", "")))
            domain_lower = domain.lower().removeprefix("www.")

            # Skip our own domain
            if our_domain_lower and domain_lower == our_domain_lower:
                continue

            if domain_lower not in seen_domains:
                seen_domains.add(domain_lower)
                domain_counter[domain_lower] += 1
                domain_positions.setdefault(domain_lower, []).append(r.get("position", 0))

                if domain_lower not in domain_types:
                    site_type = classify_site_type(domain_lower, r.get("url", ""))
                    domain_types[domain_lower] = site_type
                    type_counter[site_type] += 1

    # Build top competitors
    top_competitors = []
    for domain, count in domain_counter.most_common(20):
        positions = domain_positions.get(domain, [])
        avg_pos = sum(positions) / len(positions) if positions else 0
        top_competitors.append({
            "domain": domain,
            "appearances": count,
            "avg_position": round(avg_pos, 1),
            "site_type": domain_types.get(domain, "commercial"),
        })

    return {
        "top_competitors": top_competitors,
        "site_type_distribution": dict(type_counter),
        "total_keywords": len(serp_data),
    }


# ---- Async DB functions ----


async def save_serp_results(
    db: AsyncSession,
    session_id: uuid.UUID,
    keyword_id: uuid.UUID,
    keyword_phrase: str,
    results_json: list[dict],
    features: list[str] | None = None,
) -> None:
    """Save/upsert SERP results for a keyword in a session."""
    stmt = insert(SessionSerpResult).values(
        id=uuid.uuid4(),
        session_id=session_id,
        keyword_id=keyword_id,
        keyword_phrase=keyword_phrase,
        results_json=results_json,
        features=features,
        parsed_at=datetime.now(timezone.utc),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_serp_result_session_keyword",
        set_={
            "results_json": stmt.excluded.results_json,
            "features": stmt.excluded.features,
            "parsed_at": datetime.now(timezone.utc),
        },
    )
    await db.execute(stmt)
    await db.flush()


async def get_session_serp_summary(
    db: AsyncSession, session_id: uuid.UUID, our_domain: str = ""
) -> dict:
    """Load SERP results for session and run analysis."""
    result = await db.execute(
        select(SessionSerpResult).where(SessionSerpResult.session_id == session_id)
    )
    serp_rows = result.scalars().all()

    serp_data = [
        {
            "keyword_phrase": r.keyword_phrase,
            "results": r.results_json or [],
        }
        for r in serp_rows
    ]

    return analyze_serp_results(serp_data, our_domain)


async def get_top_competitor(
    db: AsyncSession, session_id: uuid.UUID, our_domain: str = ""
) -> str | None:
    """Get the domain appearing most in TOP-10 across session keywords."""
    summary = await get_session_serp_summary(db, session_id, our_domain)
    competitors = summary.get("top_competitors", [])
    if competitors:
        return competitors[0]["domain"]
    return None
