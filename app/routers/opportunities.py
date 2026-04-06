"""Growth Opportunities router — gap keywords, lost positions, cannibalization, visibility trend."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.gap import GapKeyword
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


@router.get("/{site_id}/opportunities/detail/gap/{gap_keyword_id}", response_class=HTMLResponse)
async def opportunities_detail_gap(
    request: Request,
    site_id: uuid.UUID,
    gap_keyword_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX partial — Gap keyword slide-over detail."""
    site = await _get_site_or_404(db, site_id)
    result = await db.execute(
        select(GapKeyword).where(
            GapKeyword.id == gap_keyword_id,
            GapKeyword.site_id == site_id,
        )
    )
    gap_kw = result.scalar_one_or_none()
    if not gap_kw:
        raise HTTPException(status_code=404, detail="Gap keyword not found")

    item = {
        "id": str(gap_kw.id),
        "phrase": gap_kw.phrase,
        "competitor_domain": gap_kw.competitor_domain,
        "competitor_position": gap_kw.competitor_position,
        "our_position": gap_kw.our_position,
        "potential_score": gap_kw.potential_score,
        "frequency": gap_kw.frequency,
    }
    return templates.TemplateResponse(
        request,
        "analytics/partials/detail_gap.html",
        {"site": site, "item": item},
    )


@router.get("/{site_id}/opportunities/detail/loss/{keyword_id}", response_class=HTMLResponse)
async def opportunities_detail_loss(
    request: Request,
    site_id: uuid.UUID,
    keyword_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX partial — Lost position slide-over detail."""
    site = await _get_site_or_404(db, site_id)
    result = await db.execute(
        text(
            """
            SELECT klp.keyword_id, k.phrase, klp.url, klp.position, klp.previous_position, klp.delta
            FROM keyword_latest_positions klp
            JOIN keywords k ON k.id = klp.keyword_id
            WHERE klp.keyword_id = :keyword_id AND klp.site_id = :site_id
            ORDER BY klp.delta ASC LIMIT 1
            """
        ),
        {"keyword_id": keyword_id, "site_id": site_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Loss keyword not found")

    item = {
        "keyword_id": str(row[0]),
        "phrase": row[1],
        "url": row[2],
        "position": row[3],
        "previous_position": row[4],
        "delta": row[5],
    }
    return templates.TemplateResponse(
        request,
        "analytics/partials/detail_loss.html",
        {"site": site, "item": item},
    )


@router.get("/{site_id}/opportunities/detail/cannibal/{keyword_id}", response_class=HTMLResponse)
async def opportunities_detail_cannibal(
    request: Request,
    site_id: uuid.UUID,
    keyword_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> HTMLResponse:
    """HTMX partial — Cannibalization slide-over detail."""
    site = await _get_site_or_404(db, site_id)
    result = await db.execute(
        text(
            """
            SELECT klp.keyword_id, k.phrase, klp.url, klp.position
            FROM keyword_latest_positions klp
            JOIN keywords k ON k.id = klp.keyword_id
            WHERE klp.keyword_id = :keyword_id AND klp.site_id = :site_id
              AND klp.position IS NOT NULL AND klp.position <= 50 AND klp.url IS NOT NULL
            ORDER BY klp.position
            """
        ),
        {"keyword_id": keyword_id, "site_id": site_id},
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Cannibalization data not found")

    phrase = rows[0][1]
    pages = []
    seen_urls: set[str] = set()
    for row in rows:
        if row[2] not in seen_urls:
            pages.append({"url": row[2], "position": row[3]})
            seen_urls.add(row[2])

    item = {
        "keyword_id": str(keyword_id),
        "phrase": phrase,
        "pages": pages,
    }
    return templates.TemplateResponse(
        request,
        "analytics/partials/detail_cannibal.html",
        {"site": site, "item": item},
    )
