"""WP Pipeline router: jobs, approval, rollback, batch."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.user import User
from app.models.wp_content_job import WpContentJob, JobStatus
from app.services.site_service import get_site
from app.tasks.wp_content_tasks import run_content_pipeline, push_to_wp, rollback_job

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
templates = Jinja2Templates(directory="app/templates")


class PipelineRequest(BaseModel):
    page_url: str
    wp_post_id: int | None = None
    original_content: str | None = None


@router.post("/sites/{site_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def start_pipeline(
    site_id: uuid.UUID,
    payload: PipelineRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Start content enrichment pipeline for a page."""
    site = await get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    job = WpContentJob(
        site_id=site_id,
        page_url=payload.page_url,
        wp_post_id=payload.wp_post_id,
        original_content=payload.original_content,
    )
    db.add(job)
    await db.flush()
    await db.commit()

    task = run_content_pipeline.delay(str(job.id))
    return {"job_id": str(job.id), "task_id": task.id}


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    result = await db.execute(select(WpContentJob).where(WpContentJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


@router.post("/jobs/{job_id}/approve")
async def approve_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Approve a job and push content to WP."""
    result = await db.execute(select(WpContentJob).where(WpContentJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.awaiting_approval:
        raise HTTPException(status_code=400, detail=f"Job is {job.status.value}, not awaiting_approval")

    job.status = JobStatus.approved
    await db.flush()
    await db.commit()

    task = push_to_wp.delay(str(job.id))
    return {"status": "approved", "push_task_id": task.id}


@router.post("/jobs/{job_id}/reject")
async def reject_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    result = await db.execute(select(WpContentJob).where(WpContentJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.failed
    job.error_message = "Rejected by user"
    await db.flush()
    await db.commit()
    return {"status": "rejected", "job_id": str(job.id)}


@router.post("/jobs/{job_id}/rollback")
async def rollback(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    result = await db.execute(select(WpContentJob).where(WpContentJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.pushed:
        raise HTTPException(status_code=400, detail="Can only rollback pushed jobs")
    task = rollback_job.delay(str(job.id))
    return {"status": "rolling_back", "task_id": task.id}


@router.get("/sites/{site_id}/jobs")
async def list_jobs(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    result = await db.execute(
        select(WpContentJob)
        .where(WpContentJob.site_id == site_id)
        .order_by(WpContentJob.created_at.desc())
        .limit(50)
    )
    return [_job_to_dict(j) for j in result.scalars().all()]


@router.post("/sites/{site_id}/batch", status_code=status.HTTP_202_ACCEPTED)
async def batch_pipeline(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Run pipeline for all pages of a site that need enrichment."""
    from app.models.crawl import Page
    site = await get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Find pages missing TOC or schema
    pages = (await db.execute(
        select(Page).where(
            Page.site_id == site_id,
            Page.http_status == 200,
        ).order_by(Page.crawled_at.desc())
    )).scalars().all()

    # Deduplicate by URL (latest crawl)
    seen_urls: set[str] = set()
    unique_pages = []
    for p in pages:
        if p.url not in seen_urls:
            seen_urls.add(p.url)
            unique_pages.append(p)

    jobs_created = 0
    for p in unique_pages:
        if not p.has_toc or not p.has_schema:
            job = WpContentJob(site_id=site_id, page_url=p.url)
            db.add(job)
            await db.flush()
            run_content_pipeline.delay(str(job.id))
            jobs_created += 1

    await db.commit()
    return {"jobs_created": jobs_created, "site_id": str(site_id)}


def _job_to_dict(job: WpContentJob) -> dict:
    return {
        "id": str(job.id),
        "site_id": str(job.site_id),
        "page_url": job.page_url,
        "wp_post_id": job.wp_post_id,
        "status": job.status.value,
        "has_changes": job.diff_json.get("has_changes") if job.diff_json else None,
        "diff_json": job.diff_json,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "processed_at": job.processed_at.isoformat() if job.processed_at else None,
        "pushed_at": job.pushed_at.isoformat() if job.pushed_at else None,
    }
