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
    """Process WP content for a post — creates a WpContentJob and delegates to the content pipeline.

    Skips gracefully if site is disabled.
    """
    skip = site_active_guard(site_id)
    if skip:
        return skip

    from app.database import get_sync_db
    from app.models.wp_content_job import WpContentJob
    from app.models.site import Site
    from app.tasks.wp_content_tasks import run_content_pipeline
    from sqlalchemy import select

    with get_sync_db() as db:
        site = db.execute(select(Site).where(Site.id == uuid.UUID(site_id))).scalar_one_or_none()
        if not site:
            return {"status": "skipped", "reason": "site not found"}

        # Build page URL from WP post ID
        page_url = f"{site.url.rstrip('/')}/wp-json/wp/v2/posts/{post_id}"

        job = WpContentJob(
            site_id=site.id,
            wp_post_id=post_id,
            page_url=page_url,
            status="pending",
        )
        db.add(job)
        db.flush()
        job_id = str(job.id)

    logger.info("Created WpContentJob, dispatching pipeline", site_id=site_id, post_id=post_id, job_id=job_id)
    run_content_pipeline.delay(job_id)
    return {"status": "dispatched", "site_id": site_id, "post_id": post_id, "job_id": job_id}


@celery_app.task(name="app.tasks.wp_tasks.fetch_wp_posts", bind=True, max_retries=3)
def fetch_wp_posts(self, site_id: str, page: int = 1) -> dict:
    """Fetch WP posts for a site and save to pages table. Skips if site is disabled."""
    skip = site_active_guard(site_id)
    if skip:
        return skip
    site = _get_site_sync(site_id)
    from app.services.wp_service import get_posts_sync
    posts = get_posts_sync(site, page=page)
    saved = _save_wp_items_as_pages(site_id, posts, item_type="post")
    logger.info("Fetched and saved WP posts", site_id=site_id, fetched=len(posts), saved=saved)
    return {"status": "ok", "site_id": site_id, "fetched": len(posts), "saved": saved}


@celery_app.task(name="app.tasks.wp_tasks.fetch_wp_pages", bind=True, max_retries=3)
def fetch_wp_pages(self, site_id: str, page: int = 1) -> dict:
    """Fetch WP pages for a site and save to pages table. Skips if site is disabled."""
    skip = site_active_guard(site_id)
    if skip:
        return skip
    site = _get_site_sync(site_id)
    from app.services.wp_service import get_pages_sync
    pages = get_pages_sync(site, page=page)
    saved = _save_wp_items_as_pages(site_id, pages, item_type="page")
    logger.info("Fetched and saved WP pages", site_id=site_id, fetched=len(pages), saved=saved)
    return {"status": "ok", "site_id": site_id, "fetched": len(pages), "saved": saved}


def _save_wp_items_as_pages(site_id: str, items: list[dict], item_type: str = "post") -> int:
    """Save WP REST API post/page items into the pages table via a synthetic crawl job."""
    from app.database import get_sync_db
    from app.models.crawl import CrawlJob, CrawlJobStatus, Page, PageType
    from sqlalchemy import select

    if not items:
        return 0

    sid = uuid.UUID(site_id)

    with get_sync_db() as db:
        # Create a synthetic crawl job to group these pages
        job = CrawlJob(site_id=sid, status=CrawlJobStatus.done, pages_crawled=len(items))
        db.add(job)
        db.flush()

        saved = 0
        for item in items:
            link = item.get("link", "")
            if not link:
                continue

            title = ""
            title_obj = item.get("title")
            if isinstance(title_obj, dict):
                title = title_obj.get("rendered", "")
            elif isinstance(title_obj, str):
                title = title_obj

            page_type = PageType.article if item_type == "post" else PageType.landing

            # Skip duplicates within same crawl job
            existing = db.execute(
                select(Page).where(Page.crawl_job_id == job.id, Page.url == link)
            ).scalar_one_or_none()
            if existing:
                continue

            pg = Page(
                site_id=sid,
                crawl_job_id=job.id,
                url=link,
                title=title,
                http_status=200,
                page_type=page_type,
                depth=0,
            )
            db.add(pg)
            saved += 1

    return saved
