from celery import Celery
from celery.signals import beat_init, worker_process_init, worker_process_shutdown

from app.config import settings

celery_app = Celery(
    "seo_platform",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.crawl_tasks",
        "app.tasks.wp_tasks",
        "app.tasks.default_tasks",
        "app.tasks.position_tasks",
        "app.tasks.wp_content_tasks",
        "app.tasks.metrika_tasks",
        "app.tasks.audit_tasks",
        "app.tasks.digest_tasks",
        "app.tasks.analytics_tasks",
        "app.tasks.intent_tasks",
        "app.tasks.smoke_tasks",
        "app.tasks.report_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Moscow",
    enable_utc=True,
    result_expires=3600,
    task_acks_late=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.crawl_tasks.*": {"queue": "crawl"},
        "app.tasks.position_tasks.*": {"queue": "crawl"},
        "app.tasks.wp_tasks.*": {"queue": "wp"},
        "app.tasks.default_tasks.*": {"queue": "default"},
    },
    task_default_queue="default",
    redbeat_redis_url=settings.REDIS_URL,
)

# Module-level Playwright browser instance (one per worker process)
_playwright = None
_browser = None


@worker_process_init.connect
def init_playwright_browser(**kwargs):
    """Initialize a module-level Playwright Browser when the worker process starts.

    This avoids spawning a new browser for every task — one browser per worker
    process; each task creates its own BrowserContext from this shared browser.
    """
    global _playwright, _browser
    try:
        from playwright.sync_api import sync_playwright

        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
    except Exception as exc:  # pragma: no cover — only runs inside worker
        import logging

        logging.getLogger(__name__).warning(
            "Playwright browser init failed (non-crawler worker?): %s", exc
        )


@worker_process_shutdown.connect
def shutdown_playwright_browser(**kwargs):
    """Close the module-level Playwright Browser on worker process shutdown."""
    global _playwright, _browser
    try:
        if _browser is not None:
            _browser.close()
            _browser = None
        if _playwright is not None:
            _playwright.stop()
            _playwright = None
    except Exception:  # pragma: no cover
        pass


def get_browser():
    """Return the process-level Playwright Browser (or None if not initialised)."""
    return _browser


@beat_init.connect
def restore_crawl_schedules(**kwargs):
    """Restore crawl schedules from PostgreSQL on Beat startup.

    Ensures schedules survive Redis FLUSHALL and container restarts.
    """
    try:
        from app.services.schedule_service import (
            restore_schedules_from_db,
            restore_position_schedules_from_db,
        )

        restore_schedules_from_db()
        restore_position_schedules_from_db()
        from app.services.digest_service import restore_digest_schedules_from_db
        restore_digest_schedules_from_db()
        from app.tasks.report_tasks import restore_report_schedules_from_db
        restore_report_schedules_from_db()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "Failed to restore schedules from DB: %s", exc
        )
