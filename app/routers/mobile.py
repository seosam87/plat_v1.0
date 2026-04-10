"""Mobile router: /m/ — touch-friendly mobile web app.

All endpoints use plain Jinja2Templates (NOT the nav-aware `templates` from
template_engine.py) so no sidebar injection occurs on mobile pages.

Auth: every endpoint uses Depends(get_current_user) explicitly.
UIAuthMiddleware in main.py also redirects unauthenticated /m/ requests to login.
Public auth endpoints under /m/auth/ are excluded from UIAuthMiddleware.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token
from app.config import settings
from app.dependencies import get_db
from app.models.user import User
from app.services.site_service import get_sites
from app.services.telegram_auth import validate_telegram_webapp_initdata

router = APIRouter(prefix="/m", tags=["mobile"])

# Plain Jinja2Templates — does NOT inject sidebar, breadcrumbs, or nav context.
mobile_templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Public auth endpoints (excluded from UIAuthMiddleware via /m/auth/ prefix)
# ---------------------------------------------------------------------------


@router.post("/auth/telegram-webapp")
async def auth_telegram_webapp(
    request: Request,
    init_data: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Validate Telegram WebApp initData and issue JWT cookie.

    Called automatically by the JS in base_mobile.html when the page is opened
    inside Telegram WebApp. No authentication required (public endpoint).
    """
    user_data = validate_telegram_webapp_initdata(
        init_data, settings.TELEGRAM_BOT_TOKEN
    )
    if not user_data:
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Ошибка авторизации. Откройте приложение заново через Telegram."
            },
        )

    telegram_id = user_data.get("id")
    if not telegram_id:
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Ошибка авторизации. Откройте приложение заново через Telegram."
            },
        )

    result = await db.execute(
        select(User).where(User.telegram_id == int(telegram_id))
    )
    user = result.scalar_one_or_none()

    if not user:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Аккаунт не найден. Привяжите Telegram в настройках профиля."
            },
        )

    token = create_access_token(str(user.id), user.role.value)
    response = JSONResponse(content={"ok": True})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


@router.get("/auth/link-required")
async def auth_link_required(request: Request):
    """Instruction page for users who opened Mini App without linking Telegram."""
    return mobile_templates.TemplateResponse(
        "mobile/tg_link_required.html",
        {"request": request},
    )


# ---------------------------------------------------------------------------
# Protected endpoints (require authentication)
# ---------------------------------------------------------------------------


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
