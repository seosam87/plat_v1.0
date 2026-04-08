"""LLM brief enhancement router (Phase 16 LLM-04).

Endpoints:
- POST /briefs/{brief_id}/llm-enhance       -- dispatch LLM enhancement job (HTMX)
- GET  /briefs/llm-jobs/{job_id}             -- poll job status (HTMX)
- POST /briefs/llm-jobs/{job_id}/accept      -- accept LLM output (HTMX, marks job accepted)

LLM-03 invariant: ContentBrief rows are NEVER mutated. AI output lives only in
LLMBriefJob.output_json and is optionally shown as a UI overlay.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.dependencies import get_db
from app.models.analytics import ContentBrief
from app.models.llm_brief_job import LLMBriefJob
from app.models.user import User
from app.template_engine import templates

router = APIRouter(prefix="/briefs", tags=["llm-briefs"])


async def _get_redis():
    """Return a connected async Redis client."""
    import redis.asyncio as aioredis
    from app.config import settings
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


# ---------------------------------------------------------------------------
# POST /briefs/{brief_id}/llm-enhance — dispatch LLM job
# ---------------------------------------------------------------------------


@router.post("/{brief_id}/llm-enhance", response_class=HTMLResponse)
async def enhance_brief(
    request: Request,
    brief_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Dispatch an LLM enhancement job for the given brief.

    Returns an HTMX partial that immediately starts polling the job status.
    All error paths return friendly HTML — never 500.
    """
    # 1. Load brief + verify ownership/existence
    result = await db.execute(select(ContentBrief).where(ContentBrief.id == brief_id))
    brief = result.scalar_one_or_none()
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")

    # 2. Check if user has an Anthropic key
    if not current_user.has_anthropic_key:
        return HTMLResponse(
            '<div class="p-3 bg-amber-50 border border-amber-200 rounded text-sm text-amber-700">'
            'Настройте Anthropic API key в <a href="/profile/" class="underline font-medium">Профиле</a>, '
            "чтобы использовать AI-улучшение брифа."
            "</div>",
            status_code=400,
        )

    # 3. Check circuit breaker
    redis = await _get_redis()
    try:
        from app.services.llm.llm_service import is_circuit_open
        if await is_circuit_open(redis, current_user.id):
            return HTMLResponse(
                '<div class="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">'
                "LLM временно недоступен (3 ошибки подряд). Попробуйте через 15 минут."
                "</div>",
                status_code=429,
            )
    finally:
        await redis.aclose()

    # 4. Create LLMBriefJob row
    job = LLMBriefJob(
        user_id=current_user.id,
        brief_id=brief_id,
        status="pending",
    )
    db.add(job)
    await db.flush()
    await db.commit()

    # 5. Dispatch Celery task
    try:
        from app.tasks.llm_tasks import generate_llm_brief_enhancement
        generate_llm_brief_enhancement.delay(job.id)
        logger.info("Dispatched LLM enhancement job {} for brief {}", job.id, brief_id)
    except Exception as exc:
        logger.error("Failed to dispatch LLM task for job {}: {}", job.id, exc)
        job.status = "failed"
        job.error_message = f"Не удалось запустить задачу: {exc}"
        await db.commit()
        return HTMLResponse(
            f'<div class="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">'
            f"Ошибка запуска задачи: {exc}"
            f"</div>"
        )

    # 6. Return HTMX polling partial
    return HTMLResponse(
        f'<div id="llm-job-{job.id}" '
        f'hx-get="/briefs/llm-jobs/{job.id}" '
        f'hx-trigger="load, every 2s" '
        f'hx-swap="outerHTML" '
        f'class="flex items-center gap-2 p-3 bg-blue-50 border border-blue-100 rounded text-sm text-blue-700">'
        f'<svg class="animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" '
        f'viewBox="0 0 24 24" style="width:1rem;height:1rem;">'
        f'<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25"></circle>'
        f'<path fill="currentColor" class="opacity-75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>'
        f"</svg>"
        f"генерация…"
        f"</div>"
    )


# ---------------------------------------------------------------------------
# GET /briefs/llm-jobs/{job_id} — poll job status
# ---------------------------------------------------------------------------


@router.get("/llm-jobs/{job_id}", response_class=HTMLResponse)
async def poll_job(
    request: Request,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """HTMX polling endpoint for LLM brief job status.

    - pending/running: returns self-polling spinner with elapsed time
    - done: returns preview with 3 sections + Accept + Regenerate buttons (stops polling)
    - failed: returns error message + Regenerate button (stops polling)
    """
    job = await db.get(LLMBriefJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="LLM job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Calculate elapsed seconds
    now = datetime.now(timezone.utc)
    created = job.created_at
    if created.tzinfo is None:
        from datetime import timezone as _tz
        created = created.replace(tzinfo=_tz.utc)
    elapsed = int((now - created).total_seconds())

    # Pending / running — keep polling
    if job.status in ("pending", "running"):
        return HTMLResponse(
            f'<div id="llm-job-{job.id}" '
            f'hx-get="/briefs/llm-jobs/{job.id}" '
            f'hx-trigger="every 2s" '
            f'hx-swap="outerHTML" '
            f'class="flex items-center gap-2 p-3 bg-blue-50 border border-blue-100 rounded text-sm text-blue-700">'
            f'<svg class="animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" '
            f'viewBox="0 0 24 24" style="width:1rem;height:1rem;">'
            f'<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25"></circle>'
            f'<path fill="currentColor" class="opacity-75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>'
            f"</svg>"
            f"генерация… ({elapsed}s)"
            f"</div>"
        )

    # Failed — show error + Regenerate (no polling)
    if job.status == "failed":
        err_msg = job.error_message or "Неизвестная ошибка"
        return HTMLResponse(
            f'<div id="llm-job-{job.id}" class="p-3 bg-red-50 border border-red-200 rounded text-sm">'
            f'<div class="text-red-700 font-medium mb-2">Ошибка генерации</div>'
            f'<div class="text-red-600 text-xs mb-3 font-mono">{err_msg}</div>'
            f'<button hx-post="/briefs/{job.brief_id}/llm-enhance" '
            f'hx-target="#ai-brief-result" hx-swap="innerHTML" '
            f'class="px-3 py-1.5 text-xs font-medium rounded bg-gray-200 text-gray-700 hover:bg-gray-300">'
            f"Повторить"
            f"</button>"
            f"</div>"
        )

    # Done — render preview (no polling)
    output = job.output_json or {}
    expanded_sections = output.get("expanded_sections", [])
    faq_block = output.get("faq_block", [])
    title_variants = output.get("title_variants", [])
    meta_variants = output.get("meta_variants", [])

    return templates.TemplateResponse(
        request,
        "analytics/_llm_job_preview.html",
        {
            "job": job,
            "expanded_sections": expanded_sections,
            "faq_block": faq_block,
            "title_variants": title_variants,
            "meta_variants": meta_variants,
            "brief_id": job.brief_id,
        },
    )


# ---------------------------------------------------------------------------
# POST /briefs/llm-jobs/{job_id}/accept — accept LLM output
# ---------------------------------------------------------------------------


@router.post("/llm-jobs/{job_id}/accept", response_class=HTMLResponse)
async def accept_job(
    request: Request,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Accept LLM job output — marks job as 'accepted' and returns merged HTML.

    LLM-03 invariant: ContentBrief row is NOT mutated. The merge is a UI overlay only.
    Marking job.status='accepted' enables brief_detail.html to auto-show the accepted
    output on reload (query for latest accepted job by brief_id).
    """
    job = await db.get(LLMBriefJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="LLM job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if job.status not in ("done", "accepted"):
        raise HTTPException(status_code=400, detail="Job is not done yet")

    # Mark as accepted (so brief detail page can show it on reload)
    job.status = "accepted"
    await db.commit()

    output = job.output_json or {}
    expanded_sections = output.get("expanded_sections", [])
    faq_block = output.get("faq_block", [])
    title_variants = output.get("title_variants", [])
    meta_variants = output.get("meta_variants", [])

    return templates.TemplateResponse(
        request,
        "analytics/_llm_job_accepted.html",
        {
            "job": job,
            "expanded_sections": expanded_sections,
            "faq_block": faq_block,
            "title_variants": title_variants,
            "meta_variants": meta_variants,
        },
    )
