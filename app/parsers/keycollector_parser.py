"""Key Collector export parser.

Reads xlsx/csv files exported from Key Collector 4.

Expected columns (auto-detected):
- Phrase: "Фраза", "Keyword", "Phrase"
- Group: "Родительская группа", "Parent Group", "Группа"
- Position Yandex: "Позиция [Yandex]", "Позиция [Яндекс]"
- Position Google: "Позиция [Google]"
- URL Yandex: "URL позиции [Yandex]", "URL позиции [Яндекс]"
- URL Google: "URL позиции [Google]"
- Frequency: "Частота [YW]", "Частота", "Frequency"

Output:
- keywords: list of {phrase, group_name, frequency, positions: [{engine, position, url}]}
"""
from __future__ import annotations

from app.parsers.base import find_column, read_file, safe_int


def parse_keycollector(path: str) -> dict:
    """Parse a Key Collector export file.

    Returns:
        {
            "keywords": [{
                "phrase": str,
                "group_name": str|None,
                "frequency": int|None,
                "positions": [{"engine": "yandex"|"google", "position": int|None, "url": str|None}],
            }],
            "groups": [str],  # unique group names found
            "row_count": int,
        }
    """
    rows = read_file(path)
    if not rows:
        return {"keywords": [], "groups": [], "row_count": 0}

    headers = rows[0]
    data_rows = rows[1:]

    # Auto-detect columns
    phrase_col = find_column(headers, ["фраза", "phrase", "keyword", "ключевое слово", "запрос"])
    group_col = find_column(headers, [
        "родительская группа", "parent group", "группа", "group",
    ])
    freq_col = find_column(headers, [
        "частота [yw]", "частота", "frequency", "freq", "базовая частота",
    ])
    pos_ya_col = find_column(headers, [
        "позиция [yandex]", "позиция [яндекс]", "position yandex",
    ])
    pos_google_col = find_column(headers, [
        "позиция [google]", "position google",
    ])
    url_ya_col = find_column(headers, [
        "url позиции [yandex]", "url позиции [яндекс]",
    ])
    url_google_col = find_column(headers, [
        "url позиции [google]",
    ])

    if phrase_col is None:
        # Fallback: first column
        phrase_col = 0

    groups_seen: set[str] = set()
    keywords = []

    for row in data_rows:
        if len(row) <= phrase_col:
            continue
        phrase = row[phrase_col].strip()
        if not phrase:
            continue

        group_name = _safe_get(row, group_col)
        if group_name:
            groups_seen.add(group_name)

        frequency = safe_int(_safe_get(row, freq_col) or "") if freq_col is not None else None

        positions = []
        # Yandex
        if pos_ya_col is not None:
            pos_val = safe_int(_safe_get(row, pos_ya_col) or "")
            url_val = _safe_get(row, url_ya_col)
            if pos_val is not None or url_val:
                positions.append({"engine": "yandex", "position": pos_val, "url": url_val})
        # Google
        if pos_google_col is not None:
            pos_val = safe_int(_safe_get(row, pos_google_col) or "")
            url_val = _safe_get(row, url_google_col)
            if pos_val is not None or url_val:
                positions.append({"engine": "google", "position": pos_val, "url": url_val})

        keywords.append({
            "phrase": phrase,
            "group_name": group_name,
            "frequency": frequency,
            "positions": positions,
        })

    return {
        "keywords": keywords,
        "groups": sorted(groups_seen),
        "row_count": len(keywords),
    }


def _safe_get(row: list[str], col: int | None) -> str | None:
    if col is None or col >= len(row):
        return None
    val = row[col].strip()
    return val if val else None
