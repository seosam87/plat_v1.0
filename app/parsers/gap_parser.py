"""Parser for competitor keyword files (keys.so, Topvisor, generic CSV/XLSX)."""
from __future__ import annotations

from app.parsers.base import find_column, safe_int

# Column candidate names for auto-detection
_PHRASE_CANDIDATES = ["Запрос", "Ключ", "Keyword", "phrase", "query", "ключевое слово"]
_FREQUENCY_CANDIDATES = ["Частотность", "Частота", "Frequency", "Volume", "freq", "volume", "ws"]
_POSITION_CANDIDATES = ["Позиция", "Position", "pos", "rank", "Ранг"]


def parse_gap_file(rows: list[list[str]]) -> list[dict]:
    """Parse competitor keyword file rows into structured dicts.

    Supports keys.so, Topvisor position exports, and generic formats.
    Returns [{phrase, frequency, position}].
    """
    if not rows or len(rows) < 2:
        return []

    header = rows[0]
    phrase_col = find_column(header, _PHRASE_CANDIDATES)
    freq_col = find_column(header, _FREQUENCY_CANDIDATES)
    pos_col = find_column(header, _POSITION_CANDIDATES)

    if phrase_col is None:
        return []

    results = []
    for row in rows[1:]:
        if not row or len(row) <= phrase_col:
            continue

        phrase = row[phrase_col].strip()
        if not phrase or phrase == "-":
            continue

        frequency = safe_int(row[freq_col]) if freq_col is not None and len(row) > freq_col else None
        position = safe_int(row[pos_col]) if pos_col is not None and len(row) > pos_col else None

        results.append({
            "phrase": phrase,
            "frequency": frequency,
            "position": position,
        })

    return results
