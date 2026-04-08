"""Celery tasks for site crawling.

Default mode: httpx + BeautifulSoup (fast, lightweight, no browser).
Fallback/on-demand: Playwright (for JS-rendered pages).
"""
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
from app.services.notifications import notify




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
def crawl_site(self, site_id: str, use_playwright: bool = False) -> dict:
    """Crawl a site.

    Default: httpx + BeautifulSoup (fast, no browser needed).
    use_playwright=True: Playwright headless browser (for JS-rendered pages).
    """
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

    mode = "playwright" if use_playwright else "httpx"
    logger.info("crawl_site started", site_id=site_id, crawl_job_id=str(crawl_job_id), mode=mode)

    # ------------------------------------------------------------------
    # Playwright context (only if requested)
    # ------------------------------------------------------------------
    context = None
    if use_playwright:
        browser = get_browser()
        if browser is None:
            logger.warning("Playwright not available, falling back to httpx", site_id=site_id)
            use_playwright = False
        else:
            context = browser.new_context()

    try:
        # --------------------------------------------------------------
        # Sitemap → seed URLs
        # --------------------------------------------------------------
        from app.services.crawler_service import (
            classify_page_type,
            extract_internal_links_bs4,
            extract_seo_data,
            extract_seo_data_bs4,
            fetch_page_httpx,
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
                if use_playwright and context:
                    http_status, seo, internal_links = _crawl_page_playwright(
                        context, url, base_url, depth
                    )
                else:
                    http_status, seo, internal_links = _crawl_page_httpx(
                        url, base_url, depth
                    )

                page_type_str = classify_page_type(url, seo.get("h1", ""))

                # Persist Page + PageSnapshot
                _persist_page(
                    site_id, crawl_job_id, url, http_status, seo,
                    page_type_str, depth, internal_links,
                )
                pages_crawled += 1

                # Enqueue internal links
                for link in internal_links:
                    if link not in visited:
                        queue.append((link, depth + 1))

            except Exception as exc:
                logger.warning("Error crawling page", url=url, error=str(exc))

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

        # Auto-create SEO tasks for 404s and lost-indexation pages
        with get_sync_db() as db:
            from app.services.task_service import create_auto_tasks

            create_auto_tasks(db, uuid.UUID(site_id), crawl_job_id)

        # Detect changes and dispatch Telegram alerts
        with get_sync_db() as db:
            from app.services.change_monitoring_service import process_crawl_changes
            from app.models.site import Site
            from sqlalchemy import select as sa_select

            site = db.execute(
                sa_select(Site).where(Site.id == uuid.UUID(site_id))
            ).scalar_one_or_none()
            if site:
                change_result = process_crawl_changes(
                    db, uuid.UUID(site_id), site.name, crawl_job_id
                )
                logger.info(
                    "Change monitoring done",
                    site_id=site_id,
                    total_changes=change_result["total_changes"],
                    alerts_sent=change_result["alerts_sent"],
                )

        logger.info(
            "crawl_site finished",
            site_id=site_id,
            crawl_job_id=str(crawl_job_id),
            pages_crawled=pages_crawled,
            mode=mode,
        )
        # In-app notification guard (D-02): crawl_site has no user_id arg today.
        # Pass user_id once callers plumb it through; Telegram dispatch above is unchanged.
        _user_id = None  # TODO: accept user_id kwarg in a future phase
        _domain = site.domain if site and hasattr(site, "domain") else site_id
        if _user_id is not None:
            import asyncio as _aio
            from app.database import AsyncSessionLocal as _ASL

            async def _emit_crawl_done():
                async with _ASL() as _db:
                    await notify(
                        db=_db, user_id=_user_id, kind="crawl.completed",
                        title="Краул завершён",
                        body=f"Сайт {_domain}: обработано {pages_crawled} страниц",
                        link_url=f"/sites/{site_id}/crawl",
                        site_id=uuid.UUID(site_id), severity="info",
                    )
                    await _db.commit()

            _aio.run(_emit_crawl_done())
        else:
            logger.debug(
                "no user scope; skipping in-app notification",
                task="crawl_site",
                kind="crawl.completed",
            )
        return {"status": "done", "site_id": site_id, "crawl_job_id": str(crawl_job_id), "pages_crawled": pages_crawled}

    except SoftTimeLimitExceeded:
        logger.warning("crawl_site soft timeout", site_id=site_id, crawl_job_id=str(crawl_job_id))
        with get_sync_db() as db:
            job = db.get(CrawlJob, crawl_job_id)
            job.status = CrawlJobStatus.failed
            job.error_message = "timeout"
            job.finished_at = datetime.now(timezone.utc)
        # In-app notification guard (D-02): no user_id in scope; skip silently
        _user_id = None  # TODO: accept user_id kwarg in a future phase
        if _user_id is not None:
            import asyncio as _aio
            from app.database import AsyncSessionLocal as _ASL

            async def _emit_crawl_timeout():
                async with _ASL() as _db:
                    await notify(
                        db=_db, user_id=_user_id, kind="crawl.failed",
                        title="Краул: ошибка", body="Превышено время выполнения краула",
                        link_url=f"/sites/{site_id}/crawl",
                        site_id=uuid.UUID(site_id), severity="error",
                    )
                    await _db.commit()

            _aio.run(_emit_crawl_timeout())
        else:
            logger.debug(
                "no user scope; skipping in-app notification",
                task="crawl_site",
                kind="crawl.failed",
            )
        return {"status": "failed", "reason": "timeout", "site_id": site_id}

    except Exception as exc:
        logger.error("crawl_site failed", site_id=site_id, error=str(exc))
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

        # In-app notification guard (D-02): no user_id in scope; skip silently
        _user_id = None  # TODO: accept user_id kwarg in a future phase
        if _user_id is not None:
            import asyncio as _aio
            from app.database import AsyncSessionLocal as _ASL

            async def _emit_crawl_error():
                async with _ASL() as _db:
                    await notify(
                        db=_db, user_id=_user_id, kind="crawl.failed",
                        title="Краул: ошибка", body=str(exc)[:200],
                        link_url=f"/sites/{site_id}/crawl",
                        site_id=uuid.UUID(site_id), severity="error",
                    )
                    await _db.commit()

            _aio.run(_emit_crawl_error())
        else:
            logger.debug(
                "no user scope; skipping in-app notification",
                task="crawl_site",
                kind="crawl.failed",
            )
        if is_network_error:
            raise self.retry(exc=exc, countdown=60)
        return {"status": "failed", "reason": str(exc), "site_id": site_id}

    finally:
        if context:
            context.close()
            logger.info("crawl_site BrowserContext closed", site_id=site_id)


def _crawl_page_httpx(
    url: str, base_url: str, depth: int,
) -> tuple[int | None, dict, list[str]]:
    """Fetch and extract page data using httpx + BeautifulSoup."""
    from app.services.crawler_service import (
        extract_internal_links_bs4,
        extract_seo_data_bs4,
        fetch_page_httpx,
    )

    http_status, html = fetch_page_httpx(url)
    seo = extract_seo_data_bs4(html) if html else {
        "title": "", "h1": "", "meta_description": "",
        "has_noindex": False, "has_schema": False, "has_toc": False, "canonical_url": "",
    }

    internal_links: list[str] = []
    if depth < 5 and html:
        all_links = extract_internal_links_bs4(html, base_url)
        internal_links = list(dict.fromkeys(all_links))  # deduplicate, preserve order

    return http_status, seo, internal_links


def _crawl_page_playwright(
    context, url: str, base_url: str, depth: int,
) -> tuple[int | None, dict, list[str]]:
    """Fetch and extract page data using Playwright."""
    from app.services.crawler_service import extract_seo_data

    pw_page = context.new_page()
    try:
        response = pw_page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        http_status = response.status if response else None
        seo = extract_seo_data(pw_page)

        internal_links: list[str] = []
        if depth < 5:
            anchors = pw_page.query_selector_all("a[href]")
            for anchor in anchors:
                href = anchor.get_attribute("href")
                if not href:
                    continue
                norm = _normalise_url(url, href)
                if norm and _is_internal_link(base_url, norm):
                    internal_links.append(norm)

        return http_status, seo, internal_links
    finally:
        pw_page.close()


def _persist_page(
    site_id: str,
    crawl_job_id: uuid.UUID,
    url: str,
    http_status: int | None,
    seo: dict,
    page_type_str: str,
    depth: int,
    internal_links: list[str],
) -> None:
    """Save Page + PageSnapshot to DB, compute diff vs previous crawl."""
    from app.database import get_sync_db
    from app.models.crawl import Page, PageSnapshot, PageType
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
            canonical_url=seo.get("canonical_url") or None,
            crawled_at=datetime.now(timezone.utc),
        )
        db.add(page_row)
        db.flush()

        snap_data = build_snapshot(page_row)

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
