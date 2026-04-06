"""Quick Wins router: pages ranked 4-20 by opportunity score with batch fix dispatch."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.site import Site
from app.models.user import User
from app.services.quick_wins_service import dispatch_batch_fix, get_quick_wins
from app.template_engine import templates

router = APIRouter(prefix="/analytics", tags=["quick-wins"])


class BatchFixRequest(BaseModel):
    page_ids: list[str]
    fix_types: list[str]


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("/{site_id}/quick-wins", response_class=HTMLResponse)
async def quick_wins_page(
    request: Request,
    site_id: uuid.UUID,
    issue_type: str | None = None,
    content_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """Quick Wins page — shows pages ranked 4-20 by opportunity score."""
    site = await _get_site_or_404(db, site_id)
    pages = await get_quick_wins(db, site_id, issue_type=issue_type, content_type=content_type)

    return templates.TemplateResponse(
        request,
        "analytics/quick_wins.html",
        {
            "site": site,
            "pages": pages,
            "issue_type": issue_type or "",
            "content_type": content_type or "",
        },
    )


@router.get("/{site_id}/quick-wins/table", response_class=HTMLResponse)
async def quick_wins_table(
    request: Request,
    site_id: uuid.UUID,
    issue_type: str | None = None,
    content_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX partial — returns just the table body for filter updates."""
    site = await _get_site_or_404(db, site_id)
    pages = await get_quick_wins(db, site_id, issue_type=issue_type, content_type=content_type)

    return templates.TemplateResponse(
        request,
        "analytics/partials/quick_wins_table.html",
        {
            "site": site,
            "pages": pages,
            "issue_type": issue_type or "",
            "content_type": content_type or "",
        },
    )


@router.post("/{site_id}/quick-wins/batch-fix")
async def batch_fix(
    request: Request,
    site_id: uuid.UUID,
    body: BatchFixRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> JSONResponse:
    """Dispatch batch fix for selected pages. Returns JSON with dispatched count."""
    await _get_site_or_404(db, site_id)

    try:
        page_ids = [uuid.UUID(pid) for pid in body.page_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid page_id format")

    result = await dispatch_batch_fix(
        db,
        site_id=site_id,
        page_ids=page_ids,
        fix_types=body.fix_types,
    )

    n = result.get("dispatched", 0)
    response = JSONResponse(content=result)
    response.headers["HX-Trigger"] = (
        f'{{"showToast": {{"message": "Фикс запущен для {n} страниц", "type": "info"}}}}'
    )
    return response


@router.get("/{site_id}/fix-status/{task_id}", response_class=HTMLResponse)
async def fix_status(
    request: Request,
    site_id: uuid.UUID,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX polling endpoint — returns fix_status partial showing spinner or completion."""
    from app.models.wp_content_job import WpContentJob, JobStatus

    # Try to find the job by task_id (treated as wp_content_job id)
    is_complete = False
    try:
        job_id = uuid.UUID(task_id)
        result = await db.execute(
            select(WpContentJob).where(
                WpContentJob.id == job_id,
                WpContentJob.site_id == site_id,
            )
        )
        job = result.scalar_one_or_none()
        if job and job.status not in (JobStatus.pending, JobStatus.processing):
            is_complete = True
    except (ValueError, Exception):
        is_complete = True  # Unknown task_id — stop polling

    return templates.TemplateResponse(
        request,
        "analytics/partials/fix_status.html",
        {"task_id": task_id, "is_complete": is_complete, "site_id": site_id},
    )
