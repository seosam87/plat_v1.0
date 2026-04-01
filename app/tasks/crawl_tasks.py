from loguru import logger

from app.celery_app import celery_app, get_browser
from app.tasks.wp_tasks import site_active_guard


@celery_app.task(
    name="app.tasks.crawl_tasks.crawl_site",
    bind=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=360,
)
def crawl_site(self, site_id: str) -> dict:
    """Crawl a site using Playwright. Each task gets its own BrowserContext."""
    skip = site_active_guard(site_id)
    if skip:
        return skip

    browser = get_browser()
    if browser is None:
        logger.warning("Playwright browser not available for crawl_site", site_id=site_id)
        return {"status": "error", "reason": "browser not initialised", "site_id": site_id}

    context = browser.new_context()
    try:
        logger.info("crawl_site started", site_id=site_id)
        # Full crawl logic implemented in 03-02
        return {"status": "stub", "site_id": site_id}
    finally:
        context.close()
        logger.info("crawl_site BrowserContext closed", site_id=site_id)
