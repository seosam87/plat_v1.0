"""Unit tests for app.services.overview_service."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.task import TaskPriority, TaskStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    *,
    status: TaskStatus = TaskStatus.open,
    priority: TaskPriority = TaskPriority.p3,
    due_date: date | None = None,
) -> MagicMock:
    task = MagicMock()
    task.id = uuid.uuid4()
    task.site_id = uuid.uuid4()
    task.title = "Test task"
    task.url = "https://example.com/page"
    task.priority = priority
    task.status = status
    task.due_date = due_date
    return task


def _make_redis_mock(cached_value: str | None = None) -> MagicMock:
    """Return an async-compatible Redis mock."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=cached_value)
    redis_mock.set = AsyncMock()
    redis_mock.aclose = AsyncMock()
    return redis_mock


# ---------------------------------------------------------------------------
# aggregated_positions — cache hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregated_positions_cache_hit():
    """Cache hit: returns parsed dict without calling db.execute."""
    cached_data = {"top3": 5, "top10": 20, "top100": 80, "trend_up": 10, "trend_down": 3}
    cached_json = json.dumps(cached_data)

    redis_mock = _make_redis_mock(cached_value=cached_json)
    db_mock = AsyncMock()

    async def _fake_get_redis():
        return redis_mock

    with patch("app.services.overview_service._get_redis", side_effect=_fake_get_redis):
        from app.services.overview_service import aggregated_positions

        result = await aggregated_positions(db_mock)

    assert result == cached_data
    db_mock.execute.assert_not_called()
    redis_mock.set.assert_not_called()


# ---------------------------------------------------------------------------
# aggregated_positions — cache miss
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregated_positions_cache_miss():
    """Cache miss: calls db.execute, stores JSON in cache, returns correct keys."""
    redis_mock = _make_redis_mock(cached_value=None)

    # Build a fake DB row
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "top3": 4,
        "top10": 15,
        "top100": 60,
        "trend_up": 7,
        "trend_down": 2,
    }[key]

    mappings_mock = MagicMock()
    mappings_mock.one_or_none.return_value = row

    execute_result = MagicMock()
    execute_result.mappings.return_value = mappings_mock

    db_mock = AsyncMock()
    db_mock.execute = AsyncMock(return_value=execute_result)

    # Patch _get_redis as a coroutine returning the mock
    async def _fake_get_redis():
        return redis_mock

    with patch("app.services.overview_service._get_redis", side_effect=_fake_get_redis):
        from app.services.overview_service import aggregated_positions

        result = await aggregated_positions(db_mock)

    assert result["top3"] == 4
    assert result["top10"] == 15
    assert result["top100"] == 60
    assert result["trend_up"] == 7
    assert result["trend_down"] == 2
    assert set(result.keys()) == {"top3", "top10", "top100", "trend_up", "trend_down"}

    # Confirm cache was written with correct TTL
    redis_mock.set.assert_called_once()
    call_kwargs = redis_mock.set.call_args
    assert call_kwargs.kwargs.get("ex") == 300 or (
        len(call_kwargs.args) >= 3 and call_kwargs.args[2] == 300
    )


# ---------------------------------------------------------------------------
# todays_tasks — empty result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_todays_tasks_empty():
    """Returns empty list when DB returns no rows."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock

    db_mock = AsyncMock()
    db_mock.execute = AsyncMock(return_value=execute_result)

    from app.services.overview_service import todays_tasks

    result = await todays_tasks(db_mock)
    assert result == []


# ---------------------------------------------------------------------------
# todays_tasks — is_overdue logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_todays_tasks_is_overdue_yesterday():
    """is_overdue=True for tasks with due_date yesterday."""
    yesterday = date.today() - timedelta(days=1)
    task = _make_task(status=TaskStatus.open, due_date=yesterday)

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [task]

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock

    db_mock = AsyncMock()
    db_mock.execute = AsyncMock(return_value=execute_result)

    from app.services.overview_service import todays_tasks

    result = await todays_tasks(db_mock)
    assert len(result) == 1
    assert result[0]["is_overdue"] is True


@pytest.mark.asyncio
async def test_todays_tasks_is_overdue_today_is_false():
    """is_overdue=False for tasks with due_date today (today is due, not overdue)."""
    today = date.today()
    task = _make_task(status=TaskStatus.open, due_date=today)

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [task]

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock

    db_mock = AsyncMock()
    db_mock.execute = AsyncMock(return_value=execute_result)

    from app.services.overview_service import todays_tasks

    result = await todays_tasks(db_mock)
    assert len(result) == 1
    assert result[0]["is_overdue"] is False


@pytest.mark.asyncio
async def test_todays_tasks_in_progress_no_due_date_not_overdue():
    """is_overdue=False for in_progress task with no due_date."""
    task = _make_task(status=TaskStatus.in_progress, due_date=None)

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [task]

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock

    db_mock = AsyncMock()
    db_mock.execute = AsyncMock(return_value=execute_result)

    from app.services.overview_service import todays_tasks

    result = await todays_tasks(db_mock)
    assert len(result) == 1
    assert result[0]["is_overdue"] is False
    assert result[0]["due_date"] is None
    assert result[0]["status"] == "in_progress"
