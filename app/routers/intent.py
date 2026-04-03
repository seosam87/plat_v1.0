"""Intent detection router: batch detect, review proposals, confirm."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.site import Site
from app.models.user import User
from app.services import intent_service

router = APIRouter(prefix="/intent", tags=["intent"])
templates = Jinja2Templates(directory="app/templates")


class DetectRequest(BaseModel):
    keyword_ids: list[str] | None = None


class ConfirmRequest(BaseModel):
    keyword_id: str
    intent: str


class BulkConfirmRequest(BaseModel):
    proposals: list[dict]


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("/{site_id}", response_class=HTMLResponse)
async def intent_page(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> HTMLResponse:
    """Intent detection page."""
    site = await _get_site_or_404(db, site_id)
    unclustered = await intent_service.get_unclustered_keywords(db, site_id)
    return templates.TemplateResponse(
        request,
        "intent/index.html",
        {
            "site_id": str(site_id),
            "site": site,
            "unclustered": unclustered,
            "proposals": [],
        },
    )


@router.post("/{site_id}/detect")
async def detect_intent(
    site_id: uuid.UUID,
    payload: DetectRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Trigger batch intent detection for site keywords."""
    from app.tasks.intent_tasks import batch_detect_intents

    kw_ids = payload.keyword_ids
    task = batch_detect_intents.delay(str(site_id), kw_ids)
    return {"task_id": task.id, "status": "queued"}


@router.get("/{site_id}/proposals")
async def get_proposals(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    """Get intent proposals for unclustered keywords."""
    unclustered = await intent_service.get_unclustered_keywords(db, site_id)
    if not unclustered:
        return []
    kw_ids = [uuid.UUID(k["id"]) for k in unclustered]
    proposals = await intent_service.batch_detect_intent(db, site_id, kw_ids, use_cache=True)
    return proposals


@router.post("/{site_id}/confirm")
async def confirm_proposal(
    site_id: uuid.UUID,
    payload: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Confirm a single intent proposal."""
    await intent_service.confirm_intent(db, uuid.UUID(payload.keyword_id), payload.intent)
    await db.commit()
    return {"confirmed": True, "keyword_id": payload.keyword_id, "intent": payload.intent}


@router.post("/{site_id}/bulk-confirm")
async def bulk_confirm(
    site_id: uuid.UUID,
    payload: BulkConfirmRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Confirm all proposals at once."""
    count = await intent_service.bulk_confirm_intents(db, payload.proposals)
    await db.commit()
    return {"confirmed": count}
