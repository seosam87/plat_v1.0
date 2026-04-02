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


@router.get("/sites/{site_id}/distribution")
async def position_distribution(
    site_id: uuid.UUID,
    engine: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Get keyword distribution across TOP-3/10/30/100."""
    dist = await position_service.get_position_distribution(db, site_id, engine=engine)
    return {"site_id": str(site_id), **dist}


@router.get("/sites/{site_id}/lost-gained")
async def lost_gained(
    site_id: uuid.UUID,
    days: int = 7,
    engine: str | None = None,
    threshold: int = 10,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Find keywords that entered or left the TOP-N."""
    result = await position_service.get_lost_gained_keywords(
        db, site_id, days=days, engine=engine, threshold=threshold
    )
    return {"site_id": str(site_id), "days": days, "threshold": threshold, **result}


@router.get("/sites/{site_id}/compare")
async def compare_dates(
    site_id: uuid.UUID,
    date_a: str,
    date_b: str,
    engine: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Compare positions between two dates."""
    rows = await position_service.compare_positions_by_date(
        db, site_id, date_a, date_b, engine=engine
    )
    return {"site_id": str(site_id), "date_a": date_a, "date_b": date_b, "count": len(rows), "positions": rows}


@router.get("/sites/{site_id}/by-url")
async def positions_by_url(
    site_id: uuid.UUID,
    url: str,
    engine: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Get positions filtered by ranking URL."""
    rows = await position_service.get_positions_by_url(
        db, site_id, url, engine=engine
    )
    return {"site_id": str(site_id), "url_filter": url, "count": len(rows), "positions": rows}


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


@router.get("/tasks/{task_id}/status")
async def get_task_status(
    task_id: str,
    _: User = Depends(require_admin),
) -> dict:
    """Poll Celery task status for position check progress."""
    from app.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    response: dict = {"task_id": task_id, "status": result.status}
    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.result)
    return response


# ---- Position Schedule endpoints ----


@router.get("/sites/{site_id}/schedule")
async def get_position_schedule(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Get position check schedule for a site."""
    from app.services.schedule_service import get_position_schedule as _get_pos_schedule

    schedule = await _get_pos_schedule(db, site_id)
    if not schedule:
        return {"site_id": str(site_id), "schedule_type": "manual", "is_active": False}
    return {
        "site_id": str(site_id),
        "schedule_type": schedule.schedule_type.value,
        "cron_expression": schedule.cron_expression,
        "is_active": schedule.is_active,
    }


@router.put("/sites/{site_id}/schedule")
async def update_position_schedule(
    site_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Update position check schedule (manual / daily / weekly / every_12h)."""
    from app.models.schedule import ScheduleType
    from app.services.schedule_service import upsert_position_schedule
    from app.services.site_service import get_site as _get_site

    site = await _get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    schedule_type_str = body.get("schedule_type", "manual")
    try:
        schedule_type = ScheduleType(schedule_type_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid schedule_type: {schedule_type_str}")

    schedule = await upsert_position_schedule(db, site_id, schedule_type)
    await db.commit()

    return {
        "site_id": str(site_id),
        "schedule_type": schedule.schedule_type.value,
        "cron_expression": schedule.cron_expression,
        "is_active": schedule.is_active,
    }
