import uuid

from loguru import logger

from app.celery_app import celery_app


def _get_site_sync(site_id: str):
    """Load site synchronously for use inside Celery tasks."""
    from app.database import get_sync_db
    from app.models.site import Site
    from sqlalchemy import select

    with get_sync_db() as db:
        result = db.execute(select(Site).where(Site.id == uuid.UUID(site_id)))
        return result.scalar_one_or_none()


def site_active_guard(site_id: str) -> dict | None:
    """
    Return a skip dict if site is missing or disabled, else None (proceed).
    Call at the top of every task that targets a specific site.
    """
    site = _get_site_sync(site_id)
    if site is None:
        logger.warning("Task skipped — site not found", site_id=site_id)
        return {"status": "skipped", "reason": "site not found", "site_id": site_id}
    if not site.is_active:
        logger.info("Task skipped — site disabled", site_id=site_id)
        return {"status": "skipped", "reason": "site disabled", "site_id": site_id}
    return None


@celery_app.task(name="app.tasks.wp_tasks.process_wp_content", bind=True, max_retries=3)
def process_wp_content(self, site_id: str, post_id: int) -> dict:
    """Process WP content for a post. Skips gracefully if site is disabled."""
    skip = site_active_guard(site_id)
    if skip:
        return skip
    logger.info("Processing WP content", site_id=site_id, post_id=post_id)
    # Full implementation in Phase 8
    return {"status": "stub", "site_id": site_id, "post_id": post_id}


@celery_app.task(name="app.tasks.wp_tasks.fetch_wp_posts", bind=True, max_retries=3)
def fetch_wp_posts(self, site_id: str, page: int = 1) -> dict:
    """Fetch WP posts for a site. Skips gracefully if site is disabled."""
    skip = site_active_guard(site_id)
    if skip:
        return skip
    site = _get_site_sync(site_id)
    from app.services.wp_service import get_posts_sync
    posts = get_posts_sync(site, page=page)
    return {"status": "ok", "site_id": site_id, "count": len(posts)}


@celery_app.task(name="app.tasks.wp_tasks.fetch_wp_pages", bind=True, max_retries=3)
def fetch_wp_pages(self, site_id: str, page: int = 1) -> dict:
    """Fetch WP pages for a site. Skips gracefully if site is disabled."""
    skip = site_active_guard(site_id)
    if skip:
        return skip
    site = _get_site_sync(site_id)
    from app.services.wp_service import get_pages_sync
    pages = get_pages_sync(site, page=page)
    return {"status": "ok", "site_id": site_id, "count": len(pages)}
