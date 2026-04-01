"""Playwright SERP parser — low-volume fallback (<50 req/day).

Used only when DataForSEO is not configured or as a supplement.
Rotates User-Agent strings and applies configurable delays.
"""
from __future__ import annotations

import random
import time
from datetime import date

from loguru import logger

from app.config import settings

# Daily request counter (reset by worker restart or date change)
_daily_count: int = 0
_count_date: date | None = None

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def _get_ua() -> str:
    return random.choice(USER_AGENTS)


def _check_daily_limit() -> bool:
    """Return True if under daily limit, False if exceeded."""
    global _daily_count, _count_date
    today = date.today()
    if _count_date != today:
        _daily_count = 0
        _count_date = today
    return _daily_count < settings.SERP_MAX_DAILY_REQUESTS


def _increment_counter() -> None:
    global _daily_count
    _daily_count += 1


def get_daily_usage() -> dict:
    """Return current daily SERP usage stats."""
    global _daily_count, _count_date
    today = date.today()
    if _count_date != today:
        return {"date": today.isoformat(), "used": 0, "limit": settings.SERP_MAX_DAILY_REQUESTS}
    return {"date": today.isoformat(), "used": _daily_count, "limit": settings.SERP_MAX_DAILY_REQUESTS}


def parse_serp_sync(
    keyword: str,
    engine: str = "google",
    region: str = "ru",
) -> list[dict]:
    """Parse SERP using Playwright (synchronous — for Celery tasks).

    Returns list of {position, url, title} from organic results.
    Respects daily limit and politeness delay.
    """
    if not _check_daily_limit():
        logger.warning("SERP daily limit reached", used=_daily_count, limit=settings.SERP_MAX_DAILY_REQUESTS)
        return []

    from app.celery_app import get_browser

    browser = get_browser()
    if browser is None:
        logger.warning("Playwright browser not available for SERP parsing")
        return []

    ua = _get_ua()
    context = browser.new_context(user_agent=ua)
    results: list[dict] = []

    try:
        page = context.new_page()
        try:
            # Build search URL
            if engine == "yandex":
                search_url = f"https://yandex.ru/search/?text={keyword}&lr=213"
            else:
                search_url = f"https://www.google.com/search?q={keyword}&gl={region}&hl=ru"

            page.goto(search_url, wait_until="domcontentloaded", timeout=20_000)

            # Detect SERP features before organic results
            serp_features = _detect_serp_features(page, engine)

            # Extract organic results
            if engine == "yandex":
                items = page.query_selector_all("li.serp-item")
                for i, item in enumerate(items[:20], 1):
                    link_el = item.query_selector("a.OrganicTitle-Link")
                    if link_el:
                        href = link_el.get_attribute("href") or ""
                        title = link_el.inner_text().strip()
                        results.append({"position": i, "url": href, "title": title})
            else:
                items = page.query_selector_all("div.g")
                for i, item in enumerate(items[:20], 1):
                    link_el = item.query_selector("a")
                    title_el = item.query_selector("h3")
                    if link_el:
                        href = link_el.get_attribute("href") or ""
                        title = title_el.inner_text().strip() if title_el else ""
                        if href.startswith("http"):
                            results.append({"position": i, "url": href, "title": title})

            _increment_counter()
            logger.info("SERP parsed", keyword=keyword, engine=engine, results=len(results), features=serp_features)

        finally:
            page.close()

    except Exception as exc:
        logger.warning("SERP parse failed", keyword=keyword, error=str(exc))

    finally:
        context.close()

    # Politeness delay
    delay_s = settings.SERP_DELAY_MS / 1000.0
    if delay_s > 0:
        time.sleep(delay_s)

    return {"results": results, "features": serp_features}


def _detect_serp_features(page, engine: str) -> list[str]:
    """Detect SERP features present on the page.

    Returns list of feature names found: featured_snippet, paa, video,
    images, knowledge_panel, local_pack, ads.
    """
    features: list[str] = []

    if engine == "google":
        # Featured snippet
        if page.query_selector("div.xpdopen, div[data-attrid='wa:/description'], div.IZ6rdc"):
            features.append("featured_snippet")
        # People Also Ask
        if page.query_selector("div.related-question-pair, div[data-sgrd], div.wQiwMc"):
            features.append("paa")
        # Video carousel
        if page.query_selector("div.dXiKIc, video-voyager, div[data-ved] g-scrolling-carousel"):
            features.append("video")
        # Image pack
        if page.query_selector("div.islrc, div#imagebox_bigimages"):
            features.append("images")
        # Knowledge panel
        if page.query_selector("div.kp-wholepage, div.osrp-blk"):
            features.append("knowledge_panel")
        # Local pack
        if page.query_selector("div.VkpGBb, div[data-local-attribute]"):
            features.append("local_pack")
        # Ads
        if page.query_selector("div.uEierd, div[data-text-ad]"):
            features.append("ads")
    elif engine == "yandex":
        # Yandex SERP features
        if page.query_selector("div.Fact, div.AnswerFact"):
            features.append("featured_snippet")
        if page.query_selector("div.RelatedQuestions"):
            features.append("paa")
        if page.query_selector("div.VideoThumb"):
            features.append("video")
        if page.query_selector("div.MMGallery"):
            features.append("images")
        if page.query_selector("div.ObjectAnswer"):
            features.append("knowledge_panel")
        if page.query_selector("div.MapSearchSnippet"):
            features.append("local_pack")
        if page.query_selector("div.Advert"):
            features.append("ads")

    return features
