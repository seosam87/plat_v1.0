"""Dead Content detection service.

Identifies pages with zero Metrika traffic in last 30 days, or with significant
position drops (avg delta < -10), and auto-generates recommendations for each.

Decision references:
  D-05: zero-traffic detection via metrika_traffic_pages
  D-06: recommendation engine (merge/redirect/rewrite/delete)
  D-07: recommendation override stored in Redis
  D-08: SEO task creation for dead content pages
  D-09: merge candidate search deferred; label only
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any

import redis.asyncio as aioredis
from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.crawl import CrawlJob, CrawlJobStatus, Page
from app.models.keyword import Keyword
from app.models.keyword_latest_position import KeywordLatestPosition
from app.models.metrika import MetrikaTrafficPage
from app.models.task import SeoTask, TaskPriority, TaskStatus, TaskType
from app.utils.url_normalize import normalize_url

# Redis TTL for recommendation overrides: 30 days
_REC_TTL = 30 * 24 * 3600  # seconds


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _rec_key(site_id: uuid.UUID, normalized_url: str) -> str:
    """Redis key for a recommendation override."""
    return f"dead_content_rec:{site_id}:{normalized_url}"


# ---------------------------------------------------------------------------
# Recommendation engine (pure function — easy to test)
# ---------------------------------------------------------------------------


def compute_recommendation(
    traffic_30d: int,
    keyword_count: int,
    avg_delta: float | None,
    avg_position: float | None,
) -> tuple[str, str]:
    """Determine an auto-recommendation label and human-readable reason.

    Rules (applied in priority order):

    1. No traffic + no keywords           → delete
    2. No traffic + keywords + pos > 50   → redirect
    3. No traffic + keywords + pos ≤ 50   → rewrite
    4. Traffic > 0 + avg_delta < -10      → rewrite (position drop)
    5. Default                            → merge

    Args:
        traffic_30d:    Sum of Metrika visits over last 30 days.
        keyword_count:  Number of keywords assigned (target_url matches page).
        avg_delta:      Average position delta across assigned keywords (negative = drop).
        avg_position:   Average current position across assigned keywords.

    Returns:
        (recommendation, reason) tuple. recommendation is one of
        "delete", "redirect", "rewrite", "merge".
    """
    if traffic_30d == 0 and keyword_count == 0:
        return ("delete", "Нет ключей и нет трафика")

    if traffic_30d == 0 and keyword_count > 0:
        if avg_position is not None and avg_position > 50:
            return (
                "redirect",
                "Есть ключи, но позиции > 50 — перенаправить на релевантную страницу",
            )
        if avg_position is not None and avg_position <= 50:
            return (
                "rewrite",
                "Есть ключи с позициями — переписать контент",
            )
        # Keywords assigned but no position data
        return (
            "rewrite",
            "Есть привязанные ключи, но нет трафика — переписать контент",
        )

    if traffic_30d > 0 and avg_delta is not None and avg_delta < -10:
        return (
            "rewrite",
            "Трафик падает, позиции ухудшились — переписать контент",
        )

    return ("merge", "Рассмотреть объединение с релевантной страницей")


# ---------------------------------------------------------------------------
# Main detection query
# ---------------------------------------------------------------------------


async def get_dead_content(db: AsyncSession, site_id: uuid.UUID) -> dict[str, Any]:
    """Detect dead content pages for a site.

    Returns:
        {
            "pages": [
                {
                    "page_id": str,
                    "url": str,
                    "traffic_30d": int,
                    "keyword_count": int,
                    "avg_position_delta": float | None,
                    "avg_position": float | None,
                    "recommendation": str,
                    "recommendation_reason": str,
                },
                ...
            ],
            "stats": {
                "zero_traffic": int,   # pages with zero traffic
                "position_drop": int,  # pages with avg_delta < -10 (and traffic > 0)
                "total": int,
            },
        }
    """
    cutoff: date = date.today() - timedelta(days=30)

    # --- Step 1: Find latest crawl job for this site ---
    latest_job_result = await db.execute(
        select(CrawlJob.id)
        .where(CrawlJob.site_id == site_id, CrawlJob.status == CrawlJobStatus.done)
        .order_by(CrawlJob.finished_at.desc())
        .limit(1)
    )
    latest_job_id = latest_job_result.scalar_one_or_none()

    if latest_job_id is None:
        logger.debug(f"dead_content: no completed crawl job for site {site_id}")
        return {"pages": [], "stats": {"zero_traffic": 0, "position_drop": 0, "total": 0}}

    # --- Step 2: Fetch all pages from latest crawl ---
    pages_result = await db.execute(
        select(Page.id, Page.url)
        .where(Page.crawl_job_id == latest_job_id)
    )
    all_pages = pages_result.all()  # list of Row(id, url)

    if not all_pages:
        return {"pages": [], "stats": {"zero_traffic": 0, "position_drop": 0, "total": 0}}

    # --- Step 3: Metrika traffic: SUM(visits) per normalized URL (last 30 days) ---
    traffic_result = await db.execute(
        select(
            MetrikaTrafficPage.page_url,
            func.sum(MetrikaTrafficPage.visits).label("total_visits"),
        )
        .where(
            MetrikaTrafficPage.site_id == site_id,
            MetrikaTrafficPage.period_end >= cutoff,
        )
        .group_by(MetrikaTrafficPage.page_url)
    )
    # Build normalized-URL → visits mapping
    traffic_map: dict[str, int] = {}
    for row in traffic_result.all():
        norm = normalize_url(row.page_url)
        if norm:
            traffic_map[norm] = int(row.total_visits or 0)

    # --- Step 4: Position data from keyword_latest_positions ---
    pos_result = await db.execute(
        select(
            KeywordLatestPosition.url,
            func.count(KeywordLatestPosition.id).label("kw_count"),
            func.avg(KeywordLatestPosition.delta).label("avg_delta"),
            func.avg(KeywordLatestPosition.position).label("avg_position"),
        )
        .where(KeywordLatestPosition.site_id == site_id)
        .group_by(KeywordLatestPosition.url)
    )
    # Build normalized-URL → {kw_count, avg_delta, avg_position}
    position_map: dict[str, dict] = {}
    for row in pos_result.all():
        norm = normalize_url(row.url)
        if norm:
            position_map[norm] = {
                "kw_count": int(row.kw_count or 0),
                "avg_delta": float(row.avg_delta) if row.avg_delta is not None else None,
                "avg_position": float(row.avg_position) if row.avg_position is not None else None,
            }

    # --- Step 5: Keyword counts via target_url (from Keyword table) ---
    kw_count_result = await db.execute(
        select(
            Keyword.target_url,
            func.count(Keyword.id).label("kw_count"),
        )
        .where(
            Keyword.site_id == site_id,
            Keyword.target_url.is_not(None),
        )
        .group_by(Keyword.target_url)
    )
    keyword_count_map: dict[str, int] = {}
    for row in kw_count_result.all():
        norm = normalize_url(row.target_url)
        if norm:
            keyword_count_map[norm] = int(row.kw_count or 0)

    # --- Step 6: Load recommendation overrides from Redis ---
    try:
        r = await _get_redis()
        overrides: dict[str, str] = {}
        for _, page_url in all_pages:
            norm = normalize_url(page_url)
            if norm:
                key = _rec_key(site_id, norm)
                stored = await r.get(key)
                if stored:
                    overrides[norm] = stored
        await r.aclose()
    except Exception as exc:
        logger.warning(f"dead_content: Redis unavailable ({exc}), skipping overrides")
        overrides = {}

    # --- Step 7: Build dead-content candidates ---
    result_pages: list[dict] = []
    zero_traffic_count = 0
    position_drop_count = 0

    for page_row in all_pages:
        page_id = page_row.id
        page_url = page_row.url
        norm = normalize_url(page_url)
        if not norm:
            continue

        traffic_30d = traffic_map.get(norm, 0)
        pos_data = position_map.get(norm, {})
        avg_delta = pos_data.get("avg_delta")
        avg_position = pos_data.get("avg_position")

        # keyword_count: prefer position table count, supplement with Keyword.target_url
        kw_count_from_positions = pos_data.get("kw_count", 0)
        kw_count_from_mapping = keyword_count_map.get(norm, 0)
        keyword_count = max(kw_count_from_positions, kw_count_from_mapping)

        # Is this dead content?
        is_zero_traffic = traffic_30d == 0
        is_position_drop = (
            avg_delta is not None and avg_delta < -10 and traffic_30d > 0
        )

        if not (is_zero_traffic or is_position_drop):
            continue

        # Track stats
        if is_zero_traffic:
            zero_traffic_count += 1
        if is_position_drop:
            position_drop_count += 1

        # Recommendation: use Redis override if present, else compute
        if norm in overrides:
            recommendation = overrides[norm]
            recommendation_reason = "Переопределено пользователем"
        else:
            recommendation, recommendation_reason = compute_recommendation(
                traffic_30d=traffic_30d,
                keyword_count=keyword_count,
                avg_delta=avg_delta,
                avg_position=avg_position,
            )

        result_pages.append(
            {
                "page_id": str(page_id),
                "url": page_url,
                "traffic_30d": traffic_30d,
                "keyword_count": keyword_count,
                "avg_position_delta": avg_delta,
                "avg_position": avg_position,
                "recommendation": recommendation,
                "recommendation_reason": recommendation_reason,
            }
        )

    return {
        "pages": result_pages,
        "stats": {
            "zero_traffic": zero_traffic_count,
            "position_drop": position_drop_count,
            "total": len(result_pages),
        },
    }


# ---------------------------------------------------------------------------
# Recommendation override (Redis-backed)
# ---------------------------------------------------------------------------


async def update_recommendation(
    db: AsyncSession,
    site_id: uuid.UUID,
    page_url: str,
    recommendation: str,
) -> None:
    """Store a user-selected recommendation override in Redis (TTL 30 days).

    Args:
        db:             Async DB session (unused but kept for API consistency).
        site_id:        Site UUID.
        page_url:       Raw page URL (will be normalized).
        recommendation: One of "delete", "redirect", "rewrite", "merge".
    """
    valid = {"delete", "redirect", "rewrite", "merge"}
    if recommendation not in valid:
        logger.warning(f"dead_content.update_recommendation: invalid value '{recommendation}'")
        return

    norm = normalize_url(page_url)
    if not norm:
        return

    try:
        r = await _get_redis()
        key = _rec_key(site_id, norm)
        await r.set(key, recommendation, ex=_REC_TTL)
        await r.aclose()
        logger.info(f"dead_content: override set {key} → {recommendation}")
    except Exception as exc:
        logger.error(f"dead_content.update_recommendation: Redis error: {exc}")


# ---------------------------------------------------------------------------
# SEO task creation for dead content pages
# ---------------------------------------------------------------------------


async def create_dead_content_tasks(
    db: AsyncSession,
    site_id: uuid.UUID,
    page_ids: list[uuid.UUID],
) -> int:
    """Create SeoTask records for the selected dead content pages.

    For each page_id:
      - Looks up the page URL from the DB
      - Loads any Redis recommendation override
      - Creates a SeoTask(type=manual, priority=p3, status=open)

    Returns:
        Number of tasks created.
    """
    if not page_ids:
        return 0

    # Fetch pages by IDs
    pages_result = await db.execute(
        select(Page.id, Page.url).where(
            Page.id.in_(page_ids),
            Page.site_id == site_id,
        )
    )
    pages = pages_result.all()

    if not pages:
        return 0

    # Load Redis overrides for these pages
    try:
        r = await _get_redis()
        overrides: dict[str, str] = {}
        for _, page_url in pages:
            norm = normalize_url(page_url)
            if norm:
                stored = await r.get(_rec_key(site_id, norm))
                if stored:
                    overrides[norm] = stored
        await r.aclose()
    except Exception as exc:
        logger.warning(f"dead_content.create_tasks: Redis unavailable ({exc})")
        overrides = {}

    created_count = 0
    for page_row in pages:
        page_id = page_row.id
        page_url = page_row.url
        norm = normalize_url(page_url) or page_url

        recommendation = overrides.get(norm, "merge")
        reason = "Рассмотреть объединение с релевантной страницей"

        title = f"Мёртвый контент: {recommendation} — {page_url}"
        description = reason

        task = SeoTask(
            site_id=site_id,
            task_type=TaskType.manual,
            url=page_url,
            title=title[:500],
            description=description,
            status=TaskStatus.open,
            priority=TaskPriority.p3,
        )
        db.add(task)
        created_count += 1

    await db.flush()
    logger.info(f"dead_content: created {created_count} tasks for site {site_id}")
    return created_count
