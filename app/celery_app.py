from celery import Celery

from app.config import settings

celery_app = Celery(
    "seo_platform",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.crawl_tasks",
        "app.tasks.wp_tasks",
        "app.tasks.default_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_acks_late=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.crawl_tasks.*": {"queue": "crawl"},
        "app.tasks.wp_tasks.*": {"queue": "wp"},
        "app.tasks.default_tasks.*": {"queue": "default"},
    },
    task_default_queue="default",
    redbeat_redis_url=settings.REDIS_URL,
)
