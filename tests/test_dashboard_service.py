"""Unit tests for dashboard_service.projects_table()."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(**kwargs):
    """Create a mapping-like row with the expected dashboard columns."""
    defaults = {
        "id": "aaaaaaaa-0000-0000-0000-000000000001",
        "name": "Test Project",
        "status": "active",
        "site_name": "example.com",
        "site_id": "bbbbbbbb-0000-0000-0000-000000000002",
        "open_tasks": 3,
        "in_progress_tasks": 1,
        "top3": 5,
        "top10": 20,
        "top30": 50,
        "total_positions": 100,
        "created_at": "2026-01-01T00:00:00",
    }
    defaults.update(kwargs)
    return MagicMock(**{"__getitem__": lambda self, k: defaults[k], "keys": lambda self: defaults.keys()})


# ---------------------------------------------------------------------------
# Test: cache miss — SQL executed, result cached and returned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_projects_table_cache_miss():
    """On cache miss: SQL runs, result is cached, list of dicts returned."""
    row = _make_row()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # cache miss
    mock_redis.set = AsyncMock()
    mock_redis.aclose = AsyncMock()

    mock_mappings = MagicMock()
    mock_mappings.all.return_value = [row]

    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mappings

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.dashboard_service._get_redis", return_value=AsyncMock(return_value=mock_redis)):
        from app.services.dashboard_service import projects_table

        # Patch _get_redis to be a coroutine returning our mock_redis
        async def fake_get_redis():
            return mock_redis

        with patch("app.services.dashboard_service._get_redis", fake_get_redis):
            result = await projects_table(mock_db)

    assert isinstance(result, list)
    assert len(result) == 1
    item = result[0]
    assert item["id"] == "aaaaaaaa-0000-0000-0000-000000000001"
    assert item["name"] == "Test Project"
    assert item["status"] == "active"
    assert item["site_name"] == "example.com"
    assert item["open_tasks"] == 3
    assert item["in_progress_tasks"] == 1
    assert item["top3"] == 5
    assert item["top10"] == 20
    assert item["top30"] == 50
    assert item["total_positions"] == 100

    # Verify redis.set was called with correct key and TTL
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert call_args[0][0] == "dashboard:projects_table"
    assert call_args[1]["ex"] == 300


# ---------------------------------------------------------------------------
# Test: cache hit — DB not queried, cached value returned directly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_projects_table_cache_hit():
    """On cache hit: DB is NOT called, cached JSON is deserialized and returned."""
    cached_data = [
        {
            "id": "cccccccc-0000-0000-0000-000000000003",
            "name": "Cached Project",
            "status": "active",
            "site_name": "cached.com",
            "site_id": "dddddddd-0000-0000-0000-000000000004",
            "open_tasks": 2,
            "in_progress_tasks": 0,
            "top3": 10,
            "top10": 30,
            "top30": 60,
            "total_positions": 120,
        }
    ]

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))
    mock_redis.set = AsyncMock()
    mock_redis.aclose = AsyncMock()

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()  # should NOT be called

    async def fake_get_redis():
        return mock_redis

    with patch("app.services.dashboard_service._get_redis", fake_get_redis):
        from app.services.dashboard_service import projects_table
        result = await projects_table(mock_db)

    assert result == cached_data
    mock_db.execute.assert_not_called()
    mock_redis.set.assert_not_called()


# ---------------------------------------------------------------------------
# Test: empty result — empty list cached and returned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_projects_table_empty_result():
    """When no active projects exist, an empty list is returned and cached."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.aclose = AsyncMock()

    mock_mappings = MagicMock()
    mock_mappings.all.return_value = []

    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mappings

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def fake_get_redis():
        return mock_redis

    with patch("app.services.dashboard_service._get_redis", fake_get_redis):
        from app.services.dashboard_service import projects_table
        result = await projects_table(mock_db)

    assert result == []
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert json.loads(call_args[0][1]) == []
