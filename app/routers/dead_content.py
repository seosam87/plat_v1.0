"""Dead Content router — pages with zero traffic or position drops > 10."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.site import Site
from app.models.user import User
from app.services.dead_content_service import (
    create_dead_content_tasks,
    get_dead_content,
    update_recommendation,
)
from app.template_engine import templates

router = APIRouter(prefix="/analytics", tags=["dead-content"])


class CreateTasksRequest(BaseModel):
    page_ids: list[str]


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


# ---------------------------------------------------------------------------
# Dead Content page
# ---------------------------------------------------------------------------


@router.get("/{site_id}/dead-content", response_class=HTMLResponse)
async def dead_content_page(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    """Render the Dead Content page with zero-traffic and position-drop pages."""
    site = await _get_site_or_404(db, site_id)
    data = await get_dead_content(db, site_id)
    return templates.TemplateResponse(
        "analytics/dead_content.html",
        {
            "request": request,
            "site": site,
            "pages": data["pages"],
            "stats": data["stats"],
        },
    )


# ---------------------------------------------------------------------------
# HTMX: update recommendation override
# ---------------------------------------------------------------------------


@router.post("/{site_id}/dead-content/{page_id}/recommendation", response_class=HTMLResponse)
async def update_page_recommendation(
    request: Request,
    site_id: uuid.UUID,
    page_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    """Store a user-selected recommendation override for a dead content page.

    Expects a form field: recommendation (merge|redirect|rewrite|delete).
    Returns HX-Trigger toast on success.
    """
    form = await request.form()
    recommendation = form.get("recommendation", "")

    valid = {"merge", "redirect", "rewrite", "delete"}
    if recommendation not in valid:
        raise HTTPException(status_code=422, detail=f"Invalid recommendation: {recommendation}")

    # page_id here is a string URL-encoded page ID; we need the page URL.
    # Get it from the form — the template sends page_url as a hidden field.
    page_url = form.get("page_url", "")
    if not page_url:
        raise HTTPException(status_code=422, detail="page_url is required")

    await update_recommendation(db, site_id, page_url, recommendation)

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Trigger"] = (
        '{"showToast": {"message": "Рекомендация обновлена", "type": "success"}}'
    )
    return response


# ---------------------------------------------------------------------------
# HTMX: create SEO tasks for selected dead content pages
# ---------------------------------------------------------------------------


@router.post("/{site_id}/dead-content/create-tasks", response_class=HTMLResponse)
async def create_tasks_for_dead_content(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    """Create SEO tasks for the selected dead content pages.

    Expects JSON body: {"page_ids": ["uuid1", "uuid2", ...]}.
    Returns HX-Trigger toast with count of created tasks.
    """
    body = await request.json()
    raw_ids: list[str] = body.get("page_ids", [])
    page_ids: list[uuid.UUID] = []
    for raw in raw_ids:
        try:
            page_ids.append(uuid.UUID(raw))
        except ValueError:
            pass

    count = await create_dead_content_tasks(db, site_id, page_ids)

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Trigger"] = (
        f'{{"showToast": {{"message": "Задачи созданы: {count} страниц добавлено в очередь", "type": "success"}}}}'
    )
    return response
