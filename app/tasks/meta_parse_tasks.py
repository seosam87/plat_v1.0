"""Celery task for Meta Tag Parser tool."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import get_sync_db


@celery_app.task(
    name="app.tasks.meta_parse_tasks.run_meta_parse",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=1200,   # 500 URLs × ~2s each = ~1000s max
    time_limit=1260,
)
def run_meta_parse(self, job_id: str) -> dict:
    """Fetch and parse meta tags for all URLs in a MetaParseJob.

    Flow:
    1. Load job from DB, set status='running'
    2. asyncio.run(fetch_and_parse_urls(...)) — async-in-sync via prefork-safe asyncio.run()
    3. Write MetaParseResult rows to DB
    4. Update job status to 'complete'

    On exception: mark job as 'failed', retry up to 3 times with 30s countdown.

    Args:
        job_id: UUID string of the MetaParseJob to process.

    Returns:
        Dict with status and count fields.
    """
    from app.models.meta_parse_job import MetaParseJob, MetaParseResult
    from app.services.meta_parse_service import fetch_and_parse_urls

    job_uuid = uuid.UUID(job_id)

    # ------------------------------------------------------------------
    # Mark as running, load URLs
    # ------------------------------------------------------------------
    with get_sync_db() as db:
        job = db.get(MetaParseJob, job_uuid)
        if not job:
            return {"status": "failed", "error": "Job not found"}
        job.status = "running"
        db.commit()
        urls = list(job.input_urls)

    # ------------------------------------------------------------------
    # Run async fetch inside sync Celery task (safe with prefork pool)
    # ------------------------------------------------------------------
    try:
        results = asyncio.run(fetch_and_parse_urls(urls, concurrency=5))
    except Exception as e:
        with get_sync_db() as db:
            job = db.get(MetaParseJob, job_uuid)
            if job:
                job.status = "failed"
                job.error_message = str(e)[:500]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        raise self.retry(exc=e, countdown=30)

    # ------------------------------------------------------------------
    # Write results to DB
    # ------------------------------------------------------------------
    with get_sync_db() as db:
        for r in results:
            db.add(MetaParseResult(job_id=job_uuid, **r))
        job = db.get(MetaParseJob, job_uuid)
        if job:
            job.status = "complete"
            job.result_count = len(results)
            job.completed_at = datetime.now(timezone.utc)
        db.commit()

    return {"status": "complete", "count": len(results)}
