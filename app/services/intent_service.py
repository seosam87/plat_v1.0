"""Intent auto-detect service: analyze SERP for commercial vs informational intent."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.serp_analysis_service import classify_site_type


# ---- Pure functions ----


def detect_intent_from_serp(results: list[dict]) -> dict:
    """Analyze SERP TOP-10 to determine intent.

    Returns {intent, commercial_count, informational_count, confidence}.
    """
    if not results:
        return {"intent": "unknown", "commercial_count": 0, "informational_count": 0, "confidence": 0.0}

    commercial = 0
    informational = 0
    for r in results[:10]:
        domain = r.get("domain", "")
        url = r.get("url", "")
        site_type = classify_site_type(domain, url)
        if site_type == "commercial":
            commercial += 1
        elif site_type == "informational":
            informational += 1
        # aggregator doesn't count toward either

    total = commercial + informational
    if total == 0:
        return {"intent": "unknown", "commercial_count": 0, "informational_count": 0, "confidence": 0.0}

    confidence = round(max(commercial, informational) / max(total, 1), 2)

    if commercial >= 7:
        intent = "commercial"
    elif informational >= 7:
        intent = "informational"
    else:
        intent = "mixed"

    return {
        "intent": intent,
        "commercial_count": commercial,
        "informational_count": informational,
        "confidence": confidence,
    }


# ---- Async functions ----


async def batch_detect_intent(
    db: AsyncSession,
    site_id: uuid.UUID,
    keyword_ids: list[uuid.UUID],
    use_cache: bool = True,
) -> list[dict]:
    """Detect intent for a batch of keywords. Uses SERP cache where available."""
    from app.models.analytics import SessionSerpResult
    from app.models.keyword import Keyword

    proposals = []

    for kid in keyword_ids:
        kw_result = await db.execute(select(Keyword).where(Keyword.id == kid))
        kw = kw_result.scalar_one_or_none()
        if not kw:
            continue

        serp_results = None

        # Check cache
        if use_cache:
            cached = await db.execute(
                select(SessionSerpResult)
                .where(SessionSerpResult.keyword_id == kid)
                .order_by(SessionSerpResult.parsed_at.desc())
                .limit(1)
            )
            cached_row = cached.scalar_one_or_none()
            if cached_row:
                serp_results = cached_row.results_json

        # Parse if not cached
        if serp_results is None:
            try:
                from app.services.proxy_serp_service import parse_serp_with_proxy
                serp = await parse_serp_with_proxy(kw.phrase, engine=kw.engine or "yandex")
                serp_results = serp.get("results", [])
            except Exception:
                serp_results = []

        detection = detect_intent_from_serp(serp_results or [])
        proposals.append({
            "keyword_id": str(kw.id),
            "phrase": kw.phrase,
            "proposed_intent": detection["intent"],
            "confidence": detection["confidence"],
            "commercial_count": detection["commercial_count"],
            "informational_count": detection["informational_count"],
        })

    return proposals


async def confirm_intent(
    db: AsyncSession, keyword_id: uuid.UUID, intent: str
) -> None:
    """Update keyword's cluster intent."""
    from app.models.keyword import Keyword
    from app.models.cluster import KeywordCluster

    kw = (await db.execute(select(Keyword).where(Keyword.id == keyword_id))).scalar_one_or_none()
    if kw and kw.cluster_id:
        cluster = (await db.execute(
            select(KeywordCluster).where(KeywordCluster.id == kw.cluster_id)
        )).scalar_one_or_none()
        if cluster:
            cluster.intent = intent
            await db.flush()


async def bulk_confirm_intents(
    db: AsyncSession, proposals: list[dict]
) -> int:
    """Apply all proposed intents. Returns count confirmed."""
    count = 0
    for p in proposals:
        if p.get("proposed_intent") and p["proposed_intent"] != "mixed":
            await confirm_intent(db, uuid.UUID(p["keyword_id"]), p["proposed_intent"])
            count += 1
    await db.flush()
    return count


async def get_unclustered_keywords(
    db: AsyncSession, site_id: uuid.UUID, limit: int = 100
) -> list[dict]:
    """Keywords where cluster intent is unknown or no cluster."""
    from app.models.keyword import Keyword
    from app.models.cluster import KeywordCluster

    result = await db.execute(
        select(Keyword)
        .outerjoin(KeywordCluster, Keyword.cluster_id == KeywordCluster.id)
        .where(
            Keyword.site_id == site_id,
            (KeywordCluster.intent == "unknown") | (Keyword.cluster_id == None),  # noqa: E711
        )
        .limit(limit)
    )
    keywords = result.scalars().all()
    return [{"id": str(k.id), "phrase": k.phrase, "frequency": k.frequency} for k in keywords]
