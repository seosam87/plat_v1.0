"""Celery task for Batch Wordstat frequency tool.

Processes up to 1000 phrases with progress tracking.
Updates job.progress_pct every 50 phrases.
Stores results in WordstatBatchResult + WordstatMonthlyData tables.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import get_sync_db


@celery_app.task(
    name="app.tasks.wordstat_batch_tasks.run_wordstat_batch",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=3600,
    time_limit=3660,
)
def run_wordstat_batch(self, job_id: str) -> dict:
    """Process a batch Wordstat frequency job.

    Flow:
    1. Mark job as running.
    2. Load OAuth token from service_credentials (yandex_direct).
    3. Process phrases: exact + broad + monthly dynamics per phrase.
    4. Update progress_pct every 50 phrases.
    5. Store WordstatBatchResult + WordstatMonthlyData rows.
    6. Mark complete | partial | failed.

    Args:
        job_id: UUID string of the WordstatBatchJob to process.

    Returns:
        Dict with status and count fields.
    """
    from app.models.wordstat_batch_job import (
        WordstatBatchJob,
        WordstatBatchResult,
        WordstatMonthlyData,
    )
    from app.services.batch_wordstat_service import fetch_wordstat_batch_sync
    from app.services.service_credential_service import get_credential_sync

    job_uuid = uuid.UUID(job_id)

    # Mark running
    with get_sync_db() as db:
        job = db.get(WordstatBatchJob, job_uuid)
        if not job:
            return {"status": "failed", "error": "Job not found"}
        job.status = "running"
        db.commit()
        phrases = list(job.input_phrases)

    total = len(phrases)

    # Load OAuth token
    with get_sync_db() as db:
        creds = get_credential_sync(db, "yandex_direct")

    oauth_token = (creds or {}).get("token") if creds else None
    if not oauth_token:
        with get_sync_db() as db:
            job = db.get(WordstatBatchJob, job_uuid)
            if job:
                job.status = "failed"
                job.error_message = "OAuth-токен не настроен"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        return {"status": "failed", "error": "No OAuth token"}

    processed_count = 0
    partial_error = False

    # Process in chunks of 10 to allow progress updates and handle rate-limit retries
    chunk_size = 10
    for chunk_start in range(0, total, chunk_size):
        chunk = phrases[chunk_start : chunk_start + chunk_size]

        try:
            chunk_results = fetch_wordstat_batch_sync(
                phrases=chunk,
                oauth_token=oauth_token,
            )
        except Exception as exc:
            # Transient error on entire chunk — retry the whole task
            raise self.retry(exc=exc, countdown=60)

        # Write chunk results to DB
        with get_sync_db() as db:
            for result_data in chunk_results:
                result_row = WordstatBatchResult(
                    job_id=job_uuid,
                    phrase=result_data["phrase"],
                    freq_exact=result_data.get("freq_exact"),
                    freq_broad=result_data.get("freq_broad"),
                )
                db.add(result_row)
                db.flush()  # get result_row.id

                for m in result_data.get("monthly", []):
                    monthly_row = WordstatMonthlyData(
                        result_id=result_row.id,
                        year_month=m["year_month"],
                        frequency=m["frequency"],
                    )
                    db.add(monthly_row)

            processed_count += len(chunk_results)

            # Update progress every 50 phrases (update within each chunk_size=10 iteration too)
            should_update = (processed_count % 50 == 0) or (processed_count >= total)
            if should_update or chunk_start == 0:
                job = db.get(WordstatBatchJob, job_uuid)
                if job:
                    job.result_count = processed_count
                    progress_pct = int(processed_count / total * 100) if total > 0 else 0
                    job.progress_pct = progress_pct
            db.commit()

    # Determine final status
    if partial_error and processed_count > 0:
        final_status = "partial"
    elif processed_count == 0:
        final_status = "failed"
    else:
        final_status = "complete"

    with get_sync_db() as db:
        job = db.get(WordstatBatchJob, job_uuid)
        if job:
            job.status = final_status
            job.result_count = processed_count
            job.progress_pct = 100 if final_status == "complete" else job.progress_pct
            job.completed_at = datetime.now(timezone.utc)
            if partial_error:
                job.error_message = "лимит API исчерпан — сохранены частичные данные"
            db.commit()

    return {"status": final_status, "count": processed_count}
