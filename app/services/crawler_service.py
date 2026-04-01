"""Crawler service: sitemap parsing, SEO data extraction, page classification."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from loguru import logger

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment,misc]


def parse_sitemap(base_url: str) -> list[str]:
    """Fetch {base_url}/sitemap.xml and return all <loc> URLs.

    Returns an empty list on any failure (network error, parse error, etc.).
    """
    sitemap_url = base_url.rstrip("/") + "/sitemap.xml"
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            response = client.get(sitemap_url)
            response.raise_for_status()
            content = response.text
    except Exception as exc:
        logger.warning("parse_sitemap failed", url=sitemap_url, error=str(exc))
        return []

    try:
        soup = BeautifulSoup(content, "lxml-xml")
        locs = soup.find_all("loc")
        return [loc.get_text(strip=True) for loc in locs if loc.get_text(strip=True)]
    except Exception as exc:
        logger.warning("parse_sitemap XML parse failed", url=sitemap_url, error=str(exc))
        return []


def extract_seo_data(page) -> dict:
    """Extract SEO metadata from a Playwright Page object.

    Parameters
    ----------
    page:
        A ``playwright.sync_api.Page`` instance (typed loosely to avoid hard
        import at module level when Playwright is not installed in test env).

    Returns
    -------
    dict with keys: title, h1, meta_description, has_noindex, has_schema, has_toc
    """
    title: str = page.title() or ""

    # First h1 text
    h1_el = page.query_selector("h1")
    h1: str = h1_el.inner_text().strip() if h1_el else ""

    # Meta description
    meta_desc_el = page.query_selector("meta[name='description']")
    meta_description: str = (
        meta_desc_el.get_attribute("content") or ""
        if meta_desc_el
        else ""
    )

    # noindex detection
    robots_el = page.query_selector("meta[name='robots']")
    robots_content: str = (
        robots_el.get_attribute("content") or ""
        if robots_el
        else ""
    )
    has_noindex: bool = "noindex" in robots_content.lower()

    # Schema.org JSON-LD detection
    schema_scripts = page.query_selector_all(
        "script[type='application/ld+json']"
    )
    has_schema: bool = len(schema_scripts) > 0

    # TOC detection — looks for id/class containing "toc" or "table-of-contents"
    toc_el = page.query_selector(
        "[id*='toc'], [class*='toc'], "
        "[id*='table-of-contents'], [class*='table-of-contents']"
    )
    has_toc: bool = toc_el is not None

    return {
        "title": title,
        "h1": h1,
        "meta_description": meta_description,
        "has_noindex": has_noindex,
        "has_schema": has_schema,
        "has_toc": has_toc,
    }


def classify_page_type(url: str, h1: str) -> str:
    """Classify a page as category / product / landing / article.

    Heuristics (first match wins):
    - URL contains /category/ or /tag/          → "category"
    - URL contains /product/ or h1 has "buy"    → "product"
    - No path segments after domain (homepage)  → "landing"
    - Otherwise                                 → "article"
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    # category / tag
    if re.search(r"/(category|tag)/", path, re.IGNORECASE):
        return "category"

    # product
    if re.search(r"/product/", path, re.IGNORECASE):
        return "product"
    if re.search(r"\bbuy\b", h1, re.IGNORECASE):
        return "product"

    # landing page — no meaningful path segments
    path_segments = [s for s in path.split("/") if s]
    if not path_segments:
        return "landing"

    return "article"
