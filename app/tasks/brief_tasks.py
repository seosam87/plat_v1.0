"""Celery tasks for the Copywriting Brief tool — 4-step chain.

Chain flow:
  step1_serp -> step2_crawl -> step3_aggregate -> step4_finalize

Each step receives job_id (str) and returns job_id (str) so the chain
passes it automatically. Use .si() signatures in dispatch (not .s()).
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from loguru import logger

from app.celery_app import celery_app
from app.database import get_sync_db


@celery_app.task(
    name="app.tasks.brief_tasks.run_brief_step1_serp",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=300,
    time_limit=360,
)
def run_brief_step1_serp(self, job_id: str) -> str:
    """Step 1: Fetch SERP results via XMLProxy and collect TOP-10 URLs per phrase.

    Stores collected URLs in job.intermediate_data for use by step 2.
    """
    from app.models.brief_job import BriefJob
    from app.services.service_credential_service import get_credential_sync
    from app.services.xmlproxy_service import XMLProxyError, search_yandex_sync

    job_uuid = uuid.UUID(job_id)

    # Mark running
    with get_sync_db() as db:
        job = db.get(BriefJob, job_uuid)
        if not job:
            return job_id
        job.status = "running"
        job.intermediate_data = {}
        db.commit()
        phrases = list(job.input_phrases)
        region = job.input_region or 213

    # Get XMLProxy credentials
    with get_sync_db() as db:
        creds = get_credential_sync(db, "xmlproxy")

    if not creds or not creds.get("user") or not creds.get("key"):
        with get_sync_db() as db:
            job = db.get(BriefJob, job_uuid)
            if job:
                job.status = "failed"
                job.error_message = "XMLProxy не настроен"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        return job_id

    # Fetch TOP-10 URLs per phrase
    urls_per_phrase: dict[str, list[str]] = {}
    all_snippets: list[str] = []

    for phrase in phrases:
        try:
            serp = search_yandex_sync(creds["user"], creds["key"], phrase, lr=region, max_position=10)
            results = serp.get("results", [])
            phrase_urls = [r["url"] for r in results[:10] if r.get("url")]
            urls_per_phrase[phrase] = phrase_urls
            # Collect snippets for highlights
            for r in results:
                snippet = r.get("snippet", "").strip()
                if snippet:
                    all_snippets.append(snippet)
        except XMLProxyError as e:
            logger.warning("brief step1: XMLProxy error for phrase '{}': {}", phrase, e)
            raise self.retry(exc=e, countdown=30)
        except Exception as e:
            logger.error("brief step1: unexpected error for phrase '{}': {}", phrase, e)
            raise self.retry(exc=e, countdown=30)

    # Flatten unique URLs (deduplicated, preserving order)
    seen_urls: set[str] = set()
    all_urls: list[str] = []
    for phrase_urls in urls_per_phrase.values():
        for url in phrase_urls:
            if url not in seen_urls:
                seen_urls.add(url)
                all_urls.append(url)

    with get_sync_db() as db:
        job = db.get(BriefJob, job_uuid)
        if job:
            job.intermediate_data = {
                "urls": all_urls,
                "urls_per_phrase": urls_per_phrase,
                "snippets": all_snippets[:100],  # cap snippets
            }
            db.commit()

    logger.info("brief step1 done: job={} urls={}", job_id, len(all_urls))
    return job_id


@celery_app.task(
    name="app.tasks.brief_tasks.run_brief_step2_crawl",
    bind=True,
    max_retries=1,
    queue="default",
    soft_time_limit=900,
    time_limit=960,
)
def run_brief_step2_crawl(self, job_id: str) -> str:
    """Step 2: Crawl TOP-10 pages via Playwright and store extracted data.

    Reads URL list from job.intermediate_data, crawls each page, stores
    crawled page data back into intermediate_data for step 3.
    """
    from app.models.brief_job import BriefJob
    from app.services.brief_top10_service import crawl_top10_page

    job_uuid = uuid.UUID(job_id)

    with get_sync_db() as db:
        job = db.get(BriefJob, job_uuid)
        if not job:
            return job_id
        intermediate = job.intermediate_data or {}
        urls = intermediate.get("urls", [])

    crawled_pages: list[dict | None] = []
    total = len(urls)

    for i, url in enumerate(urls):
        try:
            page_data = crawl_top10_page(url)
            crawled_pages.append(page_data)
        except Exception as exc:
            logger.warning("brief step2: error crawling {}: {}", url, exc)
            crawled_pages.append(None)

        # Progress update every 5 pages
        if i % 5 == 0:
            pct = int((i + 1) / total * 50) + 10 if total else 10
            with get_sync_db() as db:
                j = db.get(BriefJob, job_uuid)
                if j:
                    j.progress_pct = pct
                    db.commit()

        # Polite crawl: 0.5s between pages
        if i < total - 1:
            time.sleep(0.5)

    # Store crawled pages data in intermediate_data
    with get_sync_db() as db:
        job = db.get(BriefJob, job_uuid)
        if job:
            intermediate = job.intermediate_data or {}
            # Filter None pages for storage (keep non-None only)
            intermediate["crawled_pages"] = [p for p in crawled_pages if p]
            intermediate["pages_attempted"] = total
            job.intermediate_data = intermediate
            db.commit()

    crawled_count = sum(1 for p in crawled_pages if p is not None)
    logger.info("brief step2 done: job={} crawled={}/{}", job_id, crawled_count, total)
    return job_id


@celery_app.task(
    name="app.tasks.brief_tasks.run_brief_step3_aggregate",
    bind=True,
    max_retries=1,
    queue="default",
    soft_time_limit=120,
    time_limit=180,
)
def run_brief_step3_aggregate(self, job_id: str) -> str:
    """Step 3: Aggregate crawled data into BriefResult.

    Reads crawled_pages and snippets from intermediate_data.
    Creates one BriefResult row per BriefJob.
    """
    from app.models.brief_job import BriefJob, BriefResult
    from app.services.brief_top10_service import aggregate_brief_data

    job_uuid = uuid.UUID(job_id)

    with get_sync_db() as db:
        job = db.get(BriefJob, job_uuid)
        if not job:
            return job_id
        intermediate = job.intermediate_data or {}
        phrases = list(job.input_phrases)

    crawled_pages = intermediate.get("crawled_pages", [])
    pages_attempted = intermediate.get("pages_attempted", len(crawled_pages))
    snippets = intermediate.get("snippets", [])

    # Reconstruct full list (crawled_pages stored without None, pages_attempted holds total)
    agg = aggregate_brief_data(crawled_pages, phrases, serp_snippets=snippets)
    # Override pages_attempted with stored value (includes failed crawls)
    agg["pages_attempted"] = pages_attempted

    with get_sync_db() as db:
        brief_result = BriefResult(job_id=job_uuid, **agg)
        db.add(brief_result)
        job = db.get(BriefJob, job_uuid)
        if job:
            job.progress_pct = 90
        db.commit()

    logger.info("brief step3 done: job={} pages_crawled={}", job_id, agg.get("pages_crawled", 0))
    return job_id


@celery_app.task(
    name="app.tasks.brief_tasks.run_brief_step4_finalize",
    bind=True,
    max_retries=1,
    queue="default",
    soft_time_limit=30,
    time_limit=60,
)
def run_brief_step4_finalize(self, job_id: str) -> str:
    """Step 4: Mark BriefJob as complete and clear intermediate data.

    Clears intermediate_data to reclaim storage — the aggregated
    result is already persisted in the brief_results table.
    """
    from app.models.brief_job import BriefJob

    job_uuid = uuid.UUID(job_id)

    with get_sync_db() as db:
        job = db.get(BriefJob, job_uuid)
        if job:
            job.status = "complete"
            job.completed_at = datetime.now(timezone.utc)
            job.result_count = 1
            job.progress_pct = 100
            job.intermediate_data = None  # Clear to save space
            db.commit()

    logger.info("brief step4 done: job={} status=complete", job_id)
    return job_id
