"""Celery tasks for site crawling using Playwright."""
from __future__ import annotations

import time
import uuid
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from app.celery_app import celery_app, get_browser
from app.config import settings
from app.tasks.wp_tasks import site_active_guard


def _is_internal_link(base_url: str, href: str) -> bool:
    """Return True if href belongs to the same domain as base_url."""
    base_host = urlparse(base_url).netloc
    href_host = urlparse(href).netloc
    return href_host == base_host or not href_host


def _normalise_url(base_url: str, href: str) -> str | None:
    """Resolve href relative to base_url; return None for non-http URLs."""
    try:
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            return None
        # Strip fragment
        return parsed._replace(fragment="").geturl()
    except Exception:
        return None


@celery_app.task(
    name="app.tasks.crawl_tasks.crawl_site",
    bind=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=360,
)
def crawl_site(self, site_id: str) -> dict:
    """Crawl a site using Playwright. Each task gets its own BrowserContext."""
    # ------------------------------------------------------------------
    # Guard: skip disabled / missing sites
    # ------------------------------------------------------------------
    skip = site_active_guard(site_id)
    if skip:
        return skip

    # ------------------------------------------------------------------
    # Load site record
    # ------------------------------------------------------------------
    from app.database import get_sync_db
    from app.models.site import Site
    from sqlalchemy import select

    with get_sync_db() as db:
        row = db.execute(select(Site).where(Site.id == uuid.UUID(site_id)))
        site = row.scalar_one_or_none()

    if site is None:
        return {"status": "skipped", "reason": "site not found", "site_id": site_id}

    base_url = site.url.rstrip("/")

    # ------------------------------------------------------------------
    # Create CrawlJob
    # ------------------------------------------------------------------
    from app.models.crawl import CrawlJob, CrawlJobStatus, Page, PageType

    crawl_job_id = uuid.uuid4()
    with get_sync_db() as db:
        job = CrawlJob(
            id=crawl_job_id,
            site_id=uuid.UUID(site_id),
            status=CrawlJobStatus.running,
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()

    logger.info("crawl_site started", site_id=site_id, crawl_job_id=str(crawl_job_id))

    # ------------------------------------------------------------------
    # Playwright browser context
    # ------------------------------------------------------------------
    browser = get_browser()
    if browser is None:
        logger.warning("Playwright browser not available", site_id=site_id)
        with get_sync_db() as db:
            job = db.get(CrawlJob, crawl_job_id)
            job.status = CrawlJobStatus.failed
            job.error_message = "browser not initialised"
            job.finished_at = datetime.now(timezone.utc)
        return {"status": "error", "reason": "browser not initialised", "site_id": site_id}

    context = browser.new_context()

    try:
        # --------------------------------------------------------------
        # Sitemap → seed URLs
        # --------------------------------------------------------------
        from app.services.crawler_service import (
            classify_page_type,
            extract_seo_data,
            parse_sitemap,
        )

        seed_urls = parse_sitemap(base_url)
        if not seed_urls:
            seed_urls = [base_url]

        max_pages = settings.CRAWLER_MAX_PAGES
        delay_s = settings.CRAWLER_DELAY_MS / 1000.0

        # BFS queue: (url, depth)
        queue: deque[tuple[str, int]] = deque((u, 0) for u in seed_urls[:max_pages])
        visited: set[str] = set()
        pages_crawled = 0

        # --------------------------------------------------------------
        # Crawl loop
        # --------------------------------------------------------------
        while queue and pages_crawled < max_pages:
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            try:
                pw_page = context.new_page()
                try:
                    response = pw_page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    http_status = response.status if response else None

                    seo = extract_seo_data(pw_page)
                    page_type_str = classify_page_type(url, seo.get("h1", ""))

                    # Collect internal links for BFS (max depth=5)
                    internal_links: list[str] = []
                    if depth < 5:
                        anchors = pw_page.query_selector_all("a[href]")
                        for anchor in anchors:
                            href = anchor.get_attribute("href")
                            if not href:
                                continue
                            norm = _normalise_url(url, href)
                            if norm and _is_internal_link(base_url, norm) and norm not in visited:
                                internal_links.append(norm)

                    # Persist Page + PageSnapshot
                    from app.models.crawl import PageSnapshot
                    from app.services.diff_service import build_snapshot, compute_diff
                    from sqlalchemy import select as sa_select

                    page_id = uuid.uuid4()
                    with get_sync_db() as db:
                        page_row = Page(
                            id=page_id,
                            site_id=uuid.UUID(site_id),
                            crawl_job_id=crawl_job_id,
                            url=url,
                            title=seo.get("title"),
                            h1=seo.get("h1"),
                            meta_description=seo.get("meta_description"),
                            http_status=http_status,
                            depth=depth,
                            internal_link_count=len(internal_links),
                            page_type=PageType(page_type_str),
                            has_toc=seo.get("has_toc", False),
                            has_schema=seo.get("has_schema", False),
                            has_noindex=seo.get("has_noindex", False),
                            crawled_at=datetime.now(timezone.utc),
                        )
                        db.add(page_row)
                        db.flush()

                        # Build snapshot data
                        snap_data = build_snapshot(page_row)

                        # Look up previous snapshot for the same (site_id, url)
                        prev_page = db.execute(
                            sa_select(Page)
                            .where(
                                Page.site_id == uuid.UUID(site_id),
                                Page.url == url,
                                Page.id != page_id,
                            )
                            .order_by(Page.crawled_at.desc())
                            .limit(1)
                        ).scalar_one_or_none()

                        diff_data: dict | None = None
                        if prev_page is not None:
                            prev_snap = db.execute(
                                sa_select(PageSnapshot)
                                .where(PageSnapshot.page_id == prev_page.id)
                                .order_by(PageSnapshot.created_at.desc())
                                .limit(1)
                            ).scalar_one_or_none()
                            if prev_snap is not None:
                                diff_data = compute_diff(prev_snap.snapshot_data, snap_data) or None

                        snapshot_row = PageSnapshot(
                            id=uuid.uuid4(),
                            page_id=page_id,
                            crawl_job_id=crawl_job_id,
                            snapshot_data=snap_data,
                            diff_data=diff_data,
                            created_at=datetime.now(timezone.utc),
                        )
                        db.add(snapshot_row)

                    pages_crawled += 1

                    # Enqueue internal links
                    for link in internal_links:
                        if link not in visited:
                            queue.append((link, depth + 1))

                finally:
                    pw_page.close()

            except Exception as exc:
                logger.warning("Error crawling page", url=url, error=str(exc))
                # Continue to next URL rather than aborting entire job

            # Politeness delay
            if delay_s > 0:
                time.sleep(delay_s)

        # --------------------------------------------------------------
        # Finalise CrawlJob → done
        # --------------------------------------------------------------
        with get_sync_db() as db:
            job = db.get(CrawlJob, crawl_job_id)
            job.status = CrawlJobStatus.done
            job.pages_crawled = pages_crawled
            job.finished_at = datetime.now(timezone.utc)

        logger.info(
            "crawl_site finished",
            site_id=site_id,
            crawl_job_id=str(crawl_job_id),
            pages_crawled=pages_crawled,
        )
        return {"status": "done", "site_id": site_id, "crawl_job_id": str(crawl_job_id), "pages_crawled": pages_crawled}

    except SoftTimeLimitExceeded:
        logger.warning("crawl_site soft timeout", site_id=site_id, crawl_job_id=str(crawl_job_id))
        with get_sync_db() as db:
            job = db.get(CrawlJob, crawl_job_id)
            job.status = CrawlJobStatus.failed
            job.error_message = "timeout"
            job.finished_at = datetime.now(timezone.utc)
        return {"status": "failed", "reason": "timeout", "site_id": site_id}

    except Exception as exc:
        logger.error("crawl_site failed", site_id=site_id, error=str(exc))
        # Retry for network-like errors; fail immediately otherwise
        error_str = str(exc).lower()
        is_network_error = any(
            kw in error_str
            for kw in ("connection", "timeout", "network", "refused", "reset")
        )
        with get_sync_db() as db:
            job = db.get(CrawlJob, crawl_job_id)
            job.status = CrawlJobStatus.failed
            job.error_message = str(exc)[:500]
            job.finished_at = datetime.now(timezone.utc)

        if is_network_error:
            raise self.retry(exc=exc, countdown=60)
        return {"status": "failed", "reason": str(exc), "site_id": site_id}

    finally:
        context.close()
        logger.info("crawl_site BrowserContext closed", site_id=site_id)
