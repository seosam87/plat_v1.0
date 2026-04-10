"""Mobile router: /m/ — touch-friendly mobile web app.

All endpoints use plain Jinja2Templates (NOT the nav-aware `templates` from
template_engine.py) so no sidebar injection occurs on mobile pages.

Auth: every endpoint uses Depends(get_current_user) explicitly.
UIAuthMiddleware in main.py also redirects unauthenticated /m/ requests to login.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.dependencies import get_db
from app.models.user import User
from app.services.site_service import get_sites

router = APIRouter(prefix="/m", tags=["mobile"])

# Plain Jinja2Templates — does NOT inject sidebar, breadcrumbs, or nav context.
mobile_templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def mobile_index(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mobile homepage — digest view with site selector."""
    sites = await get_sites(db)
    return mobile_templates.TemplateResponse(
        "mobile/index.html",
        {
            "request": request,
            "user": user,
            "sites": sites,
            "active_tab": "digest",
        },
    )
