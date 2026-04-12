from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.yandex_errors import YandexError, YandexErrorStatus, YandexErrorType


async def list_errors(
    db: AsyncSession,
    site_id: uuid.UUID,
    error_type: YandexErrorType,
    status_filter: YandexErrorStatus | None = None,
    limit: int = 5,
    offset: int = 0,
) -> list[YandexError]:
    stmt = select(YandexError).where(
        YandexError.site_id == site_id,
        YandexError.error_type == error_type,
    )
    if status_filter:
        stmt = stmt.where(YandexError.status == status_filter)
    stmt = (
        stmt.order_by(
            # open first, then by detected_at DESC
            YandexError.status.asc(),
            YandexError.detected_at.desc().nulls_last(),
        )
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_errors(
    db: AsyncSession,
    site_id: uuid.UUID,
    error_type: YandexErrorType,
) -> int:
    stmt = select(func.count(YandexError.id)).where(
        YandexError.site_id == site_id,
        YandexError.error_type == error_type,
        YandexError.status == YandexErrorStatus.open,
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def get_error(db: AsyncSession, error_id: uuid.UUID) -> YandexError | None:
    stmt = select(YandexError).where(YandexError.id == error_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def last_fetched_at(db: AsyncSession, site_id: uuid.UUID) -> str | None:
    stmt = select(func.max(YandexError.fetched_at)).where(YandexError.site_id == site_id)
    result = await db.execute(stmt)
    val = result.scalar()
    return val.strftime("%d.%m.%Y %H:%M") if val else None
