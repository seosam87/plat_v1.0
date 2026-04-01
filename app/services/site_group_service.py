"""Site group service: CRUD + user access management."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site import Site
from app.models.site_group import SiteGroup, user_site_groups
from app.models.user import User, UserRole


async def create_group(db: AsyncSession, name: str, description: str | None = None) -> SiteGroup:
    group = SiteGroup(name=name, description=description)
    db.add(group)
    await db.flush()
    return group


async def list_groups(db: AsyncSession) -> list[SiteGroup]:
    result = await db.execute(select(SiteGroup).order_by(SiteGroup.name))
    return list(result.scalars().all())


async def get_group(db: AsyncSession, group_id: uuid.UUID) -> SiteGroup | None:
    result = await db.execute(select(SiteGroup).where(SiteGroup.id == group_id))
    return result.scalar_one_or_none()


async def update_group(db: AsyncSession, group: SiteGroup, name: str | None = None, description: str | None = None) -> SiteGroup:
    if name is not None:
        group.name = name
    if description is not None:
        group.description = description
    await db.flush()
    return group


async def delete_group(db: AsyncSession, group: SiteGroup) -> None:
    await db.delete(group)


# ---- User ↔ Group assignment ----

async def assign_user_to_group(db: AsyncSession, user_id: uuid.UUID, group_id: uuid.UUID) -> None:
    await db.execute(
        user_site_groups.insert().values(user_id=user_id, site_group_id=group_id)
    )
    await db.flush()


async def remove_user_from_group(db: AsyncSession, user_id: uuid.UUID, group_id: uuid.UUID) -> None:
    await db.execute(
        delete(user_site_groups).where(
            user_site_groups.c.user_id == user_id,
            user_site_groups.c.site_group_id == group_id,
        )
    )
    await db.flush()


async def get_user_group_ids(db: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Return list of site_group_ids the user has access to."""
    result = await db.execute(
        select(user_site_groups.c.site_group_id).where(user_site_groups.c.user_id == user_id)
    )
    return [row[0] for row in result.all()]


async def get_group_users(db: AsyncSession, group_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(
        select(user_site_groups.c.user_id).where(user_site_groups.c.site_group_id == group_id)
    )
    return [row[0] for row in result.all()]


# ---- Site assignment ----

async def assign_site_to_group(db: AsyncSession, site_id: uuid.UUID, group_id: uuid.UUID | None) -> None:
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if site:
        site.site_group_id = group_id
        await db.flush()


# ---- Access-filtered site queries ----

async def get_accessible_sites(db: AsyncSession, user: User) -> list[Site]:
    """Return sites visible to a user based on their role and group assignments.

    - admin: sees all sites
    - manager/client: sees only sites in their assigned groups + ungrouped sites (if no groups assigned, sees nothing)
    """
    if user.role == UserRole.admin:
        result = await db.execute(select(Site).order_by(Site.created_at.desc()))
        return list(result.scalars().all())

    group_ids = await get_user_group_ids(db, user.id)
    if not group_ids:
        return []

    result = await db.execute(
        select(Site)
        .where(Site.site_group_id.in_(group_ids))
        .order_by(Site.created_at.desc())
    )
    return list(result.scalars().all())


async def can_access_site(db: AsyncSession, user: User, site_id: uuid.UUID) -> bool:
    """Check if user can access a specific site."""
    if user.role == UserRole.admin:
        return True

    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()
    if not site:
        return False

    if not site.site_group_id:
        return False  # ungrouped sites are admin-only

    group_ids = await get_user_group_ids(db, user.id)
    return site.site_group_id in group_ids
