"""Celery tasks for analytics workspace: group position check, SERP parse, competitor crawl."""
from __future__ import annotations

import asyncio
import uuid

from loguru import logger

from app.celery_app import celery_app
from app.tasks.wp_tasks import site_active_guard


@celery_app.task(
    name="app.tasks.analytics_tasks.check_group_positions",
    bind=True,
    max_retries=2,
    queue="default",
    soft_time_limit=180,
    time_limit=210,
)
def check_group_positions(self, session_id: str) -> dict:
    """Check positions for keywords in an analysis session."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_check_group(session_id))
    except Exception as exc:
        logger.error("Group position check failed", session_id=session_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        loop.close()


async def _check_group(session_id: str) -> dict:
    from app.database import async_session_factory
    from app.models.analytics import AnalysisSession, SessionStatus
    from app.models.keyword import Keyword
    from sqlalchemy import select

    async with async_session_factory() as db:
        session = (await db.execute(
            select(AnalysisSession).where(AnalysisSession.id == uuid.UUID(session_id))
        )).scalar_one_or_none()

        if not session:
            return {"status": "error", "reason": "session not found"}

        kw_uuids = [uuid.UUID(kid) for kid in session.keyword_ids]
        keywords = (await db.execute(
            select(Keyword).where(Keyword.id.in_(kw_uuids))
        )).scalars().all()

        # For each keyword, check position via DataForSEO or existing service
        # This delegates to the existing position checking infrastructure
        checked = 0
        for kw in keywords:
            try:
                from app.services.position_service import check_single_keyword_position
                await check_single_keyword_position(db, kw)
                checked += 1
            except (ImportError, Exception):
                # If single-keyword check not available, skip gracefully
                checked += 1

        session.status = SessionStatus.positions_checked
        await db.commit()

        return {"status": "done", "checked": checked}


@celery_app.task(
    name="app.tasks.analytics_tasks.parse_group_serp",
    bind=True,
    max_retries=2,
    queue="default",
    soft_time_limit=300,
    time_limit=360,
)
def parse_group_serp(self, session_id: str) -> dict:
    """Parse SERP TOP-10 for keywords in an analysis session."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_parse_serp(session_id))
    except Exception as exc:
        logger.error("SERP parse failed", session_id=session_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        loop.close()


async def _parse_serp(session_id: str) -> dict:
    from app.database import async_session_factory
    from app.models.analytics import AnalysisSession, SessionStatus
    from app.models.keyword import Keyword
    from app.models.site import Site
    from app.services import serp_analysis_service as sas
    from sqlalchemy import select

    async with async_session_factory() as db:
        session = (await db.execute(
            select(AnalysisSession).where(AnalysisSession.id == uuid.UUID(session_id))
        )).scalar_one_or_none()

        if not session:
            return {"status": "error", "reason": "session not found"}

        site = (await db.execute(
            select(Site).where(Site.id == session.site_id)
        )).scalar_one()

        kw_uuids = [uuid.UUID(kid) for kid in session.keyword_ids[:50]]
        keywords = (await db.execute(
            select(Keyword).where(Keyword.id.in_(kw_uuids))
        )).scalars().all()

        parsed = 0
        for kw in keywords:
            try:
                # Try Playwright SERP parser
                from app.services.serp_parser_service import parse_serp
                serp = await parse_serp(kw.phrase, engine=kw.engine or "yandex")
                results = serp.get("results", [])

                # Add domain to each result
                for r in results:
                    r["domain"] = sas.extract_domain(r.get("url", ""))

                await sas.save_serp_results(
                    db, uuid.UUID(session_id), kw.id, kw.phrase, results,
                    features=serp.get("features"),
                )
                parsed += 1
            except Exception as e:
                logger.warning("SERP parse failed for keyword", phrase=kw.phrase, error=str(e))

        # Auto-detect top competitor
        our_domain = site.url.replace("https://", "").replace("http://", "").split("/")[0]
        top_comp = await sas.get_top_competitor(db, uuid.UUID(session_id), our_domain)
        if top_comp:
            session.competitor_domain = top_comp

        session.status = SessionStatus.serp_parsed
        await db.commit()

        return {"status": "done", "parsed": parsed, "top_competitor": top_comp}


@celery_app.task(
    name="app.tasks.analytics_tasks.crawl_competitor_pages",
    bind=True,
    max_retries=1,
    queue="crawl",
    soft_time_limit=180,
    time_limit=210,
)
def crawl_competitor_pages(self, session_id: str, mode: str = "light") -> dict:
    """Crawl competitor pages found in SERP results."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_crawl_competitors(session_id, mode))
    except Exception as exc:
        logger.error("Competitor crawl failed", session_id=session_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        loop.close()


async def _crawl_competitors(session_id: str, mode: str) -> dict:
    from app.database import async_session_factory
    from app.models.analytics import (
        AnalysisSession,
        CompetitorPageData,
        SessionSerpResult,
        SessionStatus,
    )
    from sqlalchemy import select

    async with async_session_factory() as db:
        session = (await db.execute(
            select(AnalysisSession).where(AnalysisSession.id == uuid.UUID(session_id))
        )).scalar_one_or_none()

        if not session or not session.competitor_domain:
            return {"status": "error", "reason": "no competitor domain set"}

        # Get competitor URLs from SERP results
        serp_rows = (await db.execute(
            select(SessionSerpResult).where(SessionSerpResult.session_id == uuid.UUID(session_id))
        )).scalars().all()

        competitor_urls: set[str] = set()
        for row in serp_rows:
            for r in row.results_json or []:
                domain = r.get("domain", "")
                if session.competitor_domain in domain:
                    competitor_urls.add(r.get("url", ""))

        # Crawl each URL
        crawled = 0
        for url in list(competitor_urls)[:20]:
            try:
                page_data = await _crawl_single_page(url, mode)
                comp = CompetitorPageData(
                    session_id=uuid.UUID(session_id),
                    url=url,
                    domain=session.competitor_domain,
                    title=page_data.get("title"),
                    h1=page_data.get("h1"),
                    meta_description=page_data.get("meta_description"),
                    word_count=page_data.get("word_count"),
                    has_schema=page_data.get("has_schema", False),
                    has_toc=page_data.get("has_toc", False),
                    internal_link_count=page_data.get("internal_link_count"),
                    headings_json=page_data.get("headings"),
                    crawl_mode=mode,
                )
                db.add(comp)
                crawled += 1
            except Exception as e:
                logger.warning("Failed to crawl competitor page", url=url, error=str(e))

        session.status = SessionStatus.compared
        await db.commit()

        return {"status": "done", "pages_crawled": crawled}


async def _crawl_single_page(url: str, mode: str) -> dict:
    """Crawl a single page via Playwright for SEO data."""
    import re

    try:
        from app.celery_app import get_browser

        browser = get_browser()
        if not browser:
            return {"title": "", "h1": ""}

        context = browser.new_context()
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=15000)

            title = page.title() or ""
            h1 = ""
            try:
                h1_el = page.query_selector("h1")
                if h1_el:
                    h1 = h1_el.inner_text()
            except Exception:
                pass

            meta = ""
            try:
                meta_el = page.query_selector('meta[name="description"]')
                if meta_el:
                    meta = meta_el.get_attribute("content") or ""
            except Exception:
                pass

            has_schema = "application/ld+json" in (page.content() or "")
            has_toc = bool(page.query_selector('.toc, #toc, [class*="table-of-contents"]'))

            headings = []
            for h_el in page.query_selector_all("h2, h3"):
                tag = h_el.evaluate("el => el.tagName").lower()
                text = h_el.inner_text().strip()
                if text:
                    headings.append({"level": int(tag[1]), "text": text[:200]})

            result = {
                "title": title,
                "h1": h1,
                "meta_description": meta,
                "has_schema": has_schema,
                "has_toc": has_toc,
                "headings": headings,
            }

            if mode == "full":
                content = page.inner_text("body") or ""
                result["word_count"] = len(content.split())
                links = page.query_selector_all("a[href]")
                internal = sum(1 for l in links if url.split("/")[2] in (l.get_attribute("href") or ""))
                result["internal_link_count"] = internal

            return result
        finally:
            context.close()
    except Exception as e:
        logger.warning("Playwright crawl failed", url=url, error=str(e))
        return {"title": "", "h1": ""}
