"""Crawler service: sitemap parsing, SEO data extraction, page classification.

Two extraction modes:
- httpx + BeautifulSoup (default, lightweight, fast, no browser needed)
- Playwright (fallback / on demand, handles JS-rendered pages)
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, urljoin

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

    # Canonical URL
    canonical_el = page.query_selector("link[rel='canonical']")
    canonical_url: str = (
        canonical_el.get_attribute("href") or ""
        if canonical_el
        else ""
    )

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
        "canonical_url": canonical_url,
    }


# ---------------------------------------------------------------------------
# httpx + BeautifulSoup extraction (lightweight, no browser)
# ---------------------------------------------------------------------------

def fetch_page_httpx(
    url: str,
    timeout: float = 15.0,
    headers: dict | None = None,
) -> tuple[int | None, str]:
    """Fetch a page with httpx. Returns (http_status, html_body).

    Returns (None, "") on network errors.
    """
    default_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SEOPlatformBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    if headers:
        default_headers.update(headers)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=default_headers)
            return resp.status_code, resp.text
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("fetch_page_httpx failed", url=url, error=str(exc))
        return None, ""


def extract_seo_data_bs4(html: str) -> dict:
    """Extract SEO metadata from HTML using BeautifulSoup.

    Same return format as extract_seo_data (Playwright version).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # H1
    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(strip=True) if h1_tag else ""

    # Meta description
    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_tag.get("content", "") if meta_tag else ""

    # noindex
    robots_tag = soup.find("meta", attrs={"name": "robots"})
    robots_content = robots_tag.get("content", "") if robots_tag else ""
    has_noindex = "noindex" in robots_content.lower()

    # Schema.org JSON-LD
    schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    has_schema = len(schema_scripts) > 0

    # Canonical URL
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical_url = canonical_tag.get("href", "") if canonical_tag else ""

    # TOC
    toc_el = soup.find(attrs={"id": re.compile(r"toc|table-of-contents", re.I)})
    if not toc_el:
        toc_el = soup.find(attrs={"class": re.compile(r"toc|table-of-contents", re.I)})
    has_toc = toc_el is not None

    return {
        "title": title,
        "h1": h1,
        "meta_description": meta_description,
        "has_noindex": has_noindex,
        "has_schema": has_schema,
        "has_toc": has_toc,
        "canonical_url": canonical_url,
    }


def extract_internal_links_bs4(html: str, base_url: str) -> list[str]:
    """Extract internal links from HTML using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    base_host = urlparse(base_url).netloc
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        try:
            full = urljoin(base_url, href)
            parsed = urlparse(full)
            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc == base_host or not parsed.netloc:
                clean = parsed._replace(fragment="").geturl()
                links.append(clean)
        except Exception:
            continue
    return links


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
