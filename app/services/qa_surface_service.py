"""QA Surface Tracker service layer.

Provides CRUD, matrix query, status transitions, and overdue scan logic.
Per D-02: create_feature_surface auto-creates 3 SurfaceCheck child rows.
Per D-03: scan_overdue only transitions `passed` -> `needs_retest`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.qa_surface import CheckStatus, FeatureSurface, Surface, SurfaceCheck


async def create_feature_surface(
    db: AsyncSession,
    slug: str,
    name: str,
    description: str | None,
    retest_days: int,
) -> FeatureSurface:
    """Create a FeatureSurface and auto-create 3 SurfaceCheck child rows.

    Per D-02: one check row per surface (desktop, mobile, telegram).
    """
    feature = FeatureSurface(
        slug=slug,
        name=name,
        description=description,
        retest_days=retest_days,
    )
    db.add(feature)
    await db.flush()  # get feature.id before adding children

    for surface in Surface:
        db.add(
            SurfaceCheck(
                feature_id=feature.id,
                surface=surface,
                status=CheckStatus.not_tested,
            )
        )
    await db.commit()

    # Reload with checks
    result = await db.execute(
        select(FeatureSurface)
        .options(selectinload(FeatureSurface.checks))
        .where(FeatureSurface.id == feature.id)
    )
    return result.scalar_one()


async def list_features_with_checks(db: AsyncSession) -> list[FeatureSurface]:
    """Return all FeatureSurface rows with checks eagerly loaded.

    Single query via selectinload to avoid N+1.
    """
    result = await db.execute(
        select(FeatureSurface)
        .options(selectinload(FeatureSurface.checks))
        .order_by(FeatureSurface.name)
    )
    return list(result.scalars().all())


async def get_feature_by_id(
    db: AsyncSession, feature_id: uuid.UUID
) -> FeatureSurface:
    """Get a single FeatureSurface with checks. Raises 404 if not found."""
    result = await db.execute(
        select(FeatureSurface)
        .options(selectinload(FeatureSurface.checks))
        .where(FeatureSurface.id == feature_id)
    )
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature surface not found")
    return feature


async def get_feature_by_slug(
    db: AsyncSession, slug: str
) -> FeatureSurface | None:
    """Get a single FeatureSurface by slug with checks. Returns None if not found."""
    result = await db.execute(
        select(FeatureSurface)
        .options(selectinload(FeatureSurface.checks))
        .where(FeatureSurface.slug == slug)
    )
    return result.scalar_one_or_none()


async def update_feature_surface(
    db: AsyncSession,
    feature_id: uuid.UUID,
    name: str,
    slug: str,
    description: str | None,
    retest_days: int,
) -> FeatureSurface:
    """Update parent FeatureSurface fields only (not child checks)."""
    feature = await get_feature_by_id(db, feature_id)
    feature.name = name
    feature.slug = slug
    feature.description = description
    feature.retest_days = retest_days
    feature.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(feature)
    return feature


async def delete_feature_surface(
    db: AsyncSession, feature_id: uuid.UUID
) -> None:
    """Delete a FeatureSurface (cascade deletes all child SurfaceCheck rows)."""
    feature = await get_feature_by_id(db, feature_id)
    await db.delete(feature)
    await db.commit()


async def get_check_by_id(
    db: AsyncSession, check_id: uuid.UUID
) -> SurfaceCheck:
    """Get a single SurfaceCheck. Raises 404 if not found."""
    result = await db.execute(
        select(SurfaceCheck).where(SurfaceCheck.id == check_id)
    )
    check = result.scalar_one_or_none()
    if check is None:
        raise HTTPException(status_code=404, detail="Surface check not found")
    return check


async def mark_check_tested(
    db: AsyncSession,
    check_id: uuid.UUID,
    status: CheckStatus,
    notes: str | None,
    tested_by: str | None,
) -> SurfaceCheck:
    """Set status, last_tested_at=now(utc), notes, tested_by on a SurfaceCheck."""
    check = await get_check_by_id(db, check_id)
    check.status = status
    check.last_tested_at = datetime.now(timezone.utc)
    check.notes = notes
    check.tested_by = tested_by
    check.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(check)
    return check


async def scan_overdue() -> dict:
    """Scan all active FeatureSurfaces and mark overdue `passed` checks as `needs_retest`.

    Per D-03: ONLY transitions `passed` -> `needs_retest`.
    - `failed` checks remain `failed` (actively broken, not just stale)
    - `not_tested` checks remain `not_tested` (no baseline yet)
    - A `passed` check is overdue if last_tested_at is None OR older than now - retest_days

    Opens its own AsyncSessionLocal session (called from Celery task).
    Returns {"status": "ok", "marked": N}
    """
    now = datetime.now(timezone.utc)
    marked = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FeatureSurface)
            .options(selectinload(FeatureSurface.checks))
            .where(FeatureSurface.is_active.is_(True))
        )
        features = result.scalars().all()

        for feature in features:
            deadline = now - timedelta(days=feature.retest_days)
            for check in feature.checks:
                if check.status == CheckStatus.passed:
                    if (
                        check.last_tested_at is None
                        or check.last_tested_at < deadline
                    ):
                        check.status = CheckStatus.needs_retest
                        check.updated_at = now
                        marked += 1

        await db.commit()

    return {"status": "ok", "marked": marked}
