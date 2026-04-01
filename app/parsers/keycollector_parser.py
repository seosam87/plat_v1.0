"""Key Collector export parser.

Reads xlsx/csv files exported from Key Collector 4.

Expected columns (auto-detected):
- Phrase: "Фраза", "Keyword", "Phrase"
- Group: "Родительская группа", "Parent Group", "Группа"
- Position Yandex: "Позиция [Yandex]", "Позиция [Яндекс]"
- URL Yandex: "URL позиции [Yandex]", "URL позиции [Яндекс]"

Note: KC files in this project contain only Yandex data (no Google, no frequency).
Groups support nesting via "Родительская группа" column.

Output:
- keywords: list of {phrase, group_name, position, url}
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
                "position": int|None,
                "url": str|None,
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
    pos_col = find_column(headers, [
        "позиция [yandex]", "позиция [яндекс]", "position yandex", "позиция",
    ])
    url_col = find_column(headers, [
        "url позиции [yandex]", "url позиции [яндекс]", "url позиции",
    ])

    if phrase_col is None:
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

        position = safe_int(_safe_get(row, pos_col) or "") if pos_col is not None else None
        url = _safe_get(row, url_col)

        keywords.append({
            "phrase": phrase,
            "group_name": group_name,
            "position": position,
            "url": url,
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
