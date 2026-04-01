"""Competitor router: CRUD, position comparison, SERP overlap detection."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.user import User
from app.services import competitor_service

router = APIRouter(prefix="/competitors", tags=["competitors"])


class CompetitorCreate(BaseModel):
    domain: str
    name: str | None = None
    notes: str | None = None


@router.post("/sites/{site_id}", status_code=status.HTTP_201_CREATED)
async def create_competitor(
    site_id: uuid.UUID,
    payload: CompetitorCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    c = await competitor_service.create_competitor(
        db, site_id, payload.domain, payload.name, payload.notes
    )
    await db.commit()
    return {"id": str(c.id), "domain": c.domain, "name": c.name}


@router.get("/sites/{site_id}")
async def list_competitors(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    comps = await competitor_service.list_competitors(db, site_id)
    return [{"id": str(c.id), "domain": c.domain, "name": c.name, "notes": c.notes} for c in comps]


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(
    competitor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    c = await competitor_service.get_competitor(db, competitor_id)
    if not c:
        raise HTTPException(status_code=404, detail="Competitor not found")
    await competitor_service.delete_competitor(db, c)
    await db.commit()


@router.get("/sites/{site_id}/compare/{competitor_id}")
async def compare_with_competitor(
    site_id: uuid.UUID,
    competitor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Compare our positions vs a competitor."""
    c = await competitor_service.get_competitor(db, competitor_id)
    if not c:
        raise HTTPException(status_code=404, detail="Competitor not found")
    rows = await competitor_service.compare_positions(db, site_id, c.domain)
    return {
        "site_id": str(site_id),
        "competitor": c.domain,
        "count": len(rows),
        "positions": rows,
    }


@router.get("/sites/{site_id}/detect")
async def detect_competitors(
    site_id: uuid.UUID,
    min_shared: int = 3,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Auto-detect competitors from SERP data."""
    detected = await competitor_service.detect_serp_competitors(db, site_id, min_shared)
    return {"site_id": str(site_id), "count": len(detected), "competitors": detected}
