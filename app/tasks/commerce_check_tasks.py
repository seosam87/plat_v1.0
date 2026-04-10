"""Celery task for Commercialization Check tool."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import get_sync_db


@celery_app.task(
    name="app.tasks.commerce_check_tasks.run_commerce_check",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=600,
    time_limit=660,
)
def run_commerce_check(self, job_id: str) -> dict:
    """Process commercialization check job via XMLProxy Yandex SERP analysis.

    Flow:
    1. Mark job as running
    2. Fetch XMLProxy credentials
    3. For each phrase: call search_yandex_sync, analyze_commercialization
    4. Write CommerceCheckResult rows, update job status (complete|partial|failed)

    Partial result: saved when XMLProxy balance codes 32/33 are returned.
    Retry: on transient errors (codes other than 32/33), up to max_retries=3.

    Args:
        job_id: UUID string of the CommerceCheckJob to process.

    Returns:
        Dict with status and count fields.
    """
    from app.models.commerce_check_job import CommerceCheckJob, CommerceCheckResult
    from app.services.commerce_check_service import analyze_commercialization
    from app.services.service_credential_service import get_credential_sync
    from app.services.xmlproxy_service import XMLProxyError, search_yandex_sync

    job_uuid = uuid.UUID(job_id)

    # Mark running
    with get_sync_db() as db:
        job = db.get(CommerceCheckJob, job_uuid)
        if not job:
            return {"status": "failed", "error": "Job not found"}
        job.status = "running"
        db.commit()
        phrases = list(job.input_phrases)

    # Get XMLProxy credentials
    with get_sync_db() as db:
        creds = get_credential_sync(db, "xmlproxy")
    if not creds or not creds.get("user") or not creds.get("key"):
        with get_sync_db() as db:
            job = db.get(CommerceCheckJob, job_uuid)
            if job:
                job.status = "failed"
                job.error_message = "XMLProxy не настроен"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        return {"status": "failed"}

    results = []
    balance_exhausted = False

    for i, phrase in enumerate(phrases):
        # Progress update every 10 phrases
        if i % 10 == 0:
            with get_sync_db() as db:
                j = db.get(CommerceCheckJob, job_uuid)
                if j:
                    j.result_count = i
                    db.commit()
        try:
            serp = search_yandex_sync(creds["user"], creds["key"], phrase, max_position=10)
            result_data = analyze_commercialization(phrase, serp.get("results", []))
            results.append(result_data)
        except XMLProxyError as e:
            if e.code in (32, 33):
                balance_exhausted = True
                break
            raise self.retry(exc=e, countdown=30)
        except Exception as e:
            raise self.retry(exc=e, countdown=30)

    # Determine final status
    if balance_exhausted and results:
        status = "partial"
    elif not results and balance_exhausted:
        status = "failed"
    else:
        status = "complete"

    # Write results to DB
    with get_sync_db() as db:
        for r in results:
            db.add(CommerceCheckResult(job_id=job_uuid, **r))
        job = db.get(CommerceCheckJob, job_uuid)
        if job:
            job.status = status
            job.result_count = len(results)
            job.completed_at = datetime.now(timezone.utc)
            if balance_exhausted:
                job.error_message = "Баланс XMLProxy исчерпан — сохранены частичные данные"
        db.commit()

    return {"status": status, "count": len(results)}
