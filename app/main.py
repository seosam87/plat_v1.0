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
from app.routers.sites import router as sites_router
from app.services.site_service import get_sites

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

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(sites_router)


@app.get("/ui/sites", response_class=HTMLResponse)
async def ui_sites(request: Request, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    sites = await get_sites(db)
    return templates.TemplateResponse(request, "sites/index.html", {"sites": sites})


@app.get("/")
async def root():
    return {"status": "ok", "service": "SEO Management Platform"}
