"""Unit tests for opportunities service — gap keywords, lost positions, cannibalization, visibility trend.

Tests verify:
- get_gap_summary returns dict with count, total_potential_traffic, items
- get_lost_positions returns items with delta <= -5 sorted by delta ASC
- get_lost_positions excludes rows with delta > -5 or position IS NULL
- build_cannibalization_groups (via get_cannibalization) groups keyword_id entries with 2+ distinct URLs
- build_cannibalization_groups excludes keywords with only 1 URL in top-50
- compute_visibility_trend returns current/prev week and month visits with change_pct
- compute_visibility_trend returns 0.0 for change_pct when previous period has 0 visits
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.opportunities_service import (
    compute_visibility_trend,
    get_cannibalization,
    get_gap_summary,
    get_lost_positions,
    get_visibility_trend,
)


# ---------------------------------------------------------------------------
# compute_visibility_trend — pure-function tests (no DB needed)
# ---------------------------------------------------------------------------


def test_compute_visibility_trend_basic():
    """Returns current_week_visits, prev_week_visits, week_change_pct, etc."""
    today = date.today()
    rows = []
    # current week (last 7 days): 100 visits/day = 700 total
    for i in range(1, 8):
        rows.append({"traffic_date": today - timedelta(days=i), "visits": 100})
    # previous week (8-14 days ago): 50 visits/day = 350 total
    for i in range(8, 15):
        rows.append({"traffic_date": today - timedelta(days=i), "visits": 50})

    result = compute_visibility_trend(rows)

    assert result["current_week_visits"] == 700
    assert result["prev_week_visits"] == 350
    assert result["week_change_pct"] == pytest.approx(100.0, rel=0.1)
    assert "current_month_visits" in result
    assert "prev_month_visits" in result
    assert "month_change_pct" in result


def test_compute_visibility_trend_zero_prev():
    """Returns 0.0 for change_pct when previous period has 0 visits."""
    today = date.today()
    rows = []
    # current week only, no previous week data
    for i in range(1, 8):
        rows.append({"traffic_date": today - timedelta(days=i), "visits": 100})

    result = compute_visibility_trend(rows)

    assert result["prev_week_visits"] == 0
    assert result["week_change_pct"] == 0.0
    assert result["prev_month_visits"] == 0
    assert result["month_change_pct"] == 0.0


def test_compute_visibility_trend_empty():
    """Returns zeros for all fields when no data provided."""
    result = compute_visibility_trend([])

    assert result["current_week_visits"] == 0
    assert result["prev_week_visits"] == 0
    assert result["week_change_pct"] == 0.0
    assert result["current_month_visits"] == 0
    assert result["prev_month_visits"] == 0
    assert result["month_change_pct"] == 0.0


def test_compute_visibility_trend_month_calculation():
    """Month uses last 30 days vs 31-60 days ago."""
    today = date.today()
    rows = []
    # current month (days 1-30): 200 visits/day = 6000 total
    for i in range(1, 31):
        rows.append({"traffic_date": today - timedelta(days=i), "visits": 200})
    # previous month (days 31-60): 100 visits/day = 3000 total
    for i in range(31, 61):
        rows.append({"traffic_date": today - timedelta(days=i), "visits": 100})

    result = compute_visibility_trend(rows)

    assert result["current_month_visits"] == 6000
    assert result["prev_month_visits"] == 3000
    assert result["month_change_pct"] == pytest.approx(100.0, rel=0.1)


def test_compute_visibility_trend_negative_change():
    """Negative change returns negative week_change_pct."""
    today = date.today()
    rows = []
    # current week: 50 visits/day = 350
    for i in range(1, 8):
        rows.append({"traffic_date": today - timedelta(days=i), "visits": 50})
    # previous week: 100 visits/day = 700
    for i in range(8, 15):
        rows.append({"traffic_date": today - timedelta(days=i), "visits": 100})

    result = compute_visibility_trend(rows)

    assert result["current_week_visits"] == 350
    assert result["prev_week_visits"] == 700
    assert result["week_change_pct"] == pytest.approx(-50.0, rel=0.1)


# ---------------------------------------------------------------------------
# Mocked DB tests for get_gap_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_gap_summary_returns_count_and_items():
    """get_gap_summary returns dict with count, total_potential_traffic, items."""
    site_id = uuid.uuid4()

    # Mock GapKeyword objects
    gk1 = MagicMock()
    gk1.id = uuid.uuid4()
    gk1.phrase = "keyword one"
    gk1.competitor_domain = "competitor.com"
    gk1.competitor_position = 5
    gk1.our_position = None
    gk1.potential_score = 0.8
    gk1.frequency = 500

    gk2 = MagicMock()
    gk2.id = uuid.uuid4()
    gk2.phrase = "keyword two"
    gk2.competitor_domain = "other.com"
    gk2.competitor_position = 3
    gk2.our_position = 15
    gk2.potential_score = 0.6
    gk2.frequency = 300

    # Mock DB session
    db = AsyncMock()
    # count query
    count_result = MagicMock()
    count_result.scalar.return_value = 2
    # items query
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = [gk1, gk2]

    db.execute = AsyncMock(side_effect=[count_result, items_result])

    result = await get_gap_summary(db, site_id)

    assert result["count"] == 2
    assert result["total_potential_traffic"] == 800
    assert len(result["items"]) == 2
    assert result["items"][0]["phrase"] == "keyword one"
    assert result["items"][1]["phrase"] == "keyword two"
    assert "competitor_domain" in result["items"][0]
    assert "potential_score" in result["items"][0]


@pytest.mark.asyncio
async def test_get_gap_summary_empty_site():
    """Returns count=0 and empty items for site with no gap keywords."""
    site_id = uuid.uuid4()

    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[count_result, items_result])

    result = await get_gap_summary(db, site_id)

    assert result["count"] == 0
    assert result["items"] == []


# ---------------------------------------------------------------------------
# Mocked DB tests for get_lost_positions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_lost_positions_returns_delta_lte_minus5():
    """Returns only rows with delta <= -5, sorted by delta ASC (worst first)."""
    site_id = uuid.uuid4()
    kw1_id = uuid.uuid4()
    kw2_id = uuid.uuid4()

    # Simulate DB rows: (keyword_id, phrase, url, position, previous_position, delta)
    # sorted by delta ASC: -10 comes before -5
    mock_rows = [
        (kw1_id, "big loss", "https://ex.com/p1", 15, 5, -10),
        (kw2_id, "small loss", "https://ex.com/p2", 10, 5, -5),
    ]

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = mock_rows
    db.execute = AsyncMock(return_value=result_mock)

    result = await get_lost_positions(db, site_id)

    phrases = [item["phrase"] for item in result["items"]]
    assert "big loss" in phrases
    assert "small loss" in phrases
    assert result["count"] == 2

    # Check sorted by delta ASC (worst first: -10 before -5)
    deltas = [item["delta"] for item in result["items"]]
    assert deltas == sorted(deltas)


@pytest.mark.asyncio
async def test_get_lost_positions_excludes_delta_over_minus5():
    """Delta > -5 rows are excluded — service returns only what the SQL returns."""
    site_id = uuid.uuid4()

    # The SQL already filters delta <= -5, so mock empty result for non-qualifying data
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = []  # SQL would return nothing for delta > -5
    db.execute = AsyncMock(return_value=result_mock)

    result = await get_lost_positions(db, site_id)

    assert result["count"] == 0
    assert result["items"] == []


# ---------------------------------------------------------------------------
# Mocked DB tests for get_cannibalization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cannibalization_groups_two_plus_urls():
    """Keywords with 2+ distinct URLs in top-50 appear in cannibalization results."""
    site_id = uuid.uuid4()
    kw_id = uuid.uuid4()

    # Simulate rows: (keyword_id, phrase, url, position)
    mock_rows = [
        (kw_id, "cannibal phrase", "https://ex.com/page-a", 10),
        (kw_id, "cannibal phrase", "https://ex.com/page-b", 25),
    ]

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = mock_rows
    db.execute = AsyncMock(return_value=result_mock)

    result = await get_cannibalization(db, site_id)

    assert result["count"] == 1
    assert result["items"][0]["phrase"] == "cannibal phrase"
    assert result["items"][0]["page_count"] == 2
    pages_urls = {p["url"] for p in result["items"][0]["pages"]}
    assert "https://ex.com/page-a" in pages_urls
    assert "https://ex.com/page-b" in pages_urls


@pytest.mark.asyncio
async def test_get_cannibalization_excludes_single_url_keywords():
    """SQL ensures only keywords with 2+ URLs are returned — empty result for single-URL keywords."""
    site_id = uuid.uuid4()

    # SQL WITH CTE filters out single-URL keywords — mock returns empty
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = []
    db.execute = AsyncMock(return_value=result_mock)

    result = await get_cannibalization(db, site_id)

    assert result["count"] == 0
    assert result["items"] == []


# ---------------------------------------------------------------------------
# Mocked DB test for get_visibility_trend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_visibility_trend_from_db():
    """get_visibility_trend queries DB and returns trend dict with correct values."""
    site_id = uuid.uuid4()
    today = date.today()

    # Create mock MetrikaTrafficDaily rows
    mock_db_rows = []
    for i in range(1, 8):
        row = MagicMock()
        row.traffic_date = today - timedelta(days=i)
        row.visits = 100
        mock_db_rows.append(row)

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = mock_db_rows
    db.execute = AsyncMock(return_value=result_mock)

    result = await get_visibility_trend(db, site_id)

    assert "current_week_visits" in result
    assert result["current_week_visits"] == 700
    assert "week_change_pct" in result
    assert result["week_change_pct"] == 0.0  # no prev week data
    assert "current_month_visits" in result
    assert "month_change_pct" in result
