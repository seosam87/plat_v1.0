"""Tests for ad traffic comparison service: CR%, CPC, trend."""
from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.report_service import ad_traffic_comparison, ad_traffic_trend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_row(source: str, sessions: int, conversions: int, cost: float):
    """Create a mock result row with named attributes."""
    row = MagicMock()
    row.source = source
    row.sessions = sessions
    row.conversions = conversions
    row.cost = cost
    return row


def _make_execute_result(rows):
    """Return an AsyncMock for db.execute() that yields the given rows."""
    result = MagicMock()
    result.return_value = rows
    mock = MagicMock()
    mock.__iter__ = lambda self: iter(rows)
    return mock


# ---------------------------------------------------------------------------
# ad_traffic_comparison tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_comparison_includes_cr_and_cpc_fields():
    """ad_traffic_comparison must return cr_a, cr_b, cpc_a, cpc_b per source."""
    site_id = uuid.uuid4()
    pa_start = date(2024, 1, 1)
    pa_end = date(2024, 1, 31)
    pb_start = date(2024, 2, 1)
    pb_end = date(2024, 2, 29)

    row_a = _make_db_row("Yandex Direct", sessions=100, conversions=10, cost=5000.0)
    row_b = _make_db_row("Yandex Direct", sessions=120, conversions=15, cost=6000.0)

    db = AsyncMock()

    call_count = 0

    async def fake_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.__iter__ = lambda s: iter([row_a])
        else:
            result.__iter__ = lambda s: iter([row_b])
        return result

    db.execute = fake_execute

    result = await ad_traffic_comparison(db, site_id, pa_start, pa_end, pb_start, pb_end)

    assert len(result) == 1
    row = result[0]
    assert "cr_a" in row
    assert "cr_b" in row
    assert "delta_cr_pct" in row
    assert "cpc_a" in row
    assert "cpc_b" in row
    assert "delta_cpc_pct" in row

    # cr_a = 10/100*100 = 10.0
    assert row["cr_a"] == pytest.approx(10.0, abs=0.01)
    # cr_b = 15/120*100 = 12.5
    assert row["cr_b"] == pytest.approx(12.5, abs=0.01)

    # cpc_a = 5000/10 = 500.0
    assert row["cpc_a"] == pytest.approx(500.0, abs=0.01)
    # cpc_b = 6000/15 = 400.0
    assert row["cpc_b"] == pytest.approx(400.0, abs=0.01)


@pytest.mark.asyncio
async def test_cr_handles_zero_sessions():
    """CR% must return 0.0 (not division error) when sessions == 0."""
    site_id = uuid.uuid4()
    pa_start = date(2024, 1, 1)
    pa_end = date(2024, 1, 31)
    pb_start = date(2024, 2, 1)
    pb_end = date(2024, 2, 29)

    row_a = _make_db_row("Yandex Direct", sessions=0, conversions=0, cost=0.0)
    row_b = _make_db_row("Yandex Direct", sessions=50, conversions=5, cost=1000.0)

    db = AsyncMock()
    call_count = 0

    async def fake_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.__iter__ = lambda s: iter([row_a])
        else:
            result.__iter__ = lambda s: iter([row_b])
        return result

    db.execute = fake_execute

    result = await ad_traffic_comparison(db, site_id, pa_start, pa_end, pb_start, pb_end)

    assert len(result) == 1
    row = result[0]
    # Sessions == 0 should give CR% = 0.0, not an exception
    assert row["cr_a"] == 0.0


@pytest.mark.asyncio
async def test_cpc_handles_zero_conversions():
    """CPC must return None (not division error) when conversions == 0."""
    site_id = uuid.uuid4()
    pa_start = date(2024, 1, 1)
    pa_end = date(2024, 1, 31)
    pb_start = date(2024, 2, 1)
    pb_end = date(2024, 2, 29)

    row_a = _make_db_row("Yandex Direct", sessions=100, conversions=0, cost=5000.0)
    row_b = _make_db_row("Yandex Direct", sessions=120, conversions=0, cost=6000.0)

    db = AsyncMock()
    call_count = 0

    async def fake_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.__iter__ = lambda s: iter([row_a])
        else:
            result.__iter__ = lambda s: iter([row_b])
        return result

    db.execute = fake_execute

    result = await ad_traffic_comparison(db, site_id, pa_start, pa_end, pb_start, pb_end)

    assert len(result) == 1
    row = result[0]
    # Conversions == 0 → CPC must be None
    assert row["cpc_a"] is None
    assert row["cpc_b"] is None
    assert row["delta_cpc_pct"] is None


# ---------------------------------------------------------------------------
# ad_traffic_trend tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trend_returns_labels_and_datasets():
    """ad_traffic_trend must return dict with 'labels' and 'datasets' keys."""
    site_id = uuid.uuid4()

    trend_row_1 = MagicMock()
    trend_row_1.__getitem__ = lambda self, key: {
        "source": "Yandex Direct",
        "period": date(2024, 1, 1),
        "sessions": 100,
    }[key]

    trend_row_2 = MagicMock()
    trend_row_2.__getitem__ = lambda self, key: {
        "source": "Yandex Direct",
        "period": date(2024, 1, 8),
        "sessions": 120,
    }[key]

    db = AsyncMock()

    async def fake_execute(*args, **kwargs):
        result = MagicMock()
        mappings_result = MagicMock()
        mappings_result.all.return_value = [trend_row_1, trend_row_2]
        result.mappings.return_value = mappings_result
        return result

    db.execute = fake_execute

    data = await ad_traffic_trend(db, site_id, granularity="weekly")

    assert "labels" in data
    assert "datasets" in data
    assert isinstance(data["labels"], list)
    assert isinstance(data["datasets"], list)


@pytest.mark.asyncio
async def test_trend_empty_returns_empty_labels():
    """ad_traffic_trend with no data returns empty labels and datasets."""
    site_id = uuid.uuid4()
    db = AsyncMock()

    async def fake_execute(*args, **kwargs):
        result = MagicMock()
        mappings_result = MagicMock()
        mappings_result.all.return_value = []
        result.mappings.return_value = mappings_result
        return result

    db.execute = fake_execute

    data = await ad_traffic_trend(db, site_id, granularity="monthly")

    assert data["labels"] == []
    assert data["datasets"] == []
