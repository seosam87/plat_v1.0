"""QA Surface Tracker — admin UI for managing feature coverage across surfaces.

Routes are under /ui/qa/ prefix. All endpoints require authentication.
Per D-05: discover_routes() called at request time ONLY (never at import time)
to avoid circular import with app.main.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.dependencies import get_db
from app.models.qa_surface import Surface, CheckStatus
from app.services import qa_surface_service as svc
from app.template_engine import templates

router = APIRouter(prefix="/ui/qa", tags=["qa"])

STATUS_COLORS = {
    "not_tested":   {"bg": "#f3f4f6", "text": "#6b7280"},
    "passed":       {"bg": "#d1fae5", "text": "#065f46"},
    "failed":       {"bg": "#fee2e2", "text": "#991b1b"},
    "needs_retest": {"bg": "#fef3c7", "text": "#92400e"},
}


# ---------------------------------------------------------------------------
# GET /ui/qa/ — Matrix view
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def qa_matrix(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Render the QA surface matrix: features as rows, surfaces as columns."""
    features = await svc.list_features_with_checks(db)
    return templates.TemplateResponse(request, "qa/index.html", {
        "features": features,
        "surfaces": list(Surface),
        "status_colors": STATUS_COLORS,
        "CheckStatus": CheckStatus,
    })


# ---------------------------------------------------------------------------
# GET /ui/qa/features/new — Create feature form
# ---------------------------------------------------------------------------

@router.get("/features/new", response_class=HTMLResponse)
async def new_feature_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Render the create-feature form."""
    return templates.TemplateResponse(request, "qa/feature_form.html", {
        "feature": None,
        "mode": "create",
    })


# ---------------------------------------------------------------------------
# POST /ui/qa/features — Create feature
# ---------------------------------------------------------------------------

@router.post("/features", response_class=HTMLResponse)
async def create_feature(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    retest_days: int = Form(30),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> RedirectResponse:
    """Create a new FeatureSurface and redirect to matrix."""
    await svc.create_feature_surface(db, slug, name, description or None, retest_days)
    return RedirectResponse("/ui/qa/", status_code=303)


# ---------------------------------------------------------------------------
# GET /ui/qa/features/{feature_surface_id} — Edit feature form
# ---------------------------------------------------------------------------

@router.get("/features/{feature_surface_id}", response_class=HTMLResponse)
async def edit_feature_form(
    request: Request,
    feature_surface_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Render the edit-feature form."""
    feature = await svc.get_feature_by_id(db, feature_surface_id)
    return templates.TemplateResponse(request, "qa/feature_form.html", {
        "feature": feature,
        "mode": "edit",
    })


# ---------------------------------------------------------------------------
# POST /ui/qa/features/{feature_surface_id} — Update feature
# ---------------------------------------------------------------------------

@router.post("/features/{feature_surface_id}", response_class=HTMLResponse)
async def update_feature(
    request: Request,
    feature_surface_id: uuid.UUID,
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    retest_days: int = Form(30),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> RedirectResponse:
    """Update a FeatureSurface and redirect to matrix."""
    await svc.update_feature_surface(db, feature_surface_id, name, slug, description or None, retest_days)
    return RedirectResponse("/ui/qa/", status_code=303)


# ---------------------------------------------------------------------------
# POST /ui/qa/features/{feature_surface_id}/delete — Delete feature
# ---------------------------------------------------------------------------

@router.post("/features/{feature_surface_id}/delete", response_class=HTMLResponse)
async def delete_feature(
    request: Request,
    feature_surface_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> RedirectResponse:
    """Delete a FeatureSurface (cascade deletes checks) and redirect to matrix."""
    await svc.delete_feature_surface(db, feature_surface_id)
    return RedirectResponse("/ui/qa/", status_code=303)


# ---------------------------------------------------------------------------
# GET /ui/qa/checks/{surface_check_id}/edit — HTMX partial: inline check edit
# ---------------------------------------------------------------------------

@router.get("/checks/{surface_check_id}/edit", response_class=HTMLResponse)
async def edit_check_cell(
    request: Request,
    surface_check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Return the edit mode for an inline check cell (HTMX partial)."""
    check = await svc.get_check_by_id(db, surface_check_id)
    return templates.TemplateResponse(request, "qa/_check_cell.html", {
        "check": check,
        "statuses": list(CheckStatus),
        "mode": "edit",
        "status_colors": STATUS_COLORS,
    })


# ---------------------------------------------------------------------------
# POST /ui/qa/checks/{surface_check_id}/mark-tested — Mark check tested
# ---------------------------------------------------------------------------

@router.post("/checks/{surface_check_id}/mark-tested", response_class=HTMLResponse)
async def mark_tested(
    request: Request,
    surface_check_id: uuid.UUID,
    status: str = Form(...),
    notes: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Mark a surface check as tested and return updated cell partial."""
    username = getattr(user, "username", None)
    updated_check = await svc.mark_check_tested(
        db, surface_check_id, CheckStatus(status), notes or None, username
    )
    return templates.TemplateResponse(request, "qa/_check_cell.html", {
        "check": updated_check,
        "mode": "view",
        "status_colors": STATUS_COLORS,
    })


# ---------------------------------------------------------------------------
# GET /ui/qa/checks/{surface_check_id} — HTMX partial: restore view cell
# ---------------------------------------------------------------------------

@router.get("/checks/{surface_check_id}", response_class=HTMLResponse)
async def view_check_cell(
    request: Request,
    surface_check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Return the view mode for an inline check cell (HTMX cancel restore)."""
    check = await svc.get_check_by_id(db, surface_check_id)
    return templates.TemplateResponse(request, "qa/_check_cell.html", {
        "check": check,
        "mode": "view",
        "status_colors": STATUS_COLORS,
    })


# ---------------------------------------------------------------------------
# GET /ui/qa/candidates — Route discovery page
# ---------------------------------------------------------------------------

@router.get("/candidates", response_class=HTMLResponse)
async def candidates_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> HTMLResponse:
    """Discover app routes and present them for grouping into user flows.

    Per D-05 and RESEARCH.md pitfall #1: imports happen inside function body
    to avoid circular import with app.main at module level.
    """
    from app.main import app as _app
    from tests._smoke_helpers import discover_routes
    routes = discover_routes(_app)
    return templates.TemplateResponse(request, "qa/candidates.html", {
        "routes": routes,
        "surfaces": list(Surface),
    })


# ---------------------------------------------------------------------------
# POST /ui/qa/candidates/save — Save selected routes as a new user flow
# ---------------------------------------------------------------------------

@router.post("/candidates/save", response_class=HTMLResponse)
async def save_candidate(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    retest_days: int = Form(30),
    routes: list[str] = Form([]),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> RedirectResponse:
    """Save selected route candidates as a new FeatureSurface user flow."""
    # Combine routes into description context if provided
    combined_description = description or None
    if routes:
        route_list = "\n".join(routes)
        if combined_description:
            combined_description = f"{combined_description}\n\nRoutes:\n{route_list}"
        else:
            combined_description = f"Routes:\n{route_list}"
    await svc.create_feature_surface(db, slug, name, combined_description, retest_days)
    return RedirectResponse("/ui/qa/", status_code=303)
