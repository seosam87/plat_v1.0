"""Celery tasks for automated position checking."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger

from app.celery_app import celery_app
from app.database import get_sync_db
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

    Engine split (per D-17, D-18):
      - engine='yandex' -> XMLProxy (per D-01, only Yandex source)
      - engine='google' or engine=None -> DataForSEO if configured, else logged as skipped

    Returns a dict that always includes a `diagnostics` key with a list of
    {"level": "info"|"warning"|"error", "message": str} entries explaining
    what happened during the check.
    """
    skip = site_active_guard(site_id)
    if skip:
        skip["diagnostics"] = [{"level": "warning", "message": f"Task skipped: {skip.get('reason', 'unknown')}"}]
        return skip

    from app.models.keyword import Keyword
    from app.config import settings
    from sqlalchemy import select

    diagnostics = []  # list of {"level": "info"|"warning"|"error", "message": str}

    with get_sync_db() as db:
        keywords = db.execute(
            select(Keyword).where(Keyword.site_id == uuid.UUID(site_id))
        ).scalars().all()

    if not keywords:
        diagnostics.append({"level": "warning", "message": "No keywords found for this site. Import keywords first."})
        return {"status": "skipped", "reason": "no keywords", "site_id": site_id, "positions_written": 0, "alerts_sent": 0, "diagnostics": diagnostics}

    logger.info("Position check started", site_id=site_id, keywords=len(keywords))

    # Split keywords by engine (per D-17, D-18)
    yandex_kws = [kw for kw in keywords if kw.engine and kw.engine.value == "yandex"]
    google_kws = [kw for kw in keywords if not kw.engine or kw.engine.value == "google"]

    # Diagnostic info about keyword split
    if yandex_kws:
        diagnostics.append({"level": "info", "message": f"Found {len(yandex_kws)} Yandex keyword(s) — will check via XMLProxy"})
    if google_kws:
        diagnostics.append({"level": "info", "message": f"Found {len(google_kws)} Google keyword(s)"})
    if not yandex_kws and not google_kws:
        diagnostics.append({"level": "warning", "message": "Keywords exist but none matched engine filter"})

    written = 0

    # Process Yandex keywords via XMLProxy (per D-01: ONLY source for Yandex)
    if yandex_kws:
        written += _check_via_xmlproxy(self, site_id, yandex_kws, diagnostics)

    # Process Google keywords via DataForSEO or log as skipped (per D-17)
    if google_kws:
        if settings.DATAFORSEO_LOGIN and settings.DATAFORSEO_PASSWORD:
            written += _check_via_dataforseo(site_id, google_kws, diagnostics)
        else:
            # Per D-17: Google parsing out of scope for this phase
            diagnostics.append({"level": "warning", "message": f"{len(google_kws)} Google keyword(s) skipped — DataForSEO not configured. Go to Settings > Data Sources."})
            for kw in google_kws:
                logger.info(
                    "Google keyword skipped: no source configured",
                    phrase=kw.phrase,
                    site_id=site_id,
                )

    # Check for position drops and send Telegram alerts
    alerts_sent = _send_drop_alerts(site_id)

    logger.info("Position check done", site_id=site_id, written=written, alerts=alerts_sent)

    if written == 0 and not diagnostics:
        diagnostics.append({"level": "warning", "message": "Check completed but no positions were recorded. Verify API credentials and keyword configuration."})
    elif written > 0:
        diagnostics.append({"level": "info", "message": f"Successfully recorded {written} position(s)"})

    return {"status": "done", "site_id": site_id, "positions_written": written, "alerts_sent": alerts_sent, "diagnostics": diagnostics}


def _check_via_xmlproxy(self_task, site_id: str, keywords, diagnostics: list | None = None) -> int:
    """Check Yandex positions via XMLProxy. Per D-01, D-02, D-03.

    Args:
        self_task: Celery task instance (for retry).
        site_id: Site UUID as string.
        keywords: List of Keyword model instances with engine='yandex'.
        diagnostics: List to append diagnostic messages to.

    Returns:
        Number of position records written.
    """
    if diagnostics is None:
        diagnostics = []

    from app.services.xmlproxy_service import search_yandex_sync, fetch_balance_sync, XMLProxyError
    from app.services.service_credential_service import get_credential_sync
    from app.services.telegram_service import send_message_sync, is_configured
    from app.services.position_service import write_position_sync
    from app.models.site import Site
    from app.config import settings
    from sqlalchemy import select

    with get_sync_db() as db:
        creds = get_credential_sync(db, "xmlproxy")

    if not creds or not creds.get("user") or not creds.get("key"):
        logger.warning("XMLProxy not configured, skipping Yandex keywords", site_id=site_id)
        diagnostics.append({"level": "error", "message": "XMLProxy credentials not configured. Go to Settings > Data Sources to add XMLProxy user/key."})
        return 0

    user, key = creds["user"], creds["key"]

    # Fetch balance ONCE before loop (per Research pitfall 5 / D-03)
    balance_data = fetch_balance_sync(user, key)
    if balance_data:
        balance = balance_data.get("data", 0)
        if balance <= 0:
            logger.warning("XMLProxy balance zero — skipping Yandex keywords", site_id=site_id)
            diagnostics.append({"level": "error", "message": "XMLProxy balance is 0 RUB. Top up your XMLProxy account."})
            if is_configured():
                send_message_sync(
                    f"XMLProxy balance is 0. Yandex position checks paused for site {site_id}."
                )
            return 0
        threshold = getattr(settings, "XMLPROXY_LOW_BALANCE_THRESHOLD", 50)
        if balance < threshold:
            logger.warning("XMLProxy balance low", balance=balance, threshold=threshold, site_id=site_id)
            diagnostics.append({"level": "warning", "message": f"XMLProxy balance low: {balance} RUB (threshold: {threshold})"})
            if is_configured():
                send_message_sync(
                    f"XMLProxy balance low: {balance} RUB (threshold: {threshold})"
                )

    with get_sync_db() as db:
        site = db.execute(
            select(Site).where(Site.id == uuid.UUID(site_id))
        ).scalar_one_or_none()

    if not site:
        logger.warning("Site not found for XMLProxy check", site_id=site_id)
        diagnostics.append({"level": "error", "message": "Site not found in database"})
        return 0

    site_domain = site.url.rstrip("/").replace("https://", "").replace("http://", "")
    lr = site.yandex_region or 213
    written = 0

    for kw in keywords:
        try:
            result = search_yandex_sync(user, key, kw.phrase, lr=lr)
        except XMLProxyError as e:
            if e.code == -55:
                # Async request — retry after 300s (per D-02)
                logger.info("XMLProxy async (-55) — retrying in 300s", keyword=kw.phrase)
                raise self_task.retry(countdown=300, max_retries=3)
            elif e.code == -32:
                # Insufficient funds — alert and stop
                logger.error("XMLProxy balance zero (-32)", keyword=kw.phrase)
                diagnostics.append({"level": "error", "message": "XMLProxy insufficient funds (error -32). Top up account."})
                if is_configured():
                    send_message_sync("XMLProxy: insufficient funds. Yandex checks stopped.")
                return written
            elif e.code == -34:
                # Invalid credentials
                logger.error("XMLProxy invalid credentials (-34)", keyword=kw.phrase)
                diagnostics.append({"level": "error", "message": "XMLProxy credentials are invalid. Check Settings > Data Sources."})
                if is_configured():
                    send_message_sync("XMLProxy: invalid credentials. Check settings.")
                return written
            elif e.code == -132:
                # Rate limit — skip this keyword and continue
                logger.warning("XMLProxy rate limit (-132), skipping keyword", keyword=kw.phrase)
                continue
            else:
                logger.error("XMLProxy unknown error", code=e.code, msg=e.message, keyword=kw.phrase)
                continue
        except Exception as exc:
            logger.warning("XMLProxy request failed", keyword=kw.phrase, error=str(exc))
            continue

        # Find site position in results
        position = None
        url = None
        for item in result.get("results", []):
            if site_domain in (item.get("url") or ""):
                position = item.get("position")
                url = item.get("url")
                break

        engine_str = "yandex"
        with get_sync_db() as db:
            write_position_sync(db, kw.id, uuid.UUID(site_id), engine_str, position, url=url)
            written += 1

    return written


def _check_via_dataforseo(site_id: str, keywords, diagnostics: list | None = None) -> int:
    """Batch check via DataForSEO SERP API (sync wrapper). Google keywords only."""
    if diagnostics is None:
        diagnostics = []

    import asyncio
    from app.services.dataforseo_service import fetch_serp_batch
    from app.services.position_service import write_position_sync
    from app.models.site import Site
    from sqlalchemy import select

    with get_sync_db() as db:
        site = db.execute(select(Site).where(Site.id == uuid.UUID(site_id))).scalar_one_or_none()

    if not site:
        diagnostics.append({"level": "error", "message": "Site not found for DataForSEO check"})
        return 0

    site_domain = site.url.rstrip("/").replace("https://", "").replace("http://", "")

    batch = [{"keyword": kw.phrase, "location_code": 2643, "language_code": "ru"} for kw in keywords[:100]]

    try:
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(fetch_serp_batch(batch))
        loop.close()
    except Exception as exc:
        logger.warning("DataForSEO batch failed", error=str(exc))
        diagnostics.append({"level": "error", "message": f"DataForSEO batch request failed: {str(exc)}"})
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
    """Fallback: Playwright SERP parser (Google only, respects daily limit)."""
    from app.services.serp_parser_service import parse_serp_sync, _check_daily_limit
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
