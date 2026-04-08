"""Unit tests for notification_tasks.cleanup_old_notifications Celery task.

Tests mock the DB session and verify delete logic + row count reporting.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_ctx(rowcount: int = 0) -> MagicMock:
    """Create a mock async context manager for AsyncSessionLocal().

    Returns a context manager that yields a mock DB session whose execute()
    returns a result with the given rowcount.
    """
    result = MagicMock()
    result.rowcount = rowcount

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, db


# ---------------------------------------------------------------------------
# test_cleanup_deletes_old
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_deletes_old():
    """_cleanup() executes DELETE for rows older than 30 days.

    Verifies that db.execute() is called with a SQL text containing
    'notifications' and '30 days', and that db.commit() is called after.
    """
    from app.tasks.notification_tasks import _cleanup

    ctx, db = _make_db_ctx(rowcount=2)

    with patch("app.database.AsyncSessionLocal", return_value=ctx):
        result = await _cleanup()

    assert db.execute.called
    call_args = db.execute.call_args[0][0]
    sql_str = str(call_args)
    assert "notifications" in sql_str.lower()
    assert "30 days" in sql_str.lower() or "interval" in sql_str.lower()
    db.commit.assert_awaited_once()
    assert result["status"] == "ok"
    assert result["deleted_count"] == 2


# ---------------------------------------------------------------------------
# test_cleanup_returns_count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_returns_count():
    """_cleanup() returns the exact number of deleted rows in the result dict."""
    from app.tasks.notification_tasks import _cleanup

    for expected_deleted in [0, 1, 5, 100]:
        ctx, db = _make_db_ctx(rowcount=expected_deleted)
        with patch("app.database.AsyncSessionLocal", return_value=ctx):
            result = await _cleanup()
        assert result["deleted_count"] == expected_deleted, (
            f"Expected {expected_deleted} deleted, got {result['deleted_count']}"
        )


# ---------------------------------------------------------------------------
# test_cleanup_no_rows_to_delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_no_rows_to_delete():
    """_cleanup() returns 0 deleted count when no old rows exist."""
    from app.tasks.notification_tasks import _cleanup

    ctx, db = _make_db_ctx(rowcount=0)

    with patch("app.database.AsyncSessionLocal", return_value=ctx):
        result = await _cleanup()

    assert result["status"] == "ok"
    assert result["deleted_count"] == 0


# ---------------------------------------------------------------------------
# test_cleanup_task_registered_in_beat
# ---------------------------------------------------------------------------

def test_cleanup_task_registered_in_beat():
    """Celery beat_schedule contains 'notifications-cleanup-nightly' entry."""
    from app.celery_app import celery_app

    beat = celery_app.conf.beat_schedule
    assert "notifications-cleanup-nightly" in beat, (
        f"Expected 'notifications-cleanup-nightly' in beat_schedule, got: {list(beat.keys())}"
    )
    entry = beat["notifications-cleanup-nightly"]
    assert entry["task"] == "app.tasks.notification_tasks.cleanup_old_notifications"
