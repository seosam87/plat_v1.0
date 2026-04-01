"""Base parser utilities: file reading, column auto-detection."""
from __future__ import annotations

import csv
import io
from pathlib import Path

import openpyxl


def read_file(path: str | Path) -> list[list[str]]:
    """Read xlsx or csv file, return rows as list of string lists.

    First row is header. Handles UTF-8 and Windows-1251 for CSV.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".xlsx":
        return _read_xlsx(path)
    elif suffix in (".csv", ".tsv"):
        return _read_csv(path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def _read_xlsx(path: Path) -> list[list[str]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append([str(cell) if cell is not None else "" for cell in row])
    wb.close()
    return rows


def _read_csv(path: Path) -> list[list[str]]:
    # Try UTF-8 first, fallback to cp1251
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            with open(path, "r", encoding=encoding, newline="") as f:
                # Auto-detect delimiter
                sample = f.read(4096)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                reader = csv.reader(f, dialect)
                return [row for row in reader]
        except (UnicodeDecodeError, csv.Error):
            continue
    raise ValueError(f"Cannot read CSV: encoding/format not supported: {path}")


def find_column(headers: list[str], candidates: list[str]) -> int | None:
    """Find column index by trying candidate names (case-insensitive, stripped)."""
    normalized = [h.strip().lower() for h in headers]
    for candidate in candidates:
        candidate_lower = candidate.strip().lower()
        for i, h in enumerate(normalized):
            if h == candidate_lower:
                return i
    # Partial match fallback
    for candidate in candidates:
        candidate_lower = candidate.strip().lower()
        for i, h in enumerate(normalized):
            if candidate_lower in h:
                return i
    return None


def safe_int(value: str) -> int | None:
    """Parse string to int, returning None on failure."""
    if not value or value.strip() in ("", "-", "n/a", "None"):
        return None
    try:
        # Handle floats like "3.0"
        return int(float(value.strip().replace(",", ".")))
    except (ValueError, TypeError):
        return None
