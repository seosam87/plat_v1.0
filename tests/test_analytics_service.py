"""Tests for analytics service: CSV export, filter options format."""
from app.services.analytics_service import export_session_keywords_csv


def test_csv_export_basic():
    keywords = [
        {"phrase": "seo продвижение", "frequency": 1000, "region": "Moscow", "target_url": "https://e.com/seo/", "latest_position": 5, "delta": 2},
        {"phrase": "раскрутка сайта", "frequency": 500, "region": None, "target_url": None, "latest_position": None, "delta": None},
    ]
    csv_str = export_session_keywords_csv(keywords)
    assert "Phrase" in csv_str
    assert "seo продвижение" in csv_str
    assert "раскрутка сайта" in csv_str


def test_csv_export_empty():
    csv_str = export_session_keywords_csv([])
    lines = csv_str.strip().split("\n")
    assert len(lines) == 1  # header only


def test_csv_export_header_columns():
    csv_str = export_session_keywords_csv([])
    header = csv_str.strip().split("\n")[0]
    assert "Phrase" in header
    assert "Frequency" in header
    assert "Position" in header
    assert "Delta" in header


def test_csv_export_preserves_frequency():
    keywords = [{"phrase": "test", "frequency": 42, "region": "", "target_url": "", "latest_position": 3, "delta": -1}]
    csv_str = export_session_keywords_csv(keywords)
    assert "42" in csv_str


def test_csv_export_handles_none():
    keywords = [{"phrase": "test", "frequency": None}]
    csv_str = export_session_keywords_csv(keywords)
    assert "test" in csv_str


def test_csv_export_multiple_rows():
    keywords = [{"phrase": f"kw{i}", "frequency": i * 100} for i in range(5)]
    csv_str = export_session_keywords_csv(keywords)
    lines = csv_str.strip().split("\n")
    assert len(lines) == 6  # header + 5 data rows
