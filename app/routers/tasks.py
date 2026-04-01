import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.task import SeoTask, TaskStatus
from app.models.user import User

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    site_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[dict]:
    """List SEO tasks, optionally filtered by site and/or status."""
    query = select(SeoTask).order_by(SeoTask.created_at.desc())
    if site_id:
        query = query.where(SeoTask.site_id == site_id)
    if status:
        query = query.where(SeoTask.status == TaskStatus(status))
    result = await db.execute(query)
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "site_id": str(t.site_id),
            "crawl_job_id": str(t.crawl_job_id) if t.crawl_job_id else None,
            "task_type": t.task_type.value,
            "status": t.status.value,
            "url": t.url,
            "title": t.title,
            "description": t.description,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


@router.patch("/{task_id}/status")
async def update_task_status(
    task_id: uuid.UUID,
    new_status: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Update a task's status (open → in_progress → resolved)."""
    result = await db.execute(select(SeoTask).where(SeoTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus(new_status)
    await db.flush()
    return {"id": str(task.id), "status": task.status.value}
