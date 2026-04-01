import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.user import User
from app.services import site_service

router = APIRouter(prefix="/sites", tags=["sites"])


class SiteCreate(BaseModel):
    name: str
    url: str
    wp_username: str
    app_password: str


class SiteUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    wp_username: str | None = None
    app_password: str | None = None


class SiteOut(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    wp_username: str
    connection_status: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(
    payload: SiteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> SiteOut:
    site = await site_service.create_site(
        db,
        name=payload.name,
        url=payload.url,
        wp_username=payload.wp_username,
        app_password=payload.app_password,
        actor_id=current_user.id,
    )
    return SiteOut.model_validate(site)


@router.get("", response_model=list[SiteOut])
async def list_sites(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[SiteOut]:
    sites = await site_service.get_sites(db)
    return [SiteOut.model_validate(s) for s in sites]


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SiteOut:
    site = await site_service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteOut.model_validate(site)


@router.put("/{site_id}", response_model=SiteOut)
async def update_site(
    site_id: uuid.UUID,
    payload: SiteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> SiteOut:
    site = await site_service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    site = await site_service.update_site(
        db, site,
        name=payload.name,
        url=payload.url,
        wp_username=payload.wp_username,
        app_password=payload.app_password,
        actor_id=current_user.id,
    )
    return SiteOut.model_validate(site)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    site = await site_service.get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    await site_service.delete_site(db, site, actor_id=current_user.id)
