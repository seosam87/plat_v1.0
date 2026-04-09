"""Phase 19.2 Plan 03: Tour API router tests."""
import pytest
from httpx import AsyncClient

from app.main import app
from app.auth.dependencies import require_admin


@pytest.fixture(autouse=True)
def _clear_tour_cache():
    from app.routers.tours import _load_all_tours
    _load_all_tours.cache_clear()
    yield
    _load_all_tours.cache_clear()


@pytest.fixture
def admin_override():
    """Override require_admin to always pass (returns a sentinel user-like)."""
    class _U:
        id = "test-admin"
        role = "admin"
    app.dependency_overrides[require_admin] = lambda: _U()
    yield
    app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_list_tours_empty_or_ok(client: AsyncClient, admin_override):
    resp = await client.get("/api/tours/", params={"page": "/ui/keyword-suggest/"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


@pytest.mark.asyncio
async def test_list_tours_forbidden_for_non_admin(client: AsyncClient):
    # No auth override => unauthenticated => 401 from get_current_user
    resp = await client.get("/api/tours/", params={"page": "/ui"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_tour_not_found(client: AsyncClient, admin_override):
    resp = await client.get("/api/tours/definitely-not-a-real-tour")
    assert resp.status_code == 404
