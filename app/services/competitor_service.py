"""Competitor service: CRUD, SERP overlap detection, position comparison."""
from __future__ import annotations

import uuid
from collections import defaultdict

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor


# ---- CRUD ----


async def create_competitor(
    db: AsyncSession, site_id: uuid.UUID, domain: str, name: str | None = None, notes: str | None = None,
) -> Competitor:
    domain = domain.strip().lower().rstrip("/")
    # Strip protocol if present
    for prefix in ("https://", "http://", "www."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    comp = Competitor(site_id=site_id, domain=domain, name=name, notes=notes)
    db.add(comp)
    await db.flush()
    return comp


async def list_competitors(db: AsyncSession, site_id: uuid.UUID) -> list[Competitor]:
    result = await db.execute(
        select(Competitor).where(Competitor.site_id == site_id).order_by(Competitor.domain)
    )
    return list(result.scalars().all())


async def get_competitor(db: AsyncSession, competitor_id: uuid.UUID) -> Competitor | None:
    result = await db.execute(select(Competitor).where(Competitor.id == competitor_id))
    return result.scalar_one_or_none()


async def delete_competitor(db: AsyncSession, competitor: Competitor) -> None:
    await db.delete(competitor)


# ---- Analysis ----


async def compare_positions(
    db: AsyncSession,
    site_id: uuid.UUID,
    competitor_domain: str,
) -> list[dict]:
    """Compare site positions vs competitor for shared keywords.

    Uses keyword_positions data where competitor URLs contain the competitor domain.
    Returns list of {keyword_id, phrase, our_position, competitor_position, delta}.
    """
    result = await db.execute(text("""
        WITH our_latest AS (
            SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                kp.keyword_id, k.phrase, kp.position AS our_position, kp.engine
            FROM keyword_positions kp
            JOIN keywords k ON k.id = kp.keyword_id
            WHERE kp.site_id = :site_id
              AND kp.position IS NOT NULL
            ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
        ),
        competitor_positions AS (
            SELECT DISTINCT ON (kp.keyword_id, kp.engine)
                kp.keyword_id, kp.position AS comp_position, kp.url AS comp_url
            FROM keyword_positions kp
            WHERE kp.site_id = :site_id
              AND kp.url ILIKE :domain_pattern
              AND kp.position IS NOT NULL
            ORDER BY kp.keyword_id, kp.engine, kp.checked_at DESC
        )
        SELECT
            o.keyword_id, o.phrase, o.engine,
            o.our_position,
            c.comp_position,
            c.comp_url,
            o.our_position - c.comp_position AS delta
        FROM our_latest o
        JOIN competitor_positions c ON o.keyword_id = c.keyword_id
        ORDER BY c.comp_position ASC
    """), {"site_id": site_id, "domain_pattern": f"%{competitor_domain}%"})

    return [dict(r) for r in result.mappings().all()]


async def detect_serp_competitors(
    db: AsyncSession,
    site_id: uuid.UUID,
    min_shared: int = 3,
) -> list[dict]:
    """Auto-detect competitors from SERP data.

    Finds domains that appear in TOP-10 for the same keywords as our site.
    Returns list of {domain, shared_keywords, avg_position} sorted by frequency.
    """
    # Get our site domain for exclusion
    from app.models.site import Site
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one_or_none()
    if not site:
        return []
    our_domain = site.url.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")

    result = await db.execute(text(r"""
        WITH our_keywords AS (
            SELECT DISTINCT keyword_id
            FROM keyword_positions
            WHERE site_id = :site_id AND position IS NOT NULL AND position <= 10
        ),
        all_serp AS (
            SELECT DISTINCT ON (kp.keyword_id, kp.url)
                kp.keyword_id, kp.url, kp.position
            FROM keyword_positions kp
            WHERE kp.site_id = :site_id
              AND kp.position IS NOT NULL
              AND kp.position <= 10
              AND kp.url IS NOT NULL
            ORDER BY kp.keyword_id, kp.url, kp.checked_at DESC
        )
        SELECT
            regexp_replace(
                regexp_replace(url, '^https?://(www\.)?', ''),
                '/.*$', ''
            ) AS domain,
            COUNT(DISTINCT keyword_id) AS shared_keywords,
            ROUND(AVG(position)::numeric, 1) AS avg_position
        FROM all_serp
        WHERE keyword_id IN (SELECT keyword_id FROM our_keywords)
        GROUP BY domain
        HAVING COUNT(DISTINCT keyword_id) >= :min_shared
        ORDER BY shared_keywords DESC
    """), {"site_id": site_id, "min_shared": min_shared})

    rows = [dict(r) for r in result.mappings().all()]
    # Exclude our own domain
    return [r for r in rows if our_domain not in r.get("domain", "")]
