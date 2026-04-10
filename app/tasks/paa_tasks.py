"""Celery task for PAA (People Also Ask) SERP aggregation tool."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from loguru import logger

from app.celery_app import celery_app
from app.database import get_sync_db


@celery_app.task(
    name="app.tasks.paa_tasks.run_paa",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=300,
    time_limit=360,
)
def run_paa(self, job_id: str) -> dict:
    """Process a PAA extraction job using XMLProxy + BeautifulSoup.

    Flow:
    1. Mark job as running
    2. Fetch XMLProxy credentials
    3. For each phrase: call fetch_yandex_html_sync, extract_paa_for_phrase
    4. Write PAAResult rows, update job status (complete|failed)

    Retry: on transient XMLProxyError, up to max_retries=3.

    Args:
        job_id: UUID string of the PAAJob to process.

    Returns:
        Dict with ``status`` and ``count`` fields.
    """
    from app.models.paa_job import PAAJob, PAAResult
    from app.services.paa_service import extract_paa_for_phrase
    from app.services.service_credential_service import get_credential_sync
    from app.services.xmlproxy_service import XMLProxyError, fetch_yandex_html_sync

    job_uuid = uuid.UUID(job_id)

    # -----------------------------------------------------------------------
    # Step 1: mark job as running
    # -----------------------------------------------------------------------
    with get_sync_db() as db:
        job = db.get(PAAJob, job_uuid)
        if not job:
            logger.error("PAA job {} not found", job_id)
            return {"status": "failed", "error": "Job not found"}
        job.status = "running"
        db.commit()
        phrases = list(job.input_phrases)

    # -----------------------------------------------------------------------
    # Step 2: fetch XMLProxy credentials
    # -----------------------------------------------------------------------
    with get_sync_db() as db:
        creds = get_credential_sync(db, "xmlproxy")

    if not creds or not creds.get("user") or not creds.get("key"):
        with get_sync_db() as db:
            job = db.get(PAAJob, job_uuid)
            if job:
                job.status = "failed"
                job.error_message = "XMLProxy не настроен"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        logger.warning("PAA job {}: XMLProxy credentials not configured", job_id)
        return {"status": "failed"}

    xmlproxy_user: str = creds["user"]
    xmlproxy_key: str = creds["key"]

    # -----------------------------------------------------------------------
    # Step 3: process each phrase
    # -----------------------------------------------------------------------
    all_results: list[dict] = []

    for i, phrase in enumerate(phrases):
        # Progress update every 10 phrases
        if i % 10 == 0:
            with get_sync_db() as db:
                j = db.get(PAAJob, job_uuid)
                if j:
                    j.result_count = len(all_results)
                    db.commit()

        try:
            html = fetch_yandex_html_sync(xmlproxy_user, xmlproxy_key, phrase)
            phrase_results = extract_paa_for_phrase(phrase, html)
            all_results.extend(phrase_results)
            logger.debug(
                "PAA job {}: phrase '{}' → {} questions",
                job_id,
                phrase[:50],
                len(phrase_results),
            )
        except XMLProxyError as exc:
            logger.warning(
                "PAA job {}: XMLProxyError code={} for phrase '{}': {}",
                job_id,
                exc.code,
                phrase[:50],
                exc.message,
            )
            raise self.retry(exc=exc, countdown=30)
        except Exception as exc:
            logger.warning(
                "PAA job {}: unexpected error for phrase '{}': {}",
                job_id,
                phrase[:50],
                exc,
            )
            raise self.retry(exc=exc, countdown=30)

        # Rate limiting — XMLProxy has per-second limits
        if i < len(phrases) - 1:
            time.sleep(0.5)

    # -----------------------------------------------------------------------
    # Step 4: write results to DB, update job status
    # -----------------------------------------------------------------------
    with get_sync_db() as db:
        for r in all_results:
            db.add(
                PAAResult(
                    job_id=job_uuid,
                    phrase=r["phrase"],
                    question=r["question"],
                    source_block=r["source_block"],
                )
            )
        job = db.get(PAAJob, job_uuid)
        if job:
            job.status = "complete"
            job.result_count = len(all_results)
            job.completed_at = datetime.now(timezone.utc)
        db.commit()

    logger.info(
        "PAA job {} complete: {} phrases → {} questions",
        job_id,
        len(phrases),
        len(all_results),
    )
    return {"status": "complete", "count": len(all_results)}
