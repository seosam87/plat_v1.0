"""Intake router: site audit intake form, section saves, checklist refresh."""
from __future__ import annotations

import json as _json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_manager_or_above
from app.dependencies import get_db
from app.models.client import Client
from app.models.oauth_token import OAuthToken
from app.models.site import Site
from app.models.user import User
from app.services import intake_service
from app.template_engine import templates

router = APIRouter(prefix="/ui/sites", tags=["intake"])


# ---------------------------------------------------------------------------
# GET intake form page
# ---------------------------------------------------------------------------


@router.get("/{site_id}/intake", response_class=HTMLResponse)
async def intake_form(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    # Fetch site
    site_result = await db.execute(select(Site).where(Site.id == site_id))
    site = site_result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")

    # Get or create intake record
    intake = await intake_service.get_or_create_intake(db, site_id=site.id)
    await db.commit()

    # Get verification checklist
    checklist = await intake_service.get_verification_checklist(db, site_id=site.id)

    # Check GSC connection
    gsc_count_result = await db.execute(
        select(func.count()).select_from(OAuthToken).where(
            OAuthToken.site_id == site.id,
            OAuthToken.provider == "gsc",
        )
    )
    gsc_connected = gsc_count_result.scalar_one() > 0

    # Fetch client if site has one
    client = None
    if site.client_id:
        client_result = await db.execute(select(Client).where(Client.id == site.client_id))
        client = client_result.scalar_one_or_none()

    logger.debug("Rendering intake form for site {}", site.id)
    return templates.TemplateResponse(
        request,
        "intake/form.html",
        {
            "site": site,
            "intake": intake,
            "checklist": checklist,
            "gsc_connected": gsc_connected,
            "client": client,
        },
    )


# ---------------------------------------------------------------------------
# POST section save endpoints
# ---------------------------------------------------------------------------


@router.post("/{site_id}/intake/access", response_class=HTMLResponse)
async def save_access(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    await intake_service.save_access_section(db, site_id=uuid.UUID(site_id))
    await db.commit()
    logger.debug("Saved access section for site {}", site_id)
    resp = HTMLResponse("")
    resp.headers["HX-Trigger"] = _json.dumps(
        {"showToast": "Раздел сохранен", "sectionSaved": "access"}
    )
    return resp


@router.post("/{site_id}/intake/goals", response_class=HTMLResponse)
async def save_goals(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    form = await request.form()
    main_goal = form.get("main_goal", "")
    target_regions = form.get("target_regions", "")
    competitors = [v for k, v in form.multi_items() if k == "competitor" and str(v).strip()]
    notes = form.get("notes", "")
    data = {
        "main_goal": main_goal,
        "target_regions": target_regions,
        "competitors": competitors,
        "notes": notes,
    }
    await intake_service.save_goals_section(db, site_id=uuid.UUID(site_id), data=data)
    await db.commit()
    logger.debug("Saved goals section for site {}", site_id)
    resp = HTMLResponse("")
    resp.headers["HX-Trigger"] = _json.dumps(
        {"showToast": "Раздел сохранен", "sectionSaved": "goals"}
    )
    return resp


@router.post("/{site_id}/intake/analytics", response_class=HTMLResponse)
async def save_analytics(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    await intake_service.save_analytics_section(db, site_id=uuid.UUID(site_id))
    await db.commit()
    logger.debug("Saved analytics section for site {}", site_id)
    resp = HTMLResponse("")
    resp.headers["HX-Trigger"] = _json.dumps(
        {"showToast": "Раздел сохранен", "sectionSaved": "analytics"}
    )
    return resp


@router.post("/{site_id}/intake/technical", response_class=HTMLResponse)
async def save_technical(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    form = await request.form()
    robots_notes = form.get("robots_notes", "")
    data = {"robots_notes": robots_notes}
    await intake_service.save_technical_section(db, site_id=uuid.UUID(site_id), data=data)
    await db.commit()
    logger.debug("Saved technical section for site {}", site_id)
    resp = HTMLResponse("")
    resp.headers["HX-Trigger"] = _json.dumps(
        {"showToast": "Раздел сохранен", "sectionSaved": "technical"}
    )
    return resp


@router.post("/{site_id}/intake/checklist", response_class=HTMLResponse)
async def save_checklist(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    await intake_service.save_checklist_section(db, site_id=uuid.UUID(site_id))
    await db.commit()
    logger.debug("Saved checklist section for site {}", site_id)
    resp = HTMLResponse("")
    resp.headers["HX-Trigger"] = _json.dumps(
        {"showToast": "Раздел сохранен", "sectionSaved": "checklist"}
    )
    return resp


# ---------------------------------------------------------------------------
# GET checklist refresh (HTMX partial)
# ---------------------------------------------------------------------------


@router.get("/{site_id}/intake/checklist", response_class=HTMLResponse)
async def refresh_checklist(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    checklist = await intake_service.get_verification_checklist(db, site_id=site_id)
    logger.debug("Refreshed checklist for site {}", site_id)
    resp = templates.TemplateResponse(
        request,
        "intake/_tab_checklist.html",
        {"checklist": checklist},
    )
    resp.headers["HX-Trigger"] = _json.dumps({"showToast": "Статусы обновлены"})
    return resp


# ---------------------------------------------------------------------------
# POST complete intake
# ---------------------------------------------------------------------------


@router.post("/{site_id}/intake/complete", response_class=HTMLResponse)
async def complete_intake(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    await intake_service.complete_intake(db, site_id=uuid.UUID(site_id))
    await db.commit()
    logger.info("Intake completed for site {}", site_id)
    resp = HTMLResponse("")
    resp.headers["HX-Trigger"] = _json.dumps(
        {"showToast": "Intake завершен", "intakeCompleted": True}
    )
    return resp
