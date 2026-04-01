"""Unit tests for metrika_service pure computation functions."""
from app.services.metrika_service import compute_period_delta


def test_compute_period_delta_basic():
    rows_a = [
        {"page_url": "/page-1/", "visits": 100, "bounce_rate": 30.0, "page_depth": 3.0, "avg_duration_seconds": 120},
        {"page_url": "/page-2/", "visits": 50, "bounce_rate": 40.0, "page_depth": 2.0, "avg_duration_seconds": 90},
    ]
    rows_b = [
        {"page_url": "/page-1/", "visits": 150, "bounce_rate": 25.0, "page_depth": 3.5, "avg_duration_seconds": 140},
        {"page_url": "/page-3/", "visits": 30, "bounce_rate": 50.0, "page_depth": 1.5, "avg_duration_seconds": 60},
    ]
    result = compute_period_delta(rows_a, rows_b)
    assert len(result) == 3  # page-1, page-2, page-3

    by_url = {r["page_url"]: r for r in result}

    # page-1: growth
    assert by_url["/page-1/"]["visits_delta"] == 50
    assert by_url["/page-1/"]["is_new"] is False
    assert by_url["/page-1/"]["is_lost"] is False

    # page-2: lost
    assert by_url["/page-2/"]["visits_b"] == 0
    assert by_url["/page-2/"]["is_lost"] is True

    # page-3: new
    assert by_url["/page-3/"]["visits_a"] == 0
    assert by_url["/page-3/"]["is_new"] is True


def test_compute_period_delta_empty():
    result = compute_period_delta([], [])
    assert result == []


def test_compute_period_delta_sorted_by_visits_b():
    rows_a = [{"page_url": "/a/", "visits": 10, "bounce_rate": None, "page_depth": None, "avg_duration_seconds": None}]
    rows_b = [
        {"page_url": "/a/", "visits": 5, "bounce_rate": None, "page_depth": None, "avg_duration_seconds": None},
        {"page_url": "/b/", "visits": 20, "bounce_rate": None, "page_depth": None, "avg_duration_seconds": None},
    ]
    result = compute_period_delta(rows_a, rows_b)
    assert result[0]["page_url"] == "/b/"  # highest visits_b first
    assert result[1]["page_url"] == "/a/"
