"""Yandex Webmaster router + SERP usage."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.user import User
from app.services import yandex_webmaster_service
from app.services.serp_parser_service import get_daily_usage

router = APIRouter(prefix="/yandex", tags=["yandex"])


@router.get("/status")
async def yandex_status(_: User = Depends(require_admin)) -> dict:
    configured = yandex_webmaster_service.is_configured()
    user_id = None
    if configured:
        try:
            user_id = await yandex_webmaster_service.get_user_id()
        except Exception:
            pass
    return {"configured": configured, "user_id": user_id}


@router.get("/hosts")
async def list_hosts(_: User = Depends(require_admin)) -> dict:
    if not yandex_webmaster_service.is_configured():
        raise HTTPException(status_code=400, detail="Yandex Webmaster not configured")
    user_id = await yandex_webmaster_service.get_user_id()
    if not user_id:
        raise HTTPException(status_code=400, detail="Cannot get Yandex user_id")
    hosts = await yandex_webmaster_service.list_hosts(user_id)
    return {"user_id": user_id, "hosts": hosts}


class FetchRequest(BaseModel):
    host_id: str
    days: int = 28


@router.post("/queries")
async def fetch_queries(
    payload: FetchRequest,
    _: User = Depends(require_admin),
) -> dict:
    if not yandex_webmaster_service.is_configured():
        raise HTTPException(status_code=400, detail="Yandex Webmaster not configured")
    user_id = await yandex_webmaster_service.get_user_id()
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=payload.days)
    rows = await yandex_webmaster_service.fetch_search_queries(
        user_id, payload.host_id, start.isoformat(), end.isoformat()
    )
    return {
        "host_id": payload.host_id,
        "period": f"{start} — {end}",
        "row_count": len(rows),
        "rows": rows[:100],
    }


@router.get("/serp/usage")
async def serp_usage(_: User = Depends(require_admin)) -> dict:
    return get_daily_usage()
