"""Mobile router: /m/ — touch-friendly mobile web app.

All endpoints use plain Jinja2Templates (NOT the nav-aware `templates` from
template_engine.py) so no sidebar injection occurs on mobile pages.

Auth: every endpoint uses Depends(get_current_user) explicitly.
UIAuthMiddleware in main.py also redirects unauthenticated /m/ requests to login.
Public auth endpoints under /m/auth/ are excluded from UIAuthMiddleware.
"""
from __future__ import annotations

import asyncio
import json
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
# /m/sites — site picker (INT-01: MOB-01, HLT-01, HLT-02)
# ---------------------------------------------------------------------------

@router.get("/sites", response_class=HTMLResponse)
async def mobile_sites(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Site picker page — lists all sites, each links to /m/health/{site_id}."""
    sites = await get_sites(db)
    return mobile_templates.TemplateResponse(
        "mobile/sites.html",
        {"request": request, "user": user, "sites": sites, "active_tab": "sites"},
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

@router.get("/reports", response_class=RedirectResponse)
async def mobile_reports_redirect():
    """Redirect /m/reports → /m/reports/new (INT-02: REP-01, BOT-03)."""
    return RedirectResponse(url="/m/reports/new", status_code=302)


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


# ---------------------------------------------------------------------------
# /m/errors — Phase 30 Yandex Errors UI (ERR-01, ERR-02)
# ---------------------------------------------------------------------------


@router.get("/errors", response_class=HTMLResponse)
async def mobile_errors(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    site_id: str | None = None,
):
    """Errors page — 3 error sections (Indexing/Crawl/Sanctions) with site dropdown and sync."""
    from app.models.yandex_errors import YandexErrorType
    from app.services.site_service import get_sites
    from app.services.yandex_errors_service import count_errors, last_fetched_at, list_errors

    sites = await get_sites(db)

    if not sites:
        ctx = {
            "request": request,
            "user": user,
            "active_tab": "errors",
            "sites": [],
            "has_sites": False,
        }
        return mobile_templates.TemplateResponse("mobile/errors/index.html", ctx)

    # Determine selected site
    if not site_id:
        site_id = request.cookies.get("m_errors_site_id")
    if not site_id or not any(str(s.id) == site_id for s in sites):
        site_id = str(sites[0].id)

    selected_uuid = uuid.UUID(site_id)
    indexing_errors = await list_errors(db, selected_uuid, YandexErrorType.indexing, limit=5)
    crawl_errors = await list_errors(db, selected_uuid, YandexErrorType.crawl, limit=5)
    sanction_errors = await list_errors(db, selected_uuid, YandexErrorType.sanction, limit=5)
    indexing_count = await count_errors(db, selected_uuid, YandexErrorType.indexing)
    crawl_count = await count_errors(db, selected_uuid, YandexErrorType.crawl)
    sanction_count = await count_errors(db, selected_uuid, YandexErrorType.sanction)
    last_synced = await last_fetched_at(db, selected_uuid)

    ctx = {
        "request": request,
        "user": user,
        "active_tab": "errors",
        "sites": sites,
        "has_sites": True,
        "selected_site_id": site_id,
        "indexing_errors": indexing_errors,
        "crawl_errors": crawl_errors,
        "sanction_errors": sanction_errors,
        "indexing_count": indexing_count,
        "crawl_count": crawl_count,
        "sanction_count": sanction_count,
        "last_synced": last_synced,
    }

    response: Response
    if request.headers.get("HX-Request"):
        response = mobile_templates.TemplateResponse(
            "mobile/errors/partials/errors_content.html", ctx
        )
    else:
        response = mobile_templates.TemplateResponse("mobile/errors/index.html", ctx)

    response.set_cookie(
        key="m_errors_site_id",
        value=site_id,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,
    )
    return response


@router.post("/errors/sync", response_class=HTMLResponse)
async def mobile_errors_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    site_id: str = Form(...),
):
    """Trigger Celery sync task for Yandex Webmaster errors and return polling partial."""
    from app.tasks.yandex_errors_tasks import sync_yandex_errors

    result = sync_yandex_errors.delay(site_id)
    return mobile_templates.TemplateResponse(
        "mobile/errors/partials/sync_progress.html",
        {
            "request": request,
            "task_id": result.id,
            "site_id": site_id,
            "sync_status": "running",
        },
    )


@router.get("/errors/sync/status/{task_id}", response_class=HTMLResponse)
async def mobile_errors_sync_status(
    request: Request,
    task_id: str,
    site_id: str,
    user: User = Depends(get_current_user),
):
    """HTMX polling endpoint — returns sync progress partial every 3s."""
    import json as _json

    import redis as redis_lib

    sync_status = "running"
    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        raw = r.get(f"yandex_sync:{task_id}")
        if raw:
            data = _json.loads(raw)
            sync_status = data.get("status", "running")
        else:
            from app.celery_app import celery_app

            ar = celery_app.AsyncResult(task_id)
            if ar.ready() and ar.successful():
                sync_status = "done"
            elif ar.failed():
                sync_status = "error"
    except Exception:
        pass

    return mobile_templates.TemplateResponse(
        "mobile/errors/partials/sync_progress.html",
        {
            "request": request,
            "task_id": task_id,
            "site_id": site_id,
            "sync_status": sync_status,
        },
    )


@router.get("/errors/content", response_class=HTMLResponse)
async def mobile_errors_content(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    site_id: str = "",
):
    """Reload all 3 error sections after sync is complete."""
    from app.models.yandex_errors import YandexErrorType
    from app.services.yandex_errors_service import count_errors, last_fetched_at, list_errors

    if not site_id:
        site_id = request.cookies.get("m_errors_site_id", "")

    ctx: dict = {"request": request}
    if site_id:
        selected_uuid = uuid.UUID(site_id)
        ctx.update(
            {
                "selected_site_id": site_id,
                "indexing_errors": await list_errors(db, selected_uuid, YandexErrorType.indexing, limit=5),
                "crawl_errors": await list_errors(db, selected_uuid, YandexErrorType.crawl, limit=5),
                "sanction_errors": await list_errors(db, selected_uuid, YandexErrorType.sanction, limit=5),
                "indexing_count": await count_errors(db, selected_uuid, YandexErrorType.indexing),
                "crawl_count": await count_errors(db, selected_uuid, YandexErrorType.crawl),
                "sanction_count": await count_errors(db, selected_uuid, YandexErrorType.sanction),
                "last_synced": await last_fetched_at(db, selected_uuid),
            }
        )

    return mobile_templates.TemplateResponse(
        "mobile/errors/partials/errors_content.html", ctx
    )


@router.get("/errors/{error_type}/all", response_class=HTMLResponse)
async def mobile_errors_show_all(
    request: Request,
    error_type: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    site_id: str = "",
    page: int = 1,
):
    """Expand full error list for a given error_type with pagination."""
    from app.models.yandex_errors import YandexErrorType
    from app.services.yandex_errors_service import count_errors, list_errors

    if error_type not in ("indexing", "crawl", "sanction"):
        raise HTTPException(status_code=422, detail="Invalid error_type")

    et = YandexErrorType(error_type)
    page_size = 20
    selected_uuid = uuid.UUID(site_id) if site_id else None

    if not selected_uuid:
        return mobile_templates.TemplateResponse(
            "mobile/errors/partials/section.html",
            {
                "request": request,
                "section_title": error_type,
                "section_type": error_type,
                "errors": [],
                "count": 0,
                "show_all": True,
                "has_more": False,
                "page": 1,
                "selected_site_id": site_id,
                "badge_class": "bg-gray-100 text-gray-700",
                "section_icon": "",
            },
        )

    errors = await list_errors(db, selected_uuid, et, limit=page_size, offset=(page - 1) * page_size)
    total = await count_errors(db, selected_uuid, et)

    section_map = {
        "indexing": ("Ошибки индексации", "bg-blue-100 text-blue-700"),
        "crawl": ("Ошибки краулинга", "bg-orange-100 text-orange-700"),
        "sanction": ("Санкции", "bg-red-100 text-red-700"),
    }
    section_title, badge_class = section_map[error_type]

    return mobile_templates.TemplateResponse(
        "mobile/errors/partials/section.html",
        {
            "request": request,
            "section_title": section_title,
            "section_type": error_type,
            "errors": errors,
            "count": total,
            "show_all": True,
            "has_more": (page * page_size) < total,
            "page": page,
            "selected_site_id": site_id,
            "badge_class": badge_class,
            "section_icon": "",
        },
    )


@router.get("/errors/{error_id}/brief/form", response_class=HTMLResponse)
async def mobile_error_brief_form(
    request: Request,
    error_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return inline brief form for a specific error row (HTMX outerHTML swap)."""
    from app.services.project_service import get_accessible_projects
    from app.services.yandex_errors_service import get_error

    error = await get_error(db, uuid.UUID(error_id))
    if not error:
        raise HTTPException(status_code=404, detail="Ошибка не найдена")

    projects = await get_accessible_projects(db, user)

    return mobile_templates.TemplateResponse(
        "mobile/errors/partials/brief_form.html",
        {"request": request, "error": error, "projects": projects},
    )


@router.post("/errors/{error_id}/brief", response_class=HTMLResponse)
async def mobile_error_brief_submit(
    request: Request,
    error_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    description: str = Form(""),
    priority: str = Form("p3"),
    project_id: str | None = Form(None),
):
    """Create SeoTask from error row with source_error_id FK. Returns success confirmation."""
    from app.models.task import SeoTask, TaskPriority, TaskStatus, TaskType
    from app.models.yandex_errors import YandexErrorType
    from app.services.yandex_errors_service import get_error

    error = await get_error(db, uuid.UUID(error_id))
    if not error:
        raise HTTPException(status_code=404, detail="Ошибка не найдена")

    # Map error_type to TaskType
    type_map = {
        YandexErrorType.indexing: TaskType.yandex_indexing,
        YandexErrorType.crawl: TaskType.yandex_crawl,
        YandexErrorType.sanction: TaskType.yandex_sanction,
    }
    task_type = type_map[error.error_type]

    task = SeoTask(
        site_id=error.site_id,
        url=error.url or "",
        title=error.title,
        description=description or None,
        task_type=task_type,
        priority=TaskPriority(priority),
        project_id=uuid.UUID(project_id) if project_id else None,
        source_error_id=error.id,
        status=TaskStatus.open,
    )
    db.add(task)
    await db.flush()
    await db.commit()

    return mobile_templates.TemplateResponse(
        "mobile/errors/partials/brief_result.html",
        {"request": request, "task_id": task.id},
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


# ---------------------------------------------------------------------------
# /m/tasks/new — Phase 30 Quick Task & Copywriter Brief (TSK-01, TSK-02)
# ---------------------------------------------------------------------------


@router.get("/tasks/new", response_class=HTMLResponse)
async def mobile_tasks_new(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    mode: str = "task",
):
    """Quick task / copywriter brief creation page with mode toggle (D-12)."""
    from app.services.mobile_brief_service import list_clients_for_brief
    from app.services.project_service import get_accessible_projects

    projects = await get_accessible_projects(db, user)
    clients = await list_clients_for_brief(db) if mode == "brief" else []
    return mobile_templates.TemplateResponse(
        "mobile/tasks/new.html",
        {
            "request": request,
            "user": user,
            "mode": mode,
            "projects": projects,
            "clients": clients,
            "active_tab": "more",
        },
    )


@router.get("/tasks/new/form", response_class=HTMLResponse)
async def mobile_tasks_new_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    mode: str = "task",
):
    """HTMX swap partial for mode toggle on /m/tasks/new."""
    from app.services.mobile_brief_service import list_clients_for_brief
    from app.services.project_service import get_accessible_projects

    projects = await get_accessible_projects(db, user)
    clients = await list_clients_for_brief(db) if mode == "brief" else []
    template = (
        "mobile/tasks/partials/brief_form.html"
        if mode == "brief"
        else "mobile/tasks/partials/task_form.html"
    )
    return mobile_templates.TemplateResponse(
        template,
        {"request": request, "projects": projects, "clients": clients},
    )


@router.post("/tasks/new", response_class=HTMLResponse)
async def mobile_tasks_new_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    mode: str = Form("task"),
    text: str = Form(None),
    keywords: str = Form(None),
    priority: str = Form("p3"),
    project_id: str = Form(...),
    tone: str = Form(None),
    length: str = Form(None),
    recipient_id: str | None = Form(None),
    action: str = Form("save"),
):
    """Handle quick task (mode=task) or copywriter brief (mode=brief) creation."""
    from app.models.project import Project
    from app.models.site import Site
    from app.models.task import SeoTask, TaskPriority, TaskStatus, TaskType
    from app.services.mobile_brief_service import (
        render_brief,
        send_brief_email,
        send_brief_telegram,
    )

    # Parse and validate project UUID
    try:
        proj_uuid = uuid.UUID(project_id)
    except (ValueError, AttributeError):
        return HTMLResponse(
            content='<script>showToast("Неверный идентификатор проекта.", "error"); setTimeout(() => window.history.back(), 1500);</script>'
        )

    proj_result = await db.execute(select(Project).where(Project.id == proj_uuid))
    project = proj_result.scalar_one_or_none()
    if project is None:
        return HTMLResponse(
            content='<script>showToast("Проект не найден.", "error"); setTimeout(() => window.history.back(), 1500);</script>'
        )

    # Defensive check: project must have a linked site
    if project.site_id is None:
        return HTMLResponse(
            content='<script>showToast("У проекта нет привязанного сайта. Привяжите сайт в настройках проекта.", "error"); setTimeout(() => window.history.back(), 1500);</script>'
        )

    if mode == "task":
        title = (text or "")[:80].strip() or "Задача"
        task = SeoTask(
            site_id=project.site_id,
            task_type=TaskType.manual,
            status=TaskStatus.open,
            url="",
            title=title,
            description=text,
            project_id=proj_uuid,
            priority=TaskPriority(priority),
            source_error_id=None,
        )
        db.add(task)
        await db.commit()
        return HTMLResponse(
            content='<script>showToast("Задача создана", "success"); setTimeout(() => window.location.href = "/m/", 1000);</script>'
        )

    else:
        # mode == "brief"
        site_result = await db.execute(select(Site).where(Site.id == project.site_id))
        site = site_result.scalar_one_or_none()
        site_url = site.url if site else ""

        keywords_list = [k.strip() for k in (keywords or "").split("\n") if k.strip()]
        rendered = render_brief(
            project.name,
            site_url,
            length or "2000",
            tone or "Информационный",
            keywords_list,
        )

        task = SeoTask(
            site_id=project.site_id,
            task_type=TaskType.manual,
            status=TaskStatus.open,
            url="",
            title=f"ТЗ копирайтеру: {len(keywords_list)} ключевых слов",
            description=rendered,
            project_id=proj_uuid,
            priority=TaskPriority(priority),
            source_error_id=None,
        )
        db.add(task)
        await db.commit()

        toast_msg = "ТЗ сохранено"
        if recipient_id and action == "send":
            from app.models.client import Client as ClientModel

            try:
                recipient_uuid = uuid.UUID(recipient_id)
                client_result = await db.execute(
                    select(ClientModel).where(ClientModel.id == recipient_uuid)
                )
                client = client_result.scalar_one_or_none()
                if client and client.email:
                    tg_ok = await send_brief_telegram(rendered, client.email)
                    email_ok = await send_brief_email(rendered, client.email, project.name)
                    if tg_ok or email_ok:
                        toast_msg = "ТЗ создано и отправлено клиенту"
                    else:
                        toast_msg = "ТЗ сохранено (отправка не удалась)"
                else:
                    toast_msg = "ТЗ сохранено (клиент без контактов)"
            except (ValueError, AttributeError):
                toast_msg = "ТЗ сохранено (ошибка получателя)"

        return HTMLResponse(
            content=f'<script>showToast("{toast_msg}", "success"); setTimeout(() => window.location.href = "/m/", 1000);</script>'
        )


# ---------------------------------------------------------------------------
# /m/pages — Phase 31 Pages App (PAG-01)
# ---------------------------------------------------------------------------


@router.get("/pages", response_class=HTMLResponse)
async def mobile_pages(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    site_id: str | None = None,
    tab: str = "all",
    offset: int = 0,
):
    """Pages list screen — audit status from latest crawl with 4 filter tabs."""
    from sqlalchemy import func

    from app.models.crawl import CrawlJob, CrawlJobStatus, Page
    from app.models.site import Site

    sites_result = await db.execute(select(Site).order_by(Site.domain))
    sites = sites_result.scalars().all()

    if not sites:
        ctx = {
            "request": request,
            "user": user,
            "active_tab": "pages",
            "sites": [],
            "pages": [],
        }
        return mobile_templates.TemplateResponse("mobile/pages/index.html", ctx)

    # Determine selected site
    if not site_id:
        site_id = request.cookies.get("m_pages_site_id")
    if not site_id or not any(str(s.id) == site_id for s in sites):
        site_id = str(sites[0].id)

    # Tab validation
    valid_tabs = ("all", "no_schema", "no_toc", "noindex")
    if tab not in valid_tabs:
        tab = "all"

    selected_uuid = uuid.UUID(site_id)

    # Latest completed crawl subquery
    latest_crawl_sq = (
        select(CrawlJob.id)
        .where(
            CrawlJob.site_id == selected_uuid,
            CrawlJob.status == CrawlJobStatus.done,
        )
        .order_by(CrawlJob.finished_at.desc())
        .limit(1)
        .scalar_subquery()
    )

    base_filter = Page.crawl_job_id == latest_crawl_sq

    # Count queries for tab badges
    count_all = (
        await db.execute(select(func.count()).select_from(Page).where(base_filter))
    ).scalar_one()
    count_no_schema = (
        await db.execute(
            select(func.count()).select_from(Page).where(base_filter, Page.has_schema == False)  # noqa: E712
        )
    ).scalar_one()
    count_no_toc = (
        await db.execute(
            select(func.count()).select_from(Page).where(base_filter, Page.has_toc == False)  # noqa: E712
        )
    ).scalar_one()
    count_noindex = (
        await db.execute(
            select(func.count()).select_from(Page).where(base_filter, Page.has_noindex == True)  # noqa: E712
        )
    ).scalar_one()

    # Build filtered query
    pages_q = select(Page).where(base_filter)
    if tab == "no_schema":
        pages_q = pages_q.where(Page.has_schema == False)  # noqa: E712
    elif tab == "no_toc":
        pages_q = pages_q.where(Page.has_toc == False)  # noqa: E712
    elif tab == "noindex":
        pages_q = pages_q.where(Page.has_noindex == True)  # noqa: E712

    pages_q = pages_q.order_by(Page.url).limit(21).offset(offset)
    rows = (await db.execute(pages_q)).scalars().all()

    pages = rows[:20]
    has_more = len(rows) > 20
    next_offset = offset + 20

    ctx = {
        "request": request,
        "user": user,
        "active_tab": "pages",
        "sites": sites,
        "pages": pages,
        "site_id": site_id,
        "tab": tab,
        "counts": {
            "all": count_all,
            "no_schema": count_no_schema,
            "no_toc": count_no_toc,
            "noindex": count_noindex,
        },
        "has_more": has_more,
        "offset": offset,
        "next_offset": next_offset,
    }

    if request.headers.get("HX-Request"):
        response = mobile_templates.TemplateResponse(
            "mobile/pages/partials/pages_content.html", ctx
        )
    else:
        response = mobile_templates.TemplateResponse("mobile/pages/index.html", ctx)

    response.set_cookie(
        key="m_pages_site_id",
        value=site_id,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,
    )
    return response


@router.get("/pages/detail/{page_id}", response_class=HTMLResponse)
async def mobile_page_detail(
    request: Request,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Inline expand detail for a page card."""
    from app.models.crawl import Page
    from app.models.site import Site

    page = (
        await db.execute(select(Page).where(Page.id == page_id))
    ).scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    site = (
        await db.execute(select(Site).where(Site.id == page.site_id))
    ).scalar_one_or_none()

    return mobile_templates.TemplateResponse(
        "mobile/pages/partials/page_detail.html",
        {"request": request, "page": page, "site": site},
    )


@router.get("/pages/detail/{page_id}/collapsed", response_class=HTMLResponse)
async def mobile_page_detail_collapsed(
    request: Request,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Collapse expanded page detail back to compact row."""
    from app.models.crawl import Page

    page = (
        await db.execute(select(Page).where(Page.id == page_id))
    ).scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    return mobile_templates.TemplateResponse(
        "mobile/pages/partials/page_row.html",
        {"request": request, "page": page},
    )


# ---------------------------------------------------------------------------
# /m/pages/{site_id}/{page_id}/edit — Phase 31 Title/Meta edit (PAG-03)
# ---------------------------------------------------------------------------


@router.get("/pages/{site_id}/{page_id}/edit", response_class=HTMLResponse)
async def mobile_page_edit(
    request: Request,
    site_id: uuid.UUID,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Title/Meta edit screen with SERP preview (D-15)."""
    from app.models.crawl import Page
    from app.models.site import Site

    page = await db.get(Page, page_id)
    if page is None or page.site_id != site_id:
        raise HTTPException(status_code=404, detail="Page not found")

    site = await db.get(Site, site_id)

    return mobile_templates.TemplateResponse(
        "mobile/pages/edit.html",
        {"request": request, "page": page, "site": site, "site_id": site_id, "active_tab": "pages"},
    )


@router.post("/pages/{site_id}/{page_id}/edit", response_class=HTMLResponse)
async def mobile_page_edit_submit(
    request: Request,
    site_id: uuid.UUID,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create WpContentJob with awaiting_approval status and redirect to /m/pipeline (D-13, D-15)."""
    from markupsafe import Markup
    from app.models.crawl import Page
    from app.models.site import Site
    from app.models.wp_content_job import WpContentJob, JobStatus
    from app.services.content_pipeline import compute_content_diff

    form = await request.form()
    title = (form.get("title") or "").strip()
    meta_description = (form.get("meta_description") or "").strip()

    if not title:
        page = await db.get(Page, page_id)
        site = await db.get(Site, site_id)
        return mobile_templates.TemplateResponse(
            "mobile/pages/edit.html",
            {
                "request": request,
                "page": page,
                "site": site,
                "site_id": site_id,
                "active_tab": "pages",
                "error": "Заголовок страницы не может быть пустым",
            },
        )

    page = await db.get(Page, page_id)
    if page is None or page.site_id != site_id:
        raise HTTPException(status_code=404, detail="Page not found")

    # Resolve wp_post_id from latest WpContentJob for this page URL
    # (Per Pitfall 1 — Page model has no wp_post_id field)
    wp_job = (await db.execute(
        select(WpContentJob)
        .where(
            WpContentJob.site_id == site_id,
            WpContentJob.page_url == page.url,
        )
        .order_by(WpContentJob.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    wp_post_id = wp_job.wp_post_id if wp_job else None

    original = f"Title: {page.title or ''}\nMeta: {page.meta_description or ''}"
    updated = f"Title: {title}\nMeta: {meta_description}"
    diff = compute_content_diff(original, updated)

    job = WpContentJob(
        site_id=site_id,
        wp_post_id=wp_post_id,
        page_url=page.url,
        post_type="title_meta",
        status=JobStatus.awaiting_approval,
        original_content=original,
        processed_content=updated,
        diff_json=diff,
        rollback_payload={
            "original_title": page.title,
            "original_meta": page.meta_description,
            "wp_post_id": wp_post_id,
        },
    )
    db.add(job)
    await db.commit()

    return RedirectResponse("/m/pipeline", status_code=303)


# ---------------------------------------------------------------------------
# /m/pipeline — Phase 31 Approve Queue (PAG-02)
# ---------------------------------------------------------------------------


def _parse_diff_lines(diff_text: str) -> list[dict]:
    """Parse unified diff text into classified lines with XSS-safe HTML.

    Escapes each line with markupsafe.escape() BEFORE wrapping in ins/del tags
    to prevent XSS (Pitfall 2 from RESEARCH.md).
    """
    from markupsafe import escape, Markup

    result = []
    for line in diff_text.split("\n"):
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            content = str(escape(line[1:]))
            result.append({"type": "added", "html": Markup(f'<ins class="bg-green-100 text-green-800">{content}</ins>')})
        elif line.startswith("-"):
            content = str(escape(line[1:]))
            result.append({"type": "removed", "html": Markup(f'<del class="bg-red-100 text-red-800 line-through">{content}</del>')})
        elif line:
            content = str(escape(line))
            result.append({"type": "context", "html": Markup(content)})
    return result


@router.get("/pipeline", response_class=HTMLResponse)
async def mobile_pipeline(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    site_id: str | None = None,
    status: str | None = None,
):
    """Pipeline approve queue — shows WpContentJobs filtered by status (D-08, D-09)."""
    from sqlalchemy import func
    from app.models.site import Site
    from app.models.wp_content_job import WpContentJob, JobStatus

    sites = await get_sites(db)

    if not site_id:
        site_id = request.cookies.get("m_pages_site_id")
    if not site_id or not any(str(s.id) == site_id for s in sites):
        site_id = str(sites[0].id) if sites else None

    status_filter = status or "awaiting_approval"

    status_map = {
        "awaiting_approval": JobStatus.awaiting_approval,
        "pushed": JobStatus.pushed,
        "failed": JobStatus.failed,
    }
    job_status = status_map.get(status_filter, JobStatus.awaiting_approval)

    jobs = []
    counts = {"awaiting_approval": 0, "pushed": 0, "failed": 0}

    if site_id:
        selected_uuid = uuid.UUID(site_id)

        jobs_result = await db.execute(
            select(WpContentJob)
            .where(
                WpContentJob.site_id == selected_uuid,
                WpContentJob.status == job_status,
            )
            .order_by(WpContentJob.created_at.desc())
            .limit(50)
        )
        raw_jobs = jobs_result.scalars().all()

        # Parse diff for each job
        jobs = []
        for job in raw_jobs:
            diff_text = (job.diff_json or {}).get("diff_text", "") if job.diff_json else ""
            parsed = _parse_diff_lines(diff_text) if diff_text else []
            # Attach parsed diff as a non-persisted attribute
            job.__dict__["parsed_diff_lines"] = parsed
            jobs.append(job)

        # Count queries for tab badges
        for s, js in status_map.items():
            cnt = (await db.execute(
                select(func.count()).select_from(WpContentJob).where(
                    WpContentJob.site_id == selected_uuid,
                    WpContentJob.status == js,
                )
            )).scalar_one()
            counts[s] = cnt

    ctx = {
        "request": request,
        "user": user,
        "active_tab": "pages",
        "sites": sites,
        "site_id": site_id,
        "status_filter": status_filter,
        "jobs": jobs,
        "counts": counts,
    }

    response: Response
    if request.headers.get("HX-Request"):
        response = mobile_templates.TemplateResponse(
            "mobile/pipeline/partials/pipeline_content.html", ctx
        )
    else:
        response = mobile_templates.TemplateResponse("mobile/pipeline/index.html", ctx)

    if site_id:
        response.set_cookie(
            key="m_pages_site_id",
            value=site_id,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30,
        )
    return response


@router.post("/pipeline/{job_id}/approve", response_class=HTMLResponse)
async def mobile_pipeline_approve(
    request: Request,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve a job — set status=approved and dispatch push_to_wp Celery task (D-10, D-11)."""
    from app.models.wp_content_job import WpContentJob, JobStatus
    from app.tasks.wp_content_tasks import push_to_wp

    job = await db.get(WpContentJob, job_id)
    if job is None or job.status != JobStatus.awaiting_approval:
        return HTMLResponse(
            content='<div class="bg-red-50 text-red-800 text-sm p-3 rounded">Задание не найдено или уже обработано.</div>',
            status_code=200,
        )

    job.status = JobStatus.approved
    await db.commit()
    push_to_wp.delay(str(job.id))

    # Re-attach parsed diff for template rendering
    diff_text = (job.diff_json or {}).get("diff_text", "") if job.diff_json else ""
    job.__dict__["parsed_diff_lines"] = _parse_diff_lines(diff_text) if diff_text else []

    response = mobile_templates.TemplateResponse(
        "mobile/pipeline/partials/job_card.html",
        {"request": request, "job": job},
    )
    response.headers["HX-Trigger"] = '{"showToast": {"msg": "Изменение принято и отправлено в WP", "type": "success"}}'
    return response


@router.post("/pipeline/{job_id}/reject", response_class=HTMLResponse)
async def mobile_pipeline_reject(
    request: Request,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reject a job — set status=rolled_back and remove from queue (D-10)."""
    from app.models.wp_content_job import WpContentJob, JobStatus

    job = await db.get(WpContentJob, job_id)
    if job is None or job.status != JobStatus.awaiting_approval:
        return HTMLResponse(content="", status_code=200)

    job.status = JobStatus.rolled_back
    await db.commit()

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Trigger"] = '{"showToast": {"msg": "Изменение отклонено", "type": "info"}}'
    return response


@router.post("/pipeline/{job_id}/rollback", response_class=HTMLResponse)
async def mobile_pipeline_rollback(
    request: Request,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Rollback a pushed job — dispatch rollback_job Celery task (D-12)."""
    from app.models.wp_content_job import WpContentJob, JobStatus
    from app.tasks.wp_content_tasks import rollback_job

    job = await db.get(WpContentJob, job_id)
    if job is None or job.status != JobStatus.pushed:
        return HTMLResponse(
            content='<div class="bg-red-50 text-red-800 text-sm p-3 rounded">Задание не найдено или не может быть откатано.</div>',
            status_code=200,
        )

    rollback_job.delay(str(job.id))

    # Re-attach parsed diff for template rendering
    diff_text = (job.diff_json or {}).get("diff_text", "") if job.diff_json else ""
    job.__dict__["parsed_diff_lines"] = _parse_diff_lines(diff_text) if diff_text else []

    response = mobile_templates.TemplateResponse(
        "mobile/pipeline/partials/job_card.html",
        {"request": request, "job": job},
    )
    response.headers["HX-Trigger"] = '{"showToast": {"msg": "Откат выполнен", "type": "info"}}'
    return response


# ---------------------------------------------------------------------------
# /m/pages/fix — Phase 31 Quick Fix TOC/Schema (PAG-03)
# ---------------------------------------------------------------------------


@router.post("/pages/fix/{page_id}/toc", response_class=HTMLResponse)
async def mobile_fix_toc(
    request: Request,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dispatch quick_fix_toc Celery task. Returns green success partial immediately (D-14)."""
    from app.models.crawl import Page
    from app.tasks.pages_tasks import quick_fix_toc

    page = (await db.execute(select(Page).where(Page.id == page_id))).scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    quick_fix_toc.delay(str(page_id))

    response = mobile_templates.TemplateResponse(
        "mobile/pages/partials/fix_success.html",
        {"request": request, "message": "TOC добавлен и отправлен в WP"},
    )
    response.headers["HX-Trigger"] = '{"showToast": {"msg": "TOC добавлен", "type": "success"}}'
    return response


@router.post("/pages/fix/{page_id}/schema", response_class=HTMLResponse)
async def mobile_fix_schema(
    request: Request,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dispatch quick_fix_schema Celery task. Returns green success partial immediately (D-14)."""
    from app.models.crawl import Page
    from app.tasks.pages_tasks import quick_fix_schema

    page = (await db.execute(select(Page).where(Page.id == page_id))).scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    quick_fix_schema.delay(str(page_id))

    response = mobile_templates.TemplateResponse(
        "mobile/pages/partials/fix_success.html",
        {"request": request, "message": "Schema добавлена и отправлена в WP"},
    )
    response.headers["HX-Trigger"] = '{"showToast": {"msg": "Schema добавлена", "type": "success"}}'
    return response


# ---------------------------------------------------------------------------
# /m/pages/bulk — Phase 31 Bulk Operations (PAG-04)
# ---------------------------------------------------------------------------

# Export alias for verification scripts
mobile_router = router


@router.get("/pages/bulk/schema/confirm", response_class=HTMLResponse)
async def mobile_bulk_schema_confirm(
    request: Request,
    site_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bulk schema confirmation screen — shows count of pages without schema (D-17)."""
    from sqlalchemy import func

    from app.models.crawl import CrawlJob, CrawlJobStatus, Page
    from app.models.site import Site

    try:
        selected_uuid = uuid.UUID(site_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid site_id")

    site = (await db.execute(select(Site).where(Site.id == selected_uuid))).scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Latest completed crawl
    latest_crawl_id = (await db.execute(
        select(CrawlJob.id)
        .where(
            CrawlJob.site_id == selected_uuid,
            CrawlJob.status == CrawlJobStatus.done,
        )
        .order_by(CrawlJob.finished_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    count = 0
    if latest_crawl_id:
        count = (await db.execute(
            select(func.count()).select_from(Page).where(
                Page.crawl_job_id == latest_crawl_id,
                Page.has_schema == False,  # noqa: E712
            )
        )).scalar_one()

    return mobile_templates.TemplateResponse(
        "mobile/pages/bulk_confirm.html",
        {
            "request": request,
            "user": user,
            "site": site,
            "count": count,
            "fix_type": "schema",
            "active_tab": "pages",
        },
    )


@router.get("/pages/bulk/toc/confirm", response_class=HTMLResponse)
async def mobile_bulk_toc_confirm(
    request: Request,
    site_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bulk TOC confirmation screen — shows count of pages without TOC (D-17)."""
    from sqlalchemy import func

    from app.models.crawl import CrawlJob, CrawlJobStatus, Page
    from app.models.site import Site

    try:
        selected_uuid = uuid.UUID(site_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid site_id")

    site = (await db.execute(select(Site).where(Site.id == selected_uuid))).scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Latest completed crawl
    latest_crawl_id = (await db.execute(
        select(CrawlJob.id)
        .where(
            CrawlJob.site_id == selected_uuid,
            CrawlJob.status == CrawlJobStatus.done,
        )
        .order_by(CrawlJob.finished_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    count = 0
    if latest_crawl_id:
        count = (await db.execute(
            select(func.count()).select_from(Page).where(
                Page.crawl_job_id == latest_crawl_id,
                Page.has_toc == False,  # noqa: E712
            )
        )).scalar_one()

    return mobile_templates.TemplateResponse(
        "mobile/pages/bulk_confirm.html",
        {
            "request": request,
            "user": user,
            "site": site,
            "count": count,
            "fix_type": "toc",
            "active_tab": "pages",
        },
    )


@router.post("/pages/bulk/schema", response_class=HTMLResponse)
async def mobile_bulk_schema_start(
    request: Request,
    site_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dispatch bulk_fix_schema Celery task. Returns progress partial (D-16, D-18)."""
    from sqlalchemy import func

    from app.models.crawl import CrawlJob, CrawlJobStatus, Page
    from app.tasks.pages_tasks import bulk_fix_schema

    try:
        selected_uuid = uuid.UUID(site_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid site_id")

    # Get count for initial progress display
    latest_crawl_id = (await db.execute(
        select(CrawlJob.id)
        .where(
            CrawlJob.site_id == selected_uuid,
            CrawlJob.status == CrawlJobStatus.done,
        )
        .order_by(CrawlJob.finished_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    total = 0
    if latest_crawl_id:
        total = (await db.execute(
            select(func.count()).select_from(Page).where(
                Page.crawl_job_id == latest_crawl_id,
                Page.has_schema == False,  # noqa: E712
            )
        )).scalar_one()

    result = bulk_fix_schema.delay(site_id)

    return mobile_templates.TemplateResponse(
        "mobile/pages/partials/bulk_progress.html",
        {
            "request": request,
            "task_id": result.id,
            "status": "running",
            "done": 0,
            "total": total,
            "pct": 0,
            "errors": 0,
            "site_id": site_id,
            "fix_type": "schema",
        },
    )


@router.post("/pages/bulk/toc", response_class=HTMLResponse)
async def mobile_bulk_toc_start(
    request: Request,
    site_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dispatch bulk_fix_toc Celery task. Returns progress partial (D-16, D-18)."""
    from sqlalchemy import func

    from app.models.crawl import CrawlJob, CrawlJobStatus, Page
    from app.tasks.pages_tasks import bulk_fix_toc

    try:
        selected_uuid = uuid.UUID(site_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid site_id")

    # Get count for initial progress display
    latest_crawl_id = (await db.execute(
        select(CrawlJob.id)
        .where(
            CrawlJob.site_id == selected_uuid,
            CrawlJob.status == CrawlJobStatus.done,
        )
        .order_by(CrawlJob.finished_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    total = 0
    if latest_crawl_id:
        total = (await db.execute(
            select(func.count()).select_from(Page).where(
                Page.crawl_job_id == latest_crawl_id,
                Page.has_toc == False,  # noqa: E712
            )
        )).scalar_one()

    result = bulk_fix_toc.delay(site_id)

    return mobile_templates.TemplateResponse(
        "mobile/pages/partials/bulk_progress.html",
        {
            "request": request,
            "task_id": result.id,
            "status": "running",
            "done": 0,
            "total": total,
            "pct": 0,
            "errors": 0,
            "site_id": site_id,
            "fix_type": "toc",
        },
    )


@router.get("/pages/bulk/progress/{task_id}", response_class=HTMLResponse)
async def mobile_bulk_progress(
    request: Request,
    task_id: str,
    site_id: str = "",
    fix_type: str = "schema",
    user: User = Depends(get_current_user),
):
    """HTMX polling endpoint — reads Redis progress for bulk operation (D-18)."""
    import redis as redis_lib

    r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        data = r.get(f"bulk:{task_id}:progress")
        if data:
            progress = json.loads(data)
        else:
            progress = {"done": 0, "total": 0, "status": "running", "errors": []}
    except Exception:
        progress = {"done": 0, "total": 0, "status": "running", "errors": []}

    done = progress.get("done", 0)
    total = progress.get("total", 0)
    status = progress.get("status", "running")
    error_list = progress.get("errors", [])
    errors = len(error_list)
    pct = int(done / total * 100) if total > 0 else 0

    response = mobile_templates.TemplateResponse(
        "mobile/pages/partials/bulk_progress.html",
        {
            "request": request,
            "task_id": task_id,
            "status": status,
            "done": done,
            "total": total,
            "pct": pct,
            "errors": errors,
            "site_id": site_id,
            "fix_type": fix_type,
        },
    )

    if status == "done":
        done_msg = f"Schema добавлена на {done} страниц" if fix_type == "schema" else f"TOC добавлен на {done} страниц"
        response.headers["HX-Trigger"] = (
            f'{{"showToast": {{"msg": "{done_msg}", "type": "success"}}}}'
        )

    return response


# ---------------------------------------------------------------------------
# Agent diff viewer (Claude Code agent spike — phase 33)
# ---------------------------------------------------------------------------


@router.get("/agent/diff/{task_id}", response_class=HTMLResponse)
async def agent_diff_page(
    request: Request,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Show full diff from a Claude Code agent task (spike)."""
    import pathlib
    diff_file = pathlib.Path(f"/tmp/agent_diffs/{task_id}.txt")
    diff_content = ""
    if diff_file.exists():
        diff_content = diff_file.read_text(errors="replace")
    else:
        diff_content = "Diff не найден. Возможно, задача ещё выполняется или уже удалена."
    return mobile_templates.TemplateResponse(
        "mobile/agent/diff.html",
        {"request": request, "task_id": task_id, "diff": diff_content},
    )
