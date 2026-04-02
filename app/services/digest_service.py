"""Digest service: build weekly digest, schedule management via redbeat."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from celery.schedules import crontab
from loguru import logger
from redbeat import RedBeatSchedulerEntry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.models.change_monitoring import ChangeAlert, DigestSchedule

REDBEAT_DIGEST_PREFIX = "digest-schedule:"


# ---- Pure helpers ----


def compute_digest_cron(day_of_week: int, hour: int, minute: int) -> str:
    """Convert user-facing day_of_week (1=Mon..7=Sun) to cron expression.

    Cron format: minute hour * * day_of_week (0=Sun in cron).
    """
    cron_dow = day_of_week % 7  # 1→1(Mon), ..., 7→0(Sun)
    return f"{minute} {hour} * * {cron_dow}"


# ---- Digest builder (sync for Celery) ----


def build_digest(db: Session, site_id: uuid.UUID, days: int = 7) -> dict:
    """Collect changes for a site over the last N days."""
    from app.models.site import Site

    site = db.execute(
        select(Site).where(Site.id == site_id)
    ).scalar_one_or_none()
    site_name = site.name if site else "Unknown"

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    alerts = db.execute(
        select(ChangeAlert)
        .where(ChangeAlert.site_id == site_id, ChangeAlert.created_at >= cutoff)
        .order_by(ChangeAlert.created_at.desc())
    ).scalars().all()

    period_start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    period_end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    result: dict = {
        "site_id": str(site_id),
        "site_name": site_name,
        "period": f"{period_start} – {period_end}",
        "error": [],
        "warning": [],
        "info": [],
        "total": len(alerts),
    }

    for a in alerts:
        sev = a.severity.value if hasattr(a.severity, "value") else a.severity
        ct = a.change_type.value if hasattr(a.change_type, "value") else a.change_type
        entry = {
            "change_type": ct,
            "page_url": a.page_url,
            "details": a.details or "",
            "severity": sev,
        }
        if sev in result:
            result[sev].append(entry)

    return result


def send_digest(db: Session, site_id: uuid.UUID) -> dict:
    """Build and send weekly digest via Telegram."""
    from app.services.telegram_service import format_weekly_digest, send_message_sync

    data = build_digest(db, site_id)
    all_changes = data["error"] + data["warning"] + data["info"]
    msg = format_weekly_digest(data["site_name"], all_changes, data["period"])
    sent = send_message_sync(msg)

    return {"sent": sent, "total_changes": data["total"]}


# ---- Schedule management (async for FastAPI) ----


async def get_digest_schedule(
    db: AsyncSession, site_id: uuid.UUID
) -> DigestSchedule | None:
    result = await db.execute(
        select(DigestSchedule).where(DigestSchedule.site_id == site_id)
    )
    return result.scalar_one_or_none()


async def upsert_digest_schedule(
    db: AsyncSession,
    site_id: uuid.UUID,
    is_active: bool,
    day_of_week: int = 1,
    hour: int = 9,
    minute: int = 0,
) -> DigestSchedule:
    """Create or update digest schedule and sync to redbeat."""
    cron_expr = compute_digest_cron(day_of_week, hour, minute)

    result = await db.execute(
        select(DigestSchedule).where(DigestSchedule.site_id == site_id)
    )
    sched = result.scalar_one_or_none()

    if sched:
        sched.is_active = is_active
        sched.day_of_week = day_of_week
        sched.hour = hour
        sched.minute = minute
        sched.cron_expression = cron_expr
    else:
        sched = DigestSchedule(
            site_id=site_id,
            is_active=is_active,
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            cron_expression=cron_expr,
        )
        db.add(sched)

    await db.flush()

    # Sync to redbeat
    if is_active:
        register_digest_beat(str(site_id), cron_expr)
    else:
        remove_digest_beat(str(site_id))

    return sched


# ---- redbeat integration ----


def _redbeat_key(site_id: str) -> str:
    return f"{REDBEAT_DIGEST_PREFIX}{site_id}"


def register_digest_beat(site_id: str, cron_expression: str) -> None:
    """Register a redbeat entry for weekly digest."""
    key = _redbeat_key(site_id)
    parts = cron_expression.split()
    if len(parts) != 5:
        logger.warning("Invalid cron expression for digest", cron=cron_expression)
        return

    try:
        # Remove existing entry
        try:
            existing = RedBeatSchedulerEntry.from_key(key, app=celery_app)
            existing.delete()
        except KeyError:
            pass

        schedule = crontab(
            minute=parts[0],
            hour=parts[1],
            day_of_month=parts[2],
            month_of_year=parts[3],
            day_of_week=parts[4],
        )
        entry = RedBeatSchedulerEntry(
            name=key,
            task="app.tasks.digest_tasks.send_weekly_digest",
            schedule=schedule,
            args=[site_id],
            app=celery_app,
        )
        entry.save()
        logger.info("Digest beat registered", site_id=site_id, cron=cron_expression)
    except Exception as exc:
        logger.warning("Failed to register digest beat", site_id=site_id, error=str(exc))


def remove_digest_beat(site_id: str) -> None:
    """Remove redbeat entry for digest."""
    key = _redbeat_key(site_id)
    try:
        entry = RedBeatSchedulerEntry.from_key(key, app=celery_app)
        entry.delete()
        logger.info("Digest beat removed", site_id=site_id)
    except KeyError:
        pass
    except Exception as exc:
        logger.warning("Failed to remove digest beat", site_id=site_id, error=str(exc))


def restore_digest_schedules_from_db() -> None:
    """Restore all active digest schedules on Beat startup."""
    from app.database import get_sync_db

    with get_sync_db() as db:
        schedules = db.execute(
            select(DigestSchedule).where(DigestSchedule.is_active == True)  # noqa: E712
        ).scalars().all()

        for s in schedules:
            if s.cron_expression:
                register_digest_beat(str(s.site_id), s.cron_expression)

        logger.info("Restored digest schedules", count=len(schedules))
