"""Mobile digest service: async queries for /m/digest and /m/health pages.

Standalone async service — does NOT import from morning_digest_service.py
(which uses sync Session and would block the event loop).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from loguru import logger
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.change_monitoring import ChangeAlert
from app.models.crawl import CrawlJob, CrawlJobStatus, Page
from app.models.keyword import Keyword
from app.models.position import KeywordPosition
from app.models.site import Site
from app.models.task import SeoTask, TaskStatus

# Russian short month names (locale-independent)
_RU_MONTHS = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "май", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}


def _ru_short_date(d: date) -> str:
    """Format date as Russian short: '10 апр'."""
    return f"{d.day} {_RU_MONTHS[d.month]}"


async def get_top_position_changes(
    db: AsyncSession, limit: int = 5
) -> list[dict]:
    """Top position changes across all sites in the last 7 days.

    CRITICAL: Always filters on checked_at >= cutoff for partition safety.
    """
    cutoff = datetime.utcnow() - timedelta(days=7)
    logger.debug("get_top_position_changes: cutoff={}", cutoff)

    stmt = (
        select(
            KeywordPosition.delta,
            KeywordPosition.checked_at,
            Keyword.phrase,
            Site.name.label("site_name"),
            Site.id.label("site_id"),
        )
        .join(Keyword, KeywordPosition.keyword_id == Keyword.id)
        .join(Site, KeywordPosition.site_id == Site.id)
        .where(
            KeywordPosition.checked_at >= cutoff,
            KeywordPosition.delta.isnot(None),
        )
        .order_by(desc(func.abs(KeywordPosition.delta)))
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()
    logger.debug("get_top_position_changes: found {} rows", len(rows))

    return [
        {
            "keyword": row.phrase,
            "site_name": row.site_name,
            "site_id": str(row.site_id),
            "delta": row.delta,
            "checked_at": row.checked_at,
        }
        for row in rows
    ]


async def get_recent_crawl_errors(
    db: AsyncSession, limit: int = 5
) -> list[dict]:
    """Recent crawl errors: pages with HTTP 404 or noindex flag."""
    logger.debug("get_recent_crawl_errors: limit={}", limit)

    stmt = (
        select(
            Page.url,
            Page.http_status,
            Page.has_noindex,
            Page.crawl_job_id,
            Site.name.label("site_name"),
            Site.id.label("site_id"),
        )
        .join(Site, Page.site_id == Site.id)
        .where(
            (Page.http_status == 404) | (Page.has_noindex.is_(True))
        )
        .order_by(desc(Page.crawled_at))
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()
    logger.debug("get_recent_crawl_errors: found {} rows", len(rows))

    return [
        {
            "url": row.url,
            "http_status": row.http_status,
            "has_noindex": row.has_noindex,
            "site_name": row.site_name,
            "site_id": str(row.site_id),
            "crawl_job_id": str(row.crawl_job_id),
        }
        for row in rows
    ]


async def get_recent_alerts(
    db: AsyncSession, limit: int = 5
) -> list[dict]:
    """Recent change alerts (dispatched ones, ordered by sent_at)."""
    logger.debug("get_recent_alerts: limit={}", limit)

    stmt = (
        select(
            ChangeAlert.change_type,
            ChangeAlert.severity,
            ChangeAlert.page_url,
            ChangeAlert.details,
            ChangeAlert.sent_at,
            Site.name.label("site_name"),
            Site.id.label("site_id"),
        )
        .join(Site, ChangeAlert.site_id == Site.id)
        .where(ChangeAlert.sent_at.isnot(None))
        .order_by(desc(ChangeAlert.sent_at))
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()
    logger.debug("get_recent_alerts: found {} rows", len(rows))

    return [
        {
            "change_type": row.change_type.value,
            "severity": row.severity.value,
            "page_url": row.page_url,
            "details": row.details,
            "site_name": row.site_name,
            "site_id": str(row.site_id),
        }
        for row in rows
    ]


async def get_overdue_tasks(
    db: AsyncSession, limit: int = 5
) -> list[dict]:
    """Overdue SEO tasks (due_date < today, not resolved)."""
    today = date.today()
    logger.debug("get_overdue_tasks: today={}", today)

    stmt = (
        select(
            SeoTask.title,
            SeoTask.due_date,
            Site.name.label("site_name"),
            Site.id.label("site_id"),
        )
        .join(Site, SeoTask.site_id == Site.id)
        .where(
            SeoTask.due_date < today,
            SeoTask.status != TaskStatus.resolved,
        )
        .order_by(SeoTask.due_date)
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()
    logger.debug("get_overdue_tasks: found {} rows", len(rows))

    return [
        {
            "title": row.title,
            "due_date": row.due_date,
            "overdue_days": (today - row.due_date).days if row.due_date else 0,
            "site_name": row.site_name,
            "site_id": str(row.site_id),
        }
        for row in rows
    ]


async def build_mobile_digest(db: AsyncSession) -> dict:
    """Build the full mobile digest with all 4 blocks.

    Returns dict with keys: position_changes, crawl_errors, alerts,
    overdue_tasks, today (formatted Russian short date).
    """
    logger.debug("build_mobile_digest: building digest")

    position_changes = await get_top_position_changes(db, limit=5)
    crawl_errors = await get_recent_crawl_errors(db, limit=5)
    alerts = await get_recent_alerts(db, limit=5)
    overdue_tasks = await get_overdue_tasks(db, limit=5)

    return {
        "position_changes": position_changes,
        "crawl_errors": crawl_errors,
        "alerts": alerts,
        "overdue_tasks": overdue_tasks,
        "today": _ru_short_date(date.today()),
    }


async def get_mobile_site_health(
    db: AsyncSession, site_id: uuid.UUID
) -> dict:
    """Build health card data for a single site (6 metrics with status colors).

    Used by Plan 02 (/m/health/{site_id}).
    """
    logger.debug("get_mobile_site_health: site_id={}", site_id)
    today = date.today()
    cutoff = datetime.utcnow() - timedelta(days=7)

    # 1. Site status: latest CrawlJob
    latest_crawl_stmt = (
        select(CrawlJob)
        .where(CrawlJob.site_id == site_id)
        .order_by(desc(CrawlJob.finished_at))
        .limit(1)
    )
    latest_crawl_result = await db.execute(latest_crawl_stmt)
    latest_crawl = latest_crawl_result.scalar_one_or_none()

    if latest_crawl:
        site_reachable = latest_crawl.status == CrawlJobStatus.done
        site_status_color = "green" if site_reachable else "red"
        site_status_value = latest_crawl.status.value

        last_crawl_data = {
            "status": latest_crawl.status.value,
            "finished_at": latest_crawl.finished_at,
            "pages_crawled": latest_crawl.pages_crawled,
        }

        # Check if crawl is older than 7 days
        crawl_age_days = None
        if latest_crawl.finished_at:
            crawl_age_days = (datetime.utcnow() - latest_crawl.finished_at.replace(tzinfo=None)).days
        last_crawl_color = "green"
        if crawl_age_days is None:
            last_crawl_color = "grey"
        elif crawl_age_days > 7:
            last_crawl_color = "yellow"
    else:
        site_status_color = "grey"
        site_status_value = "no_data"
        last_crawl_data = None
        last_crawl_color = "grey"

    # 2. Crawl error count from latest CrawlJob
    crawl_error_count = 0
    crawl_error_color = "green"
    if latest_crawl:
        error_count_stmt = (
            select(func.count())
            .select_from(Page)
            .where(
                Page.crawl_job_id == latest_crawl.id,
                (Page.http_status == 404) | (Page.has_noindex.is_(True)),
            )
        )
        error_result = await db.execute(error_count_stmt)
        crawl_error_count = error_result.scalar() or 0

        if crawl_error_count == 0:
            crawl_error_color = "green"
        elif crawl_error_count <= 5:
            crawl_error_color = "yellow"
        else:
            crawl_error_color = "red"

    # 4. Position changes count (abs(delta) > 10) in last 7 days
    # CRITICAL: filter checked_at >= cutoff for partition safety
    pos_changes_stmt = (
        select(func.count())
        .select_from(KeywordPosition)
        .where(
            KeywordPosition.site_id == site_id,
            KeywordPosition.checked_at >= cutoff,
            func.abs(KeywordPosition.delta) > 10,
        )
    )
    pos_result = await db.execute(pos_changes_stmt)
    position_changes_count = pos_result.scalar() or 0
    position_changes_color = "red" if position_changes_count > 0 else "green"

    # 5. Overdue task count
    overdue_stmt = (
        select(func.count())
        .select_from(SeoTask)
        .where(
            SeoTask.site_id == site_id,
            SeoTask.due_date < today,
            SeoTask.status != TaskStatus.resolved,
        )
    )
    overdue_result = await db.execute(overdue_stmt)
    overdue_task_count = overdue_result.scalar() or 0

    if overdue_task_count == 0:
        overdue_color = "green"
    elif overdue_task_count <= 3:
        overdue_color = "yellow"
    else:
        overdue_color = "red"

    # 6. Indexation status (check metrika_token)
    site_stmt = select(Site.metrika_token).where(Site.id == site_id)
    site_result = await db.execute(site_stmt)
    metrika_token = site_result.scalar_one_or_none()
    indexation_status = "connected" if metrika_token else "no_data"
    indexation_color = "green" if metrika_token else "grey"

    return {
        "site_status": {
            "value": site_status_value,
            "color": site_status_color,
        },
        "crawl_error_count": {
            "value": crawl_error_count,
            "color": crawl_error_color,
        },
        "last_crawl": {
            "value": last_crawl_data,
            "color": last_crawl_color,
        },
        "position_changes_count": {
            "value": position_changes_count,
            "color": position_changes_color,
        },
        "overdue_task_count": {
            "value": overdue_task_count,
            "color": overdue_color,
        },
        "indexation_status": {
            "value": indexation_status,
            "color": indexation_color,
        },
    }
