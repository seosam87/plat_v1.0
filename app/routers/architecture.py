"""Site Architecture router: SF import, sitemap, URL tree, roles, inlinks."""
import shutil
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.architecture import PageLink, SitemapEntry
from app.models.crawl import CrawlJob, Page
from app.models.site import Site
from app.models.user import User
from app.services import architecture_service as arch

router = APIRouter(prefix="/architecture", tags=["architecture"])
templates = Jinja2Templates(directory="app/templates")


class RoleUpdate(BaseModel):
    role: str


async def _get_site_or_404(db: AsyncSession, site_id: uuid.UUID) -> Site:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


# ---- Page ----


@router.get("/{site_id}", response_class=HTMLResponse)
async def architecture_page(
    request: Request,
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    site = await _get_site_or_404(db, site_id)

    # Sitemap stats
    sm_result = await db.execute(
        select(SitemapEntry.status, SitemapEntry.id)
        .where(SitemapEntry.site_id == site_id)
    )
    sm_entries = sm_result.all()
    sm_stats = {"orphan": 0, "missing": 0, "ok": 0, "total": len(sm_entries)}
    for row in sm_entries:
        if row[0] in sm_stats:
            sm_stats[row[0]] += 1

    # Recent crawls for inlinks diff selector
    crawls_result = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.site_id == site_id)
        .order_by(CrawlJob.started_at.desc())
        .limit(10)
    )
    crawls = crawls_result.scalars().all()

    return templates.TemplateResponse("architecture/index.html", {
        "request": request,
        "site": site,
        "sm_stats": sm_stats,
        "crawls": crawls,
    })


# ---- SF Import ----


@router.post("/{site_id}/import-sf")
async def import_sf(
    site_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await _get_site_or_404(db, site_id)
    suffix = Path(file.filename or "file.csv").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        result = await arch.import_sf_data(db, site_id, tmp_path)
        await db.commit()
        return result
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---- Sitemap ----


@router.post("/{site_id}/sitemap/fetch")
async def fetch_sitemap(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    site = await _get_site_or_404(db, site_id)
    content = await arch.fetch_sitemap(site.url)
    if not content:
        raise HTTPException(status_code=400, detail="Could not fetch sitemap.xml")
    entries = arch.parse_sitemap_xml(content)
    result = await arch.compare_sitemap(db, site_id, entries)
    await db.commit()
    return result


@router.post("/{site_id}/sitemap/upload")
async def upload_sitemap(
    site_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await _get_site_or_404(db, site_id)
    content = (await file.read()).decode("utf-8")
    entries = arch.parse_sitemap_xml(content)
    result = await arch.compare_sitemap(db, site_id, entries)
    await db.commit()
    return result


@router.get("/{site_id}/sitemap/results", response_model=None)
async def sitemap_results(
    site_id: uuid.UUID,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    q = select(SitemapEntry).where(SitemapEntry.site_id == site_id)
    if status:
        q = q.where(SitemapEntry.status == status)
    q = q.order_by(SitemapEntry.url)
    result = await db.execute(q)
    return [
        {"url": e.url, "status": e.status, "in_sitemap": e.in_sitemap, "in_crawl": e.in_crawl}
        for e in result.scalars().all()
    ]


# ---- Tree ----


@router.get("/{site_id}/tree")
async def url_tree(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    result = await db.execute(
        select(Page.url, Page.architecture_role).where(Page.site_id == site_id).distinct()
    )
    rows = result.all()
    urls = [r[0] for r in rows]
    url_roles = {r[0]: r[1] for r in rows if r[1]}
    return arch.build_url_tree(urls, url_roles=url_roles)


# ---- Roles ----


@router.post("/{site_id}/detect-roles")
async def detect_roles(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    count = await arch.detect_architecture_roles(db, site_id)
    await db.commit()
    return {"classified": count}


@router.put("/{site_id}/pages/{page_id}/role")
async def set_role(
    site_id: uuid.UUID,
    page_id: uuid.UUID,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    await arch.update_page_role(db, page_id, body.role)
    await db.commit()
    return {"status": "updated"}


@router.get("/{site_id}/roles", response_model=None)
async def list_roles(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    from app.models.crawl import ArchitectureRole
    result = await db.execute(
        select(Page).where(Page.site_id == site_id, Page.architecture_role != ArchitectureRole.unknown)
        .order_by(Page.architecture_role, Page.url)
    )
    pages = result.scalars().all()
    groups: dict[str, list] = {}
    for p in pages:
        role = p.architecture_role.value if hasattr(p.architecture_role, "value") else p.architecture_role
        groups.setdefault(role, []).append({
            "id": str(p.id), "url": p.url, "title": p.title,
            "inlinks_count": p.inlinks_count, "page_type": p.page_type.value if hasattr(p.page_type, "value") else p.page_type,
        })
    return groups


# ---- Inlinks diff ----


@router.get("/{site_id}/inlinks-diff")
async def inlinks_diff(
    site_id: uuid.UUID,
    crawl_a: str | None = None,
    crawl_b: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    if not crawl_a or not crawl_b:
        return {"error": "Specify crawl_a and crawl_b parameters"}

    old_result = await db.execute(
        select(PageLink).where(
            PageLink.site_id == site_id,
            PageLink.crawl_job_id == uuid.UUID(crawl_a),
        )
    )
    old_links = [
        {"source_url": l.source_url, "target_url": l.target_url, "anchor_text": l.anchor_text}
        for l in old_result.scalars().all()
    ]

    new_result = await db.execute(
        select(PageLink).where(
            PageLink.site_id == site_id,
            PageLink.crawl_job_id == uuid.UUID(crawl_b),
        )
    )
    new_links = [
        {"source_url": l.source_url, "target_url": l.target_url, "anchor_text": l.anchor_text}
        for l in new_result.scalars().all()
    ]

    return arch.compute_inlinks_diff(old_links, new_links)
