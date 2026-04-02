"""Tests for bulk service: export functions."""
import types

from app.services.bulk_service import _keywords_to_csv, _keywords_to_xlsx


def _make_kw(**kwargs):
    defaults = {
        "phrase": "test keyword",
        "frequency": 100,
        "region": "Moscow",
        "engine": types.SimpleNamespace(value="yandex"),
        "target_url": "https://e.com/page/",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def test_csv_export_format():
    keywords = [_make_kw(phrase="seo продвижение", frequency=1000)]
    csv_str = _keywords_to_csv(keywords)
    assert "Phrase" in csv_str
    assert "seo продвижение" in csv_str
    assert "1000" in csv_str


def test_csv_export_empty():
    csv_str = _keywords_to_csv([])
    lines = csv_str.strip().split("\n")
    assert len(lines) == 1  # header only
    assert "Phrase" in lines[0]


def test_xlsx_export_produces_bytes():
    keywords = [_make_kw()]
    result = _keywords_to_xlsx(keywords)
    assert isinstance(result, bytes)
    assert len(result) > 100
    # XLSX magic bytes: PK (zip format)
    assert result[:2] == b"PK"


def test_csv_export_multiple():
    keywords = [_make_kw(phrase=f"kw{i}") for i in range(5)]
    csv_str = _keywords_to_csv(keywords)
    lines = csv_str.strip().split("\n")
    assert len(lines) == 6  # header + 5
