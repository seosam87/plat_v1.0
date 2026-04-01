"""Site groups router: CRUD, user assignment, site assignment."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.user import User
from app.services import site_group_service

router = APIRouter(prefix="/site-groups", tags=["site-groups"])


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class UserAssign(BaseModel):
    user_id: uuid.UUID


class SiteAssign(BaseModel):
    site_id: uuid.UUID
    group_id: uuid.UUID | None = None  # None to unassign


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    g = await site_group_service.create_group(db, payload.name, payload.description)
    await db.commit()
    return _group_dict(g)


@router.get("")
async def list_groups(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)) -> list[dict]:
    groups = await site_group_service.list_groups(db)
    result = []
    for g in groups:
        users = await site_group_service.get_group_users(db, g.id)
        result.append({**_group_dict(g), "user_count": len(users)})
    return result


@router.put("/{group_id}")
async def update_group(
    group_id: uuid.UUID, payload: GroupUpdate,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    g = await site_group_service.get_group(db, group_id)
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    g = await site_group_service.update_group(db, g, payload.name, payload.description)
    await db.commit()
    return _group_dict(g)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
):
    g = await site_group_service.get_group(db, group_id)
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    await site_group_service.delete_group(db, g)
    await db.commit()


# ---- User assignment ----

@router.post("/{group_id}/users")
async def add_user_to_group(
    group_id: uuid.UUID, payload: UserAssign,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    await site_group_service.assign_user_to_group(db, payload.user_id, group_id)
    await db.commit()
    return {"status": "assigned", "user_id": str(payload.user_id), "group_id": str(group_id)}


@router.delete("/{group_id}/users/{user_id}")
async def remove_user_from_group(
    group_id: uuid.UUID, user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    await site_group_service.remove_user_from_group(db, user_id, group_id)
    await db.commit()
    return {"status": "removed"}


@router.get("/{group_id}/users")
async def group_users(
    group_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    user_ids = await site_group_service.get_group_users(db, group_id)
    return {"group_id": str(group_id), "user_ids": [str(u) for u in user_ids]}


# ---- Site assignment ----

@router.post("/assign-site")
async def assign_site(
    payload: SiteAssign, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin),
) -> dict:
    await site_group_service.assign_site_to_group(db, payload.site_id, payload.group_id)
    await db.commit()
    return {"status": "assigned", "site_id": str(payload.site_id), "group_id": str(payload.group_id) if payload.group_id else None}


def _group_dict(g) -> dict:
    return {
        "id": str(g.id), "name": g.name, "description": g.description,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }
