"""Mobile router: /m/ — touch-friendly mobile web app.

All endpoints use plain Jinja2Templates (NOT the nav-aware `templates` from
template_engine.py) so no sidebar injection occurs on mobile pages.

Auth: every endpoint uses Depends(get_current_user) explicitly.
UIAuthMiddleware in main.py also redirects unauthenticated /m/ requests to login.
Public auth endpoints under /m/auth/ are excluded from UIAuthMiddleware.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from celery import chain as celery_chain
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
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


# ---------------------------------------------------------------------------
# /m/reports — Phase 29 Reports & Tools (REP-01, REP-02)
# ---------------------------------------------------------------------------

@router.get("/reports/new", response_class=HTMLResponse, name="mobile_report_new")
async def mobile_report_new(
    request: Request,
    report_token: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Single-page form for creating a PDF report (D-03).

    If ?report_token=... is present, result block is pre-rendered (server-side
    reveal alternative to HTMX swap — simpler for MVP per D-04).
    """
    from app.services.mobile_reports_service import list_clients_for_reports
    from app.services.project_service import get_accessible_projects

    projects = await get_accessible_projects(db, user)
    clients = await list_clients_for_reports(db)
    ctx = {
        "request": request,
        "active_tab": "more",
        "projects": projects,
        "clients": clients,
        "report_token": report_token,
        "report_type": request.query_params.get("report_type", ""),
        "project_name": request.query_params.get("project_name", ""),
    }
    return mobile_templates.TemplateResponse("mobile/reports/new.html", ctx)


@router.post("/reports/new", response_class=HTMLResponse)
async def mobile_report_create(
    request: Request,
    project_id: uuid.UUID = Form(...),
    report_type: str = Form("brief"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Generate PDF synchronously, store bytes in Redis, return inline result partial."""
    from app.services import report_service
    from app.services.mobile_reports_service import list_clients_for_reports, store_report_pdf

    if report_type not in ("brief", "detailed"):
        raise HTTPException(status_code=422, detail="report_type must be brief|detailed")

    try:
        pdf_bytes = await report_service.generate_pdf_report(db, project_id, report_type)
    except Exception as exc:
        logger.error("mobile report generation failed: {}", exc)
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать отчёт") from exc

    token = await store_report_pdf(pdf_bytes)

    # Load project name for display
    from app.models.project import Project
    proj = await db.get(Project, project_id)
    project_name = proj.name if proj else ""

    clients = await list_clients_for_reports(db)
    return mobile_templates.TemplateResponse(
        "mobile/reports/partials/result_block.html",
        {
            "request": request,
            "report_token": token,
            "report_type": report_type,
            "project_name": project_name,
            "clients": clients,
        },
    )


@router.get("/reports/download/{token}", name="mobile_report_download")
async def mobile_report_download(token: str) -> StreamingResponse:
    """Token-protected PDF download (D-06). No auth — token IS the auth."""
    from app.services.mobile_reports_service import load_report_pdf

    pdf_bytes = await load_report_pdf(token)
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="Token expired or invalid")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="report.pdf"'},
    )


@router.post("/reports/{token}/send/telegram", response_class=JSONResponse)
async def mobile_report_send_telegram(
    token: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JSONResponse:
    """Send link-based Telegram delivery (D-06): send_message_sync with absolute URL."""
    from app.services import telegram_service
    from app.services.mobile_reports_service import build_download_url, load_report_pdf

    pdf_bytes = await load_report_pdf(token)
    if not pdf_bytes:
        return JSONResponse({"ok": False, "error": "Ссылка истекла"}, status_code=410)

    url = build_download_url(token)
    ok = telegram_service.send_message_sync(f"Отчёт клиенту готов:\n{url}")
    if not ok:
        return JSONResponse(
            {"ok": False, "error": "Ошибка отправки в Telegram"},
            status_code=502,
        )
    return JSONResponse({"ok": True})


@router.post("/reports/{token}/send/email", response_class=JSONResponse)
async def mobile_report_send_email(
    token: str,
    client_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JSONResponse:
    """Send PDF as email attachment to selected Client.email."""
    from app.models.client import Client as ClientModel
    from app.services import smtp_service
    from app.services.mobile_reports_service import load_report_pdf

    client = await db.get(ClientModel, client_id)
    if client is None or client.is_deleted or not client.email:
        return JSONResponse(
            {"ok": False, "error": "Ошибка: email клиента не указан"},
            status_code=422,
        )

    pdf_bytes = await load_report_pdf(token)
    if not pdf_bytes:
        return JSONResponse({"ok": False, "error": "Ссылка истекла"}, status_code=410)

    ok = smtp_service.send_email_with_attachment_sync(
        to=client.email,
        subject="SEO-отчёт",
        body_html="<p>Во вложении — актуальный SEO-отчёт по вашему проекту.</p>",
        attachment_bytes=pdf_bytes,
        attachment_filename="report.pdf",
    )
    if not ok:
        return JSONResponse(
            {"ok": False, "error": "Ошибка отправки email"},
            status_code=502,
        )
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# /m/tools — Phase 29 Mobile Tools (TLS-01)
# ---------------------------------------------------------------------------

@router.get("/tools", response_class=HTMLResponse, name="mobile_tools_list")
async def mobile_tools_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Single-column card list of 6 tools (D-08, D-09)."""
    from app.routers.tools import TOOL_REGISTRY
    tools = [
        {"slug": slug, **info}
        for slug, info in TOOL_REGISTRY.items()
    ]
    return mobile_templates.TemplateResponse(
        "mobile/tools/list.html",
        {"request": request, "active_tab": "more", "tools": tools},
    )


@router.get("/tools/{slug}/run", response_class=HTMLResponse, name="mobile_tool_run_form")
async def mobile_tool_run_form(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tool entry screen. For wordstat-batch: redirect to desktop OAuth if no token (D-10)."""
    from app.routers.tools import TOOL_REGISTRY, _check_oauth_token_sync
    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    registry = TOOL_REGISTRY[slug]

    # D-10: OAuth check — redirect to desktop handshake if missing
    needs_oauth = registry.get("needs_oauth")
    if needs_oauth:
        token = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _check_oauth_token_sync(needs_oauth)
        )
        if not token:
            return RedirectResponse(
                f"/ui/integrations/{needs_oauth}/auth?return_to=/m/tools/{slug}/run",
                status_code=303,
            )

    return mobile_templates.TemplateResponse(
        "mobile/tools/run.html",
        {
            "request": request,
            "active_tab": "more",
            "slug": slug,
            "tool": {"slug": slug, **registry},
        },
    )


@router.post("/tools/{slug}/run", response_class=HTMLResponse)
async def mobile_tool_run_submit(
    slug: str,
    request: Request,
    phrases: str = Form(default=""),
    domain: str = Form(default=""),
    region: str = Form(default="213"),
    upload: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Parse input, create Job, dispatch Celery task, return polling partial."""
    from app.routers.tools import TOOL_REGISTRY, _get_tool_models, _get_tool_task
    from app.services.mobile_tools_service import parse_tool_input
    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    registry = TOOL_REGISTRY[slug]

    parsed = await parse_tool_input(phrases, upload, registry["limit"])

    JobModel, _ = _get_tool_models(slug)
    job_kwargs: dict = {
        "id": uuid.uuid4(),
        "status": "pending",
        "user_id": user.id,
        "created_at": datetime.now(timezone.utc),
        registry["input_col"]: parsed.lines,
        registry["count_col"]: parsed.count,
    }
    if registry.get("has_domain_field"):
        job_kwargs["target_domain"] = (domain or "").strip()
    if registry.get("has_region_field"):
        try:
            job_kwargs["input_region"] = int(region or "213")
        except (ValueError, TypeError):
            job_kwargs["input_region"] = 213

    job = JobModel(**job_kwargs)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    job_id_str = str(job.id)

    if slug == "brief":
        from app.tasks.brief_tasks import (
            run_brief_step1_serp,
            run_brief_step2_crawl,
            run_brief_step3_aggregate,
            run_brief_step4_finalize,
        )
        celery_chain(
            run_brief_step1_serp.si(job_id_str),
            run_brief_step2_crawl.si(job_id_str),
            run_brief_step3_aggregate.si(job_id_str),
            run_brief_step4_finalize.si(job_id_str),
        ).delay()
    else:
        _get_tool_task(slug).delay(job_id_str)

    logger.info("mobile tool dispatched slug={} job_id={} user={}", slug, job_id_str, user.id)
    return mobile_templates.TemplateResponse(
        "mobile/tools/partials/tool_progress.html",
        {
            "request": request,
            "slug": slug,
            "job_id": job_id_str,
            "status": "started",
            "checked": 0,
            "total": parsed.count,
        },
    )


@router.get("/tools/{slug}/jobs/{job_id}", response_class=HTMLResponse, name="mobile_tool_result")
async def mobile_tool_result(
    slug: str,
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Mobile result view — summary + top-20 + XLSX link + 'Показать все' button (D-13)."""
    from app.routers.tools import TOOL_REGISTRY, _get_tool_models, _result_to_row, _EXPORT_HEADERS
    from app.services.mobile_tools_service import count_results, get_paginated_results, get_top_results, get_job_for_user

    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    registry = TOOL_REGISTRY[slug]

    JobModel, ResultModel = _get_tool_models(slug)

    job = await get_job_for_user(db, JobModel, job_id, user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    total = await count_results(db, ResultModel, job_id)
    top_rows = await get_top_results(db, ResultModel, job_id, limit=20)
    top_values = [_result_to_row(r, slug) for r in top_rows]

    status_label = {
        "complete": "Завершено",
        "done": "Завершено",
        "partial": "Завершено",
        "failed": "Ошибка",
    }.get((job.status or "").lower(), "Завершено")

    return mobile_templates.TemplateResponse(
        "mobile/tools/result.html",
        {
            "request": request,
            "active_tab": "more",
            "slug": slug,
            "job_id": str(job_id),
            "tool": {"slug": slug, **registry},
            "job": job,
            "status_label": status_label,
            "total": total,
            "top_values": top_values,
            "headers": _EXPORT_HEADERS.get(slug, []),
        },
    )


@router.get("/tools/{slug}/jobs/{job_id}/all", response_class=HTMLResponse)
async def mobile_tool_result_all(
    slug: str,
    job_id: uuid.UUID,
    request: Request,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """'Показать все' modal content — paginated full results (HTMX target)."""
    from app.routers.tools import TOOL_REGISTRY, _get_tool_models, _result_to_row, _EXPORT_HEADERS
    from app.services.mobile_tools_service import count_results, get_paginated_results, get_job_for_user

    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    JobModel, ResultModel = _get_tool_models(slug)

    job = await get_job_for_user(db, JobModel, job_id, user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    page_size = 50
    rows = await get_paginated_results(db, ResultModel, job_id, page, page_size)
    total = await count_results(db, ResultModel, job_id)
    values = [_result_to_row(r, slug) for r in rows]

    return mobile_templates.TemplateResponse(
        "mobile/tools/partials/result_modal.html",
        {
            "request": request,
            "slug": slug,
            "job_id": str(job_id),
            "headers": _EXPORT_HEADERS.get(slug, []),
            "values": values,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": (page * page_size) < total,
        },
    )


@router.get("/tools/{slug}/jobs/{job_id}/status", response_class=HTMLResponse)
async def mobile_tool_job_status(
    slug: str,
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """HTMX polling endpoint — returns tool_progress.html partial."""
    from app.routers.tools import TOOL_REGISTRY, _get_tool_models
    from app.services.mobile_tools_service import get_job_for_user
    if slug not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown tool")
    JobModel, _ = _get_tool_models(slug)

    job = await get_job_for_user(db, JobModel, job_id, user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Normalize status: pending/running → started, complete/partial → done, else error
    status_raw = (job.status or "").lower()
    if status_raw in ("pending", "running", "started"):
        status = "started"
    elif status_raw in ("complete", "done", "partial"):
        status = "done"
    else:
        status = "error"

    total = getattr(job, TOOL_REGISTRY[slug]["count_col"], 0) or 0
    checked = getattr(job, "processed_count", None)
    if checked is None:
        checked = total if status == "done" else 0

    return mobile_templates.TemplateResponse(
        "mobile/tools/partials/tool_progress.html",
        {
            "request": request,
            "slug": slug,
            "job_id": str(job_id),
            "status": status,
            "checked": checked,
            "total": total,
        },
    )
