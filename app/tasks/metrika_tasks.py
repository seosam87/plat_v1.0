"""Celery tasks for on-demand Metrika data fetching."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.metrika_tasks.fetch_metrika_data",
    bind=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=150,
)
def fetch_metrika_data(self, site_id: str, date1: str, date2: str) -> dict:
    """Fetch Metrika traffic data for a site and save to DB.

    Triggered by user button click (D-08). Fetches daily aggregate
    and per-page traffic for the given date range.
    """
    import asyncio

    from sqlalchemy import select

    from app.database import get_sync_db
    from app.models.site import Site
    from app.services.crypto_service import decrypt

    with get_sync_db() as db:
        site = db.execute(
            select(Site).where(Site.id == uuid.UUID(site_id))
        ).scalar_one_or_none()

    if not site:
        return {"status": "error", "reason": "site not found"}

    if not site.metrika_counter_id or not site.metrika_token:
        return {"status": "error", "reason": "metrika not configured"}

    counter_id = site.metrika_counter_id
    token = decrypt(site.metrika_token)

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            _fetch_and_save(site_id, counter_id, token, date1, date2)
        )
        loop.close()
        return result
    except Exception as exc:
        logger.error("Metrika fetch failed", site_id=site_id, error=str(exc))
        if "420" in str(exc) or "429" in str(exc):
            raise self.retry(countdown=60, exc=exc)
        raise self.retry(countdown=10, exc=exc)


async def _fetch_and_save(
    site_id: str, counter_id: str, token: str, date1: str, date2: str
) -> dict:
    """Async inner function: fetch from API and persist to DB."""
    from datetime import date as date_type

    from app.database import AsyncSessionLocal
    from app.services.metrika_service import (
        fetch_daily_traffic,
        fetch_page_traffic,
        save_daily_snapshots,
        save_page_snapshots,
    )

    daily_rows = await fetch_daily_traffic(counter_id, token, date1, date2)
    page_rows = await fetch_page_traffic(counter_id, token, date1, date2)

    sid = uuid.UUID(site_id)
    p_start = date_type.fromisoformat(date1)
    p_end = date_type.fromisoformat(date2)

    async with AsyncSessionLocal() as db:
        daily_count = await save_daily_snapshots(db, sid, daily_rows)
        page_count = await save_page_snapshots(db, sid, p_start, p_end, page_rows)
        await db.commit()

    logger.info(
        "Metrika data saved",
        site_id=site_id,
        daily_rows=daily_count,
        page_rows=page_count,
    )
    return {
        "status": "done",
        "site_id": site_id,
        "daily_rows": daily_count,
        "page_rows": page_count,
    }
