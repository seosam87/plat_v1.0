"""Brief TOP-10 service: lightweight crawler and aggregation for Copywriting Brief tool.

Separate from crawler_service.py per D-05 — this is a lightweight, per-URL
Playwright page fetcher with no snapshot diffs or DB persistence.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from statistics import mean

from loguru import logger

# Stopwords for thematic word extraction (Russian + common English)
_STOPWORDS = {
    "что", "как", "для", "это", "при", "или", "его", "все", "они", "она",
    "он", "мы", "вы", "нас", "вас", "их", "том", "так", "уже", "ещё",
    "если", "тоже", "также", "можно", "нужно", "надо", "быть", "есть",
    "был", "была", "было", "были", "будет", "будут", "этот", "эта",
    "эти", "того", "той", "тех", "по", "на", "от", "до", "со",
    "the", "and", "for", "are", "with", "this", "that", "have",
    "from", "not", "but", "you", "they", "was", "has", "been",
}

# Commercialization indicators (Ru)
_COMMERCE_WORDS = frozenset(["цена", "купить", "заказать", "стоимость", "корзина", "добавить"])


def crawl_top10_page(url: str) -> dict | None:
    """Fetch a single TOP-10 page and extract H2s + visible text.

    Uses the process-level Playwright browser from app.celery_app.
    Creates a new BrowserContext + Page per call, always closes them.

    Args:
        url: Page URL to crawl.

    Returns:
        dict with keys "h2s" (list[str]), "text" (str), "title" (str) on success.
        None on HTTP error (status >= 400), timeout, or any exception (D-06).
    """
    from app.celery_app import get_browser

    browser = get_browser()
    if browser is None:
        logger.warning("brief_top10: Playwright browser not initialized, skipping {}", url)
        return None

    context = None
    page = None
    try:
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        response = page.goto(url, wait_until="domcontentloaded", timeout=20_000)

        if response is None or response.status >= 400:
            logger.debug("brief_top10: skipping {} (status={})", url, response.status if response else "None")
            return None

        # Extract H2 texts
        h2_elements = page.query_selector_all("h2")
        h2s = []
        for el in h2_elements:
            try:
                text = el.inner_text().strip()
                if text:
                    h2s.append(text)
            except Exception:
                pass

        # Extract page title
        title = ""
        try:
            title = page.title().strip()
        except Exception:
            pass

        # Extract visible text (truncated to 5000 chars)
        visible_text = ""
        try:
            visible_text = page.inner_text("body")[:5000]
        except Exception:
            pass

        return {"h2s": h2s, "text": visible_text, "title": title, "url": url}

    except Exception as exc:
        logger.debug("brief_top10: error crawling {} — {}", url, exc)
        return None
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        if context is not None:
            try:
                context.close()
            except Exception:
                pass


def aggregate_brief_data(crawled_pages: list[dict], phrases: list[str], serp_snippets: list[str] | None = None) -> dict:
    """Aggregate crawled TOP-10 pages into brief data structures.

    Args:
        crawled_pages: List of page dicts with keys "h2s", "text", "title", "url".
                       None entries are excluded before aggregation.
        phrases: Input keyword phrases (used for filtering in future enhancements).
        serp_snippets: Optional list of SERP snippet strings for highlights.

    Returns:
        dict matching BriefResult column structure.
    """
    # Filter None/empty pages
    pages = [p for p in crawled_pages if p]

    pages_crawled = len(pages)
    pages_attempted = len(crawled_pages)

    if not pages:
        return {
            "title_suggestions": [],
            "h2_cloud": [],
            "highlights": [],
            "thematic_words": [],
            "avg_text_length": 0,
            "avg_h2_count": 0.0,
            "commercialization_pct": 0,
            "pages_crawled": 0,
            "pages_attempted": pages_attempted,
        }

    # H2 cloud: Counter of all H2 texts, sorted by count desc
    all_h2s: list[str] = []
    for page in pages:
        all_h2s.extend(page.get("h2s", []))
    h2_counter = Counter(all_h2s)
    h2_cloud = [{"text": text, "count": count} for text, count in h2_counter.most_common(50)]

    # Thematic words: tokenize all visible text, remove stopwords, top 100
    all_text = " ".join(page.get("text", "") for page in pages)
    raw_words = re.findall(r'\b[а-яА-ЯёЁa-zA-Z]{3,}\b', all_text)
    word_counter = Counter(w.lower() for w in raw_words if w.lower() not in _STOPWORDS)
    thematic_words = [{"word": word, "freq": freq} for word, freq in word_counter.most_common(100)]

    # Title suggestions: deduplicated page titles
    seen_titles: set[str] = set()
    title_suggestions: list[str] = []
    for page in pages:
        t = page.get("title", "").strip()
        if t and t not in seen_titles:
            seen_titles.add(t)
            title_suggestions.append(t)

    # Highlights: from SERP snippets — deduplicated list
    highlights: list[str] = []
    if serp_snippets:
        seen_snippets: set[str] = set()
        for snippet in serp_snippets:
            s = snippet.strip()
            if s and s not in seen_snippets:
                seen_snippets.add(s)
                highlights.append(s)

    # Volume stats
    text_lengths = [len(page.get("text", "")) for page in pages]
    h2_counts = [len(page.get("h2s", [])) for page in pages]
    avg_text_length = int(mean(text_lengths)) if text_lengths else 0
    avg_h2_count = round(mean(h2_counts), 1) if h2_counts else 0.0

    # Commercialization %: pages with commerce indicators / total
    commercial_count = 0
    for page in pages:
        text_lower = page.get("text", "").lower()
        if any(word in text_lower for word in _COMMERCE_WORDS):
            commercial_count += 1
    commercialization_pct = int(commercial_count / pages_crawled * 100) if pages_crawled else 0

    return {
        "title_suggestions": title_suggestions,
        "h2_cloud": h2_cloud,
        "highlights": highlights,
        "thematic_words": thematic_words,
        "avg_text_length": avg_text_length,
        "avg_h2_count": avg_h2_count,
        "commercialization_pct": commercialization_pct,
        "pages_crawled": pages_crawled,
        "pages_attempted": pages_attempted,
    }
