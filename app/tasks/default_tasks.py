from app.celery_app import celery_app


@celery_app.task(name="app.tasks.default_tasks.send_notification")
def send_notification(message: str) -> dict:
    """Stub: send notification. Implemented in Phase 6."""
    return {"status": "stub", "message": message}
