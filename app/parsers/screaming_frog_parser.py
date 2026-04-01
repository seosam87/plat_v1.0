"""Screaming Frog export parser.

Reads xlsx/csv files exported from Screaming Frog ("Export > Internal > All").

Expected columns (auto-detected):
- URL: "Address", "URL", "Url"
- Status: "Status Code", "Status"
- Title: "Title 1", "Title", "Page Title"
- H1: "H1-1", "H1", "Heading 1"
- Word Count: "Word Count", "WordCount"
- Inlinks: "Inlinks", "Inlinks Count", "Unique Inlinks"

Output:
- pages: list of {url, http_status, title, h1, word_count, inlinks}
"""
from __future__ import annotations

from app.parsers.base import find_column, read_file, safe_int


def parse_screaming_frog(path: str) -> dict:
    """Parse a Screaming Frog export file.

    Returns:
        {
            "pages": [{
                "url": str,
                "http_status": int|None,
                "title": str|None,
                "h1": str|None,
                "word_count": int|None,
                "inlinks": int|None,
            }],
            "summary": {
                "total": int,
                "status_distribution": dict[str, int],
                "with_title": int,
                "with_h1": int,
                "avg_word_count": float|None,
            },
            "row_count": int,
        }
    """
    rows = read_file(path)
    if not rows:
        return {"pages": [], "summary": _empty_summary(), "row_count": 0}

    headers = rows[0]
    data_rows = rows[1:]

    url_col = find_column(headers, ["address", "url", "адрес"])
    status_col = find_column(headers, ["status code", "status", "statuscode", "код ответа"])
    title_col = find_column(headers, ["title 1", "title", "page title", "заголовок"])
    h1_col = find_column(headers, ["h1-1", "h1", "heading 1", "заголовок h1"])
    wc_col = find_column(headers, ["word count", "wordcount", "words", "слова"])
    inlinks_col = find_column(headers, [
        "unique inlinks", "inlinks", "inlinks count", "входящие ссылки",
    ])

    if url_col is None:
        url_col = 0

    pages = []
    status_dist: dict[str, int] = {}
    with_title = 0
    with_h1 = 0
    word_counts: list[int] = []

    for row in data_rows:
        if len(row) <= url_col:
            continue
        url = row[url_col].strip()
        if not url or not (url.startswith("http") or url.startswith("/")):
            continue

        http_status = safe_int(row[status_col] if status_col is not None and len(row) > status_col else "")
        title = _safe_get(row, title_col)
        h1 = _safe_get(row, h1_col)
        word_count = safe_int(row[wc_col] if wc_col is not None and len(row) > wc_col else "")
        inlinks = safe_int(row[inlinks_col] if inlinks_col is not None and len(row) > inlinks_col else "")

        pages.append({
            "url": url,
            "http_status": http_status,
            "title": title,
            "h1": h1,
            "word_count": word_count,
            "inlinks": inlinks,
        })

        # Stats
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


def _safe_get(row: list[str], col: int | None) -> str | None:
    if col is None or col >= len(row):
        return None
    val = row[col].strip()
    return val if val else None


def _empty_summary() -> dict:
    return {
        "total": 0,
        "status_distribution": {},
        "with_title": 0,
        "with_h1": 0,
        "avg_word_count": None,
    }
