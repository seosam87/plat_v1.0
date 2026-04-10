"""Mobile router: /m/ — touch-friendly mobile web app.

All endpoints use plain Jinja2Templates (NOT the nav-aware `templates` from
template_engine.py) so no sidebar injection occurs on mobile pages.

Auth: every endpoint uses Depends(get_current_user) explicitly.
UIAuthMiddleware in main.py also redirects unauthenticated /m/ requests to login.
Public auth endpoints under /m/auth/ are excluded from UIAuthMiddleware.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
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
    """Mobile homepage — renders the digest view."""
    from app.services.mobile_digest_service import build_mobile_digest

    data = await build_mobile_digest(db)
    return mobile_templates.TemplateResponse(
        "mobile/digest.html",
        {"request": request, "user": user, "active_tab": "digest", **data},
    )


@router.get("/digest")
async def mobile_digest(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Digest page alias — same content as /m/."""
    from app.services.mobile_digest_service import build_mobile_digest

    data = await build_mobile_digest(db)
    return mobile_templates.TemplateResponse(
        "mobile/digest.html",
        {"request": request, "user": user, "active_tab": "digest", **data},
    )


# ---------------------------------------------------------------------------
# Health card endpoints (/m/health/{site_id})
# ---------------------------------------------------------------------------

# Russian short month names for date formatting
_RU_MONTHS = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "май", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}


def _format_health_metrics(health: dict) -> list[dict]:
    """Convert raw health data to display metrics list for health.html template.

    Each metric: {label, value (display string), status (green/yellow/red/grey)}.
    Service returns 'color' key — mapped to 'status' for template consistency.
    """
    # 1. Site status
    raw_status = health["site_status"]["value"]
    if raw_status == "done":
        site_display = "Доступен"
    elif raw_status == "no_data":
        site_display = "Нет данных"
    else:
        site_display = "Недоступен"

    # 2. Crawl errors
    error_count = health["crawl_error_count"]["value"]

    # 3. Last crawl
    last_crawl_raw = health["last_crawl"]["value"]
    if last_crawl_raw and last_crawl_raw.get("finished_at"):
        dt = last_crawl_raw["finished_at"]
        last_crawl_display = f"{dt.day} {_RU_MONTHS[dt.month]} — {last_crawl_raw['status']}"
    else:
        last_crawl_display = "Нет данных"

    # 4. Position changes
    pos_count = health["position_changes_count"]["value"]
    pos_display = f"{pos_count} резких" if pos_count > 0 else "0"

    # 5. Overdue tasks
    overdue_count = health["overdue_task_count"]["value"]

    # 6. Indexation
    idx_raw = health["indexation_status"]["value"]
    idx_display = "Подключено" if idx_raw == "connected" else "Нет данных"

    return [
        {"label": "Доступность сайта", "value": site_display, "status": health["site_status"]["color"]},
        {"label": "Ошибки краулера", "value": str(error_count), "status": health["crawl_error_count"]["color"]},
        {"label": "Последний краулинг", "value": last_crawl_display, "status": health["last_crawl"]["color"]},
        {"label": "Изменения позиций (7 дн.)", "value": pos_display, "status": health["position_changes_count"]["color"]},
        {"label": "Просроченные задачи", "value": str(overdue_count), "status": health["overdue_task_count"]["color"]},
        {"label": "Статус индексации", "value": idx_display, "status": health["indexation_status"]["color"]},
    ]


@router.get("/health/{site_id}")
async def mobile_health(
    site_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Health card page — 6 operational metrics for a single site."""
    from app.models.site import Site
    from app.services.mobile_digest_service import get_mobile_site_health

    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Сайт не найден")

    health = await get_mobile_site_health(db, site_id)
    metrics = _format_health_metrics(health)

    return mobile_templates.TemplateResponse(
        "mobile/health.html",
        {"request": request, "user": user, "site": site, "metrics": metrics, "active_tab": "sites"},
    )


@router.post("/health/{site_id}/crawl", status_code=202)
async def mobile_trigger_crawl(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger a crawl for the site. Returns 202 Accepted."""
    from app.models.site import Site
    from app.tasks.crawl_tasks import crawl_site as crawl_site_task

    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Сайт не найден")

    crawl_site_task.delay(str(site_id))
    return Response(status_code=202)


@router.get("/health/{site_id}/task-form", response_class=HTMLResponse)
async def mobile_task_form(
    site_id: uuid.UUID,
    request: Request,
    url: str = "",
    user: User = Depends(get_current_user),
):
    """Return inline task creation form fragment (HTMX partial)."""
    prefilled_title = f"Ошибка: {url}" if url else ""
    return mobile_templates.TemplateResponse(
        "mobile/partials/task_form.html",
        {"request": request, "site_id": site_id, "prefilled_title": prefilled_title},
    )


@router.post("/health/{site_id}/tasks", response_class=HTMLResponse)
async def mobile_create_task(
    site_id: uuid.UUID,
    request: Request,
    title: str = Form(...),
    priority: str = Form("p3"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a manual SEO task for the site. Returns empty 201."""
    from app.models.task import SeoTask, TaskPriority, TaskType

    task = SeoTask(
        site_id=site_id,
        task_type=TaskType.manual,
        url="",
        title=title,
        priority=TaskPriority(priority),
    )
    db.add(task)
    await db.flush()
    await db.commit()
    return HTMLResponse(content="", status_code=201)
