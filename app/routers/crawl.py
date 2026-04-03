"""Crawl router: change feed API + UI routes."""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from app.template_engine import templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.crawl import CrawlJob, Page, PageSnapshot
from app.models.user import User

router = APIRouter(tags=["crawls"])

FilterType = Literal["all", "seo_changed", "content_changed", "new_pages", "status_changed"]

# SEO fields we compare for the seo_changed filter
SEO_FIELDS = {"title", "h1", "meta_description"}


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------


@router.get("/crawls/{crawl_job_id}/pages")
async def list_crawl_pages(
    crawl_job_id: uuid.UUID,
    filter: FilterType = "all",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    """Return pages for a crawl job, optionally filtered by change type."""
    # Verify job exists
    job_result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == crawl_job_id)
    )
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    pages_result = await db.execute(
        select(Page).where(Page.crawl_job_id == crawl_job_id).order_by(Page.crawled_at)
    )
    pages = pages_result.scalars().all()

    # Fetch snapshots for all pages in one query
    page_ids = [p.id for p in pages]
    snaps_result = await db.execute(
        select(PageSnapshot).where(PageSnapshot.page_id.in_(page_ids))
    )
    snaps_by_page: dict[uuid.UUID, PageSnapshot] = {}
    for snap in snaps_result.scalars().all():
        # Keep only the latest snapshot per page
        if snap.page_id not in snaps_by_page:
            snaps_by_page[snap.page_id] = snap

    output = []
    for page in pages:
        snap = snaps_by_page.get(page.id)
        diff_data = snap.diff_data if snap else None

        # Apply filter
        if filter == "seo_changed":
            if not diff_data or not any(k in SEO_FIELDS for k in diff_data):
                continue
        elif filter == "content_changed":
            if not diff_data or "content_preview" not in diff_data:
                continue
        elif filter == "status_changed":
            if not diff_data or "http_status" not in diff_data:
                continue
        elif filter == "new_pages":
            # new_pages = pages that have no previous snapshot (diff_data is None
            # because there was nothing to compare against)
            if diff_data is not None:
                continue

        output.append(
            {
                "id": str(page.id),
                "url": page.url,
                "title": page.title,
                "h1": page.h1,
                "http_status": page.http_status,
                "page_type": page.page_type.value,
                "has_toc": page.has_toc,
                "has_schema": page.has_schema,
                "has_noindex": page.has_noindex,
                "depth": page.depth,
                "crawled_at": page.crawled_at.isoformat(),
                "diff_data": diff_data,
            }
        )

    return output


# ---------------------------------------------------------------------------
# Analysis endpoints
# ---------------------------------------------------------------------------


@router.get("/crawls/{crawl_job_id}/analysis/duplicates")
async def crawl_duplicates(
    crawl_job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Find duplicate titles and H1 headings in a crawl."""
    from app.services.crawl_analysis_service import find_duplicate_titles, find_duplicate_h1

    job = (await db.execute(select(CrawlJob).where(CrawlJob.id == crawl_job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    titles = await find_duplicate_titles(db, job.site_id, crawl_job_id)
    h1s = await find_duplicate_h1(db, job.site_id, crawl_job_id)
    return {"crawl_job_id": str(crawl_job_id), "duplicate_titles": titles, "duplicate_h1": h1s}


@router.get("/crawls/{crawl_job_id}/analysis/orphans")
async def crawl_orphans(
    crawl_job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Find orphan pages (no inbound internal links)."""
    from app.services.crawl_analysis_service import find_orphan_pages

    job = (await db.execute(select(CrawlJob).where(CrawlJob.id == crawl_job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    orphans = await find_orphan_pages(db, job.site_id, crawl_job_id)
    return {"crawl_job_id": str(crawl_job_id), "count": len(orphans), "orphans": orphans}


@router.get("/crawls/{crawl_job_id}/analysis/canonicals")
async def crawl_canonicals(
    crawl_job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Find pages where canonical URL differs from page URL."""
    from app.services.crawl_analysis_service import find_canonical_issues

    job = (await db.execute(select(CrawlJob).where(CrawlJob.id == crawl_job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    issues = await find_canonical_issues(db, job.site_id, crawl_job_id)
    return {"crawl_job_id": str(crawl_job_id), "count": len(issues), "issues": issues}


@router.get("/crawls/{crawl_job_id}/analysis/completeness")
async def crawl_completeness(
    crawl_job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """SEO field completeness summary."""
    from app.services.crawl_analysis_service import get_seo_completeness

    job = (await db.execute(select(CrawlJob).where(CrawlJob.id == crawl_job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    completeness = await get_seo_completeness(db, job.site_id, crawl_job_id)
    return {"crawl_job_id": str(crawl_job_id), **completeness}


# ---------------------------------------------------------------------------
# UI routes
# ---------------------------------------------------------------------------


@router.get("/ui/sites/{site_id}/crawls", response_class=HTMLResponse)
async def ui_site_crawl_history(
    site_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Show list of crawl jobs for a site."""
    from app.models.site import Site

    site_result = await db.execute(select(Site).where(Site.id == site_id))
    site = site_result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")

    jobs_result = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.site_id == site_id)
        .order_by(CrawlJob.started_at.desc())
    )
    jobs = jobs_result.scalars().all()

    return templates.TemplateResponse(
        request,
        "crawl/history.html",
        {"site": site, "jobs": jobs},
    )


@router.get("/ui/crawls/{crawl_job_id}", response_class=HTMLResponse)
async def ui_crawl_feed(
    crawl_job_id: uuid.UUID,
    filter: FilterType = "all",
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Show change feed for a crawl job."""
    job_result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == crawl_job_id)
    )
    job = job_result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    # Load pages + snapshots
    pages_result = await db.execute(
        select(Page).where(Page.crawl_job_id == crawl_job_id).order_by(Page.crawled_at)
    )
    pages = pages_result.scalars().all()

    page_ids = [p.id for p in pages]
    snaps_result = await db.execute(
        select(PageSnapshot).where(PageSnapshot.page_id.in_(page_ids))
    )
    snaps_by_page: dict[uuid.UUID, PageSnapshot] = {}
    for snap in snaps_result.scalars().all():
        if snap.page_id not in snaps_by_page:
            snaps_by_page[snap.page_id] = snap

    page_rows = [
        {
            "page": p,
            "snap": snaps_by_page.get(p.id),
        }
        for p in pages
    ]

    # If HTMX partial request, return only the table body
    if request and request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request,
            "crawl/feed_rows.html",
            {"page_rows": page_rows, "filter": filter},
        )

    return templates.TemplateResponse(
        request,
        "crawl/feed.html",
        {"job": job, "page_rows": page_rows, "filter": filter},
    )
