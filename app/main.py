from app.logging_config import setup_logging

setup_logging()

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import engine
from app.dependencies import get_db
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.invites import router as invites_router
from app.routers.clusters import router as clusters_router
from app.routers.crawl import router as crawl_router
from app.routers.dataforseo import router as dataforseo_router
from app.routers.gsc import router as gsc_router
from app.routers.keywords import router as keywords_router
from app.routers.positions import router as positions_router
from app.routers.projects import router as projects_router
from app.routers.reports import router as reports_router
from app.routers.site_groups import router as site_groups_router
from app.routers.sites import router as sites_router
from app.routers.tasks import router as tasks_router
from app.routers.uploads import router as uploads_router
from app.routers.wp_pipeline import router as wp_pipeline_router
from app.routers.yandex import router as yandex_router
from app.routers.metrika import router as metrika_router
from app.routers.audit import router as audit_router
from app.routers.monitoring import router as monitoring_router
from app.routers.analytics import router as analytics_router
from app.routers.gap import router as gap_router
from app.routers.architecture import router as architecture_router
from app.services.schedule_service import get_all_schedules, upsert_schedule
from app.services.site_service import get_site, get_sites
from app.models.schedule import ScheduleType

_jinja_templates = Jinja2Templates(directory="app/templates")

# Map URL prefixes to help module names
_HELP_MODULE_MAP = {
    "/ui/sites": "sites",
    "/ui/keywords": "keywords",
    "/ui/positions": "positions",
    "/ui/crawls": "crawl",
    "/ui/clusters": "clusters",
    "/ui/cannibalization": "clusters",
    "/ui/pipeline": "pipeline",
    "/ui/projects": "projects",
    "/ui/dashboard": "reports",
    "/ui/uploads": "keywords",
    "/ui/tasks": "projects",
    "/ui/admin": "admin",
    "/ui/metrika": "metrika",
    "/audit": "audit",
    "/monitoring": "monitoring",
    "/analytics": "analytics",
    "/gap": "gap",
    "/architecture": "architecture",
}


class _HelpAwareTemplates:
    """Wrapper that auto-injects help_module into template context based on request URL."""

    def __init__(self, jinja_templates: Jinja2Templates):
        self._t = jinja_templates

    def TemplateResponse(self, request, name, context=None, **kwargs):
        ctx = dict(context or {})
        if "help_module" not in ctx:
            path = str(request.url.path)
            for prefix, module in _HELP_MODULE_MAP.items():
                if path.startswith(prefix):
                    ctx["help_module"] = module
                    break
        return self._t.TemplateResponse(request, name, ctx, **kwargs)


templates = _HelpAwareTemplates(_jinja_templates)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connectivity
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    # Shutdown: dispose engine cleanly
    await engine.dispose()


app = FastAPI(
    title="SEO Management Platform",
    lifespan=lifespan,
)

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---- Cookie-based UI auth middleware ----

PUBLIC_PATHS = {"/ui/login", "/health", "/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect"}


class UIAuthMiddleware(BaseHTTPMiddleware):
    """Redirect /ui/* requests to login page if no valid JWT cookie."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Only protect UI routes
        if not path.startswith("/ui") or path in PUBLIC_PATHS:
            return await call_next(request)

        token = request.cookies.get("access_token")
        if token:
            try:
                from app.auth.jwt import decode_access_token
                decode_access_token(token)
                return await call_next(request)
            except Exception:
                pass

        # No valid token — redirect to login
        return RedirectResponse(f"/ui/login?next={path}", status_code=302)


app.add_middleware(UIAuthMiddleware)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(invites_router)
app.include_router(site_groups_router)
app.include_router(sites_router)
app.include_router(clusters_router)
app.include_router(crawl_router)
app.include_router(tasks_router)
app.include_router(keywords_router)
app.include_router(positions_router)
app.include_router(projects_router)
app.include_router(reports_router)
app.include_router(uploads_router)
app.include_router(gsc_router)
app.include_router(dataforseo_router)
app.include_router(wp_pipeline_router)
app.include_router(yandex_router)

from app.routers.competitors import router as competitors_router
app.include_router(competitors_router)
app.include_router(metrika_router)
app.include_router(audit_router)
app.include_router(monitoring_router)
app.include_router(analytics_router)
app.include_router(gap_router)
app.include_router(architecture_router)


@app.get("/ui/sites", response_class=HTMLResponse)
async def ui_sites(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.services.site_group_service import get_accessible_sites
    from app.auth.dependencies import get_current_user
    from app.models.user import User as UserModel

    # Try to get current user from token for access filtering
    user = None
    auth_header = request.headers.get("authorization", "")
    cookie_token = request.cookies.get("access_token", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif cookie_token:
        token = cookie_token

    if token:
        try:
            from app.auth.jwt import decode_access_token
            from app.services.user_service import get_user_by_id
            payload = decode_access_token(token)
            user = await get_user_by_id(db, payload.get("sub", ""))
        except Exception:
            pass

    if user:
        sites = await get_accessible_sites(db, user)
    else:
        sites = await get_sites(db)

    all_schedules = await get_all_schedules(db)
    schedules = {str(s.site_id): s.schedule_type.value for s in all_schedules}

    # Load group names for display
    from app.services.site_group_service import list_groups
    groups = await list_groups(db)
    site_groups = {str(g.id): g.name for g in groups}

    return templates.TemplateResponse(
        request, "sites/index.html", {"sites": sites, "schedules": schedules, "site_groups": site_groups}
    )


@app.get("/ui/sites/new", response_class=HTMLResponse)
async def ui_create_site_form(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.services.site_group_service import list_groups
    groups = await list_groups(db)
    return templates.TemplateResponse(request, "sites/create.html", {"error": None, "groups": groups, "form_data": {}})


@app.post("/ui/sites/new", response_class=HTMLResponse)
async def ui_create_site(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    wp_username: str = Form(...),
    app_password: str = Form(...),
    site_group_id: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    from app.auth.jwt import decode_access_token
    from app.services.user_service import get_user_by_id
    from app.services.site_service import create_site
    from app.services.site_group_service import assign_site_to_group, list_groups

    token = request.cookies.get("access_token", "")
    try:
        payload = decode_access_token(token)
        user = await get_user_by_id(db, payload.get("sub", ""))
    except Exception:
        return RedirectResponse("/ui/login", status_code=302)

    form_data = {"name": name, "url": url, "wp_username": wp_username, "site_group_id": site_group_id}

    try:
        site = await create_site(db, name=name, url=url, wp_username=wp_username,
                                 app_password=app_password, actor_id=user.id)
        if site_group_id:
            import uuid as _uuid
            await assign_site_to_group(db, site.id, _uuid.UUID(site_group_id))
    except Exception as e:
        groups = await list_groups(db)
        return templates.TemplateResponse(request, "sites/create.html",
                                          {"error": str(e), "groups": groups, "form_data": form_data}, status_code=400)
    return RedirectResponse("/ui/sites", status_code=303)


@app.post("/ui/sites/{site_id}/schedule", response_class=HTMLResponse)
async def ui_update_schedule(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """HTMX handler: update crawl schedule from the dropdown."""
    import uuid

    form = await request.form()
    schedule_type_str = form.get("schedule_type", "manual")
    schedule_type = ScheduleType(schedule_type_str)

    site = await get_site(db, uuid.UUID(site_id))
    if not site:
        return HTMLResponse("Site not found", status_code=404)

    schedule = await upsert_schedule(db, uuid.UUID(site_id), schedule_type)
    await db.commit()

    label = schedule.schedule_type.value
    if label == "manual":
        return HTMLResponse("")
    return HTMLResponse(f'<span style="color:#059669">Saved</span>')


@app.delete("/ui/sites/{site_id}", response_class=HTMLResponse)
async def ui_delete_site(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """HTMX handler: delete a site and return empty response to remove the row."""
    import uuid as _uuid
    from app.auth.jwt import decode_access_token
    from app.services.user_service import get_user_by_id
    from app.services.site_service import delete_site

    token = request.cookies.get("access_token", "")
    try:
        payload = decode_access_token(token)
        user = await get_user_by_id(db, payload.get("sub", ""))
    except Exception:
        return HTMLResponse("Unauthorized", status_code=401)

    site = await get_site(db, _uuid.UUID(site_id))
    if not site:
        return HTMLResponse("Site not found", status_code=404)

    await delete_site(db, site, actor_id=user.id)
    return HTMLResponse("")


@app.get("/ui/tasks", response_class=HTMLResponse)
async def ui_tasks(
    request: Request,
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    site_id: str | None = None,
    task_type: str | None = None,
    priority: str | None = None,
) -> HTMLResponse:
    from app.models.task import SeoTask, TaskStatus, TaskType, TaskPriority
    from app.models.site import Site
    from sqlalchemy import select as sa_select
    import uuid as _uuid

    query = sa_select(SeoTask).order_by(SeoTask.created_at.desc()).limit(200)
    if status:
        query = query.where(SeoTask.status == TaskStatus(status))
    if site_id:
        query = query.where(SeoTask.site_id == _uuid.UUID(site_id))
    if task_type:
        query = query.where(SeoTask.task_type == TaskType(task_type))
    if priority:
        query = query.where(SeoTask.priority == TaskPriority(priority))
    result = await db.execute(query)
    tasks_list = result.scalars().all()

    # Site name lookup
    site_ids = {t.site_id for t in tasks_list}
    site_map = {}
    if site_ids:
        sites = (await db.execute(sa_select(Site).where(Site.id.in_(site_ids)))).scalars().all()
        site_map = {s.id: s.name for s in sites}

    # All sites for filter dropdown
    all_sites = await get_sites(db)

    tasks_data = [
        {
            "task_type": t.task_type.value,
            "url": t.url,
            "title": t.title,
            "status": t.status.value,
            "priority": t.priority.value if hasattr(t, "priority") and t.priority else "p3",
            "site_name": site_map.get(t.site_id, ""),
            "site_id": str(t.site_id),
            "created_at": t.created_at.isoformat() if t.created_at else "",
        }
        for t in tasks_list
    ]
    return templates.TemplateResponse(
        request, "tasks/index.html", {
            "tasks": tasks_data, "status_filter": status,
            "site_filter": site_id, "type_filter": task_type, "priority_filter": priority,
            "all_sites": [{"id": str(s.id), "name": s.name} for s in all_sites],
        }
    )


@app.get("/ui/positions", response_class=HTMLResponse)
async def ui_positions_select(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Show site selector for positions page."""
    sites = await get_sites(db)
    if not sites:
        return templates.TemplateResponse(
            request, "positions/index.html",
            {"site_name": "—", "site_id": "", "positions": [], "top_n": None, "engine": None},
        )
    # Redirect to first site
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/ui/positions/{sites[0].id}")


@app.get("/ui/positions/{site_id}", response_class=HTMLResponse)
async def ui_positions(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    engine: str | None = None,
    top_n: str | None = None,
) -> HTMLResponse:
    """Positions page for a site with filters."""
    import uuid as _uuid
    from app.services.position_service import get_latest_positions
    from app.models.keyword import Keyword
    from sqlalchemy import select as sa_select

    site = await get_site(db, _uuid.UUID(site_id))
    if not site:
        return HTMLResponse("Site not found", status_code=404)

    from app.services.position_service import get_position_distribution, get_positions_by_url

    top_n_int = int(top_n) if top_n else None
    url_filter = request.query_params.get("url", "")

    if url_filter:
        rows = await get_positions_by_url(db, _uuid.UUID(site_id), url_filter, engine=engine)
    else:
        rows = await get_latest_positions(
            db, _uuid.UUID(site_id), engine=engine, top_n=top_n_int
        )

    # Enrich with keyword phrase
    kw_ids = {r.get("keyword_id") for r in rows if r.get("keyword_id")}
    kw_map = {}
    if kw_ids:
        kws = (await db.execute(
            sa_select(Keyword).where(Keyword.id.in_(kw_ids))
        )).scalars().all()
        kw_map = {kw.id: kw.phrase for kw in kws}

    for r in rows:
        r["phrase"] = kw_map.get(r.get("keyword_id"), "")

    # Distribution summary
    distribution = await get_position_distribution(db, _uuid.UUID(site_id), engine=engine)

    return templates.TemplateResponse(
        request, "positions/index.html",
        {
            "site_name": site.name,
            "site_id": str(site.id),
            "positions": rows,
            "top_n": top_n,
            "engine": engine,
            "url_filter": url_filter,
            "distribution": distribution,
        },
    )


@app.get("/ui/metrika", response_class=HTMLResponse)
async def ui_metrika_select(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Redirect /ui/metrika to the first site's Metrika traffic page."""
    from fastapi.responses import RedirectResponse
    sites = await get_sites(db)
    if not sites:
        return templates.TemplateResponse(
            request, "metrika/index.html",
            {"site": None, "daily_data": [], "page_data": [], "events": []},
        )
    return RedirectResponse(f"/ui/metrika/{sites[0].id}")


@app.get("/ui/metrika/{site_id}", response_class=HTMLResponse)
async def ui_metrika(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Metrika traffic dashboard page for a site."""
    import uuid as _uuid
    from app.services import metrika_service as _metrika_service
    from datetime import date as _date, timedelta as _timedelta

    site = await get_site(db, _uuid.UUID(site_id))
    if not site:
        return HTMLResponse("Site not found", status_code=404)

    daily_data: list[dict] = []
    page_data: list[dict] = []
    events: list = []

    if site.metrika_counter_id:
        date_to = _date.today() - _timedelta(days=1)
        date_from = date_to - _timedelta(days=29)

        daily_data = await _metrika_service.get_daily_traffic(db, _uuid.UUID(site_id), date_from, date_to)
        page_data = await _metrika_service.get_page_traffic(db, _uuid.UUID(site_id), date_from, date_to)
        events = await _metrika_service.get_events(db, _uuid.UUID(site_id))

    return templates.TemplateResponse(
        request,
        "metrika/index.html",
        {
            "site": site,
            "daily_data": daily_data,
            "page_data": page_data,
            "events": events,
        },
    )


@app.get("/ui/uploads", response_class=HTMLResponse)
async def ui_uploads(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    from app.models.file_upload import FileUpload
    from sqlalchemy import select as sa_select

    sites = await get_sites(db)
    uploads = (await db.execute(
        sa_select(FileUpload).order_by(FileUpload.uploaded_at.desc()).limit(50)
    )).scalars().all()
    uploads_data = [
        {
            "original_name": u.original_name,
            "file_type": u.file_type.value,
            "status": u.status.value,
            "row_count": u.row_count,
            "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else "",
        }
        for u in uploads
    ]
    return templates.TemplateResponse(
        request, "uploads/index.html", {"sites": sites, "uploads": uploads_data}
    )


@app.get("/ui/datasources", response_class=HTMLResponse)
async def ui_datasources(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.services.serp_parser_service import get_daily_usage
    from app.services import yandex_webmaster_service
    from app.models.oauth_token import OAuthToken
    from sqlalchemy import select as sa_select

    # GSC status
    gsc_tokens = (await db.execute(
        sa_select(OAuthToken).where(OAuthToken.provider == "gsc")
    )).scalars().all()
    gsc_connected = len(gsc_tokens) > 0

    # Yandex status
    yandex_configured = yandex_webmaster_service.is_configured()

    return templates.TemplateResponse(request, "datasources/index.html", {
        "gsc_connected": gsc_connected,
        "gsc_sites_count": len(gsc_tokens),
        "yandex_configured": yandex_configured,
        "serp_usage": get_daily_usage(),
    })


@app.get("/ui/dashboard", response_class=HTMLResponse)
async def ui_dashboard(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.services.report_service import dashboard_summary
    from app.models.project import Project
    from sqlalchemy import select as sa_select

    from app.services.report_service import site_overview

    stats = await dashboard_summary(db)
    projects = (await db.execute(
        sa_select(Project).order_by(Project.created_at.desc()).limit(20)
    )).scalars().all()
    sites = await get_sites(db)
    site_map = {s.id: s.name for s in sites}
    stats["sites"] = len(sites)
    projects_data = [
        {"id": str(p.id), "name": p.name, "status": p.status.value,
         "site_id": str(p.site_id), "site_name": site_map.get(p.site_id, "—")}
        for p in projects
    ]

    # Per-site overview for dashboard table
    sites_overview = []
    for s in sites[:20]:
        try:
            ov = await site_overview(db, s.id)
            sites_overview.append({
                "id": str(s.id), "name": s.name,
                "keyword_count": ov["keyword_count"],
                "top3": ov["distribution"].get("top3", 0),
                "top10": ov["distribution"].get("top10", 0),
                "top30": ov["distribution"].get("top30", 0),
                "open_tasks": ov["open_tasks"],
            })
        except Exception:
            sites_overview.append({"id": str(s.id), "name": s.name, "keyword_count": 0, "top3": 0, "top10": 0, "top30": 0, "open_tasks": 0})

    return templates.TemplateResponse(request, "dashboard/index.html", {
        "stats": stats, "projects": projects_data, "sites_overview": sites_overview,
    })


@app.get("/ui/projects/{project_id}/kanban", response_class=HTMLResponse)
async def ui_kanban(project_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    import uuid as _uuid
    from app.models.project import Project
    from app.models.task import SeoTask
    from sqlalchemy import select as sa_select

    project = (await db.execute(sa_select(Project).where(Project.id == _uuid.UUID(project_id)))).scalar_one_or_none()
    if not project:
        return HTMLResponse("Project not found", status_code=404)
    tasks = (await db.execute(
        sa_select(SeoTask).where(SeoTask.project_id == _uuid.UUID(project_id)).order_by(SeoTask.created_at)
    )).scalars().all()
    grouped = {"open": [], "assigned": [], "in_progress": [], "review": [], "resolved": []}
    for t in tasks:
        grouped.setdefault(t.status.value, []).append({
            "id": str(t.id), "title": t.title, "task_type": t.task_type.value,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        })

    # Load comments
    from app.models.project_comment import ProjectComment
    from app.models.user import User as UserModel
    comments = (await db.execute(
        sa_select(ProjectComment).where(ProjectComment.project_id == _uuid.UUID(project_id))
        .order_by(ProjectComment.created_at.asc())
    )).scalars().all()
    user_ids = {c.user_id for c in comments}
    user_map: dict = {}
    if user_ids:
        users = (await db.execute(sa_select(UserModel).where(UserModel.id.in_(user_ids)))).scalars().all()
        user_map = {u.id: u.username for u in users}
    comments_data = [
        {"username": user_map.get(c.user_id, ""), "text": c.text, "created_at": c.created_at.isoformat()}
        for c in comments
    ]

    return templates.TemplateResponse(request, "projects/kanban.html", {
        "project_name": project.name, "project_id": project_id, "tasks": grouped, "comments": comments_data,
    })


@app.get("/ui/projects/{project_id}/plan", response_class=HTMLResponse)
async def ui_plan(project_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    import uuid as _uuid
    from app.models.project import Project
    from app.models.content_plan import ContentPlanItem
    from sqlalchemy import select as sa_select

    project = (await db.execute(sa_select(Project).where(Project.id == _uuid.UUID(project_id)))).scalar_one_or_none()
    if not project:
        return HTMLResponse("Project not found", status_code=404)
    items = (await db.execute(
        sa_select(ContentPlanItem).where(ContentPlanItem.project_id == _uuid.UUID(project_id))
        .order_by(ContentPlanItem.planned_date.asc().nullslast())
    )).scalars().all()
    items_data = [
        {"id": str(i.id), "proposed_title": i.proposed_title, "status": i.status.value,
         "planned_date": i.planned_date.isoformat() if i.planned_date else None,
         "wp_post_id": i.wp_post_id, "wp_post_url": i.wp_post_url, "notes": i.notes}
        for i in items
    ]
    return templates.TemplateResponse(request, "projects/plan.html", {"project_name": project.name, "items": items_data})


@app.get("/ui/pipeline/{site_id}", response_class=HTMLResponse)
async def ui_pipeline(site_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    import uuid as _uuid
    from app.models.wp_content_job import WpContentJob
    from sqlalchemy import select as sa_select

    site = await get_site(db, _uuid.UUID(site_id))
    if not site:
        return HTMLResponse("Site not found", status_code=404)
    jobs = (await db.execute(
        sa_select(WpContentJob).where(WpContentJob.site_id == _uuid.UUID(site_id))
        .order_by(WpContentJob.created_at.desc()).limit(50)
    )).scalars().all()
    jobs_data = [
        {"id": str(j.id), "page_url": j.page_url, "status": j.status.value,
         "has_changes": j.diff_json.get("has_changes") if j.diff_json else None,
         "added_lines": j.diff_json.get("added_lines", 0) if j.diff_json else 0,
         "removed_lines": j.diff_json.get("removed_lines", 0) if j.diff_json else 0,
         "created_at": j.created_at.isoformat() if j.created_at else ""}
        for j in jobs
    ]
    return templates.TemplateResponse(request, "pipeline/jobs.html", {"site_name": site.name, "site_id": str(site.id), "jobs": jobs_data})


# ---- Admin: User Management UI ----


async def _get_current_user_from_cookie(request: Request, db: AsyncSession):
    """Extract current user from JWT cookie. Returns None on failure."""
    from app.auth.jwt import decode_access_token
    from app.services.user_service import get_user_by_id

    token = request.cookies.get("access_token", "")
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        return await get_user_by_id(db, payload.get("sub", ""))
    except Exception:
        return None


@app.get("/ui/admin/users", response_class=HTMLResponse)
async def ui_admin_users(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.services.user_service import list_users
    from app.services.site_group_service import list_groups, get_user_group_ids, get_group

    user = await _get_current_user_from_cookie(request, db)
    if not user or user.role.value != "admin":
        return RedirectResponse("/ui/dashboard", status_code=302)

    users = await list_users(db, user)
    groups = await list_groups(db)
    group_map = {g.id: g.name for g in groups}

    # Build user -> group names mapping
    user_groups: dict[str, list[str]] = {}
    for u in users:
        gids = await get_user_group_ids(db, u.id)
        user_groups[str(u.id)] = [group_map.get(gid, "?") for gid in gids]

    users_data = [
        {
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "role": u.role.value,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else "",
        }
        for u in users
    ]
    return templates.TemplateResponse(
        request, "admin/users.html",
        {"users": users_data, "user_groups": user_groups, "error": None},
    )


@app.post("/ui/admin/users", response_class=HTMLResponse)
async def ui_admin_create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("client"),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    from app.auth.password import hash_password
    from app.services.user_service import create_user
    from app.models.user import UserRole

    user = await _get_current_user_from_cookie(request, db)
    if not user or user.role.value != "admin":
        return RedirectResponse("/ui/dashboard", status_code=302)

    try:
        await create_user(db, username=username, email=email,
                          password_hash=hash_password(password), role=UserRole(role))
        await db.commit()
    except Exception as e:
        return RedirectResponse(f"/ui/admin/users?error={e}", status_code=303)
    return RedirectResponse("/ui/admin/users", status_code=303)


@app.post("/ui/admin/users/{user_id}/edit", response_class=HTMLResponse)
async def ui_admin_edit_user(
    user_id: str,
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    from app.services.user_service import update_user
    from app.models.user import UserRole

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return RedirectResponse("/ui/dashboard", status_code=302)

    try:
        await update_user(db, target_user_id=user_id, current_user=current_user,
                          username=username, email=email, role=UserRole(role))
        await db.commit()
    except Exception as e:
        return RedirectResponse(f"/ui/admin/users?error={e}", status_code=303)
    return RedirectResponse("/ui/admin/users", status_code=303)


@app.post("/ui/admin/users/{user_id}/deactivate", response_class=HTMLResponse)
async def ui_admin_deactivate_user(
    user_id: str, request: Request, db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    from app.services.user_service import deactivate_user, get_user_by_id
    from app.services.site_group_service import get_user_group_ids, list_groups

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return HTMLResponse("Forbidden", status_code=403)

    await deactivate_user(db, user_id, current_user)
    await db.commit()

    # Return updated row for HTMX swap
    u = await get_user_by_id(db, user_id)
    groups = await list_groups(db)
    group_map = {g.id: g.name for g in groups}
    gids = await get_user_group_ids(db, u.id)
    user_group_names = [group_map.get(gid, "?") for gid in gids]

    return _render_user_row(u, user_group_names)


@app.post("/ui/admin/users/{user_id}/activate", response_class=HTMLResponse)
async def ui_admin_activate_user(
    user_id: str, request: Request, db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    from app.services.user_service import activate_user, get_user_by_id
    from app.services.site_group_service import get_user_group_ids, list_groups

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return HTMLResponse("Forbidden", status_code=403)

    await activate_user(db, user_id, current_user)
    await db.commit()

    u = await get_user_by_id(db, user_id)
    groups = await list_groups(db)
    group_map = {g.id: g.name for g in groups}
    gids = await get_user_group_ids(db, u.id)
    user_group_names = [group_map.get(gid, "?") for gid in gids]

    return _render_user_row(u, user_group_names)


def _render_user_row(u, group_names: list[str]) -> HTMLResponse:
    """Return a single <tr> for HTMX partial swap."""
    role_style = {
        "admin": "background:#fef3c7;color:#92400e",
        "manager": "background:#dbeafe;color:#1e40af",
        "client": "background:#f3f4f6;color:#6b7280",
    }
    status_badge = (
        '<span class="badge" style="background:#d1fae5;color:#065f46">Active</span>'
        if u.is_active
        else '<span class="badge" style="background:#fee2e2;color:#991b1b">Inactive</span>'
    )
    groups_html = ""
    if group_names:
        groups_html = " ".join(
            f'<span class="badge" style="background:#dbeafe;color:#1e40af;margin-right:.25rem">{g}</span>'
            for g in group_names
        )
    else:
        groups_html = '<span style="color:#6b7280">\u2014</span>'

    toggle_btn = ""
    uid = str(u.id)
    if u.is_active:
        toggle_btn = (
            f'<form class="inline">'
            f'<button class="btn btn-sm" style="background:#ef4444;color:white;margin-left:.5rem"'
            f' hx-post="/ui/admin/users/{uid}/deactivate"'
            f' hx-target="#user-row-{uid}" hx-swap="outerHTML"'
            f' hx-confirm="Deactivate user \'{u.username}\'?">Deactivate</button></form>'
        )
    else:
        toggle_btn = (
            f'<form class="inline">'
            f'<button class="btn btn-sm" style="background:#22c55e;color:white;margin-left:.5rem"'
            f' hx-post="/ui/admin/users/{uid}/activate"'
            f' hx-target="#user-row-{uid}" hx-swap="outerHTML"'
            f'>Activate</button></form>'
        )

    created = u.created_at.isoformat()[:10] if u.created_at else ""

    html = (
        f'<tr id="user-row-{uid}">'
        f'<td>{u.username}</td>'
        f'<td>{u.email}</td>'
        f'<td><span class="badge" style="{role_style.get(u.role.value, "")}">{u.role.value}</span></td>'
        f'<td>{status_badge}</td>'
        f'<td>{groups_html}</td>'
        f'<td style="color:#6b7280;font-size:.85rem">{created}</td>'
        f'<td>'
        f'<button class="btn btn-sm" style="background:#4f46e5;color:white"'
        f" onclick=\"openEditModal('{uid}','{u.username}','{u.email}','{u.role.value}')\">"
        f'Edit</button>'
        f'{toggle_btn}'
        f'</td></tr>'
    )
    return HTMLResponse(html)


# ---- Admin: Site Groups UI ----


@app.get("/ui/admin/groups", response_class=HTMLResponse)
async def ui_admin_groups(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.services.site_group_service import list_groups, get_group_users
    from app.services.user_service import list_users, get_user_by_id
    from app.models.site import Site
    from sqlalchemy import select as sa_select

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return RedirectResponse("/ui/dashboard", status_code=302)

    groups = await list_groups(db)
    all_users_list = await list_users(db, current_user)
    all_sites = (await db.execute(
        sa_select(Site).order_by(Site.name)
    )).scalars().all()

    # Build group -> users mapping
    group_users: dict[str, list] = {}
    for g in groups:
        uids = await get_group_users(db, g.id)
        users_in_group = []
        for uid in uids:
            u = await get_user_by_id(db, str(uid))
            if u:
                users_in_group.append({"id": str(u.id), "username": u.username})
        group_users[str(g.id)] = users_in_group

    # Build group -> sites mapping
    group_sites: dict[str, list] = {}
    for g in groups:
        sites_in = [s for s in all_sites if s.site_group_id and str(s.site_group_id) == str(g.id)]
        group_sites[str(g.id)] = [{"id": str(s.id), "name": s.name} for s in sites_in]

    groups_data = [
        {"id": str(g.id), "name": g.name, "description": g.description or ""}
        for g in groups
    ]
    all_users_data = [
        {"id": str(u.id), "username": u.username, "role": u.role.value}
        for u in all_users_list
    ]
    all_sites_data = [{"id": str(s.id), "name": s.name} for s in all_sites]

    return templates.TemplateResponse(
        request, "admin/groups.html",
        {
            "groups": groups_data,
            "group_users": group_users,
            "group_sites": group_sites,
            "all_users": all_users_data,
            "all_sites": all_sites_data,
            "error": None,
        },
    )


@app.post("/ui/admin/groups", response_class=HTMLResponse)
async def ui_admin_create_group(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    from app.services.site_group_service import create_group

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return RedirectResponse("/ui/dashboard", status_code=302)

    try:
        await create_group(db, name=name, description=description or None)
        await db.commit()
    except Exception as e:
        return RedirectResponse(f"/ui/admin/groups?error={e}", status_code=303)
    return RedirectResponse("/ui/admin/groups", status_code=303)


@app.post("/ui/admin/groups/{group_id}/edit", response_class=HTMLResponse)
async def ui_admin_edit_group(
    group_id: str,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    import uuid as _uuid
    from app.services.site_group_service import get_group, update_group

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return RedirectResponse("/ui/dashboard", status_code=302)

    g = await get_group(db, _uuid.UUID(group_id))
    if not g:
        return RedirectResponse("/ui/admin/groups", status_code=303)

    await update_group(db, g, name=name, description=description or None)
    await db.commit()
    return RedirectResponse("/ui/admin/groups", status_code=303)


@app.delete("/ui/admin/groups/{group_id}", response_class=HTMLResponse)
async def ui_admin_delete_group(
    group_id: str, request: Request, db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    import uuid as _uuid
    from app.services.site_group_service import get_group, delete_group

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return HTMLResponse("Forbidden", status_code=403)

    g = await get_group(db, _uuid.UUID(group_id))
    if g:
        await delete_group(db, g)
        await db.commit()
    return HTMLResponse("")


@app.post("/ui/admin/groups/{group_id}/users", response_class=HTMLResponse)
async def ui_admin_add_user_to_group(
    group_id: str, request: Request, db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    import uuid as _uuid
    from app.services.site_group_service import assign_user_to_group, get_group_users, get_group
    from app.services.user_service import get_user_by_id

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return HTMLResponse("Forbidden", status_code=403)

    form = await request.form()
    user_id = form.get("user_id", "")
    if not user_id:
        return HTMLResponse("Missing user_id", status_code=400)

    gid = _uuid.UUID(group_id)
    uid = _uuid.UUID(str(user_id))

    # Check not already assigned
    existing = await get_group_users(db, gid)
    if uid not in existing:
        await assign_user_to_group(db, uid, gid)
        await db.commit()

    # Return updated user badges for HTMX
    g = await get_group(db, gid)
    user_ids = await get_group_users(db, gid)
    html_parts = []
    for uid in user_ids:
        u = await get_user_by_id(db, str(uid))
        if u:
            html_parts.append(
                f'<span class="badge" style="background:#dbeafe;color:#1e40af;margin-right:.25rem">'
                f'{u.username}'
                f'<a href="#" style="color:#1e40af;text-decoration:none;margin-left:.3rem;font-weight:bold"'
                f' hx-delete="/ui/admin/groups/{group_id}/users/{u.id}"'
                f' hx-target="#group-users-{group_id}" hx-swap="innerHTML"'
                f' hx-confirm="Remove \'{u.username}\' from group \'{g.name}\'?"'
                f'>&times;</a></span>'
            )
    return HTMLResponse(" ".join(html_parts) if html_parts else '<span style="color:#6b7280;font-size:.85rem">No users assigned</span>')


@app.delete("/ui/admin/groups/{group_id}/users/{user_id}", response_class=HTMLResponse)
async def ui_admin_remove_user_from_group(
    group_id: str, user_id: str, request: Request, db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    import uuid as _uuid
    from app.services.site_group_service import remove_user_from_group, get_group_users, get_group
    from app.services.user_service import get_user_by_id

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return HTMLResponse("Forbidden", status_code=403)

    gid = _uuid.UUID(group_id)
    uid = _uuid.UUID(user_id)
    await remove_user_from_group(db, uid, gid)
    await db.commit()

    # Return updated user badges
    g = await get_group(db, gid)
    user_ids = await get_group_users(db, gid)
    html_parts = []
    for uid in user_ids:
        u = await get_user_by_id(db, str(uid))
        if u:
            html_parts.append(
                f'<span class="badge" style="background:#dbeafe;color:#1e40af;margin-right:.25rem">'
                f'{u.username}'
                f'<a href="#" style="color:#1e40af;text-decoration:none;margin-left:.3rem;font-weight:bold"'
                f' hx-delete="/ui/admin/groups/{group_id}/users/{u.id}"'
                f' hx-target="#group-users-{group_id}" hx-swap="innerHTML"'
                f' hx-confirm="Remove \'{u.username}\' from group \'{g.name if g else ""}\'?"'
                f'>&times;</a></span>'
            )
    return HTMLResponse(" ".join(html_parts) if html_parts else '<span style="color:#6b7280;font-size:.85rem">No users assigned</span>')


@app.post("/ui/admin/groups/{group_id}/sites", response_class=HTMLResponse)
async def ui_admin_assign_site_to_group(
    group_id: str, request: Request, db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    import uuid as _uuid
    from app.services.site_group_service import assign_site_to_group

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return HTMLResponse("Forbidden", status_code=403)

    form = await request.form()
    site_id = form.get("site_id", "")
    if not site_id:
        return HTMLResponse("Missing site_id", status_code=400)

    await assign_site_to_group(db, _uuid.UUID(str(site_id)), _uuid.UUID(group_id))
    await db.commit()

    # Full page refresh for this group card (redirect)
    return RedirectResponse("/ui/admin/groups", status_code=303)


# ---- Competitors UI ----


@app.get("/ui/competitors/{site_id}", response_class=HTMLResponse)
async def ui_competitors(site_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    import uuid as _uuid
    from app.services.competitor_service import list_competitors

    site = await get_site(db, _uuid.UUID(site_id))
    if not site:
        return HTMLResponse("Site not found", status_code=404)

    comps = await list_competitors(db, _uuid.UUID(site_id))
    comps_data = [
        {"id": str(c.id), "domain": c.domain, "name": c.name or c.domain, "notes": c.notes or ""}
        for c in comps
    ]

    return templates.TemplateResponse(request, "competitors/index.html", {
        "site_name": site.name, "site_id": str(site.id), "competitors": comps_data,
    })


@app.post("/ui/competitors/{site_id}/add", response_class=HTMLResponse)
async def ui_add_competitor(
    site_id: str, request: Request, db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    import uuid as _uuid
    from app.services.competitor_service import create_competitor

    form = await request.form()
    domain = form.get("domain", "").strip()
    name = form.get("name", "").strip() or None
    if domain:
        await create_competitor(db, _uuid.UUID(site_id), domain, name)
        await db.commit()
    return RedirectResponse(f"/ui/competitors/{site_id}", status_code=303)


@app.delete("/ui/competitors/{competitor_id}", response_class=HTMLResponse)
async def ui_delete_competitor(competitor_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    import uuid as _uuid
    from app.services.competitor_service import get_competitor, delete_competitor

    comp = await get_competitor(db, _uuid.UUID(competitor_id))
    if comp:
        await delete_competitor(db, comp)
        await db.commit()
    return HTMLResponse("")


# ---- Admin: Password Change ----


@app.post("/ui/admin/users/{user_id}/password", response_class=HTMLResponse)
async def ui_admin_change_password(
    user_id: str, request: Request, db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    import uuid as _uuid
    from app.auth.password import hash_password
    from app.models.user import User
    from app.services.audit_service import log_action
    from sqlalchemy import select as sa_select

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return HTMLResponse("Forbidden", status_code=403)

    form = await request.form()
    new_password = form.get("new_password", "")
    if len(new_password) < 8:
        return HTMLResponse("Password must be at least 8 characters", status_code=400)

    user = (await db.execute(
        sa_select(User).where(User.id == _uuid.UUID(user_id))
    )).scalar_one_or_none()
    if not user:
        return HTMLResponse("User not found", status_code=404)

    user.password_hash = hash_password(new_password)
    await log_action(db, action="user.password_changed", user_id=current_user.id,
                     entity_type="user", entity_id=str(user.id))
    await db.commit()
    return RedirectResponse("/ui/admin/users", status_code=303)


# ---- Admin: System Settings ----


@app.get("/ui/admin/settings", response_class=HTMLResponse)
async def ui_admin_settings(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.config import settings as app_settings

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return RedirectResponse("/ui/dashboard", status_code=303)

    settings_data = {
        "crawler_delay_ms": app_settings.CRAWLER_DELAY_MS,
        "crawler_max_pages": app_settings.CRAWLER_MAX_PAGES,
        "serp_max_daily": app_settings.SERP_MAX_DAILY_REQUESTS,
        "serp_delay_ms": app_settings.SERP_DELAY_MS,
        "gsc_configured": bool(app_settings.GSC_CLIENT_ID),
        "yandex_configured": bool(app_settings.YANDEX_WEBMASTER_TOKEN),
        "dataforseo_configured": bool(app_settings.DATAFORSEO_LOGIN and app_settings.DATAFORSEO_PASSWORD),
    }

    return templates.TemplateResponse(request, "admin/settings.html", {"settings": settings_data})


# ---- Admin: Audit Log UI ----


@app.get("/ui/admin/audit", response_class=HTMLResponse)
async def ui_admin_audit(
    request: Request, db: AsyncSession = Depends(get_db),
    action: str | None = None, user_id: str | None = None,
) -> HTMLResponse:
    import uuid as _uuid
    from app.models.audit_log import AuditLog
    from app.models.user import User
    from sqlalchemy import select as sa_select

    current_user = await _get_current_user_from_cookie(request, db)
    if not current_user or current_user.role.value != "admin":
        return RedirectResponse("/ui/dashboard", status_code=303)

    query = sa_select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)
    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == _uuid.UUID(user_id))

    logs = (await db.execute(query)).scalars().all()

    # User name lookup
    uid_set = {l.user_id for l in logs if l.user_id}
    user_map = {}
    if uid_set:
        users = (await db.execute(sa_select(User).where(User.id.in_(uid_set)))).scalars().all()
        user_map = {u.id: u.username for u in users}

    # Distinct actions for filter
    actions_result = await db.execute(
        sa_select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    all_actions = [r[0] for r in actions_result]

    all_users = (await db.execute(sa_select(User).order_by(User.username))).scalars().all()

    logs_data = [
        {
            "action": l.action,
            "username": user_map.get(l.user_id, "system"),
            "entity_type": l.entity_type or "",
            "entity_id": l.entity_id or "",
            "detail": str(l.detail_json)[:100] if l.detail_json else "",
            "created_at": l.created_at.isoformat()[:19] if l.created_at else "",
        }
        for l in logs
    ]

    return templates.TemplateResponse(request, "admin/audit.html", {
        "logs": logs_data,
        "action_filter": action,
        "user_filter": user_id,
        "all_actions": all_actions,
        "all_users": [{"id": str(u.id), "username": u.username} for u in all_users],
    })


# ---- Help System ----


HELP_DIR = "app/templates/help"
_VALID_MODULES = {
    "sites", "keywords", "positions", "crawl", "clusters",
    "pipeline", "datasources", "projects", "reports", "admin", "general",
}


@app.get("/ui/help/{module}", response_class=HTMLResponse)
async def ui_help(module: str) -> HTMLResponse:
    """Render a module help markdown file as HTML."""
    import pathlib
    if module not in _VALID_MODULES:
        return HTMLResponse("<p>Неизвестный модуль.</p>", status_code=404)

    md_path = pathlib.Path(HELP_DIR) / f"{module}.md"
    if not md_path.exists():
        return HTMLResponse(
            f"<p style='color:#6b7280'>Справка для модуля <b>{module}</b> ещё не написана. "
            f"Будет добавлена при проработке этого модуля.</p>"
        )

    md_text = md_path.read_text(encoding="utf-8")
    # Simple markdown→HTML conversion (no external dependency)
    html = _render_markdown(md_text)
    return HTMLResponse(html)


def _render_markdown(md: str) -> str:
    """Minimal markdown to HTML renderer — handles headers, bold, lists, code, tables, hr."""
    import re

    lines = md.split("\n")
    html_lines: list[str] = []
    in_list = False
    in_table = False
    in_code = False

    for line in lines:
        stripped = line.strip()

        # Fenced code blocks
        if stripped.startswith("```"):
            if in_code:
                html_lines.append("</code></pre>")
                in_code = False
            else:
                html_lines.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            html_lines.append(line)
            continue

        # Close list if needed
        if in_list and not stripped.startswith("- ") and not stripped.startswith("* ") and stripped:
            html_lines.append("</ul>")
            in_list = False

        # Close table if needed
        if in_table and not stripped.startswith("|"):
            html_lines.append("</tbody></table>")
            in_table = False

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            html_lines.append("<hr>")
            continue

        # Headers
        if stripped.startswith("### "):
            html_lines.append(f"<h3>{_inline(stripped[4:])}</h3>")
            continue
        if stripped.startswith("## "):
            html_lines.append(f"<h2>{_inline(stripped[3:])}</h2>")
            continue
        if stripped.startswith("# "):
            html_lines.append(f"<h1>{_inline(stripped[2:])}</h1>")
            continue

        # List items
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_inline(stripped[2:])}</li>")
            continue

        # Table rows
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # Skip separator row (|---|---|)
            if all(set(c) <= {"-", ":", " "} for c in cells):
                continue
            if not in_table:
                html_lines.append("<table><thead><tr>")
                html_lines.append("".join(f"<th>{_inline(c)}</th>" for c in cells))
                html_lines.append("</tr></thead><tbody>")
                in_table = True
            else:
                html_lines.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
            continue

        # Empty line
        if not stripped:
            html_lines.append("")
            continue

        # Paragraph
        html_lines.append(f"<p>{_inline(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")
    if in_table:
        html_lines.append("</tbody></table>")

    return "\n".join(html_lines)


def _inline(text: str) -> str:
    """Handle inline markdown: bold, italic, code, links."""
    import re
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


# ---- Site Detail Page ----


@app.get("/ui/sites/{site_id}/detail", response_class=HTMLResponse)
async def ui_site_detail(site_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    import uuid as _uuid
    from app.services.keyword_service import count_keywords
    from app.services.schedule_service import get_schedule, get_position_schedule
    from app.models.crawl import CrawlJob
    from app.models.task import SeoTask, TaskStatus
    from sqlalchemy import select as sa_select, func

    site = await get_site(db, _uuid.UUID(site_id))
    if not site:
        return HTMLResponse("Site not found", status_code=404)

    keyword_count = await count_keywords(db, _uuid.UUID(site_id))

    crawl_count = (await db.execute(
        sa_select(func.count()).select_from(CrawlJob).where(CrawlJob.site_id == _uuid.UUID(site_id))
    )).scalar() or 0

    task_count = (await db.execute(
        sa_select(func.count()).select_from(SeoTask).where(
            SeoTask.site_id == _uuid.UUID(site_id),
            SeoTask.status.in_([TaskStatus.open, TaskStatus.assigned, TaskStatus.in_progress]),
        )
    )).scalar() or 0

    crawl_sched = await get_schedule(db, _uuid.UUID(site_id))
    pos_sched = await get_position_schedule(db, _uuid.UUID(site_id))

    recent_crawls_rows = (await db.execute(
        sa_select(CrawlJob).where(CrawlJob.site_id == _uuid.UUID(site_id))
        .order_by(CrawlJob.started_at.desc().nullslast()).limit(5)
    )).scalars().all()
    recent_crawls = [
        {"id": str(c.id), "status": c.status.value, "pages_crawled": c.pages_crawled,
         "started_at": c.started_at.isoformat()[:16] if c.started_at else "—"}
        for c in recent_crawls_rows
    ]

    # Recent open tasks for widget
    recent_tasks = (await db.execute(
        sa_select(SeoTask).where(
            SeoTask.site_id == _uuid.UUID(site_id),
            SeoTask.status.in_([TaskStatus.open, TaskStatus.assigned, TaskStatus.in_progress]),
        ).order_by(SeoTask.created_at.desc()).limit(5)
    )).scalars().all()
    recent_tasks_data = [
        {"title": t.title, "task_type": t.task_type.value, "status": t.status.value,
         "priority": t.priority.value if hasattr(t, "priority") and t.priority else "p3",
         "url": t.url}
        for t in recent_tasks
    ]

    return templates.TemplateResponse(request, "sites/detail.html", {
        "site": {"id": str(site.id), "name": site.name, "url": site.url,
                 "connection_status": site.connection_status.value,
                 "seo_plugin": site.seo_plugin or "unknown"},
        "keyword_count": keyword_count,
        "crawl_count": crawl_count,
        "task_count": task_count,
        "crawl_schedule": crawl_sched.schedule_type.value if crawl_sched else "manual",
        "position_schedule": pos_sched.schedule_type.value if pos_sched else "manual",
        "recent_crawls": recent_crawls,
        "recent_tasks": recent_tasks_data,
    })


# ---- Keywords UI ----


@app.get("/ui/keywords/{site_id}", response_class=HTMLResponse)
async def ui_keywords(
    site_id: str, request: Request, db: AsyncSession = Depends(get_db),
    group_id: str | None = None, offset: int = 0,
) -> HTMLResponse:
    import uuid as _uuid
    from app.services.keyword_service import list_keywords, count_keywords, list_groups
    from app.models.cluster import KeywordCluster
    from app.models.keyword import KeywordGroup
    from sqlalchemy import select as sa_select

    site = await get_site(db, _uuid.UUID(site_id))
    if not site:
        return HTMLResponse("Site not found", status_code=404)

    gid = _uuid.UUID(group_id) if group_id else None
    limit = 100
    keywords = await list_keywords(db, _uuid.UUID(site_id), group_id=gid, limit=limit, offset=offset)
    total = await count_keywords(db, _uuid.UUID(site_id))
    groups = await list_groups(db, _uuid.UUID(site_id))

    # Build lookups for group and cluster names
    group_map = {g.id: g.name for g in groups}
    cluster_ids = {kw.cluster_id for kw in keywords if kw.cluster_id}
    cluster_map = {}
    if cluster_ids:
        clusters = (await db.execute(
            sa_select(KeywordCluster).where(KeywordCluster.id.in_(cluster_ids))
        )).scalars().all()
        cluster_map = {c.id: c.name for c in clusters}

    kw_data = [
        {
            "id": str(kw.id), "phrase": kw.phrase, "frequency": kw.frequency,
            "engine": kw.engine.value if kw.engine else None, "region": kw.region,
            "target_url": kw.target_url,
            "group_id": str(kw.group_id) if kw.group_id else None,
            "group_name": group_map.get(kw.group_id, ""),
            "cluster_name": cluster_map.get(kw.cluster_id, ""),
        }
        for kw in keywords
    ]
    groups_data = [{"id": str(g.id), "name": g.name} for g in groups]

    return templates.TemplateResponse(request, "keywords/index.html", {
        "site_name": site.name, "site_id": str(site.id),
        "keywords": kw_data, "total": total, "groups": groups_data,
        "group_id": group_id, "offset": offset, "limit": limit,
    })


@app.post("/ui/keywords/{site_id}/add", response_class=HTMLResponse)
async def ui_add_keyword(
    site_id: str, request: Request, db: AsyncSession = Depends(get_db),
    phrase: str = Form(...), target_url: str = Form(""), group_id: str = Form(""),
) -> HTMLResponse:
    import uuid as _uuid
    from app.services.keyword_service import add_keyword

    gid = _uuid.UUID(group_id) if group_id else None
    await add_keyword(db, _uuid.UUID(site_id), phrase, target_url=target_url or None, group_id=gid)
    await db.commit()
    return RedirectResponse(f"/ui/keywords/{site_id}", status_code=303)


@app.delete("/ui/keywords/{keyword_id}", response_class=HTMLResponse)
async def ui_delete_keyword(keyword_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    import uuid as _uuid
    from app.services.keyword_service import get_keyword, delete_keyword

    kw = await get_keyword(db, _uuid.UUID(keyword_id))
    if kw:
        await delete_keyword(db, kw)
        await db.commit()
    return HTMLResponse("")


@app.patch("/ui/keywords/{keyword_id}", response_class=HTMLResponse)
async def ui_update_keyword(
    keyword_id: str, request: Request, db: AsyncSession = Depends(get_db),
    target_url: str = Form(None), group_id: str = Form(None),
) -> HTMLResponse:
    import uuid as _uuid
    from app.services.keyword_service import get_keyword, update_keyword, list_groups
    from app.models.cluster import KeywordCluster
    from sqlalchemy import select as sa_select

    kw = await get_keyword(db, _uuid.UUID(keyword_id))
    if not kw:
        return HTMLResponse("Not found", status_code=404)

    # Determine group update
    clear_group = group_id == ""
    gid = _uuid.UUID(group_id) if group_id and group_id != "" else None

    await update_keyword(
        db, kw,
        target_url=target_url if target_url is not None else None,
        group_id=gid,
        clear_group=clear_group,
    )
    await db.commit()

    # Build updated row HTML
    groups = await list_groups(db, kw.site_id)
    group_map = {g.id: g.name for g in groups}
    group_name = group_map.get(kw.group_id, "")
    cluster_name = ""
    if kw.cluster_id:
        cl = (await db.execute(
            sa_select(KeywordCluster).where(KeywordCluster.id == kw.cluster_id)
        )).scalar_one_or_none()
        cluster_name = cl.name if cl else ""

    groups_options = ''.join(
        f'<option value="{g.id}" {"selected" if g.id == kw.group_id else ""}>{g.name}</option>'
        for g in groups
    )

    engine_val = kw.engine.value if kw.engine else "—"
    target_display = (
        f'<a href="{kw.target_url}" target="_blank" style="max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block">{kw.target_url}</a>'
        if kw.target_url else "—"
    )

    return HTMLResponse(
        f'<tr id="kw-row-{kw.id}">'
        f'<td style="font-weight:500">{kw.phrase}</td>'
        f'<td>{kw.frequency if kw.frequency else "—"}</td>'
        f'<td>{engine_val}</td>'
        f'<td>{kw.region or "—"}</td>'
        f'<td>'
        f'<select style="padding:2px 4px;border:1px solid #d1d5db;border-radius:4px;font-size:.8rem"'
        f' hx-patch="/ui/keywords/{kw.id}" hx-target="#kw-row-{kw.id}" hx-swap="outerHTML"'
        f' hx-include="this" name="group_id">'
        f'<option value="">—</option>{groups_options}</select>'
        f'</td>'
        f'<td>'
        f'<form style="display:flex;gap:4px" hx-patch="/ui/keywords/{kw.id}" hx-target="#kw-row-{kw.id}" hx-swap="outerHTML">'
        f'<input type="text" name="target_url" value="{kw.target_url or ""}"'
        f' style="width:150px;padding:2px 4px;border:1px solid #d1d5db;border-radius:4px;font-size:.8rem"'
        f' placeholder="Target URL">'
        f'<button type="submit" class="btn btn-sm" style="padding:2px 8px;font-size:.75rem">OK</button>'
        f'</form>'
        f'</td>'
        f'<td>{cluster_name or "—"}</td>'
        f'<td>'
        f'<button class="btn btn-sm" style="background:#991b1b;color:white"'
        f' hx-delete="/ui/keywords/{kw.id}"'
        f' hx-target="#kw-row-{kw.id}" hx-swap="outerHTML swap:200ms"'
        f' hx-confirm="Delete keyword \'{kw.phrase}\'?">&times;</button>'
        f'</td>'
        f'</tr>'
    )


# ---- Projects UI ----


@app.get("/ui/projects", response_class=HTMLResponse)
async def ui_projects(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.models.project import Project
    from app.models.task import SeoTask, TaskStatus
    from app.models.site import Site
    from sqlalchemy import select as sa_select, func

    projects = (await db.execute(
        sa_select(Project).order_by(Project.created_at.desc())
    )).scalars().all()

    sites = await get_sites(db)
    site_map = {s.id: s.name for s in sites}

    projects_data = []
    for p in projects:
        open_tasks = (await db.execute(
            sa_select(func.count()).select_from(SeoTask).where(
                SeoTask.project_id == p.id,
                SeoTask.status.in_([TaskStatus.open, TaskStatus.assigned]),
            )
        )).scalar() or 0
        in_progress = (await db.execute(
            sa_select(func.count()).select_from(SeoTask).where(
                SeoTask.project_id == p.id,
                SeoTask.status == TaskStatus.in_progress,
            )
        )).scalar() or 0

        projects_data.append({
            "id": str(p.id), "name": p.name, "status": p.status.value,
            "site_id": str(p.site_id), "site_name": site_map.get(p.site_id, "—"),
            "open_tasks": open_tasks, "in_progress_tasks": in_progress,
            "created_at": p.created_at.isoformat() if p.created_at else "",
        })

    sites_data = [{"id": str(s.id), "name": s.name} for s in sites]
    return templates.TemplateResponse(request, "projects/index.html", {
        "projects": projects_data, "sites": sites_data,
    })


@app.post("/ui/projects/new", response_class=HTMLResponse)
async def ui_create_project(
    request: Request, db: AsyncSession = Depends(get_db),
    name: str = Form(...), site_id: str = Form(...), description: str = Form(""),
) -> HTMLResponse:
    import uuid as _uuid
    from app.models.project import Project

    project = Project(
        site_id=_uuid.UUID(site_id),
        name=name,
        description=description or None,
    )
    db.add(project)
    await db.commit()
    return RedirectResponse("/ui/projects", status_code=303)


# ---- Clusters UI ----


@app.get("/ui/clusters/{site_id}", response_class=HTMLResponse)
async def ui_clusters(site_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    import uuid as _uuid
    from app.services.cluster_service import list_clusters
    from app.models.keyword import Keyword
    from sqlalchemy import select as sa_select

    site = await get_site(db, _uuid.UUID(site_id))
    if not site:
        return HTMLResponse("Site not found", status_code=404)

    clusters = await list_clusters(db, _uuid.UUID(site_id))

    clusters_data = []
    for c in clusters:
        keywords = (await db.execute(
            sa_select(Keyword).where(Keyword.cluster_id == c.id).limit(30)
        )).scalars().all()
        clusters_data.append({
            "id": str(c.id), "name": c.name, "target_url": c.target_url,
            "intent": c.intent.value if hasattr(c.intent, "value") else c.intent,
            "keyword_count": len(keywords),
            "keywords": [{"phrase": kw.phrase, "frequency": kw.frequency} for kw in keywords],
        })

    return templates.TemplateResponse(request, "clusters/index.html", {
        "site_name": site.name, "site_id": str(site.id), "clusters": clusters_data,
    })


@app.post("/ui/clusters/{site_id}/new", response_class=HTMLResponse)
async def ui_create_cluster(
    site_id: str, request: Request, db: AsyncSession = Depends(get_db),
    name: str = Form(...), target_url: str = Form(""),
) -> HTMLResponse:
    import uuid as _uuid
    from app.services.cluster_service import create_cluster

    await create_cluster(db, _uuid.UUID(site_id), name, target_url=target_url or None)
    await db.commit()
    return RedirectResponse(f"/ui/clusters/{site_id}", status_code=303)


@app.delete("/ui/clusters/{cluster_id}", response_class=HTMLResponse)
async def ui_delete_cluster(cluster_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    import uuid as _uuid
    from app.services.cluster_service import get_cluster, delete_cluster

    c = await get_cluster(db, _uuid.UUID(cluster_id))
    if c:
        await delete_cluster(db, c)
        await db.commit()
    return HTMLResponse("")


@app.get("/ui/cannibalization/{site_id}", response_class=HTMLResponse)
async def ui_cannibalization(site_id: str, request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    import uuid as _uuid
    from app.services.cluster_service import detect_cannibalization

    site = await get_site(db, _uuid.UUID(site_id))
    if not site:
        return HTMLResponse("Site not found", status_code=404)

    results = await detect_cannibalization(db, _uuid.UUID(site_id))
    return templates.TemplateResponse(request, "clusters/cannibalization.html", {
        "site_name": site.name, "site_id": str(site.id), "results": results,
    })


@app.get("/ui/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "login.html", {"error": error})


@app.post("/ui/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and set JWT cookie."""
    from app.auth.password import verify_password
    from app.auth.jwt import create_access_token
    from app.services.user_service import get_user_by_email

    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {"error": "Incorrect email or password"}, status_code=401)
    if not user.is_active:
        return templates.TemplateResponse(request, "login.html", {"error": "Account deactivated"}, status_code=401)

    token = create_access_token(str(user.id), user.role.value)
    next_url = request.query_params.get("next", "/ui/dashboard")
    response = RedirectResponse(next_url, status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24,  # 24h
        samesite="lax",
    )
    return response


@app.get("/ui/logout")
async def logout():
    response = RedirectResponse("/ui/login", status_code=302)
    response.delete_cookie("access_token")
    return response


@app.get("/")
async def root():
    return RedirectResponse("/ui/dashboard")
