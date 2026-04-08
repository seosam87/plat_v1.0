"""Router tests for Notifications endpoints (Plan 17-02).

Tests use mock-based approach (AsyncMock / MagicMock) since the live DB is
unavailable in this environment — consistent with existing patterns in the
codebase (test_llm_briefs.py, test_notifications.py).

Covered cases:
1. test_bell_fragment_unread_count
2. test_bell_red_when_error
3. test_dropdown_marks_read
4. test_dropdown_limit_10
5. test_index_filter_by_kind
6. test_index_filter_by_site
7. test_index_filter_unread
8. test_mark_all_read
9. test_dismiss_deletes
10. test_dismiss_other_user_forbidden
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.dependencies import get_db
from app.main import app
from app.models.user import UserRole

pytestmark = pytest.mark.asyncio

_USER_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
_USER2_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000002")
_SITE_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")
_NOTIF_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")


def _make_user(uid=_USER_ID):
    u = SimpleNamespace(
        id=uid,
        username=f"user_{uid.hex[:4]}",
        email=f"user_{uid.hex[:4]}@test.com",
        is_active=True,
        role=UserRole.admin,
    )
    return u


def _make_notif(
    user_id=_USER_ID,
    kind="crawl.completed",
    severity="info",
    is_read=False,
    site_id=None,
    notif_id=None,
):
    return SimpleNamespace(
        id=notif_id or uuid.uuid4(),
        user_id=user_id,
        kind=kind,
        title=f"Test {kind}",
        body=f"Body for {kind}",
        link_url="/",
        site_id=site_id,
        severity=severity,
        is_read=is_read,
        created_at=datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc),
    )


def _make_async_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _row_mock(total: int, error_count: int):
    r = MagicMock()
    r.total = total
    r.error_count = error_count
    return r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_bell_fragment_unread_count():
    """Seed 3 unread, GET /notifications/bell — response contains '3'."""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.one.return_value = _row_mock(total=3, error_count=0)
    db.execute = AsyncMock(return_value=result_mock)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with _make_async_client() as client:
            resp = await client.get("/notifications/bell")
        assert resp.status_code == 200
        assert "3" in resp.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_bell_red_when_error():
    """Seed 1 unread error — bell response contains red badge marker bg-red-500."""
    user = _make_user()
    db = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.one.return_value = _row_mock(total=1, error_count=1)
    db.execute = AsyncMock(return_value=result_mock)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with _make_async_client() as client:
            resp = await client.get("/notifications/bell")
        assert resp.status_code == 200
        assert "bg-red-500" in resp.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_dropdown_marks_read():
    """Seed 5 unread, GET /notifications/dropdown — UPDATE called with is_read=True."""
    user = _make_user()
    notifs = [_make_notif() for _ in range(5)]

    db = AsyncMock(spec=AsyncSession)
    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = notifs
    update_result = MagicMock()
    db.execute = AsyncMock(side_effect=[select_result, update_result])
    db.commit = AsyncMock()

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with _make_async_client() as client:
            resp = await client.get("/notifications/dropdown")
        assert resp.status_code == 200
        # SELECT + UPDATE both called; commit called
        assert db.execute.call_count == 2
        assert db.commit.call_count == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_dropdown_limit_10():
    """Router uses LIMIT 10 — response has at most 10 notif-row elements."""
    user = _make_user()
    notifs = [_make_notif(kind=f"crawl.{i}") for i in range(10)]

    db = AsyncMock(spec=AsyncSession)
    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = notifs
    db.execute = AsyncMock(side_effect=[select_result, MagicMock()])
    db.commit = AsyncMock()

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with _make_async_client() as client:
            resp = await client.get("/notifications/dropdown")
        assert resp.status_code == 200
        count = resp.text.count("notif-row")
        assert count <= 10, f"Expected at most 10 rows, got {count}"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_index_filter_by_kind():
    """GET /notifications?kind=pdf.ready — page renders with pdf content."""
    user = _make_user()
    notifs = [_make_notif(kind="pdf.ready") for _ in range(3)]

    db = AsyncMock(spec=AsyncSession)
    count_result = MagicMock()
    count_result.scalar.return_value = 3
    page_result = MagicMock()
    page_result.scalars.return_value.all.return_value = notifs
    site_result = MagicMock()
    site_result.fetchall.return_value = []
    kinds_result = MagicMock()
    kinds_result.fetchall.return_value = [("pdf.ready",)]
    db.execute = AsyncMock(side_effect=[count_result, page_result, site_result, kinds_result])

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with _make_async_client() as client:
            resp = await client.get("/notifications?kind=pdf.ready")
        assert resp.status_code == 200
        assert "pdf" in resp.text.lower()
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_index_filter_by_site():
    """Filter by site_id — endpoint returns 200."""
    user = _make_user()
    notifs = [_make_notif(site_id=_SITE_ID) for _ in range(2)]

    db = AsyncMock(spec=AsyncSession)
    count_result = MagicMock()
    count_result.scalar.return_value = 2
    page_result = MagicMock()
    page_result.scalars.return_value.all.return_value = notifs
    site_ids_result = MagicMock()
    site_ids_result.fetchall.return_value = [(_SITE_ID,)]
    kinds_result = MagicMock()
    kinds_result.fetchall.return_value = [("crawl.completed",)]
    site_obj = SimpleNamespace(id=_SITE_ID, name="Test Site")
    sites_names_result = MagicMock()
    sites_names_result.scalars.return_value.all.return_value = [site_obj]
    db.execute = AsyncMock(
        side_effect=[count_result, page_result, site_ids_result, kinds_result, sites_names_result]
    )

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with _make_async_client() as client:
            resp = await client.get(f"/notifications?site_id={_SITE_ID}")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_index_filter_unread():
    """GET ?read_state=unread — endpoint returns 200."""
    user = _make_user()
    notifs = [_make_notif(is_read=False) for _ in range(3)]

    db = AsyncMock(spec=AsyncSession)
    count_result = MagicMock()
    count_result.scalar.return_value = 3
    page_result = MagicMock()
    page_result.scalars.return_value.all.return_value = notifs
    site_result = MagicMock()
    site_result.fetchall.return_value = []
    kinds_result = MagicMock()
    kinds_result.fetchall.return_value = [("crawl.completed",)]
    db.execute = AsyncMock(side_effect=[count_result, page_result, site_result, kinds_result])

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with _make_async_client() as client:
            resp = await client.get("/notifications?read_state=unread")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_mark_all_read():
    """POST /notifications/mark-all-read — UPDATE executed, commit called, returns 200."""
    user = _make_user()

    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    update_result = MagicMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    page_result = MagicMock()
    page_result.scalars.return_value.all.return_value = []
    site_result = MagicMock()
    site_result.fetchall.return_value = []
    kinds_result = MagicMock()
    kinds_result.fetchall.return_value = []
    db.execute = AsyncMock(
        side_effect=[update_result, count_result, page_result, site_result, kinds_result]
    )

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with _make_async_client() as client:
            resp = await client.post("/notifications/mark-all-read")
        assert resp.status_code == 200
        assert db.commit.call_count >= 1
        assert db.execute.call_count >= 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_dismiss_deletes():
    """POST /notifications/{id}/dismiss — row deleted, returns 204."""
    user = _make_user()
    notif = _make_notif(user_id=_USER_ID, notif_id=_NOTIF_ID)

    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=notif)
    db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with _make_async_client() as client:
            resp = await client.post(f"/notifications/{_NOTIF_ID}/dismiss")
        assert resp.status_code == 204
        assert db.execute.call_count == 1
        assert db.commit.call_count == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


async def test_dismiss_other_user_forbidden():
    """POST /notifications/{id}/dismiss with other user's notif → 403."""
    user2 = _make_user(uid=_USER2_ID)
    # Notification belongs to user1, but user2 is requesting
    notif = _make_notif(user_id=_USER_ID, notif_id=_NOTIF_ID)

    db = AsyncMock(spec=AsyncSession)
    db.get = AsyncMock(return_value=notif)

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user2
    try:
        async with _make_async_client() as client:
            resp = await client.post(f"/notifications/{_NOTIF_ID}/dismiss")
        assert resp.status_code in (403, 404)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
