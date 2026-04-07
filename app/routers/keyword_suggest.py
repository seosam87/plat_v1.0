"""Keyword Suggest router: search form, polling, CSV export, Wordstat dispatch.

Endpoints:
- GET  /ui/keyword-suggest/                   -- main page
- POST /ui/keyword-suggest/search             -- dispatch suggest task (rate-limited 10/min)
- GET  /ui/keyword-suggest/status/{job_id}    -- HTMX polling endpoint
- GET  /ui/keyword-suggest/export             -- CSV download
- POST /ui/keyword-suggest/{job_id}/wordstat  -- dispatch Wordstat frequency fetch
- GET  /ui/keyword-suggest/{job_id}/wordstat-status -- Wordstat polling
"""
from __future__ import annotations

import io
import json
import re
import uuid
from datetime import date

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.dependencies import get_db
from app.models.site import Site
from app.models.suggest_job import SuggestJob
from app.models.user import User
from app.rate_limit import limiter
from app.services.suggest_service import SUGGEST_CACHE_TTL, suggest_cache_key
from app.tasks.suggest_tasks import fetch_suggest_keywords
from app.template_engine import templates

router = APIRouter(prefix="/ui/keyword-suggest", tags=["keyword-suggest"])


def _slugify_seed(seed: str) -> str:
    """Return a filesystem-safe slug for CSV filenames."""
    slug = re.sub(r"[^\w\-]+", "_", seed.strip().lower(), flags=re.UNICODE)
    return slug.strip("_")[:50] or "suggest"


async def _has_wordstat_token(db: AsyncSession) -> bool:
    """Check if yandex_direct credentials are configured (for Wordstat banner)."""
    try:
        from sqlalchemy import select as _select
        from app.models.service_credential import ServiceCredential

        result = await db.execute(
            _select(ServiceCredential).where(
                ServiceCredential.service_name == "yandex_direct"
            )
        )
        rec = result.scalar_one_or_none()
        return rec is not None and rec.credential_data is not None
    except Exception as exc:
        logger.debug("Wordstat token check failed: {}", exc)
        return False


async def _read_cache(cache_key: str) -> list[dict] | None:
    """Read cached suggestions list from Redis (async)."""
    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            raw = await client.get(cache_key)
        finally:
            await client.aclose()
        if raw is None:
            return None
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return None
    except Exception as exc:
        logger.warning("Redis cache read failed for {}: {}", cache_key, exc)
        return None


# ---------------------------------------------------------------------------
# 1. GET / -- main page
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def keyword_suggest_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Main keyword suggest page."""
    result = await db.execute(select(Site).order_by(Site.name))
    sites = result.scalars().all()

    has_wordstat_token = await _has_wordstat_token(db)

    return templates.TemplateResponse(
        request,
        "keyword_suggest/index.html",
        {
            "sites": sites,
            "has_wordstat_token": has_wordstat_token,
        },
    )


# ---------------------------------------------------------------------------
# 2. POST /search -- dispatch suggest task (rate-limited 10/minute)
# ---------------------------------------------------------------------------


@router.post("/search", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def search_suggestions(
    request: Request,
    seed: str = Form(...),
    include_google: bool = Form(False),
    site_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Dispatch a suggest Celery task (or return cached results immediately).

    Rate limit: 10/minute enforced via slowapi decorator applied below.
    """
    seed_clean = seed.strip()
    if not seed_clean:
        return templates.TemplateResponse(
            request,
            "keyword_suggest/partials/suggest_status.html",
            {
                "job": None,
                "status": "failed",
                "error_message": "Введите ключевую фразу.",
            },
        )

    # Resolve optional site_id
    site_uuid: uuid.UUID | None = None
    if site_id:
        try:
            site_uuid = uuid.UUID(site_id)
        except ValueError:
            site_uuid = None

    cache_key = suggest_cache_key(seed_clean, include_google)

    # Create SuggestJob row (pending)
    job = SuggestJob(
        seed=seed_clean[:200],
        include_google=include_google,
        site_id=site_uuid,
        status="pending",
        cache_key=cache_key,
    )
    db.add(job)
    await db.flush()

    # Check cache first
    cached = await _read_cache(cache_key)
    results: list[dict] | None = None
    if cached is not None:
        job.status = "complete"
        job.cache_hit = True
        job.result_count = len(cached)
        results = cached
        await db.commit()
    else:
        # Dispatch Celery task
        try:
            async_res = fetch_suggest_keywords.delay(str(job.id))
            job.celery_task_id = getattr(async_res, "id", None)
            job.status = "running"
        except Exception as exc:
            logger.error("Failed to dispatch fetch_suggest_keywords: {}", exc)
            job.status = "failed"
            job.error_message = "Не удалось запустить задачу."
        await db.commit()

    return templates.TemplateResponse(
        request,
        "keyword_suggest/partials/suggest_status.html",
        {
            "job": job,
            "status": job.status,
            "results": results,
            "cache_hit": job.cache_hit,
            "result_count": job.result_count or 0,
            "error_message": job.error_message,
        },
    )


# Rate limit "10/minute" enforced via @limiter.limit decorator above.


# ---------------------------------------------------------------------------
# 3. GET /status/{job_id} -- HTMX polling
# ---------------------------------------------------------------------------


@router.get("/status/{job_id}", response_class=HTMLResponse)
async def suggest_status(
    request: Request,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> HTMLResponse:
    """HTMX polling endpoint for suggest job status."""
    result = await db.execute(select(SuggestJob).where(SuggestJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Suggest job not found")

    results: list[dict] | None = None
    if job.status in ("complete", "partial") and job.cache_key:
        results = await _read_cache(job.cache_key) or []

    has_wordstat_token = await _has_wordstat_token(db)

    return templates.TemplateResponse(
        request,
        "keyword_suggest/partials/suggest_status.html",
        {
            "job": job,
            "status": job.status,
            "results": results,
            "cache_hit": job.cache_hit,
            "result_count": job.result_count or (len(results) if results else 0),
            "expected_count": job.expected_count or 0,
            "error_message": job.error_message,
            "has_wordstat_token": has_wordstat_token,
        },
    )


# ---------------------------------------------------------------------------
# 4. GET /export -- CSV download
# ---------------------------------------------------------------------------


@router.get("/export")
async def export_csv(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Export suggest results as UTF-8 BOM CSV."""
    import csv

    result = await db.execute(select(SuggestJob).where(SuggestJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None or not job.cache_key:
        raise HTTPException(status_code=404, detail="Suggest job not found")

    rows = await _read_cache(job.cache_key) or []

    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM
    writer = csv.writer(buf)
    writer.writerow(["Подсказка", "Источник", "Частотность"])
    for row in rows:
        kw = row.get("keyword", "") if isinstance(row, dict) else str(row)
        src_raw = row.get("source", "") if isinstance(row, dict) else ""
        src = "Яндекс" if src_raw == "yandex" else ("Google" if src_raw == "google" else "")
        freq = row.get("frequency", "") if isinstance(row, dict) else ""
        writer.writerow([kw, src, freq if freq not in (None, "") else ""])

    buf.seek(0)
    filename = f"suggest_{_slugify_seed(job.seed)}_{date.today().isoformat()}.csv"

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# 5. POST /{job_id}/wordstat -- dispatch Wordstat frequency fetch
# ---------------------------------------------------------------------------


@router.post("/{job_id}/wordstat", response_class=HTMLResponse)
async def dispatch_wordstat(
    request: Request,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Dispatch fetch_wordstat_frequency Celery task for a completed suggest job.

    Lazy import of fetch_wordstat_frequency — Plan 03 creates this task.
    """
    result = await db.execute(select(SuggestJob).where(SuggestJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Suggest job not found")

    if job.status not in ("complete", "partial") or not job.cache_key:
        return HTMLResponse(
            '<div class="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">'
            "Сначала дождитесь результатов подсказок."
            "</div>"
        )

    if not await _has_wordstat_token(db):
        return HTMLResponse(
            '<div class="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">'
            'Токен Яндекс.Директ не настроен. Перейдите в <a href="/ui/settings/" '
            'class="underline">Настройки</a>.'
            "</div>"
        )

    # Lazy import — Plan 03 creates this task; avoid ImportError if Plan 02 runs first.
    try:
        from app.tasks.suggest_tasks import fetch_wordstat_frequency  # type: ignore
    except ImportError:
        logger.warning("fetch_wordstat_frequency not yet available (Plan 03 pending)")
        return HTMLResponse(
            '<div class="p-3 bg-amber-50 border border-amber-200 rounded text-sm text-amber-700">'
            "Модуль Wordstat ещё не установлен."
            "</div>"
        )

    try:
        fetch_wordstat_frequency.delay(str(job.id))
    except Exception as exc:
        logger.error("Failed to dispatch fetch_wordstat_frequency: {}", exc)
        return HTMLResponse(
            '<div class="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">'
            "Не удалось запустить загрузку частотности."
            "</div>"
        )

    return HTMLResponse(
        f'<div id="wordstat-status" class="flex items-center gap-2 p-3 bg-blue-50 '
        f'border border-blue-100 rounded text-sm text-blue-700" '
        f'hx-get="/ui/keyword-suggest/{job.id}/wordstat-status" '
        f'hx-trigger="load delay:3s" hx-swap="outerHTML">'
        f'<svg class="animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" '
        f'viewBox="0 0 24 24" style="width:1rem;height:1rem;">'
        f'<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" '
        f'class="opacity-25"></circle>'
        f'<path fill="currentColor" class="opacity-75" '
        f'd="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>'
        f"Загружаем частотность..."
        f"</div>"
    )


# ---------------------------------------------------------------------------
# 6. GET /{job_id}/wordstat-status -- Wordstat polling endpoint
# ---------------------------------------------------------------------------


@router.get("/{job_id}/wordstat-status", response_class=HTMLResponse)
async def wordstat_status(
    request: Request,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Poll Wordstat enrichment progress by inspecting cached suggestions."""
    result = await db.execute(select(SuggestJob).where(SuggestJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Suggest job not found")

    cached = await _read_cache(job.cache_key) if job.cache_key else None

    has_frequency = bool(
        cached
        and isinstance(cached, list)
        and len(cached) > 0
        and isinstance(cached[0], dict)
        and "frequency" in cached[0]
    )

    if has_frequency:
        return HTMLResponse(
            '<div id="wordstat-status" class="p-3 bg-green-50 border border-green-200 '
            'rounded text-sm text-green-700">Частотность загружена</div>'
        )

    return HTMLResponse(
        f'<div id="wordstat-status" class="flex items-center gap-2 p-3 bg-blue-50 '
        f'border border-blue-100 rounded text-sm text-blue-700" '
        f'hx-get="/ui/keyword-suggest/{job.id}/wordstat-status" '
        f'hx-trigger="load delay:3s" hx-swap="outerHTML">'
        f'<svg class="animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" '
        f'viewBox="0 0 24 24" style="width:1rem;height:1rem;">'
        f'<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" '
        f'class="opacity-25"></circle>'
        f'<path fill="currentColor" class="opacity-75" '
        f'd="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>'
        f"Загружаем частотность..."
        f"</div>"
    )
