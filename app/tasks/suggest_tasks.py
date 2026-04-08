"""Celery tasks for keyword suggest alphabetic expansion.

Performs А-Я alphabetic expansion for a seed keyword against Yandex Suggest
(via proxy pool) and optionally Google Suggest (direct). Results are cached
in Redis with a 24h TTL. Handles proxy bans by rotating proxies with a 30s
pause and returning partial results on exhaustion.
"""
from __future__ import annotations

import json
import random
import time
import uuid

import redis as sync_redis
from loguru import logger

from app.celery_app import celery_app
from app.config import settings
from app.database import get_sync_db
from app.models.suggest_job import SuggestJob
from app.services.notifications import notify  # noqa: F401 — used for notify() wiring per D-02
from app.services.suggest_service import (
    RU_ALPHABET,
    SUGGEST_CACHE_TTL,
    deduplicate_suggestions,
    fetch_google_suggest_sync,
    fetch_yandex_suggest_sync,
    get_active_proxy_urls_sync,
    suggest_cache_key,
)


@celery_app.task(
    name="app.tasks.suggest_tasks.fetch_suggest_keywords",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=300,
    time_limit=360,
)
def fetch_suggest_keywords(self, job_id: str) -> dict:
    """Full alphabetic (А-Я) expansion suggest fetch with cache and proxy rotation.

    Flow:
    1. Load job from DB, set status='running'
    2. Check Redis cache — if hit, return immediately
    3. Iterate А-Я calling Yandex Suggest with proxy rotation
    4. If include_google=True, iterate А-Я calling Google Suggest (no proxy)
    5. Deduplicate and write to Redis cache (TTL=24h)
    6. Update job status: complete | partial (proxy exhaustion) | failed

    Args:
        job_id: UUID string of the SuggestJob to process.

    Returns:
        Dict with status, count, cache_hit, was_banned fields.
    """
    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)

    # -----------------------------------------------------------------------
    # Load job, mark as running
    # -----------------------------------------------------------------------
    with get_sync_db() as db:
        job = db.get(SuggestJob, uuid.UUID(job_id))
        if not job:
            logger.error("SuggestJob not found: {}", job_id)
            return {"status": "failed", "error": "Job not found"}
        seed = job.seed
        include_google = job.include_google
        cache_key_val = job.cache_key or suggest_cache_key(seed, include_google)
        job.status = "running"
        job.cache_key = cache_key_val
        db.commit()

    # -----------------------------------------------------------------------
    # Check Redis cache
    # -----------------------------------------------------------------------
    cached = r.get(cache_key_val)
    if cached:
        data = json.loads(cached)
        with get_sync_db() as db:
            job = db.get(SuggestJob, uuid.UUID(job_id))
            if job:
                job.status = "complete"
                job.cache_hit = True
                job.result_count = len(data)
                db.commit()
        return {"status": "complete", "cache_hit": True, "count": len(data)}

    # -----------------------------------------------------------------------
    # Alphabetic expansion — Yandex (with proxy rotation per D-05/D-06/D-17)
    # -----------------------------------------------------------------------
    proxies = get_active_proxy_urls_sync()
    yandex_all: list[str] = []
    was_banned = False
    proxy_idx = 0

    for letter in RU_ALPHABET:
        query = f"{seed} {letter}"
        # D-17: random 200-500ms pause between sequential requests
        time.sleep(random.uniform(0.2, 0.5))

        fetched = False
        for attempt in range(3):  # D-06: max 3 attempts per letter
            proxy_url = proxies[proxy_idx % len(proxies)] if proxies else None
            results = fetch_yandex_suggest_sync(query, proxy_url=proxy_url)
            if results:
                yandex_all.extend(results)
                fetched = True
                break
            # Rotate proxy on empty/error response
            proxy_idx += 1
            if proxies and proxy_idx >= len(proxies) * 3:
                # Exhausted 3 full rotations through the pool → consider all proxies banned
                was_banned = True
                break
            if proxies:
                # D-06: 30s pause before retry with next proxy
                time.sleep(30)

        if was_banned:
            logger.warning(
                "All proxies exhausted at letter '{}' for seed='{}'", letter, seed
            )
            break

    # -----------------------------------------------------------------------
    # Google expansion (no proxy, per D-07)
    # -----------------------------------------------------------------------
    google_all: list[str] = []
    if include_google:
        for letter in RU_ALPHABET:
            query = f"{seed} {letter}"
            time.sleep(random.uniform(0.2, 0.5))
            results = fetch_google_suggest_sync(query)
            google_all.extend(results)

    # -----------------------------------------------------------------------
    # Deduplicate and cache
    # -----------------------------------------------------------------------
    combined = deduplicate_suggestions(yandex_all, google_all)

    if combined:
        r.set(
            cache_key_val,
            json.dumps(combined, ensure_ascii=False),
            ex=SUGGEST_CACHE_TTL,
        )

    # -----------------------------------------------------------------------
    # Update job status
    # -----------------------------------------------------------------------
    if not combined:
        status = "failed"
    elif was_banned:
        status = "partial"
    else:
        status = "complete"

    with get_sync_db() as db:
        job = db.get(SuggestJob, uuid.UUID(job_id))
        if job:
            job.status = status
            job.result_count = len(combined)
            job.expected_count = len(RU_ALPHABET) * 10  # ~330 expected from full expansion
            if was_banned and combined:
                job.error_message = "Прокси заблокированы, получены частичные результаты"
            elif not combined:
                job.error_message = "Не удалось получить подсказки — все прокси заблокированы"
            db.commit()

    # In-app notification guard (D-02): fetch_suggest_keywords has no user_id arg today.
    # Pass user_id once callers plumb it through; Telegram not used for suggest.
    _user_id = None  # TODO: accept user_id kwarg in a future phase
    _notify_kind = "keyword_suggest.ready" if status in ("complete", "partial") else "keyword_suggest.failed"
    if _user_id is not None:
        import asyncio as _aio
        from app.database import AsyncSessionLocal as _ASL

        async def _emit_suggest_done():
            async with _ASL() as _db:
                await notify(
                    db=_db, user_id=_user_id, kind=_notify_kind,
                    title="Подсказки ключей готовы",
                    body=f"Seed: получено {len(combined)} подсказок",
                    link_url=f"/keyword-suggest/{job_id}",
                    severity="info" if status in ("complete", "partial") else "error",
                )
                await _db.commit()

        _aio.run(_emit_suggest_done())
    else:
        logger.debug(
            "no user scope; skipping in-app notification",
            task="fetch_suggest_keywords",
            kind=_notify_kind,
        )

    return {"status": status, "count": len(combined), "was_banned": was_banned}


@celery_app.task(
    name="app.tasks.suggest_tasks.fetch_wordstat_frequency",
    bind=True,
    max_retries=3,  # D-03: retry=3 for all external API calls
    queue="default",
    soft_time_limit=120,
    time_limit=150,
)
def fetch_wordstat_frequency(self, job_id: str) -> dict:
    """Fetch Wordstat frequency data for an existing suggest job's results.

    Reads cached suggestions from Redis, fetches frequency via Wordstat API,
    updates the cached data with frequency values.
    """
    from app.services.service_credential_service import get_credential_sync
    from app.services.wordstat_service import fetch_wordstat_frequency_sync

    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)

    with get_sync_db() as db:
        job = db.get(SuggestJob, uuid.UUID(job_id))
        if not job or not job.cache_key:
            return {"status": "failed", "error": "Job not found or no cache key"}
        cache_key_val = job.cache_key
        creds = get_credential_sync(db, "yandex_direct")

    if not creds or not creds.get("token"):
        return {"status": "failed", "error": "Yandex Direct token not configured"}

    token = creds["token"]

    raw = r.get(cache_key_val)
    if not raw:
        return {"status": "failed", "error": "No cached suggestions found"}

    suggestions = json.loads(raw)
    phrases = [s["keyword"] for s in suggestions]

    freq_map = fetch_wordstat_frequency_sync(phrases, oauth_token=token)

    updated_count = 0
    for s in suggestions:
        freq = freq_map.get(s["keyword"])
        if freq is not None:
            s["frequency"] = freq
            updated_count += 1

    r.set(
        cache_key_val,
        json.dumps(suggestions, ensure_ascii=False),
        ex=SUGGEST_CACHE_TTL,
    )

    return {"status": "complete", "updated": updated_count, "total": len(phrases)}
