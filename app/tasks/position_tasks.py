"""Celery tasks for automated position checking."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger

from app.celery_app import celery_app
from app.tasks.wp_tasks import site_active_guard


@celery_app.task(
    name="app.tasks.position_tasks.check_positions",
    bind=True,
    max_retries=3,
    soft_time_limit=600,
    time_limit=660,
)
def check_positions(self, site_id: str) -> dict:
    """Check positions for all keywords of a site using available sources.

    Priority: DataForSEO (batch) → GSC → Yandex Webmaster.
    Writes results to keyword_positions table.
    """
    skip = site_active_guard(site_id)
    if skip:
        return skip

    from app.database import get_sync_db
    from app.models.keyword import Keyword
    from app.services.position_service import write_position_sync
    from sqlalchemy import select

    with get_sync_db() as db:
        keywords = db.execute(
            select(Keyword).where(Keyword.site_id == uuid.UUID(site_id))
        ).scalars().all()

    if not keywords:
        return {"status": "skipped", "reason": "no keywords", "site_id": site_id}

    logger.info("Position check started", site_id=site_id, keywords=len(keywords))

    # Try DataForSEO first (batch)
    from app.config import settings
    written = 0

    if settings.DATAFORSEO_LOGIN and settings.DATAFORSEO_PASSWORD:
        written = _check_via_dataforseo(site_id, keywords)
    else:
        logger.info("DataForSEO not configured, skipping", site_id=site_id)

    # Playwright SERP fallback for remaining (if under daily limit)
    if written == 0:
        written = _check_via_serp_parser(site_id, keywords)

    # Check for position drops and send Telegram alerts
    alerts_sent = _send_drop_alerts(site_id)

    logger.info("Position check done", site_id=site_id, written=written, alerts=alerts_sent)
    return {"status": "done", "site_id": site_id, "positions_written": written, "alerts_sent": alerts_sent}


def _check_via_dataforseo(site_id: str, keywords) -> int:
    """Batch check via DataForSEO SERP API (sync wrapper)."""
    import asyncio
    from app.services.dataforseo_service import fetch_serp_batch
    from app.database import get_sync_db
    from app.services.position_service import write_position_sync
    from app.models.site import Site
    from sqlalchemy import select

    with get_sync_db() as db:
        site = db.execute(select(Site).where(Site.id == uuid.UUID(site_id))).scalar_one_or_none()

    if not site:
        return 0

    site_domain = site.url.rstrip("/").replace("https://", "").replace("http://", "")

    batch = [{"keyword": kw.phrase, "location_code": 2643, "language_code": "ru"} for kw in keywords[:100]]

    try:
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(fetch_serp_batch(batch))
        loop.close()
    except Exception as exc:
        logger.warning("DataForSEO batch failed", error=str(exc))
        return 0

    # Match results back to keywords and find position for our domain
    kw_map = {kw.phrase.lower(): kw for kw in keywords}
    written = 0

    with get_sync_db() as db:
        for result in results:
            query = result.get("keyword", "").lower()
            kw = kw_map.get(query)
            if not kw:
                continue

            # Find our site's position in SERP results
            position = None
            url = None
            for item in result.get("results", []):
                if site_domain in (item.get("url") or ""):
                    position = item.get("position")
                    url = item.get("url")
                    break

            engine_str = kw.engine.value if kw.engine else "google"
            write_position_sync(
                db, kw.id, uuid.UUID(site_id), engine_str, position, url=url
            )
            written += 1

    return written


def _check_via_serp_parser(site_id: str, keywords) -> int:
    """Fallback: Playwright SERP parser (respects daily limit)."""
    from app.services.serp_parser_service import parse_serp_sync, _check_daily_limit
    from app.database import get_sync_db
    from app.services.position_service import write_position_sync
    from app.models.site import Site
    from sqlalchemy import select

    with get_sync_db() as db:
        site = db.execute(select(Site).where(Site.id == uuid.UUID(site_id))).scalar_one_or_none()

    if not site:
        return 0

    site_domain = site.url.rstrip("/").replace("https://", "").replace("http://", "")
    written = 0

    for kw in keywords:
        if not _check_daily_limit():
            logger.info("SERP daily limit reached, stopping", written=written)
            break

        engine_str = kw.engine.value if kw.engine else "google"
        serp_data = parse_serp_sync(kw.phrase, engine=engine_str)
        results = serp_data.get("results", []) if isinstance(serp_data, dict) else serp_data
        position = None
        url = None
        for item in results:
            if site_domain in (item.get("url") or ""):
                position = item.get("position")
                url = item.get("url")
                break

        with get_sync_db() as db:
            write_position_sync(
                db, kw.id, uuid.UUID(site_id), engine_str, position, url=url
            )
            written += 1

    return written


def _send_drop_alerts(site_id: str) -> int:
    """Check recent positions for drops exceeding threshold, send Telegram alerts."""
    from app.config import settings
    from app.services.telegram_service import is_configured, send_message_sync, format_position_drop_alert

    if not is_configured():
        return 0

    threshold = settings.POSITION_DROP_THRESHOLD
    from app.database import get_sync_db
    from app.models.position import KeywordPosition
    from app.models.keyword import Keyword
    from app.models.site import Site
    from sqlalchemy import select
    from datetime import timedelta

    alerts = 0
    with get_sync_db() as db:
        site = db.execute(select(Site).where(Site.id == uuid.UUID(site_id))).scalar_one_or_none()
        if not site:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = db.execute(
            select(KeywordPosition).where(
                KeywordPosition.site_id == uuid.UUID(site_id),
                KeywordPosition.checked_at >= cutoff,
                KeywordPosition.delta != None,
            )
        ).scalars().all()

        for pos in recent:
            if pos.delta is not None and pos.delta < -threshold:
                kw = db.execute(
                    select(Keyword).where(Keyword.id == pos.keyword_id)
                ).scalar_one_or_none()
                keyword_text = kw.phrase if kw else str(pos.keyword_id)
                msg = format_position_drop_alert(
                    site.name, keyword_text,
                    pos.previous_position, pos.position,
                    url=pos.url,
                )
                if send_message_sync(msg):
                    alerts += 1

    return alerts
