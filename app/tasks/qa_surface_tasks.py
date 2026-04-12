"""QA Surface Tracker — periodic overdue scan task.

Per D-03: retest triggered by periodicity (retest_days interval).
Per D-04: no git-diff trigger, no manual trigger — pure Celery Beat.
Follows notification_tasks.py pattern exactly.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.qa_surface_tasks.scan_overdue_surfaces",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=120,
    time_limit=150,
)
def scan_overdue_surfaces(self) -> dict:
    """Scan all active FeatureSurfaces and mark overdue passed checks as needs_retest.

    Only transitions: passed -> needs_retest (when last_tested_at older than retest_days).
    Does NOT touch failed or not_tested checks.
    """
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_run_scan())
        logger.info("QA surface scan complete: {}", result)
        return result
    except Exception as exc:
        logger.error("QA surface scan failed: {}", exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()


async def _run_scan() -> dict:
    from app.services.qa_surface_service import scan_overdue
    return await scan_overdue()


def register_qa_surface_scan_schedule() -> None:
    """Register daily overdue scan in RedBeat (idempotent).

    Called from beat_init signal handler in celery_app.py.
    Runs at 04:00 server time (Europe/Moscow per celery config).
    """
    from celery.schedules import crontab
    from redbeat import RedBeatSchedulerEntry

    key = "qa-surface-scan-daily"
    try:
        RedBeatSchedulerEntry.from_key(f"redbeat:{key}", app=celery_app).delete()
    except KeyError:
        pass
    entry = RedBeatSchedulerEntry(
        name=key,
        task="app.tasks.qa_surface_tasks.scan_overdue_surfaces",
        schedule=crontab(hour=4, minute=0),
        app=celery_app,
    )
    entry.save()
    logger.info("Registered QA surface scan schedule: daily at 04:00")
