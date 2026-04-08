"""Unit tests for app.services.notifications.notify().

Tests mock the DB session to avoid requiring a live database connection.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> AsyncMock:
    """Create a mock AsyncSession with add() and flush() as async-compatible."""
    db = AsyncMock()
    db.add = MagicMock()  # add() is sync
    db.flush = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# test_notify_inserts_row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_inserts_row():
    """notify() adds a Notification to the session and flushes.

    Asserts: db.add() called once, db.flush() called once,
    returned object has correct fields, is_read=False, severity='info'.
    """
    from app.services.notifications import notify

    db = _make_db()
    user_id = uuid.uuid4()

    n = await notify(
        db=db,
        user_id=user_id,
        kind="crawl.completed",
        title="Краулинг завершён",
        body="Сайт успешно просканирован.",
        link_url="/sites/abc/crawl",
    )

    db.add.assert_called_once_with(n)
    db.flush.assert_awaited_once()

    assert n.user_id == user_id
    assert n.kind == "crawl.completed"
    assert n.title == "Краулинг завершён"
    assert n.body == "Сайт успешно просканирован."
    assert n.link_url == "/sites/abc/crawl"
    assert n.site_id is None
    assert n.is_read is False
    assert n.severity == "info"


# ---------------------------------------------------------------------------
# test_notify_with_site_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_with_site_id():
    """notify() stores site_id FK when provided."""
    from app.services.notifications import notify

    db = _make_db()
    user_id = uuid.uuid4()
    site_id = uuid.uuid4()

    n = await notify(
        db=db,
        user_id=user_id,
        kind="audit.completed",
        title="Аудит завершён",
        body="Обнаружено 3 ошибки.",
        link_url=f"/sites/{site_id}/audit",
        site_id=site_id,
    )

    assert n.site_id == site_id
    db.add.assert_called_once()
    db.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# test_notify_severity_error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_severity_error():
    """notify() stores severity='error' when passed explicitly."""
    from app.services.notifications import notify

    db = _make_db()
    user_id = uuid.uuid4()

    n = await notify(
        db=db,
        user_id=user_id,
        kind="monitoring.alert",
        title="Критическое падение позиций",
        body="Ключевое слово упало на 20+ позиций.",
        link_url="/monitoring",
        severity="error",
    )

    assert n.severity == "error"


# ---------------------------------------------------------------------------
# test_notify_severity_warning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_severity_warning():
    """notify() stores severity='warning' when passed explicitly."""
    from app.services.notifications import notify

    db = _make_db()
    user_id = uuid.uuid4()

    n = await notify(
        db=db,
        user_id=user_id,
        kind="position_check.completed",
        title="Проверка позиций завершена",
        body="Предупреждение: 5 ключевых слов вышли за top-50.",
        link_url="/positions",
        severity="warning",
    )

    assert n.severity == "warning"
    assert n.is_read is False
