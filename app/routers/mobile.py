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
from loguru import logger
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


# ---------------------------------------------------------------------------
# Positions endpoints (/m/positions)
# ---------------------------------------------------------------------------


@router.get("/positions", response_class=HTMLResponse)
async def mobile_positions(
    request: Request,
    site_id: uuid.UUID | None = None,
    period: str = "all",
    tab: str = "all",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Positions page — keyword cards with position, delta, engine, date."""
    import redis as redis_lib
    from app.services.mobile_positions_service import get_mobile_positions

    sites = await get_sites(db)

    # Default to first site if none selected
    if site_id is None and sites:
        site_id = sites[0].id

    # Map period string to period_days int
    period_map = {"7d": 7, "30d": 30, "all": None}
    period_days = period_map.get(period)

    dropped_only = tab == "dropped"

    positions: list[dict] = []
    if site_id:
        positions = await get_mobile_positions(
            db, site_id, period_days=period_days, dropped_only=dropped_only
        )

    # Check for active position check task in Redis
    active_task_id = None
    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        active_task_id = r.get(f"position_check:{site_id}")
    except Exception:
        pass

    context = {
        "request": request,
        "user": user,
        "sites": sites,
        "selected_site_id": site_id,
        "positions": positions,
        "period": period,
        "tab": tab,
        "active_task_id": active_task_id,
        "show_task_btn": tab == "dropped",
        "site_id": site_id,
        "status": "started" if active_task_id else None,
        "task_id": active_task_id,
        "checked": 0,
        "total": 0,
    }

    # HTMX partial refresh — return only the positions list content
    if request.headers.get("HX-Request"):
        # Render the list portion only
        list_html = _render_positions_list(positions, tab, site_id, request)
        return HTMLResponse(content=list_html)

    return mobile_templates.TemplateResponse("mobile/positions.html", context)


def _render_positions_list(
    positions: list[dict],
    tab: str,
    site_id: uuid.UUID | None,
    request: Request,
) -> str:
    """Render the positions list fragment as plain HTML string."""
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader("app/templates"))

    card_tmpl = env.get_template("mobile/partials/position_card.html")
    show_task_btn = tab == "dropped"

    if not positions:
        if tab == "dropped":
            return (
                '<div class="bg-white rounded-lg p-6 text-center mt-4">'
                '<p class="text-sm font-semibold text-gray-700 mb-1">Просевших позиций нет</p>'
                '<p class="text-xs text-gray-500">За выбранный период все позиции стабильны или выросли.</p>'
                "</div>"
            )
        else:
            return (
                '<div class="bg-white rounded-lg p-6 text-center mt-4">'
                '<p class="text-sm font-semibold text-gray-700 mb-1">Нет данных о позициях. Запустите первую проверку.</p>'
                "</div>"
            )

    cards = "".join(
        card_tmpl.render(kw=kw, show_task_btn=show_task_btn, site_id=site_id)
        for kw in positions
    )
    return f'<div class="bg-white rounded-lg divide-y divide-gray-100">{cards}</div>'


@router.post("/positions/check", status_code=202, response_class=HTMLResponse)
async def mobile_trigger_position_check(
    request: Request,
    site_id: uuid.UUID = Form(...),
    user: User = Depends(get_current_user),
):
    """Trigger position check Celery task, store task_id in Redis, return progress partial."""
    import redis as redis_lib
    from app.tasks.position_tasks import check_positions

    task = check_positions.delay(str(site_id))

    # Store task ID in Redis with 10 minute TTL
    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        r.setex(f"position_check:{site_id}", 600, task.id)
    except Exception:
        pass

    return mobile_templates.TemplateResponse(
        "mobile/partials/position_progress.html",
        {
            "request": request,
            "site_id": site_id,
            "task_id": task.id,
            "status": "started",
            "checked": 0,
            "total": 0,
            "positions_written": 0,
        },
        status_code=202,
    )


@router.get("/positions/check/status", response_class=HTMLResponse)
async def mobile_position_check_status(
    request: Request,
    site_id: uuid.UUID,
    task_id: str,
    user: User = Depends(get_current_user),
):
    """HTMX polling endpoint — returns current progress or done state."""
    from app.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)

    if result.state == "PROGRESS":
        checked = result.info.get("checked", 0) if result.info else 0
        total = result.info.get("total", 0) if result.info else 0
        status = "running"
        positions_written = 0
    elif result.ready() and result.successful():
        checked = 0
        total = 0
        positions_written = result.result.get("positions_written", 0) if result.result else 0
        status = "done"
    elif result.failed():
        checked = 0
        total = 0
        positions_written = 0
        status = "error"
    else:
        # PENDING or STARTED
        checked = 0
        total = 0
        positions_written = 0
        status = "running"

    return mobile_templates.TemplateResponse(
        "mobile/partials/position_progress.html",
        {
            "request": request,
            "site_id": site_id,
            "task_id": task_id,
            "status": status,
            "checked": checked,
            "total": total,
            "positions_written": positions_written,
        },
    )


@router.get("/positions/{site_id}/task-form", response_class=HTMLResponse)
async def mobile_positions_task_form(
    site_id: uuid.UUID,
    request: Request,
    prefilled_title: str = "",
    user: User = Depends(get_current_user),
):
    """Return inline task creation form fragment for positions page (HTMX partial)."""
    return mobile_templates.TemplateResponse(
        "mobile/partials/task_form.html",
        {
            "request": request,
            "site_id": site_id,
            "prefilled_title": prefilled_title,
            "post_url": f"/m/positions/{site_id}/tasks",
        },
    )


@router.post("/positions/{site_id}/tasks", response_class=HTMLResponse)
async def mobile_positions_create_task(
    site_id: uuid.UUID,
    request: Request,
    title: str = Form(...),
    priority: str = Form("p3"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a manual SEO task from the positions page. Returns empty 201."""
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


# ---------------------------------------------------------------------------
# Traffic endpoints (/m/traffic)
# ---------------------------------------------------------------------------


@router.get("/traffic", response_class=HTMLResponse)
async def mobile_traffic(
    request: Request,
    site_id: uuid.UUID | None = None,
    period: str = "30d_vs_30d",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Traffic comparison page — Metrika per-page delta between two periods."""
    from app.models.site import Site
    from app.services.mobile_traffic_service import PERIOD_PRESETS, get_traffic_comparison

    sites = await get_sites(db)

    # Default to first site if none selected
    if site_id is None and sites:
        site_id = sites[0].id

    no_metrika = False
    metrika_error = False
    comparison = None

    if site_id:
        result = await db.get(Site, site_id)
        site = result
        if site and (not site.metrika_token or not site.metrika_counter_id):
            no_metrika = True
        elif site:
            try:
                comparison = await get_traffic_comparison(
                    db, site_id, site.metrika_counter_id, site.metrika_token, preset=period
                )
            except Exception as exc:
                logger.error("Traffic comparison failed for site {}: {}", site_id, exc)
                metrika_error = True

    context = {
        "request": request,
        "user": user,
        "sites": sites,
        "selected_site_id": site_id,
        "comparison": comparison,
        "period": period,
        "presets": PERIOD_PRESETS,
        "no_metrika": no_metrika,
        "metrika_error": metrika_error,
    }

    # HTMX partial refresh — return only #traffic-content
    if request.headers.get("HX-Request"):
        return mobile_templates.TemplateResponse(
            "mobile/partials/traffic_content.html",
            context,
        )

    return mobile_templates.TemplateResponse("mobile/traffic.html", context)


@router.get("/traffic/{site_id}/task-form", response_class=HTMLResponse)
async def mobile_traffic_task_form(
    site_id: uuid.UUID,
    request: Request,
    prefilled_title: str = "",
    user: User = Depends(get_current_user),
):
    """Return inline task creation form fragment for traffic page (HTMX partial)."""
    return mobile_templates.TemplateResponse(
        "mobile/partials/task_form.html",
        {
            "request": request,
            "site_id": site_id,
            "prefilled_title": prefilled_title,
            "post_url": f"/m/traffic/{site_id}/tasks",
        },
    )


@router.post("/traffic/{site_id}/tasks", response_class=HTMLResponse)
async def mobile_traffic_create_task(
    site_id: uuid.UUID,
    request: Request,
    title: str = Form(...),
    priority: str = Form("p3"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a manual SEO task from the traffic page. Returns empty 201."""
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
