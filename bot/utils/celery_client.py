"""Lightweight Celery client for the bot container.

Per D-03: the bot uses send_task() only — it does NOT define or import
task functions, so the bot container never loads app.tasks.* modules or
Playwright. This avoids 1+ GB of unnecessary dependencies in the bot image.
"""
from celery import Celery

from bot.config import settings

# Broker-only Celery — no backend needed for fire-and-forget dispatch
_celery = Celery(broker=settings.REDIS_URL)
_celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_default_queue="default",
)


def dispatch(
    task_name: str,
    args: list | None = None,
    kwargs: dict | None = None,
    queue: str = "default",
) -> str:
    """Send a task to a Celery worker and return the task ID.

    Args:
        task_name: Fully-qualified task name, e.g. "app.tasks.crawl_tasks.run_crawl".
        args: Positional arguments for the task.
        kwargs: Keyword arguments for the task.
        queue: Target queue name (default: "default").

    Returns:
        The Celery task ID string.
    """
    result = _celery.send_task(
        task_name,
        args=args or [],
        kwargs=kwargs or {},
        queue=queue,
    )
    return result.id
