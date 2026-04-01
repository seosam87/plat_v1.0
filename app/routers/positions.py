"""Position tracking router: latest positions, history, trigger check."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.user import User
from app.services import position_service
from app.services.site_service import get_site
from app.tasks.position_tasks import check_positions as _check_positions_task

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("/sites/{site_id}")
async def latest_positions(
    site_id: uuid.UUID,
    engine: str | None = None,
    top_n: int | None = None,
    region: str | None = None,
    limit: int = 500,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Get latest position per keyword for a site."""
    rows = await position_service.get_latest_positions(
        db, site_id, engine=engine, top_n=top_n, region=region,
        limit=limit, offset=offset,
    )
    return {"site_id": str(site_id), "count": len(rows), "positions": rows}


@router.get("/keywords/{keyword_id}/history")
async def position_history(
    keyword_id: uuid.UUID,
    engine: str = "google",
    days: int = 90,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Get position history for a keyword (for Chart.js)."""
    history = await position_service.get_position_history(db, keyword_id, engine, days)
    return {"keyword_id": str(keyword_id), "engine": engine, "days": days, "history": history}


@router.post("/sites/{site_id}/check", status_code=status.HTTP_202_ACCEPTED)
async def trigger_position_check(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Trigger async position check for all keywords of a site."""
    site = await get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    task = _check_positions_task.delay(str(site_id))
    return {"task_id": task.id, "site_id": str(site_id)}
