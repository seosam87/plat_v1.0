"""Celery task for batch content audit."""
from __future__ import annotations

import asyncio
import uuid

from loguru import logger

from app.celery_app import celery_app
from app.tasks.wp_tasks import site_active_guard


@celery_app.task(
    name="app.tasks.audit_tasks.run_site_audit",
    bind=True,
    max_retries=2,
    queue="wp",
    soft_time_limit=300,
    time_limit=360,
)
def run_site_audit(self, site_id: str) -> dict:
    """Run content audit for all pages of a site.

    Steps: get pages → classify content_type → fetch HTML → run checks → save results.
    """
    skip = site_active_guard(site_id)
    if skip:
        return skip

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_audit_site(site_id))
    except Exception as exc:
        logger.error("Site audit failed", site_id=site_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        loop.close()


async def _audit_site(site_id: str) -> dict:
    """Async audit implementation."""
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.crawl import Page
    from app.models.site import Site
    from app.services import content_audit_service as cas

    async with async_session_factory() as db:
        # Get site
        result = await db.execute(
            select(Site).where(Site.id == uuid.UUID(site_id))
        )
        site = result.scalar_one_or_none()
        if not site:
            return {"status": "error", "reason": "site not found"}

        # Get latest crawl pages (deduplicated by URL)
        result = await db.execute(
            select(Page)
            .where(Page.site_id == uuid.UUID(site_id), Page.http_status == 200)
            .order_by(Page.crawled_at.desc())
        )
        all_pages = result.scalars().all()
        seen: set[str] = set()
        pages = []
        for p in all_pages:
            if p.url not in seen:
                seen.add(p.url)
                pages.append(p)

        if not pages:
            return {"status": "done", "pages_audited": 0, "issues_found": 0}

        # Classify content_type
        for p in pages:
            pt = p.page_type.value if hasattr(p.page_type, "value") else p.page_type
            ct = cas.classify_content_type(pt, p.url)
            if ct != "unknown":
                p.content_type = ct
        await db.flush()

        # Get check definitions
        checks = await cas.get_check_definitions(db)

        # Run checks per page
        total_issues = 0
        max_pages = 200
        for p in pages[:max_pages]:
            # Try to fetch HTML from WP
            html = ""
            try:
                from app.tasks.wp_content_tasks import _fetch_wp_content

                html = _fetch_wp_content(site_id, p.url) or ""
            except Exception:
                pass

            page_data = {
                "has_toc": p.has_toc,
                "has_schema": p.has_schema,
                "has_noindex": p.has_noindex,
                "internal_link_count": p.internal_link_count,
                "content_type": p.content_type.value
                if hasattr(p.content_type, "value")
                else p.content_type,
                "page_type": p.page_type.value
                if hasattr(p.page_type, "value")
                else p.page_type,
                "url": p.url,
            }

            results = cas.run_checks_for_page(html, page_data, checks)
            issues = [r for r in results if r["status"] in ("fail", "warning")]
            total_issues += len(issues)

            await cas.save_audit_results(
                db, uuid.UUID(site_id), p.url, results
            )

        await db.commit()

        logger.info(
            "Site audit complete",
            site_id=site_id,
            pages=min(len(pages), max_pages),
            issues=total_issues,
        )
        return {
            "status": "done",
            "pages_audited": min(len(pages), max_pages),
            "issues_found": total_issues,
        }
