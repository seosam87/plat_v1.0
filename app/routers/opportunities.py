"""Growth Opportunities router — gap keywords, lost positions, cannibalization, visibility trend."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.site import Site
from app.models.user import User
from app.services.opportunities_service import (
    get_cannibalization,
    get_gap_summary,
    get_lost_positions,
    get_visibility_trend,
)
from app.template_engine import templates

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("/{site_id}/opportunities", response_class=HTMLResponse)
async def opportunities_page(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """Growth Opportunities dashboard — default tab is Gaps."""
    site = await _get_site_or_404(db, site_id)
    gaps_data = await get_gap_summary(db, site_id)
    return templates.TemplateResponse(
        request,
        "analytics/opportunities.html",
        {
            "site": site,
            "active_tab": "gaps",
            "data": gaps_data,
        },
    )


@router.get("/{site_id}/opportunities/tabs/gaps", response_class=HTMLResponse)
async def opportunities_gaps(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX partial — Gap keywords tab."""
    site = await _get_site_or_404(db, site_id)
    data = await get_gap_summary(db, site_id)
    return templates.TemplateResponse(
        request,
        "analytics/partials/opportunities_gaps.html",
        {"site": site, "data": data},
    )


@router.get("/{site_id}/opportunities/tabs/losses", response_class=HTMLResponse)
async def opportunities_losses(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX partial — Lost positions tab."""
    site = await _get_site_or_404(db, site_id)
    data = await get_lost_positions(db, site_id)
    return templates.TemplateResponse(
        request,
        "analytics/partials/opportunities_losses.html",
        {"site": site, "data": data},
    )


@router.get("/{site_id}/opportunities/tabs/cannibal", response_class=HTMLResponse)
async def opportunities_cannibal(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX partial — Cannibalization tab."""
    site = await _get_site_or_404(db, site_id)
    data = await get_cannibalization(db, site_id)
    return templates.TemplateResponse(
        request,
        "analytics/partials/opportunities_cannibal.html",
        {"site": site, "data": data},
    )


@router.get("/{site_id}/opportunities/tabs/trend", response_class=HTMLResponse)
async def opportunities_trend(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX partial — Visibility trend tab."""
    site = await _get_site_or_404(db, site_id)
    trend = await get_visibility_trend(db, site_id)
    return templates.TemplateResponse(
        request,
        "analytics/partials/opportunities_trend.html",
        {"site": site, "trend": trend},
    )
