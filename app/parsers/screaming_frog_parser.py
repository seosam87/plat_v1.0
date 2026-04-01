"""Screaming Frog export parser.

Handles exports from different SF tabs:
- Internal: Address, Status Code, Title 1, H1-1, Word Count, Unique Inlinks
- External: Address, Status Code, Inlinks (external URLs linking to site)
- Page Titles: Address, Title 1, Title 1 Length, Title 1 Pixel Width
- Meta Description: Address, Meta Description 1, Meta Description 1 Length
- H1: Address, H1-1, H1-1 Length, H1-2

Auto-detects tab type based on column headers.
"""
from __future__ import annotations

from app.parsers.base import find_column, read_file, safe_int


def parse_screaming_frog(path: str) -> dict:
    """Parse a Screaming Frog export file.

    Auto-detects which SF tab the export came from and extracts accordingly.

    Returns:
        {
            "tab_type": "internal"|"external"|"page_titles"|"meta_description"|"h1"|"unknown",
            "pages": [dict],  # per-page data (fields depend on tab)
            "summary": dict,
            "row_count": int,
        }
    """
    rows = read_file(path)
    if not rows:
        return {"tab_type": "unknown", "pages": [], "summary": _empty_summary(), "row_count": 0}

    headers = rows[0]
    tab_type = _detect_tab_type(headers)

    parsers = {
        "internal": _parse_internal,
        "external": _parse_external,
        "page_titles": _parse_page_titles,
        "meta_description": _parse_meta_description,
        "h1": _parse_h1,
    }
    parser = parsers.get(tab_type, _parse_internal)
    result = parser(headers, rows[1:])
    result["tab_type"] = tab_type
    return result


def _detect_tab_type(headers: list[str]) -> str:
    """Detect which SF tab the export is from based on header columns."""
    h_lower = [h.strip().lower() for h in headers]
    joined = " ".join(h_lower)

    # Page Titles tab has "title 1 length" or "title 1 pixel width"
    if "title 1 length" in joined or "title 1 pixel" in joined:
        return "page_titles"
    # Meta Description tab has "meta description 1 length"
    if "meta description 1 length" in joined:
        return "meta_description"
    # H1 tab has "h1-1 length" or "h1-2"
    if "h1-1 length" in joined or "h1-2" in joined:
        return "h1"
    # External tab: typically no word count, has "type" column for link type
    if "word count" not in joined and find_column(headers, ["type"]) is not None:
        return "external"
    # Default: Internal
    return "internal"


# ---------------------------------------------------------------------------
# Internal tab parser (main crawl export)
# ---------------------------------------------------------------------------


def _parse_internal(headers: list[str], data_rows: list[list[str]]) -> dict:
    url_col = find_column(headers, ["address", "url", "адрес"])
    status_col = find_column(headers, ["status code", "status", "statuscode"])
    title_col = find_column(headers, ["title 1", "title", "page title"])
    h1_col = find_column(headers, ["h1-1", "h1", "heading 1"])
    wc_col = find_column(headers, ["word count", "wordcount", "words"])
    inlinks_col = find_column(headers, ["unique inlinks", "inlinks", "inlinks count"])

    if url_col is None:
        url_col = 0

    pages = []
    status_dist: dict[str, int] = {}
    with_title = 0
    with_h1 = 0
    word_counts: list[int] = []

    for row in data_rows:
        url = _safe_get(row, url_col)
        if not url or not _is_url(url):
            continue

        http_status = safe_int(_safe_get(row, status_col) or "")
        title = _safe_get(row, title_col)
        h1 = _safe_get(row, h1_col)
        word_count = safe_int(_safe_get(row, wc_col) or "")
        inlinks = safe_int(_safe_get(row, inlinks_col) or "")

        pages.append({
            "url": url,
            "http_status": http_status,
            "title": title,
            "h1": h1,
            "word_count": word_count,
            "inlinks": inlinks,
        })

        status_key = str(http_status) if http_status else "unknown"
        status_dist[status_key] = status_dist.get(status_key, 0) + 1
        if title:
            with_title += 1
        if h1:
            with_h1 += 1
        if word_count is not None:
            word_counts.append(word_count)

    total = len(pages)
    avg_wc = round(sum(word_counts) / len(word_counts), 1) if word_counts else None

    return {
        "pages": pages,
        "summary": {
            "total": total,
            "status_distribution": status_dist,
            "with_title": with_title,
            "with_h1": with_h1,
            "avg_word_count": avg_wc,
        },
        "row_count": total,
    }


# ---------------------------------------------------------------------------
# External tab parser
# ---------------------------------------------------------------------------


def _parse_external(headers: list[str], data_rows: list[list[str]]) -> dict:
    url_col = find_column(headers, ["address", "url"])
    status_col = find_column(headers, ["status code", "status"])
    inlinks_col = find_column(headers, ["inlinks", "inlinks count"])

    if url_col is None:
        url_col = 0

    pages = []
    for row in data_rows:
        url = _safe_get(row, url_col)
        if not url or not _is_url(url):
            continue
        pages.append({
            "url": url,
            "http_status": safe_int(_safe_get(row, status_col) or ""),
            "inlinks": safe_int(_safe_get(row, inlinks_col) or ""),
        })

    return {
        "pages": pages,
        "summary": {"total": len(pages)},
        "row_count": len(pages),
    }


# ---------------------------------------------------------------------------
# Page Titles tab parser
# ---------------------------------------------------------------------------


def _parse_page_titles(headers: list[str], data_rows: list[list[str]]) -> dict:
    url_col = find_column(headers, ["address", "url"])
    title_col = find_column(headers, ["title 1", "title"])
    title_len_col = find_column(headers, ["title 1 length"])
    title_px_col = find_column(headers, ["title 1 pixel width", "title pixel width"])
    status_col = find_column(headers, ["status code", "status"])

    if url_col is None:
        url_col = 0

    pages = []
    missing_title = 0
    over_60 = 0

    for row in data_rows:
        url = _safe_get(row, url_col)
        if not url or not _is_url(url):
            continue
        title = _safe_get(row, title_col)
        title_len = safe_int(_safe_get(row, title_len_col) or "")
        title_px = safe_int(_safe_get(row, title_px_col) or "")

        pages.append({
            "url": url,
            "http_status": safe_int(_safe_get(row, status_col) or ""),
            "title": title,
            "title_length": title_len,
            "title_pixel_width": title_px,
        })

        if not title:
            missing_title += 1
        if title_len and title_len > 60:
            over_60 += 1

    return {
        "pages": pages,
        "summary": {
            "total": len(pages),
            "missing_title": missing_title,
            "over_60_chars": over_60,
        },
        "row_count": len(pages),
    }


# ---------------------------------------------------------------------------
# Meta Description tab parser
# ---------------------------------------------------------------------------


def _parse_meta_description(headers: list[str], data_rows: list[list[str]]) -> dict:
    url_col = find_column(headers, ["address", "url"])
    meta_col = find_column(headers, ["meta description 1", "meta description"])
    meta_len_col = find_column(headers, ["meta description 1 length"])
    status_col = find_column(headers, ["status code", "status"])

    if url_col is None:
        url_col = 0

    pages = []
    missing_meta = 0
    over_160 = 0

    for row in data_rows:
        url = _safe_get(row, url_col)
        if not url or not _is_url(url):
            continue
        meta = _safe_get(row, meta_col)
        meta_len = safe_int(_safe_get(row, meta_len_col) or "")

        pages.append({
            "url": url,
            "http_status": safe_int(_safe_get(row, status_col) or ""),
            "meta_description": meta,
            "meta_description_length": meta_len,
        })

        if not meta:
            missing_meta += 1
        if meta_len and meta_len > 160:
            over_160 += 1

    return {
        "pages": pages,
        "summary": {
            "total": len(pages),
            "missing_meta": missing_meta,
            "over_160_chars": over_160,
        },
        "row_count": len(pages),
    }


# ---------------------------------------------------------------------------
# H1 tab parser
# ---------------------------------------------------------------------------


def _parse_h1(headers: list[str], data_rows: list[list[str]]) -> dict:
    url_col = find_column(headers, ["address", "url"])
    h1_col = find_column(headers, ["h1-1", "h1"])
    h1_len_col = find_column(headers, ["h1-1 length"])
    h1_2_col = find_column(headers, ["h1-2"])
    status_col = find_column(headers, ["status code", "status"])

    if url_col is None:
        url_col = 0

    pages = []
    missing_h1 = 0
    multiple_h1 = 0

    for row in data_rows:
        url = _safe_get(row, url_col)
        if not url or not _is_url(url):
            continue
        h1 = _safe_get(row, h1_col)
        h1_len = safe_int(_safe_get(row, h1_len_col) or "")
        h1_2 = _safe_get(row, h1_2_col)

        pages.append({
            "url": url,
            "http_status": safe_int(_safe_get(row, status_col) or ""),
            "h1": h1,
            "h1_length": h1_len,
            "h1_2": h1_2,
        })

        if not h1:
            missing_h1 += 1
        if h1_2:
            multiple_h1 += 1

    return {
        "pages": pages,
        "summary": {
            "total": len(pages),
            "missing_h1": missing_h1,
            "multiple_h1": multiple_h1,
        },
        "row_count": len(pages),
    }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _safe_get(row: list[str], col: int | None) -> str | None:
    if col is None or col >= len(row):
        return None
    val = row[col].strip()
    return val if val else None


def _is_url(val: str) -> bool:
    return val.startswith("http") or val.startswith("/")


def _empty_summary() -> dict:
    return {"total": 0}
