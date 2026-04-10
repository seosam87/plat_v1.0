"""Celery task for Relevant URL Finder tool."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import get_sync_db


@celery_app.task(
    name="app.tasks.relevant_url_tasks.run_relevant_url",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=300,   # 100 phrases × ~2s each = ~200s max
    time_limit=360,
)
def run_relevant_url(self, job_id: str) -> dict:
    """Process a RelevantUrlJob: search each phrase via XMLProxy, filter by target domain.

    Args:
        job_id: UUID string of the RelevantUrlJob to process.

    Returns:
        dict with status and result count.
    """
    from app.models.relevant_url_job import RelevantUrlJob, RelevantUrlResult
    from app.services.relevant_url_service import find_relevant_url
    from app.services.service_credential_service import get_credential_sync
    from app.services.xmlproxy_service import XMLProxyError, search_yandex_sync

    job_uuid = uuid.UUID(job_id)

    with get_sync_db() as db:
        job = db.get(RelevantUrlJob, job_uuid)
        if not job:
            return {"status": "failed", "error": "Job not found"}
        job.status = "running"
        db.commit()
        phrases = list(job.input_phrases)
        target_domain = job.target_domain

    with get_sync_db() as db:
        creds = get_credential_sync(db, "xmlproxy")

    if not creds or not creds.get("user") or not creds.get("key"):
        with get_sync_db() as db:
            job = db.get(RelevantUrlJob, job_uuid)
            if job:
                job.status = "failed"
                job.error_message = "XMLProxy не настроен"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        return {"status": "failed"}

    results = []
    balance_exhausted = False

    for i, phrase in enumerate(phrases):
        # Periodically update progress counter
        if i % 10 == 0:
            with get_sync_db() as db:
                j = db.get(RelevantUrlJob, job_uuid)
                if j:
                    j.result_count = i
                    db.commit()

        try:
            serp = search_yandex_sync(creds["user"], creds["key"], phrase, max_position=10)
            result_data = find_relevant_url(phrase, serp.get("results", []), target_domain)
            results.append(result_data)
        except XMLProxyError as e:
            if e.code in (32, 33):
                # Balance exhausted — save partial results and stop
                balance_exhausted = True
                break
            raise self.retry(exc=e, countdown=30)
        except Exception as e:
            raise self.retry(exc=e, countdown=30)

    if balance_exhausted and results:
        status = "partial"
    elif balance_exhausted and not results:
        status = "failed"
    else:
        status = "complete"

    with get_sync_db() as db:
        for r in results:
            db.add(
                RelevantUrlResult(
                    job_id=job_uuid,
                    phrase=r["phrase"],
                    url=r["url"],
                    position=r["position"],
                    top_competitors=r["top_competitors"],
                )
            )
        job = db.get(RelevantUrlJob, job_uuid)
        if job:
            job.status = status
            job.result_count = len(results)
            job.completed_at = datetime.now(timezone.utc)
            if balance_exhausted:
                job.error_message = "Баланс XMLProxy исчерпан — сохранены частичные данные"
        db.commit()

    return {"status": status, "count": len(results)}
