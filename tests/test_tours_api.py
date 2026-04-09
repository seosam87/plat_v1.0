"""Phase 19.2 Plan 03: Tour API router tests.

Uses mock-based approach (ASGITransport + dependency_overrides) since the live
DB is unavailable in this environment — consistent with existing patterns in
tests/routers/test_notifications.py and tests/test_llm_briefs.py.

Covered cases:
1. test_list_tours_empty_or_ok — admin GET /api/tours/?page=... returns 200 list
2. test_list_tours_forbidden_for_non_admin — unauthenticated → 401 or 403
3. test_get_tour_not_found — admin GET /api/tours/nonexistent → 404
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient, ASGITransport

from app.auth.dependencies import get_current_user, require_admin
from app.dependencies import get_db
from app.main import app
from app.models.user import UserRole

pytestmark = pytest.mark.asyncio


def _make_admin_user():
    return SimpleNamespace(
        id="test-admin-id",
        username="admin_user",
        email="admin@test.com",
        is_active=True,
        role=UserRole.admin,
    )


def _make_async_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_tour_cache():
    """Clear lru_cache before and after each test to prevent state leakage."""
    from app.routers.tours import _load_all_tours
    _load_all_tours.cache_clear()
    yield
    _load_all_tours.cache_clear()


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    """Ensure dependency overrides are cleaned up after each test."""
    yield
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


async def test_list_tours_empty_or_ok():
    """Admin GET /api/tours/?page=... returns 200 with a list (may be empty)."""
    admin = _make_admin_user()
    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_current_user] = lambda: admin

    async with _make_async_client() as client:
        resp = await client.get("/api/tours/", params={"page": "/ui/keyword-suggest/"})

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


async def test_list_tours_forbidden_for_non_admin():
    """Unauthenticated request returns 401 (no auth override applied)."""
    # No override — get_current_user will fail to decode a token → 401
    async with _make_async_client() as client:
        resp = await client.get("/api/tours/", params={"page": "/ui"})

    assert resp.status_code in (401, 403)


async def test_get_tour_not_found():
    """Admin GET /api/tours/nonexistent returns 404."""
    admin = _make_admin_user()
    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_current_user] = lambda: admin

    async with _make_async_client() as client:
        resp = await client.get("/api/tours/definitely-not-a-real-tour")

    assert resp.status_code == 404
