"""DataForSEO router: SERP check + search volume endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.user import User
from app.services import dataforseo_service

router = APIRouter(prefix="/dataforseo", tags=["dataforseo"])


class SerpRequest(BaseModel):
    keyword: str
    location_code: int = 2840
    language_code: str = "en"


class SerpBatchRequest(BaseModel):
    keywords: list[SerpRequest]


class VolumeRequest(BaseModel):
    keywords: list[str]
    location_code: int = 2840
    language_code: str = "en"


@router.get("/status")
async def dataforseo_status(_: User = Depends(require_admin)) -> dict:
    return {"configured": dataforseo_service.is_configured()}


@router.post("/serp")
async def serp_check(
    payload: SerpRequest,
    _: User = Depends(require_admin),
) -> dict:
    if not dataforseo_service.is_configured():
        raise HTTPException(status_code=400, detail="DataForSEO not configured")
    results = await dataforseo_service.fetch_serp(
        payload.keyword, payload.location_code, payload.language_code
    )
    return {"keyword": payload.keyword, "results": results}


@router.post("/serp/batch")
async def serp_batch(
    payload: SerpBatchRequest,
    _: User = Depends(require_admin),
) -> dict:
    if not dataforseo_service.is_configured():
        raise HTTPException(status_code=400, detail="DataForSEO not configured")
    results = await dataforseo_service.fetch_serp_batch(
        [kw.model_dump() for kw in payload.keywords]
    )
    return {"results": results}


@router.post("/volume")
async def search_volume(
    payload: VolumeRequest,
    _: User = Depends(require_admin),
) -> dict:
    if not dataforseo_service.is_configured():
        raise HTTPException(status_code=400, detail="DataForSEO not configured")
    results = await dataforseo_service.fetch_search_volume(
        payload.keywords, payload.location_code, payload.language_code
    )
    return {"results": results}
