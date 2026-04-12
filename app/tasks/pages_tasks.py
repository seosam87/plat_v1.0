"""Celery tasks for Pages App — quick fix TOC/Schema and bulk operations.

Phase 31, Plan 03. Provides:
- quick_fix_toc: push TOC directly to WP for a single page
- quick_fix_schema: push Schema JSON-LD directly to WP for a single page
- bulk_fix_schema: apply schema to all pages without schema in latest crawl
- bulk_fix_toc: apply TOC to all pages without TOC in latest crawl
"""
from __future__ import annotations

import json
import uuid

import httpx
import redis
from loguru import logger
from sqlalchemy import select, desc

from app.celery_app import celery_app
from app.config import settings
from app.database import get_sync_db


def _resolve_wp_post_id(db, page) -> int | None:
    """Resolve WP post ID for a page from WpContentJob history.

    Falls back to WP REST API slug lookup if no job history found.
    """
    from app.models.wp_content_job import WpContentJob

    # Try most recent WpContentJob for this page URL + site
    job = db.execute(
        select(WpContentJob)
        .where(
            WpContentJob.page_url == page.url,
            WpContentJob.site_id == page.site_id,
        )
        .order_by(desc(WpContentJob.created_at))
        .limit(1)
    ).scalar_one_or_none()

    if job and job.wp_post_id:
        return job.wp_post_id

    # Fallback: WP REST API slug lookup
    from app.models.site import Site
    from app.services.wp_service import _sync_auth_headers

    site = db.execute(select(Site).where(Site.id == page.site_id)).scalar_one_or_none()
    if not site:
        return None

    # Extract slug from URL
    slug = page.url.rstrip("/").split("/")[-1]
    if not slug:
        return None

    headers = _sync_auth_headers(site)
    base_url = site.url.rstrip("/")

    # Try posts endpoint first, then pages
    for endpoint in ("posts", "pages"):
        try:
            resp = httpx.get(
                f"{base_url}/wp-json/wp/v2/{endpoint}",
                params={"slug": slug},
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json()
            if results:
                return results[0].get("id")
        except Exception as exc:
            logger.warning(
                "WP slug lookup failed",
                site_id=str(page.site_id),
                slug=slug,
                endpoint=endpoint,
                error=str(exc),
            )

    return None


def _fetch_wp_post_content(site, wp_post_id: int, post_type: str = "posts") -> str | None:
    """Fetch rendered post content from WP REST API."""
    from app.services.wp_service import _sync_auth_headers

    headers = _sync_auth_headers(site)
    base_url = site.url.rstrip("/")

    # Try posts first, then pages
    for endpoint in (post_type, "posts", "pages"):
        try:
            resp = httpx.get(
                f"{base_url}/wp-json/wp/v2/{endpoint}/{wp_post_id}",
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("content", {}).get("rendered", "")
        except Exception as exc:
            logger.warning(
                "WP content fetch failed",
                site_id=str(site.id),
                wp_post_id=wp_post_id,
                endpoint=endpoint,
                error=str(exc),
            )

    return None


def _push_wp_content(site, wp_post_id: int, new_content: str, post_type: str = "posts") -> bool:
    """Push updated content to WP REST API. Returns True on success."""
    from app.services.wp_service import _sync_auth_headers

    headers = _sync_auth_headers(site)
    base_url = site.url.rstrip("/")

    # Try posts then pages
    for endpoint in (post_type, "posts", "pages"):
        try:
            resp = httpx.post(
                f"{base_url}/wp-json/wp/v2/{endpoint}/{wp_post_id}",
                json={"content": new_content},
                headers=headers,
                timeout=15,
            )
            if resp.status_code in (200, 201):
                return True
        except Exception as exc:
            logger.warning(
                "WP content push failed",
                site_id=str(site.id),
                wp_post_id=wp_post_id,
                endpoint=endpoint,
                error=str(exc),
            )

    return False


# ---------------------------------------------------------------------------
# Quick fix tasks
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, max_retries=3, queue="wp")
def quick_fix_toc(self, page_id: str) -> dict:
    """Push TOC directly to WP for a single page."""
    from app.models.crawl import Page
    from app.models.site import Site
    from app.services.content_pipeline import extract_headings, generate_toc_html, inject_toc

    try:
        with get_sync_db() as db:
            page = db.get(Page, uuid.UUID(page_id))
            if not page:
                return {"status": "error", "reason": "page not found"}

            site = db.execute(select(Site).where(Site.id == page.site_id)).scalar_one_or_none()
            if not site:
                return {"status": "error", "reason": "site not found"}

            wp_post_id = _resolve_wp_post_id(db, page)
            if not wp_post_id:
                return {"status": "error", "reason": "cannot resolve wp_post_id"}

        # Fetch current content
        with get_sync_db() as db:
            site = db.execute(select(Site).where(Site.id == uuid.UUID(str(page.site_id)))).scalar_one()

        content = _fetch_wp_post_content(site, wp_post_id)
        if not content:
            return {"status": "error", "reason": "failed to fetch WP content"}

        # Apply TOC
        headings = extract_headings(content)
        if not headings:
            # Update Page flag anyway — no headings means TOC not applicable
            with get_sync_db() as db:
                page = db.get(Page, uuid.UUID(page_id))
                if page:
                    page.has_toc = True
            return {"status": "pushed", "page_id": page_id, "note": "no headings found"}

        toc_html = generate_toc_html(headings)
        new_content = inject_toc(content, toc_html)

        # Push to WP
        pushed = _push_wp_content(site, wp_post_id, new_content)
        if not pushed:
            return {"status": "error", "reason": "WP push failed"}

        # Update Page flag
        with get_sync_db() as db:
            page = db.get(Page, uuid.UUID(page_id))
            if page:
                page.has_toc = True

        logger.info("quick_fix_toc done", page_id=page_id, wp_post_id=wp_post_id)
        return {"status": "pushed", "page_id": page_id}

    except Exception as exc:
        logger.error("quick_fix_toc failed", page_id=page_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3, queue="wp")
def quick_fix_schema(self, page_id: str) -> dict:
    """Push Schema JSON-LD directly to WP for a single page."""
    from app.models.audit import SchemaTemplate
    from app.models.crawl import Page
    from app.models.site import Site
    from app.services.content_pipeline import inject_schema
    from app.services.schema_service import render_schema_template

    try:
        with get_sync_db() as db:
            page = db.get(Page, uuid.UUID(page_id))
            if not page:
                return {"status": "error", "reason": "page not found"}

            site = db.execute(select(Site).where(Site.id == page.site_id)).scalar_one_or_none()
            if not site:
                return {"status": "error", "reason": "site not found"}

            # Load schema template (site-specific or global default)
            template = db.execute(
                select(SchemaTemplate)
                .where(SchemaTemplate.site_id == page.site_id)
                .limit(1)
            ).scalar_one_or_none()
            if not template:
                # Try global template (site_id is None)
                template = db.execute(
                    select(SchemaTemplate)
                    .where(SchemaTemplate.site_id.is_(None))
                    .limit(1)
                ).scalar_one_or_none()
            if not template:
                return {"status": "error", "reason": "no schema template found for site"}

            # Build page_data
            page_data = {
                "title": page.title or "",
                "url": page.url,
                "description": page.meta_description or "",
                "page_type": page.page_type.value,
                "content_type": page.content_type.value,
            }

            # Render schema (SYNC — safe in Celery task)
            schema_json = render_schema_template(template.template_json, page_data)
            schema_tag = f'<script type="application/ld+json">{schema_json}</script>'

            wp_post_id = _resolve_wp_post_id(db, page)
            if not wp_post_id:
                return {"status": "error", "reason": "cannot resolve wp_post_id"}

        # Fetch current content
        with get_sync_db() as db:
            site = db.execute(select(Site).where(Site.id == uuid.UUID(str(page.site_id)))).scalar_one()

        content = _fetch_wp_post_content(site, wp_post_id)
        if not content:
            return {"status": "error", "reason": "failed to fetch WP content"}

        # Inject schema
        new_content = inject_schema(content, schema_tag)

        # Push to WP
        pushed = _push_wp_content(site, wp_post_id, new_content)
        if not pushed:
            return {"status": "error", "reason": "WP push failed"}

        # Update Page flag
        with get_sync_db() as db:
            page = db.get(Page, uuid.UUID(page_id))
            if page:
                page.has_schema = True

        logger.info("quick_fix_schema done", page_id=page_id, wp_post_id=wp_post_id)
        return {"status": "pushed", "page_id": page_id}

    except Exception as exc:
        logger.error("quick_fix_schema failed", page_id=page_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


# ---------------------------------------------------------------------------
# Bulk fix tasks
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, max_retries=0, queue="wp")
def bulk_fix_schema(self, site_id: str) -> dict:
    """Apply Schema JSON-LD to all pages without schema in the latest crawl.

    Uses Redis to track progress; polls via GET /m/pages/bulk/progress/{task_id}.
    One page failure does NOT stop the batch.
    """
    from app.models.audit import SchemaTemplate
    from app.models.crawl import CrawlJob, CrawlJobStatus, Page
    from app.models.site import Site
    from app.services.content_pipeline import inject_schema
    from app.services.schema_service import render_schema_template

    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    task_id = self.request.id

    with get_sync_db() as db:
        site = db.execute(select(Site).where(Site.id == uuid.UUID(site_id))).scalar_one_or_none()
        if not site:
            r.setex(
                f"bulk:{task_id}:progress",
                3600,
                json.dumps({"done": 0, "total": 0, "errors": [], "status": "error"}),
            )
            return {"status": "error", "reason": "site not found"}

        # Latest completed crawl
        latest_crawl = db.execute(
            select(CrawlJob.id)
            .where(
                CrawlJob.site_id == uuid.UUID(site_id),
                CrawlJob.status == CrawlJobStatus.done,
            )
            .order_by(desc(CrawlJob.finished_at))
            .limit(1)
        ).scalar_one_or_none()

        if not latest_crawl:
            r.setex(
                f"bulk:{task_id}:progress",
                3600,
                json.dumps({"done": 0, "total": 0, "errors": [], "status": "error"}),
            )
            return {"status": "error", "reason": "no completed crawl found"}

        # All pages without schema in latest crawl
        pages = db.execute(
            select(Page).where(
                Page.crawl_job_id == latest_crawl,
                Page.has_schema == False,  # noqa: E712
            )
        ).scalars().all()

        total = len(pages)
        page_ids = [str(p.id) for p in pages]

        # Load schema template
        template = db.execute(
            select(SchemaTemplate)
            .where(SchemaTemplate.site_id == uuid.UUID(site_id))
            .limit(1)
        ).scalar_one_or_none()
        if not template:
            template = db.execute(
                select(SchemaTemplate)
                .where(SchemaTemplate.site_id.is_(None))
                .limit(1)
            ).scalar_one_or_none()

    progress = {"done": 0, "total": total, "errors": [], "status": "running"}
    r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))

    if not template:
        progress["status"] = "error"
        r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))
        return {"status": "error", "reason": "no schema template found"}

    for pid in page_ids:
        try:
            with get_sync_db() as db:
                page = db.get(Page, uuid.UUID(pid))
                if not page:
                    continue

                page_data = {
                    "title": page.title or "",
                    "url": page.url,
                    "description": page.meta_description or "",
                    "page_type": page.page_type.value,
                    "content_type": page.content_type.value,
                }

                schema_json = render_schema_template(template.template_json, page_data)
                schema_tag = f'<script type="application/ld+json">{schema_json}</script>'

                wp_post_id = _resolve_wp_post_id(db, page)

            if not wp_post_id:
                progress["errors"].append(f"{pid}: no wp_post_id")
                progress["done"] += 1
                r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))
                continue

            with get_sync_db() as db:
                site_obj = db.execute(select(Site).where(Site.id == uuid.UUID(site_id))).scalar_one()

            content = _fetch_wp_post_content(site_obj, wp_post_id)
            if not content:
                progress["errors"].append(f"{pid}: fetch failed")
                progress["done"] += 1
                r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))
                continue

            new_content = inject_schema(content, schema_tag)
            pushed = _push_wp_content(site_obj, wp_post_id, new_content)

            if pushed:
                with get_sync_db() as db:
                    page = db.get(Page, uuid.UUID(pid))
                    if page:
                        page.has_schema = True
            else:
                progress["errors"].append(f"{pid}: push failed")

        except Exception as exc:
            logger.error("bulk_fix_schema page error", page_id=pid, error=str(exc))
            progress["errors"].append(f"{pid}: {str(exc)[:100]}")

        progress["done"] += 1
        r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))

    progress["status"] = "done" if not progress["errors"] else "error"
    r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))

    logger.info(
        "bulk_fix_schema complete",
        site_id=site_id,
        done=progress["done"],
        errors=len(progress["errors"]),
    )
    return {
        "done": progress["done"],
        "total": total,
        "errors": len(progress["errors"]),
    }


@celery_app.task(bind=True, max_retries=0, queue="wp")
def bulk_fix_toc(self, site_id: str) -> dict:
    """Apply TOC to all pages without TOC in the latest crawl.

    Uses Redis to track progress; polls via GET /m/pages/bulk/progress/{task_id}.
    One page failure does NOT stop the batch.
    """
    from app.models.crawl import CrawlJob, CrawlJobStatus, Page
    from app.models.site import Site
    from app.services.content_pipeline import extract_headings, generate_toc_html, inject_toc

    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    task_id = self.request.id

    with get_sync_db() as db:
        site = db.execute(select(Site).where(Site.id == uuid.UUID(site_id))).scalar_one_or_none()
        if not site:
            r.setex(
                f"bulk:{task_id}:progress",
                3600,
                json.dumps({"done": 0, "total": 0, "errors": [], "status": "error"}),
            )
            return {"status": "error", "reason": "site not found"}

        # Latest completed crawl
        latest_crawl = db.execute(
            select(CrawlJob.id)
            .where(
                CrawlJob.site_id == uuid.UUID(site_id),
                CrawlJob.status == CrawlJobStatus.done,
            )
            .order_by(desc(CrawlJob.finished_at))
            .limit(1)
        ).scalar_one_or_none()

        if not latest_crawl:
            r.setex(
                f"bulk:{task_id}:progress",
                3600,
                json.dumps({"done": 0, "total": 0, "errors": [], "status": "error"}),
            )
            return {"status": "error", "reason": "no completed crawl found"}

        # All pages without TOC in latest crawl
        pages = db.execute(
            select(Page).where(
                Page.crawl_job_id == latest_crawl,
                Page.has_toc == False,  # noqa: E712
            )
        ).scalars().all()

        total = len(pages)
        page_ids = [str(p.id) for p in pages]

    progress = {"done": 0, "total": total, "errors": [], "status": "running"}
    r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))

    for pid in page_ids:
        try:
            with get_sync_db() as db:
                page = db.get(Page, uuid.UUID(pid))
                if not page:
                    continue
                wp_post_id = _resolve_wp_post_id(db, page)

            if not wp_post_id:
                progress["errors"].append(f"{pid}: no wp_post_id")
                progress["done"] += 1
                r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))
                continue

            with get_sync_db() as db:
                site_obj = db.execute(select(Site).where(Site.id == uuid.UUID(site_id))).scalar_one()

            content = _fetch_wp_post_content(site_obj, wp_post_id)
            if not content:
                progress["errors"].append(f"{pid}: fetch failed")
                progress["done"] += 1
                r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))
                continue

            headings = extract_headings(content)
            if headings:
                toc_html = generate_toc_html(headings)
                new_content = inject_toc(content, toc_html)
                pushed = _push_wp_content(site_obj, wp_post_id, new_content)
            else:
                # No headings — mark as done (TOC not applicable)
                pushed = True

            if pushed:
                with get_sync_db() as db:
                    page = db.get(Page, uuid.UUID(pid))
                    if page:
                        page.has_toc = True
            else:
                progress["errors"].append(f"{pid}: push failed")

        except Exception as exc:
            logger.error("bulk_fix_toc page error", page_id=pid, error=str(exc))
            progress["errors"].append(f"{pid}: {str(exc)[:100]}")

        progress["done"] += 1
        r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))

    progress["status"] = "done" if not progress["errors"] else "error"
    r.setex(f"bulk:{task_id}:progress", 3600, json.dumps(progress))

    logger.info(
        "bulk_fix_toc complete",
        site_id=site_id,
        done=progress["done"],
        errors=len(progress["errors"]),
    )
    return {
        "done": progress["done"],
        "total": total,
        "errors": len(progress["errors"]),
    }
