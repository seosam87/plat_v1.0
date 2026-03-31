from app.celery_app import celery_app


@celery_app.task(name="app.tasks.wp_tasks.process_wp_content")
def process_wp_content(site_id: str, post_id: int) -> dict:
    """Stub: process WP content. Implemented in Phase 8."""
    return {"status": "stub", "site_id": site_id, "post_id": post_id}
