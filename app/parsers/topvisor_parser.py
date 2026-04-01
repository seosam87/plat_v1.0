"""Topvisor export parser.

Reads xlsx/csv files exported from Topvisor "Позиции" report.
First row = headers (always).

Expected columns (auto-detected):
- Keyword: first column (usually "Запросы", "Фраза", "Keyword")
- URL: column containing http or '/'
- Frequency: column with "частот" or "frequency" in header
- Date columns: headers matching DD.MM.YYYY pattern → position history

Output:
- keywords: list of {phrase, frequency, target_url}
- position_history: list of {phrase, date, position, url}
"""
from __future__ import annotations

import re
from datetime import datetime

from app.parsers.base import find_column, read_file, safe_int

# Regex for DD.MM.YYYY date headers
_DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def parse_topvisor(path: str) -> dict:
    """Parse a Topvisor export file.

    Returns:
        {
            "keywords": [{"phrase": str, "frequency": int|None, "target_url": str|None}],
            "position_history": [{"phrase": str, "date": str (YYYY-MM-DD), "position": int|None, "url": str|None}],
            "date_columns": [str],  # discovered date headers
            "row_count": int,
        }
    """
    rows = read_file(path)
    if not rows:
        return {"keywords": [], "position_history": [], "date_columns": [], "row_count": 0}

    headers = rows[0]
    data_rows = rows[1:]

    # Find keyword column (first column by default, or by name)
    kw_col = find_column(headers, ["запросы", "фраза", "keyword", "ключевое слово"])
    if kw_col is None:
        kw_col = 0  # Topvisor always puts keywords in first column

    # Find URL column
    url_col = _find_url_column(headers)

    # Find frequency column
    freq_col = find_column(headers, ["частота", "частотность", "frequency", "freq"])

    # Find date columns
    date_cols: list[tuple[int, str]] = []
    for i, h in enumerate(headers):
        h_stripped = h.strip()
        if _DATE_RE.match(h_stripped):
            # Convert DD.MM.YYYY → YYYY-MM-DD for storage
            try:
                dt = datetime.strptime(h_stripped, "%d.%m.%Y")
                date_cols.append((i, dt.strftime("%Y-%m-%d")))
            except ValueError:
                pass

    keywords = []
    position_history = []

    for row in data_rows:
        if len(row) <= kw_col:
            continue
        phrase = row[kw_col].strip()
        if not phrase:
            continue

        frequency = safe_int(row[freq_col]) if freq_col is not None and len(row) > freq_col else None
        target_url = row[url_col].strip() if url_col is not None and len(row) > url_col and row[url_col].strip() else None

        keywords.append({
            "phrase": phrase,
            "frequency": frequency,
            "target_url": target_url,
        })

        # Extract position history from date columns
        for col_idx, date_str in date_cols:
            if len(row) > col_idx:
                pos = safe_int(row[col_idx])
                position_history.append({
                    "phrase": phrase,
                    "date": date_str,
                    "position": pos,
                    "url": target_url,
                })

    return {
        "keywords": keywords,
        "position_history": position_history,
        "date_columns": [d[1] for d in date_cols],
        "row_count": len(keywords),
    }


def _find_url_column(headers: list[str]) -> int | None:
    """Find URL column: look for header with 'url' or column values containing 'http'."""
    # By header name first
    idx = find_column(headers, ["url", "адрес", "address", "целевая страница"])
    if idx is not None:
        return idx
    # Check if any header contains http (sometimes URL is a header itself)
    for i, h in enumerate(headers):
        if "http" in h.lower() or "url" in h.lower():
            return i
    return None
