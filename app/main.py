from app.logging_config import setup_logging

setup_logging()

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(invites_router)
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
    sites = await get_sites(db)
    all_schedules = await get_all_schedules(db)
    schedules = {str(s.site_id): s.schedule_type.value for s in all_schedules}
    return templates.TemplateResponse(
        request, "sites/index.html", {"sites": sites, "schedules": schedules}
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


@app.get("/")
async def root():
    return {"status": "ok", "service": "SEO Management Platform"}
