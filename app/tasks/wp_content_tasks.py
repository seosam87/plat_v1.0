"""Celery tasks for WP content enrichment pipeline."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger

from app.celery_app import celery_app
from app.tasks.wp_tasks import site_active_guard


@celery_app.task(
    name="app.tasks.wp_content_tasks.run_content_pipeline",
    bind=True,
    max_retries=3,
    queue="wp",
    soft_time_limit=120,
    time_limit=150,
)
def run_content_pipeline(self, job_id: str) -> dict:
    """Run content enrichment pipeline for a single WP content job.

    Steps: fetch original → TOC → schema.org → internal links → compute diff → save.
    The job stays in awaiting_approval until user approves the push.
    """
    from app.database import get_sync_db
    from app.models.wp_content_job import WpContentJob, JobStatus
    from app.services.content_pipeline import (
        extract_headings, generate_toc_html, inject_toc, add_heading_ids,
        generate_schema_article, inject_schema,
        find_link_opportunities, insert_links,
        compute_content_diff,
    )
    from app.models.keyword import Keyword
    from sqlalchemy import select

    with get_sync_db() as db:
        job = db.get(WpContentJob, uuid.UUID(job_id))
        if not job:
            return {"status": "error", "reason": "job not found"}

        skip = site_active_guard(str(job.site_id))
        if skip:
            job.status = JobStatus.failed
            job.error_message = skip["reason"]
            return skip

        job.status = JobStatus.processing

    try:
        # Step 1: Fetch original content from WP if not already stored
        original = None
        with get_sync_db() as db:
            job = db.get(WpContentJob, uuid.UUID(job_id))
            original = job.original_content

        if not original and job.wp_post_id:
            original = _fetch_wp_content(str(job.site_id), job.wp_post_id)
            with get_sync_db() as db:
                job = db.get(WpContentJob, uuid.UUID(job_id))
                job.original_content = original

        if not original:
            with get_sync_db() as db:
                job = db.get(WpContentJob, uuid.UUID(job_id))
                job.status = JobStatus.failed
                job.error_message = "No content to process"
            return {"status": "failed", "reason": "no content"}

        content = original

        # Step 2: TOC generation
        headings = extract_headings(content)
        if headings:
            content = add_heading_ids(content, headings)
            toc = generate_toc_html(headings)
            content = inject_toc(content, toc)

        # Step 3: Schema.org injection
        schema_tag = generate_schema_article(
            title=headings[0]["text"] if headings else "Article",
            url=job.page_url,
        )
        content = inject_schema(content, schema_tag)

        # Step 4: Internal linking
        with get_sync_db() as db:
            job = db.get(WpContentJob, uuid.UUID(job_id))
            kws = db.execute(
                select(Keyword).where(
                    Keyword.site_id == job.site_id,
                    Keyword.target_url != None,
                )
            ).scalars().all()
            kw_urls = [{"phrase": k.phrase, "url": k.target_url} for k in kws if k.target_url]

        if kw_urls:
            opportunities = find_link_opportunities(content, kw_urls)
            content = insert_links(content, opportunities)

        # Step 5: Diff
        diff = compute_content_diff(original, content)

        # Step 6: Save and set awaiting_approval
        with get_sync_db() as db:
            job = db.get(WpContentJob, uuid.UUID(job_id))
            job.processed_content = content
            job.diff_json = diff
            job.rollback_payload = {"original_content": original, "wp_post_id": job.wp_post_id}
            job.processed_at = datetime.now(timezone.utc)
            job.status = JobStatus.awaiting_approval

        logger.info("Content pipeline done", job_id=job_id, has_changes=diff.get("has_changes"))
        return {"status": "awaiting_approval", "job_id": job_id, "has_changes": diff.get("has_changes")}

    except Exception as exc:
        logger.error("Content pipeline failed", job_id=job_id, error=str(exc))
        with get_sync_db() as db:
            job = db.get(WpContentJob, uuid.UUID(job_id))
            job.status = JobStatus.failed
            job.error_message = str(exc)[:500]
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    name="app.tasks.wp_content_tasks.push_to_wp",
    bind=True,
    max_retries=3,
    queue="wp",
)
def push_to_wp(self, job_id: str) -> dict:
    """Push approved content to WordPress."""
    from app.database import get_sync_db
    from app.models.wp_content_job import WpContentJob, JobStatus
    from app.services.wp_service import create_post_sync

    with get_sync_db() as db:
        job = db.get(WpContentJob, uuid.UUID(job_id))
        if not job or job.status != JobStatus.approved:
            return {"status": "skipped", "reason": "not approved"}

        site_id = str(job.site_id)

    skip = site_active_guard(site_id)
    if skip:
        return skip

    # Update WP post content
    from app.models.site import Site
    from app.services.wp_service import _sync_auth_headers
    from sqlalchemy import select
    import httpx

    with get_sync_db() as db:
        job = db.get(WpContentJob, uuid.UUID(job_id))
        site = db.execute(select(Site).where(Site.id == job.site_id)).scalar_one()

        if job.wp_post_id:
            url = site.url.rstrip("/") + f"/wp-json/wp/v2/posts/{job.wp_post_id}"
            headers = _sync_auth_headers(site)
            try:
                resp = httpx.post(url, json={"content": job.processed_content}, headers=headers, timeout=15)
                resp.raise_for_status()
            except Exception as exc:
                job.status = JobStatus.failed
                job.error_message = f"WP push failed: {exc}"
                return {"status": "failed", "error": str(exc)}

        job.status = JobStatus.pushed
        job.pushed_at = datetime.now(timezone.utc)

    logger.info("Content pushed to WP", job_id=job_id)
    return {"status": "pushed", "job_id": job_id}


@celery_app.task(name="app.tasks.wp_content_tasks.rollback_job", bind=True, max_retries=1, queue="wp")
def rollback_job(self, job_id: str) -> dict:
    """Rollback a pushed job to original content."""
    from app.database import get_sync_db
    from app.models.wp_content_job import WpContentJob, JobStatus
    from app.models.site import Site
    from app.services.wp_service import _sync_auth_headers
    from sqlalchemy import select
    import httpx

    with get_sync_db() as db:
        job = db.get(WpContentJob, uuid.UUID(job_id))
        if not job or not job.rollback_payload:
            return {"status": "skipped", "reason": "no rollback data"}

        site = db.execute(select(Site).where(Site.id == job.site_id)).scalar_one()
        original = job.rollback_payload.get("original_content", "")
        wp_post_id = job.rollback_payload.get("wp_post_id")

        if wp_post_id:
            url = site.url.rstrip("/") + f"/wp-json/wp/v2/posts/{wp_post_id}"
            headers = _sync_auth_headers(site)
            try:
                resp = httpx.post(url, json={"content": original}, headers=headers, timeout=15)
                resp.raise_for_status()
            except Exception as exc:
                return {"status": "failed", "error": str(exc)}

        job.status = JobStatus.rolled_back

    logger.info("Content rolled back", job_id=job_id)
    return {"status": "rolled_back", "job_id": job_id}


def _fetch_wp_content(site_id: str, wp_post_id: int) -> str | None:
    """Fetch post content from WP REST API."""
    from app.database import get_sync_db
    from app.models.site import Site
    from app.services.wp_service import _sync_auth_headers
    from sqlalchemy import select
    import httpx

    with get_sync_db() as db:
        site = db.execute(select(Site).where(Site.id == uuid.UUID(site_id))).scalar_one_or_none()
        if not site:
            return None
        url = site.url.rstrip("/") + f"/wp-json/wp/v2/posts/{wp_post_id}"
        headers = _sync_auth_headers(site)

    try:
        resp = httpx.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json().get("content", {}).get("rendered", "")
    except Exception:
        return None
