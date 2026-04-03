"""Analytics service: advanced keyword filtering, session CRUD, export."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalysisSession, SessionStatus
from app.models.cluster import KeywordCluster
from app.models.keyword import Keyword, KeywordGroup
from app.models.position import KeywordPosition


# ---- Advanced keyword filter ----


async def filter_keywords(
    db: AsyncSession,
    site_id: uuid.UUID,
    *,
    frequency_min: int | None = None,
    frequency_max: int | None = None,
    position_min: int | None = None,
    position_max: int | None = None,
    intent: str | None = None,
    cluster_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    region: str | None = None,
    engine: str | None = None,
    search: str | None = None,
    has_target_url: bool | None = None,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Filter keywords with advanced criteria including position range.

    Returns (keyword_dicts_with_position, total_count).
    """
    # Base query
    q = select(Keyword).where(Keyword.site_id == site_id)

    if search:
        q = q.where(Keyword.phrase.ilike(f"%{search}%"))
    if frequency_min is not None:
        q = q.where(Keyword.frequency >= frequency_min)
    if frequency_max is not None:
        q = q.where(Keyword.frequency <= frequency_max)
    if cluster_id:
        q = q.where(Keyword.cluster_id == cluster_id)
    if group_id:
        q = q.where(Keyword.group_id == group_id)
    if region:
        q = q.where(Keyword.region == region)
    if engine:
        q = q.where(Keyword.engine == engine)
    if has_target_url is True:
        q = q.where(Keyword.target_url != None)  # noqa: E711
    if has_target_url is False:
        q = q.where(Keyword.target_url == None)  # noqa: E711

    # Count total
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Get keywords
    result = await db.execute(q.order_by(Keyword.phrase).offset(offset).limit(limit))
    keywords = result.scalars().all()

    if not keywords:
        return [], total

    # Get latest positions for these keywords
    kw_ids = [k.id for k in keywords]
    # Subquery for latest position per keyword
    latest_pos_sq = (
        select(
            KeywordPosition.keyword_id,
            KeywordPosition.position,
            KeywordPosition.delta,
            KeywordPosition.url.label("ranking_url"),
        )
        .where(KeywordPosition.keyword_id.in_(kw_ids))
        .distinct(KeywordPosition.keyword_id)
        .order_by(KeywordPosition.keyword_id, KeywordPosition.checked_at.desc())
        .subquery()
    )
    pos_result = await db.execute(select(latest_pos_sq))
    pos_map = {
        row.keyword_id: {"position": row.position, "delta": row.delta, "ranking_url": row.ranking_url}
        for row in pos_result.all()
    }

    # Get cluster names
    cluster_ids = {k.cluster_id for k in keywords if k.cluster_id}
    cluster_names = {}
    if cluster_ids:
        cl_result = await db.execute(
            select(KeywordCluster.id, KeywordCluster.name).where(KeywordCluster.id.in_(cluster_ids))
        )
        cluster_names = {row.id: row.name for row in cl_result.all()}

    # Build result dicts
    items = []
    for k in keywords:
        pos_data = pos_map.get(k.id, {})
        pos_val = pos_data.get("position")

        # Apply position filters
        if position_min is not None and (pos_val is None or pos_val < position_min):
            continue
        if position_max is not None and (pos_val is None or pos_val > position_max):
            continue

        # Intent from cluster
        kw_intent = None
        if k.cluster_id:
            cl_result2 = await db.execute(
                select(KeywordCluster.intent).where(KeywordCluster.id == k.cluster_id)
            )
            row = cl_result2.first()
            if row:
                kw_intent = row[0].value if hasattr(row[0], "value") else row[0]

        if intent and kw_intent != intent:
            continue

        items.append({
            "id": str(k.id),
            "phrase": k.phrase,
            "frequency": k.frequency,
            "region": k.region,
            "engine": k.engine.value if hasattr(k.engine, "value") else k.engine,
            "cluster_id": str(k.cluster_id) if k.cluster_id else None,
            "cluster_name": cluster_names.get(k.cluster_id, ""),
            "group_id": str(k.group_id) if k.group_id else None,
            "target_url": k.target_url,
            "intent": kw_intent,
            "latest_position": pos_val,
            "latest_url": pos_data.get("ranking_url"),
            "delta": pos_data.get("delta"),
        })

    return items, total


# ---- Session CRUD ----


async def create_session(
    db: AsyncSession,
    site_id: uuid.UUID,
    name: str,
    keyword_ids: list[str],
    filters_applied: dict | None = None,
) -> AnalysisSession:
    session = AnalysisSession(
        site_id=site_id,
        name=name,
        keyword_ids=keyword_ids,
        keyword_count=len(keyword_ids),
        filters_applied=filters_applied,
    )
    db.add(session)
    await db.flush()
    return session


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> AnalysisSession | None:
    result = await db.execute(
        select(AnalysisSession).where(AnalysisSession.id == session_id)
    )
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession, site_id: uuid.UUID, limit: int = 20
) -> list[AnalysisSession]:
    result = await db.execute(
        select(AnalysisSession)
        .where(AnalysisSession.site_id == site_id)
        .order_by(AnalysisSession.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_session_status(
    db: AsyncSession, session_id: uuid.UUID, status: str
) -> AnalysisSession | None:
    session = await get_session(db, session_id)
    if session:
        session.status = status
        session.updated_at = datetime.now(timezone.utc)
        await db.flush()
    return session


async def delete_session(db: AsyncSession, session_id: uuid.UUID) -> bool:
    session = await get_session(db, session_id)
    if not session:
        return False
    await db.delete(session)
    await db.flush()
    return True


async def get_session_keywords(db: AsyncSession, session_id: uuid.UUID) -> list[dict]:
    """Fetch full keyword data for session's keyword_ids."""
    session = await get_session(db, session_id)
    if not session or not session.keyword_ids:
        return []

    kw_uuids = [uuid.UUID(kid) for kid in session.keyword_ids]
    result = await db.execute(
        select(Keyword).where(Keyword.id.in_(kw_uuids))
    )
    keywords = result.scalars().all()
    return [
        {
            "id": str(k.id),
            "phrase": k.phrase,
            "frequency": k.frequency,
            "region": k.region,
            "target_url": k.target_url,
        }
        for k in keywords
    ]


async def set_session_competitor(
    db: AsyncSession, session_id: uuid.UUID, domain: str
) -> AnalysisSession | None:
    session = await get_session(db, session_id)
    if session:
        session.competitor_domain = domain
        await db.flush()
    return session


async def get_filter_options(db: AsyncSession, site_id: uuid.UUID) -> dict:
    """Available filter values for UI dropdowns."""
    # Clusters
    cl_result = await db.execute(
        select(KeywordCluster.id, KeywordCluster.name, KeywordCluster.intent)
        .where(KeywordCluster.site_id == site_id)
        .order_by(KeywordCluster.name)
    )
    clusters = [
        {"id": str(r.id), "name": r.name, "intent": r.intent.value if hasattr(r.intent, "value") else r.intent}
        for r in cl_result.all()
    ]

    # Groups
    gr_result = await db.execute(
        select(KeywordGroup.id, KeywordGroup.name)
        .where(KeywordGroup.site_id == site_id)
        .order_by(KeywordGroup.name)
    )
    groups = [{"id": str(r.id), "name": r.name} for r in gr_result.all()]

    # Regions
    reg_result = await db.execute(
        select(Keyword.region).where(
            Keyword.site_id == site_id, Keyword.region != None  # noqa: E711
        ).distinct()
    )
    regions = [r[0] for r in reg_result.all() if r[0]]

    # Engines
    eng_result = await db.execute(
        select(Keyword.engine).where(
            Keyword.site_id == site_id, Keyword.engine != None  # noqa: E711
        ).distinct()
    )
    engines = [r[0].value if hasattr(r[0], "value") else r[0] for r in eng_result.all() if r[0]]

    # Frequency range
    freq_result = await db.execute(
        select(func.min(Keyword.frequency), func.max(Keyword.frequency))
        .where(Keyword.site_id == site_id)
    )
    freq_row = freq_result.first()

    return {
        "clusters": clusters,
        "groups": groups,
        "regions": regions,
        "engines": engines,
        "intents": ["unknown", "commercial", "informational", "navigational"],
        "frequency_range": {
            "min": freq_row[0] if freq_row else 0,
            "max": freq_row[1] if freq_row else 0,
        },
    }


def export_session_keywords_csv(keywords: list[dict]) -> str:
    """Generate CSV string from keyword list."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Phrase", "Frequency", "Region", "Target URL", "Position", "Delta"])
    for k in keywords:
        writer.writerow([
            k.get("phrase", ""),
            k.get("frequency", ""),
            k.get("region", ""),
            k.get("target_url", ""),
            k.get("latest_position", ""),
            k.get("delta", ""),
        ])
    return output.getvalue()


async def export_session_csv(db: AsyncSession, session_id: uuid.UUID) -> str:
    """Generate CSV string with keywords + positions for a session.

    Fetches keywords stored in the session and their latest position data,
    returns a CSV string ready for download.
    """
    keywords = await get_session_keywords(db, session_id)
    if not keywords:
        return export_session_keywords_csv([])

    # Attempt to fetch position data for each keyword
    kw_uuids = [uuid.UUID(k["id"]) for k in keywords]

    latest_pos_sq = (
        select(
            KeywordPosition.keyword_id,
            KeywordPosition.position,
            KeywordPosition.delta,
            KeywordPosition.url.label("ranking_url"),
        )
        .where(KeywordPosition.keyword_id.in_(kw_uuids))
        .distinct(KeywordPosition.keyword_id)
        .order_by(KeywordPosition.keyword_id, KeywordPosition.checked_at.desc())
        .subquery()
    )
    pos_result = await db.execute(select(latest_pos_sq))
    pos_map = {
        str(row.keyword_id): {
            "latest_position": row.position,
            "delta": row.delta,
            "latest_url": row.ranking_url,
        }
        for row in pos_result.all()
    }

    enriched = []
    for k in keywords:
        pos_data = pos_map.get(k["id"], {})
        enriched.append({**k, **pos_data})

    return export_session_keywords_csv(enriched)
