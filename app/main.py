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
from app.services.schedule_service import get_all_schedules, upsert_schedule
from app.services.site_service import get_site, get_sites
from app.models.schedule import ScheduleType

templates = Jinja2Templates(directory="app/templates")


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


@app.get("/ui/tasks", response_class=HTMLResponse)
async def ui_tasks(
    request: Request,
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
) -> HTMLResponse:
    from app.models.task import SeoTask, TaskStatus
    from sqlalchemy import select as sa_select

    query = sa_select(SeoTask).order_by(SeoTask.created_at.desc())
    if status:
        query = query.where(SeoTask.status == TaskStatus(status))
    result = await db.execute(query)
    tasks_list = result.scalars().all()
    tasks_data = [
        {
            "task_type": t.task_type.value,
            "url": t.url,
            "title": t.title,
            "status": t.status.value,
            "created_at": t.created_at.isoformat() if t.created_at else "",
        }
        for t in tasks_list
    ]
    return templates.TemplateResponse(
        request, "tasks/index.html", {"tasks": tasks_data, "status_filter": status}
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

    top_n_int = int(top_n) if top_n else None
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

    return templates.TemplateResponse(
        request, "positions/index.html",
        {
            "site_name": site.name,
            "site_id": str(site.id),
            "positions": rows,
            "top_n": top_n,
            "engine": engine,
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


@app.get("/ui/dashboard", response_class=HTMLResponse)
async def ui_dashboard(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    from app.services.report_service import dashboard_summary
    from app.models.project import Project
    from sqlalchemy import select as sa_select

    stats = await dashboard_summary(db)
    projects = (await db.execute(
        sa_select(Project).order_by(Project.created_at.desc()).limit(20)
    )).scalars().all()
    projects_data = [{"id": str(p.id), "name": p.name, "status": p.status.value} for p in projects]
    return templates.TemplateResponse(request, "dashboard/index.html", {"stats": stats, "projects": projects_data})


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
         "created_at": j.created_at.isoformat() if j.created_at else ""}
        for j in jobs
    ]
    return templates.TemplateResponse(request, "pipeline/jobs.html", {"site_name": site.name, "site_id": str(site.id), "jobs": jobs_data})


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
