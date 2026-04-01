"""Crawl schedule service — CRUD + redbeat synchronisation."""
from __future__ import annotations

import uuid

from loguru import logger
from redbeat import RedBeatSchedulerEntry
from celery.schedules import crontab
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.models.schedule import CrawlSchedule, PositionSchedule, ScheduleType

# Map schedule_type → cron expression + celery crontab kwargs
_CRON_MAP: dict[ScheduleType, tuple[str, dict]] = {
    ScheduleType.daily: ("0 3 * * *", {"minute": "0", "hour": "3"}),
    ScheduleType.weekly: ("0 3 * * 1", {"minute": "0", "hour": "3", "day_of_week": "1"}),
    ScheduleType.every_12h: ("0 3,15 * * *", {"minute": "0", "hour": "3,15"}),
}

REDBEAT_KEY_PREFIX = "crawl-schedule:"


def _redbeat_key(site_id: uuid.UUID) -> str:
    return f"{REDBEAT_KEY_PREFIX}{site_id}"


def _schedule_to_crontab(schedule_type: ScheduleType) -> crontab | None:
    """Return a celery crontab for the given schedule type, or None for manual."""
    entry = _CRON_MAP.get(schedule_type)
    if entry is None:
        return None
    _, kwargs = entry
    return crontab(**kwargs)


def _cron_expression(schedule_type: ScheduleType) -> str | None:
    entry = _CRON_MAP.get(schedule_type)
    return entry[0] if entry else None


# ---- redbeat sync ----

def sync_schedule_to_redbeat(site_id: uuid.UUID, schedule_type: ScheduleType, is_active: bool) -> None:
    """Create or update (or remove) a redbeat entry for a site's crawl schedule."""
    key = _redbeat_key(site_id)

    if schedule_type == ScheduleType.manual or not is_active:
        # Remove existing entry if any
        try:
            entry = RedBeatSchedulerEntry.from_key(key, app=celery_app)
            entry.delete()
            logger.info("Removed redbeat entry", key=key)
        except KeyError:
            pass
        return

    schedule = _schedule_to_crontab(schedule_type)
    if schedule is None:
        return

    entry = RedBeatSchedulerEntry(
        name=key,
        task="app.tasks.crawl_tasks.crawl_site",
        schedule=schedule,
        args=[str(site_id)],
        app=celery_app,
    )
    entry.save()
    logger.info("Synced redbeat entry", key=key, schedule_type=schedule_type)


def remove_redbeat_entry(site_id: uuid.UUID) -> None:
    """Remove a redbeat entry for a site (e.g. when site is deleted)."""
    key = _redbeat_key(site_id)
    try:
        entry = RedBeatSchedulerEntry.from_key(key, app=celery_app)
        entry.delete()
    except KeyError:
        pass


# ---- DB CRUD (async) ----

async def get_schedule(db: AsyncSession, site_id: uuid.UUID) -> CrawlSchedule | None:
    result = await db.execute(
        select(CrawlSchedule).where(CrawlSchedule.site_id == site_id)
    )
    return result.scalar_one_or_none()


async def get_all_schedules(db: AsyncSession) -> list[CrawlSchedule]:
    result = await db.execute(select(CrawlSchedule))
    return list(result.scalars().all())


async def upsert_schedule(
    db: AsyncSession,
    site_id: uuid.UUID,
    schedule_type: ScheduleType,
) -> CrawlSchedule:
    """Create or update the crawl schedule for a site, then sync to redbeat."""
    schedule = await get_schedule(db, site_id)
    cron_expr = _cron_expression(schedule_type)

    if schedule is None:
        schedule = CrawlSchedule(
            site_id=site_id,
            schedule_type=schedule_type,
            cron_expression=cron_expr,
        )
        db.add(schedule)
    else:
        schedule.schedule_type = schedule_type
        schedule.cron_expression = cron_expr

    await db.flush()

    # Sync to redbeat
    sync_schedule_to_redbeat(site_id, schedule_type, schedule.is_active)

    return schedule


async def set_schedule_active(
    db: AsyncSession, site_id: uuid.UUID, is_active: bool
) -> CrawlSchedule | None:
    """Activate / deactivate a schedule (e.g. when site is disabled)."""
    schedule = await get_schedule(db, site_id)
    if schedule is None:
        return None
    schedule.is_active = is_active
    await db.flush()
    sync_schedule_to_redbeat(site_id, schedule.schedule_type, is_active)
    return schedule


# ---- Boot-time restore ----

def restore_schedules_from_db() -> None:
    """Load all active schedules from PostgreSQL and sync to redbeat.

    Called at Beat startup so schedules survive Redis FLUSHALL.
    Uses a sync DB session since Beat startup is synchronous.
    """
    from app.database import get_sync_db
    from sqlalchemy import select as sa_select

    with get_sync_db() as db:
        rows = db.execute(
            sa_select(CrawlSchedule).where(
                CrawlSchedule.is_active.is_(True),
                CrawlSchedule.schedule_type != ScheduleType.manual,
            )
        ).scalars().all()

    restored = 0
    for row in rows:
        sync_schedule_to_redbeat(row.site_id, row.schedule_type, True)
        restored += 1

    logger.info("Restored crawl schedules from DB", count=restored)


# ---- Position schedule: redbeat sync ----

POSITION_REDBEAT_KEY_PREFIX = "position-schedule:"


def _position_redbeat_key(site_id: uuid.UUID) -> str:
    return f"{POSITION_REDBEAT_KEY_PREFIX}{site_id}"


def sync_position_schedule_to_redbeat(
    site_id: uuid.UUID, schedule_type: ScheduleType, is_active: bool
) -> None:
    """Create or update (or remove) a redbeat entry for a site's position check schedule."""
    key = _position_redbeat_key(site_id)

    if schedule_type == ScheduleType.manual or not is_active:
        try:
            entry = RedBeatSchedulerEntry.from_key(key, app=celery_app)
            entry.delete()
            logger.info("Removed position redbeat entry", key=key)
        except KeyError:
            pass
        return

    schedule = _schedule_to_crontab(schedule_type)
    if schedule is None:
        return

    entry = RedBeatSchedulerEntry(
        name=key,
        task="app.tasks.position_tasks.check_positions",
        schedule=schedule,
        args=[str(site_id)],
        app=celery_app,
    )
    entry.save()
    logger.info("Synced position redbeat entry", key=key, schedule_type=schedule_type)


def remove_position_redbeat_entry(site_id: uuid.UUID) -> None:
    """Remove position redbeat entry for a site (e.g. when site is deleted)."""
    key = _position_redbeat_key(site_id)
    try:
        entry = RedBeatSchedulerEntry.from_key(key, app=celery_app)
        entry.delete()
    except KeyError:
        pass


# ---- Position schedule: DB CRUD (async) ----


async def get_position_schedule(
    db: AsyncSession, site_id: uuid.UUID
) -> PositionSchedule | None:
    result = await db.execute(
        select(PositionSchedule).where(PositionSchedule.site_id == site_id)
    )
    return result.scalar_one_or_none()


async def upsert_position_schedule(
    db: AsyncSession,
    site_id: uuid.UUID,
    schedule_type: ScheduleType,
) -> PositionSchedule:
    """Create or update position check schedule for a site, then sync to redbeat."""
    schedule = await get_position_schedule(db, site_id)
    cron_expr = _cron_expression(schedule_type)

    if schedule is None:
        schedule = PositionSchedule(
            site_id=site_id,
            schedule_type=schedule_type,
            cron_expression=cron_expr,
        )
        db.add(schedule)
    else:
        schedule.schedule_type = schedule_type
        schedule.cron_expression = cron_expr

    await db.flush()
    sync_position_schedule_to_redbeat(site_id, schedule_type, schedule.is_active)
    return schedule


async def set_position_schedule_active(
    db: AsyncSession, site_id: uuid.UUID, is_active: bool
) -> PositionSchedule | None:
    """Activate / deactivate position schedule."""
    schedule = await get_position_schedule(db, site_id)
    if schedule is None:
        return None
    schedule.is_active = is_active
    await db.flush()
    sync_position_schedule_to_redbeat(site_id, schedule.schedule_type, is_active)
    return schedule


# ---- Boot-time restore for position schedules ----


def restore_position_schedules_from_db() -> None:
    """Load all active position schedules from PostgreSQL and sync to redbeat."""
    from app.database import get_sync_db
    from sqlalchemy import select as sa_select

    with get_sync_db() as db:
        rows = db.execute(
            sa_select(PositionSchedule).where(
                PositionSchedule.is_active.is_(True),
                PositionSchedule.schedule_type != ScheduleType.manual,
            )
        ).scalars().all()

    restored = 0
    for row in rows:
        sync_position_schedule_to_redbeat(row.site_id, row.schedule_type, True)
        restored += 1

    logger.info("Restored position schedules from DB", count=restored)
