"""Celery tasks for syncing Yandex Webmaster errors into the platform.

Fetches indexing errors, crawl errors, and sanctions from Yandex Webmaster API
for a given site, upserts them into the yandex_errors table, and soft-closes
errors no longer returned by the API.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import redis as sync_redis
from loguru import logger

from app.celery_app import celery_app
from app.config import settings
from app.database import get_sync_db
from app.models.site import Site
from app.models.yandex_errors import YandexError, YandexErrorStatus, YandexErrorType


def _parse_dt(value: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string from Yandex API, returning UTC-aware datetime."""
    if not value:
        return None
    try:
        # Yandex returns ISO format like "2024-01-15T10:30:00.000+03:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _extract_domain(url: str) -> str:
    """Extract hostname from a full URL for Webmaster host matching."""
    parsed = urlparse(url)
    return parsed.hostname or url.lower().rstrip("/")


@celery_app.task(
    name="app.tasks.yandex_errors_tasks.sync_yandex_errors",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=180,
    time_limit=210,
)
def sync_yandex_errors(self, site_id: str) -> dict:
    """Sync Yandex Webmaster errors for a site.

    Flow:
    1. Check token is configured
    2. Resolve Yandex user_id (cached in Redis 7d)
    3. Look up site domain from DB
    4. Resolve host_id (cached per-user 1d)
    5. Fetch indexing errors, crawl errors, sanctions
    6. Transform + upsert with on_conflict_do_update
    7. Soft-close errors not seen in this sync
    8. Store result in Redis for HTMX polling

    Args:
        site_id: UUID string of the site to sync errors for.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.services.yandex_webmaster_service import (
        fetch_crawl_errors,
        fetch_indexing_errors,
        fetch_sanctions,
        get_user_id,
        is_configured,
        resolve_host_id,
    )

    task_id = self.request.id
    r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)

    def _store_result(status: str, message: str) -> None:
        r.set(
            f"yandex_sync:{task_id}",
            json.dumps({"status": status, "message": message}),
            ex=300,
        )

    # 1. Check token
    if not is_configured():
        msg = "Yandex Webmaster не настроен"
        logger.warning("sync_yandex_errors: {}", msg, site_id=site_id)
        _store_result("error", msg)
        return {"status": "error", "message": msg}

    try:
        sync_start_time = datetime.now(timezone.utc)

        # 2. Resolve user_id (cached 7 days)
        user_id_key = "yandex:user_id"
        user_id = r.get(user_id_key)
        if not user_id:
            user_id = asyncio.run(get_user_id())
            if not user_id:
                msg = "Не удалось получить user_id Яндекса"
                _store_result("error", msg)
                return {"status": "error", "message": msg}
            r.set(user_id_key, user_id, ex=7 * 24 * 3600)

        # 3. Look up site domain from DB
        with get_sync_db() as db:
            site = db.get(Site, uuid.UUID(site_id))
            if not site:
                msg = f"Сайт {site_id} не найден"
                _store_result("error", msg)
                return {"status": "error", "message": msg}
            site_url = site.url

        domain = _extract_domain(site_url)

        # 4. Resolve host_id (cached per-user 1 day)
        host_map_key = f"yandex:host_map:{user_id}"
        host_id = None
        cached_map_raw = r.get(host_map_key)
        if cached_map_raw:
            host_map = json.loads(cached_map_raw)
            host_id = host_map.get(domain)

        if not host_id:
            host_id = asyncio.run(resolve_host_id(user_id, domain))
            if not host_id:
                msg = f"Хост не найден в Webmaster: {domain}"
                logger.warning("sync_yandex_errors: {}", msg, site_id=site_id)
                _store_result("error", msg)
                return {"status": "error", "message": msg}
            # Update cache map
            existing_map = json.loads(cached_map_raw) if cached_map_raw else {}
            existing_map[domain] = host_id
            r.set(host_map_key, json.dumps(existing_map), ex=24 * 3600)

        # 5. Fetch 3 error types
        indexing_samples = asyncio.run(fetch_indexing_errors(user_id, host_id))
        crawl_samples = asyncio.run(fetch_crawl_errors(user_id, host_id))
        sanction_items = asyncio.run(fetch_sanctions(user_id, host_id))

        site_uuid = uuid.UUID(site_id)
        now_utc = datetime.now(timezone.utc)

        # 6. Transform API responses into rows
        rows: list[dict] = []

        for sample in indexing_samples:
            url_val = sample.get("url", "")
            http_code = sample.get("http_code", "???")
            rows.append({
                "id": uuid.uuid4(),
                "site_id": site_uuid,
                "error_type": YandexErrorType.indexing,
                "subtype": sample.get("status", ""),
                "url": url_val,
                "title": f"HTTP {http_code}: {url_val[-60:]}",
                "detail": None,
                "detected_at": _parse_dt(sample.get("access_date")),
                "fetched_at": now_utc,
                "status": YandexErrorStatus.open,
            })

        for sample in crawl_samples:
            dest_url = sample.get("destination_url", "")
            source_url = sample.get("source_url", "")
            rows.append({
                "id": uuid.uuid4(),
                "site_id": site_uuid,
                "error_type": YandexErrorType.crawl,
                "subtype": "broken_link",
                "url": dest_url,
                "title": f"Битая ссылка: {dest_url[-60:]}",
                "detail": f"Источник: {source_url}" if source_url else None,
                "detected_at": _parse_dt(sample.get("discovery_date")),
                "fetched_at": now_utc,
                "status": YandexErrorStatus.open,
            })

        for item in sanction_items:
            severity = item.get("severity", "")
            count = item.get("count", 0)
            rows.append({
                "id": uuid.uuid4(),
                "site_id": site_uuid,
                "error_type": YandexErrorType.sanction,
                "subtype": severity.lower(),
                "url": "",  # sentinel — sanctions have no URL
                "title": f"{severity}: {count} проблем(а)",
                "detail": None,
                "detected_at": None,
                "fetched_at": now_utc,
                "status": YandexErrorStatus.open,
            })

        # 7. Upsert rows using on_conflict_do_update
        upserted = 0
        if rows:
            with get_sync_db() as db:
                stmt = (
                    pg_insert(YandexError)
                    .values(rows)
                    .on_conflict_do_update(
                        constraint="uq_yandex_errors_identity",
                        set_={
                            "fetched_at": pg_insert(YandexError).excluded.fetched_at,
                            "detail": pg_insert(YandexError).excluded.detail,
                            "title": pg_insert(YandexError).excluded.title,
                            # Do NOT update status — preserve user changes
                        },
                    )
                )
                db.execute(stmt)
                db.commit()
                upserted = len(rows)

        # 8. Soft-close: mark as resolved errors not seen in this sync
        with get_sync_db() as db:
            from sqlalchemy import and_, update

            close_stmt = (
                update(YandexError)
                .where(
                    and_(
                        YandexError.site_id == site_uuid,
                        YandexError.status == YandexErrorStatus.open,
                        YandexError.fetched_at < sync_start_time,
                    )
                )
                .values(status=YandexErrorStatus.resolved)
            )
            result = db.execute(close_stmt)
            db.commit()
            resolved_count = result.rowcount

        msg = f"Синхронизировано {upserted} ошибок, закрыто {resolved_count}"
        logger.info(
            "sync_yandex_errors complete",
            site_id=site_id,
            upserted=upserted,
            resolved=resolved_count,
        )
        _store_result("done", msg)
        return {"status": "done", "upserted": upserted, "resolved": resolved_count}

    except Exception as exc:
        logger.exception("sync_yandex_errors failed", site_id=site_id, exc=str(exc))
        try:
            raise self.retry(exc=exc, countdown=60)
        except self.MaxRetriesExceededError:
            _store_result("error", f"Ошибка синхронизации: {exc}")
            return {"status": "error", "message": str(exc)}
