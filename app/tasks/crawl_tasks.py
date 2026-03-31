from app.celery_app import celery_app


@celery_app.task(name="app.tasks.crawl_tasks.crawl_site")
def crawl_site(site_id: str) -> dict:
    """Stub: crawl a site. Implemented in Phase 3."""
    return {"status": "stub", "site_id": site_id}
