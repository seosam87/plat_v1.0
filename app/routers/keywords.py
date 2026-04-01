import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.user import User
from app.services import keyword_service

router = APIRouter(prefix="/keywords", tags=["keywords"])


class KeywordCreate(BaseModel):
    phrase: str
    frequency: int | None = None
    region: str | None = None
    engine: str | None = None
    target_url: str | None = None
    group_id: uuid.UUID | None = None


class KeywordOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    phrase: str
    frequency: int | None
    region: str | None
    engine: str | None
    target_url: str | None
    group_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class GroupOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None

    model_config = {"from_attributes": True}


@router.post(
    "/sites/{site_id}",
    response_model=KeywordOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_keyword(
    site_id: uuid.UUID,
    payload: KeywordCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> KeywordOut:
    kw = await keyword_service.add_keyword(
        db,
        site_id=site_id,
        phrase=payload.phrase,
        frequency=payload.frequency,
        region=payload.region,
        engine=payload.engine,
        target_url=payload.target_url,
        group_id=payload.group_id,
    )
    await db.commit()
    return KeywordOut.model_validate(kw)


@router.get("/sites/{site_id}", response_model=list[KeywordOut])
async def list_keywords(
    site_id: uuid.UUID,
    group_id: uuid.UUID | None = None,
    limit: int = 500,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[KeywordOut]:
    keywords = await keyword_service.list_keywords(
        db, site_id, group_id=group_id, limit=limit, offset=offset
    )
    return [KeywordOut.model_validate(k) for k in keywords]


@router.get("/sites/{site_id}/count")
async def count_keywords(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    count = await keyword_service.count_keywords(db, site_id)
    return {"site_id": str(site_id), "count": count}


@router.delete("/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    keyword_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> None:
    kw = await keyword_service.get_keyword(db, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    await keyword_service.delete_keyword(db, kw)
    await db.commit()


@router.get("/sites/{site_id}/groups", response_model=list[GroupOut])
async def list_groups(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[GroupOut]:
    groups = await keyword_service.list_groups(db, site_id)
    return [GroupOut.model_validate(g) for g in groups]
