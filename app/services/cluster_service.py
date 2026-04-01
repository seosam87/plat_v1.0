"""Keyword cluster service: CRUD + auto-clustering + cannibalization detection."""
from __future__ import annotations

import uuid
from collections import defaultdict

from loguru import logger
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import KeywordCluster
from app.models.keyword import Keyword


# ---- CRUD ----

async def create_cluster(
    db: AsyncSession, site_id: uuid.UUID, name: str, target_url: str | None = None
) -> KeywordCluster:
    cluster = KeywordCluster(site_id=site_id, name=name, target_url=target_url)
    db.add(cluster)
    await db.flush()
    return cluster


async def list_clusters(db: AsyncSession, site_id: uuid.UUID) -> list[KeywordCluster]:
    result = await db.execute(
        select(KeywordCluster)
        .where(KeywordCluster.site_id == site_id)
        .order_by(KeywordCluster.name)
    )
    return list(result.scalars().all())


async def get_cluster(db: AsyncSession, cluster_id: uuid.UUID) -> KeywordCluster | None:
    result = await db.execute(select(KeywordCluster).where(KeywordCluster.id == cluster_id))
    return result.scalar_one_or_none()


async def update_cluster(
    db: AsyncSession, cluster: KeywordCluster, name: str | None = None, target_url: str | None = None
) -> KeywordCluster:
    if name is not None:
        cluster.name = name
    if target_url is not None:
        cluster.target_url = target_url
    await db.flush()
    return cluster


async def delete_cluster(db: AsyncSession, cluster: KeywordCluster) -> None:
    await db.delete(cluster)


async def assign_keywords_to_cluster(
    db: AsyncSession, keyword_ids: list[uuid.UUID], cluster_id: uuid.UUID | None
) -> int:
    """Assign (or unassign if cluster_id=None) keywords to a cluster."""
    count = 0
    for kid in keyword_ids:
        result = await db.execute(select(Keyword).where(Keyword.id == kid))
        kw = result.scalar_one_or_none()
        if kw:
            kw.cluster_id = cluster_id
            count += 1
    await db.flush()
    return count


# ---- Auto-clustering via SERP intersection ----

async def auto_cluster_serp_intersection(
    db: AsyncSession,
    site_id: uuid.UUID,
    min_shared: int = 3,
) -> list[dict]:
    """Propose clusters based on SERP intersection.

    Keywords sharing ≥ min_shared URLs in their top-10 SERP results
    are grouped together. Returns proposed clusters (not saved yet).

    This reads from keyword_positions where we store the ranking URL.
    For full SERP overlap we'd need stored SERP snapshots — this is
    a simplified version using position URL overlap.
    """
    # Get keywords with their latest ranking URLs
    result = await db.execute(text("""
        SELECT DISTINCT ON (kp.keyword_id)
            kp.keyword_id, k.phrase, kp.url
        FROM keyword_positions kp
        JOIN keywords k ON k.id = kp.keyword_id
        WHERE kp.site_id = :site_id
          AND kp.position IS NOT NULL
          AND kp.position <= 10
          AND kp.url IS NOT NULL
        ORDER BY kp.keyword_id, kp.checked_at DESC
    """), {"site_id": site_id})
    rows = result.all()

    # Group keywords by ranking URL
    url_to_keywords: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        url_to_keywords[row.url].append({
            "keyword_id": row.keyword_id,
            "phrase": row.phrase,
        })

    # Keywords sharing the same URL form a natural cluster
    proposals = []
    seen_keywords: set = set()
    for url, kws in url_to_keywords.items():
        if len(kws) < 2:
            continue
        # Skip already clustered keywords
        new_kws = [kw for kw in kws if kw["keyword_id"] not in seen_keywords]
        if len(new_kws) < 2:
            continue
        for kw in new_kws:
            seen_keywords.add(kw["keyword_id"])
        proposals.append({
            "target_url": url,
            "keywords": new_kws,
            "suggested_name": new_kws[0]["phrase"][:50],
        })

    return proposals


# ---- Cannibalization detection ----

async def detect_cannibalization(
    db: AsyncSession,
    site_id: uuid.UUID,
) -> list[dict]:
    """Find keywords where 2+ different pages rank in top-100.

    Returns list of {keyword_id, phrase, pages: [{url, position}]}.
    """
    result = await db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (kp.keyword_id, kp.url)
                kp.keyword_id, k.phrase, kp.url, kp.position
            FROM keyword_positions kp
            JOIN keywords k ON k.id = kp.keyword_id
            WHERE kp.site_id = :site_id
              AND kp.position IS NOT NULL
              AND kp.position <= 100
              AND kp.url IS NOT NULL
            ORDER BY kp.keyword_id, kp.url, kp.checked_at DESC
        ),
        multi_page AS (
            SELECT keyword_id, phrase, COUNT(DISTINCT url) as page_count
            FROM latest
            GROUP BY keyword_id, phrase
            HAVING COUNT(DISTINCT url) >= 2
        )
        SELECT l.keyword_id, l.phrase, l.url, l.position
        FROM latest l
        JOIN multi_page mp ON mp.keyword_id = l.keyword_id
        ORDER BY l.keyword_id, l.position
    """), {"site_id": site_id})
    rows = result.all()

    # Group by keyword
    groups: dict[str, dict] = {}
    for row in rows:
        kid = str(row.keyword_id)
        if kid not in groups:
            groups[kid] = {
                "keyword_id": kid,
                "phrase": row.phrase,
                "pages": [],
            }
        groups[kid]["pages"].append({"url": row.url, "position": row.position})

    return list(groups.values())
