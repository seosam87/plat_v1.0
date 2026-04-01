"""Auto-task creation from crawl results — 404 and lost-indexation detection."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crawl import CrawlJob, Page, PageSnapshot
from app.models.task import SeoTask, TaskStatus, TaskType


def create_auto_tasks(
    db: Session,
    site_id: uuid.UUID,
    crawl_job_id: uuid.UUID,
) -> list[SeoTask]:
    """Scan crawl results and create tasks for 404s and lost-indexation pages.

    Called synchronously inside the Celery crawl task after crawl completes.
    """
    created: list[SeoTask] = []

    # --- 404 pages ---
    pages_404 = db.execute(
        select(Page).where(
            Page.crawl_job_id == crawl_job_id,
            Page.http_status == 404,
        )
    ).scalars().all()

    for page in pages_404:
        # Skip if an open task already exists for this URL on this site
        existing = db.execute(
            select(SeoTask).where(
                SeoTask.site_id == site_id,
                SeoTask.url == page.url,
                SeoTask.task_type == TaskType.page_404,
                SeoTask.status != TaskStatus.resolved,
            )
        ).scalar_one_or_none()

        if existing:
            continue

        task = SeoTask(
            site_id=site_id,
            crawl_job_id=crawl_job_id,
            task_type=TaskType.page_404,
            url=page.url,
            title=f"404 Not Found: {page.url}",
            description=f"Page returned HTTP 404 during crawl. Previous title: {page.title or 'unknown'}.",
        )
        db.add(task)
        created.append(task)

    # --- Lost indexation (noindex flip) ---
    # Find pages that have has_noindex=True in current crawl
    noindex_pages = db.execute(
        select(Page).where(
            Page.crawl_job_id == crawl_job_id,
            Page.has_noindex.is_(True),
        )
    ).scalars().all()

    for page in noindex_pages:
        # Check if the previous crawl's version of this page was NOT noindex
        prev_page = db.execute(
            select(Page).where(
                Page.site_id == site_id,
                Page.url == page.url,
                Page.id != page.id,
                Page.has_noindex.is_(False),
            ).order_by(Page.crawled_at.desc()).limit(1)
        ).scalar_one_or_none()

        if prev_page is None:
            # No previous indexed version — not a "lost" indexation
            continue

        # Skip if an open task already exists
        existing = db.execute(
            select(SeoTask).where(
                SeoTask.site_id == site_id,
                SeoTask.url == page.url,
                SeoTask.task_type == TaskType.lost_indexation,
                SeoTask.status != TaskStatus.resolved,
            )
        ).scalar_one_or_none()

        if existing:
            continue

        task = SeoTask(
            site_id=site_id,
            crawl_job_id=crawl_job_id,
            task_type=TaskType.lost_indexation,
            url=page.url,
            title=f"Lost indexation: {page.url}",
            description=(
                f"Page was indexed in previous crawl but now has noindex. "
                f"Title: {page.title or 'unknown'}."
            ),
        )
        db.add(task)
        created.append(task)

    if created:
        logger.info(
            "Auto-created SEO tasks",
            site_id=str(site_id),
            crawl_job_id=str(crawl_job_id),
            count=len(created),
            types=[t.task_type.value for t in created],
        )

    return created
