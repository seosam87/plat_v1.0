"""Integration tests for the tools router (Phase 24 Plan 05).

Uses dependency_overrides for get_current_user and get_db so tests run
without a live database connection. Passes a JWT cookie to satisfy the
UIAuthMiddleware which intercepts /ui/* requests before FastAPI DI.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token
from app.dependencies import get_db
from app.main import app
from app.models.commerce_check_job import CommerceCheckJob
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_db(found_job=None):
    """Return an AsyncMock that simulates an AsyncSession.

    By default scalar() returns 0 (zero job counts) and scalars().all() returns [].
    Pass found_job to return a specific job from scalar_one_or_none().
    """
    session = AsyncMock()

    # Default: scalar count returns 0
    scalar_result = MagicMock()
    scalar_result.scalar.return_value = 0
    scalar_result.scalar_one_or_none.return_value = found_job
    scalar_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))

    session.execute = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _jwt_cookie(user_id: str, role: str = "admin") -> dict:
    """Return cookies dict with a valid access_token JWT."""
    token = create_access_token(user_id, role)
    return {"access_token": token}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_user():
    uid = uuid.uuid4()
    return User(
        id=uid,
        username="test_admin",
        email="test_tools@example.com",
        password_hash="x",
        role=UserRole.admin,
        is_active=True,
    )


@pytest.fixture
def tools_client(fake_user):
    """Override get_current_user and get_db; yield (fake_db, fake_user)."""
    fake_db = _make_fake_db()

    async def _fake_user():
        return fake_user

    async def _fake_db():
        yield fake_db

    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    yield fake_db, fake_user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Tests: tools index
# ---------------------------------------------------------------------------

async def test_tools_index_returns_200(tools_client, fake_user):
    """GET /ui/tools/ returns 200 with all tool cards."""
    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/ui/tools/", cookies=cookies)
    assert resp.status_code == 200
    assert "Инструменты SEO" in resp.text
    assert "Проверка коммерциализации" in resp.text
    assert "Парсер мета-тегов" in resp.text
    assert "Поиск релевантного URL" in resp.text


async def test_tools_index_requires_auth():
    """GET /ui/tools/ without auth redirects to login (UIAuthMiddleware)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/ui/tools/", follow_redirects=False)
    assert resp.status_code in (302, 401, 403)


# ---------------------------------------------------------------------------
# Tests: tool landing pages
# ---------------------------------------------------------------------------

async def test_tool_landing_commercialization(tools_client, fake_user):
    """GET /ui/tools/commercialization/ returns 200 with input form."""
    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/ui/tools/commercialization/", cookies=cookies)
    assert resp.status_code == 200
    assert "Проверить коммерциализацию" in resp.text


async def test_tool_landing_meta_parser(tools_client, fake_user):
    """GET /ui/tools/meta-parser/ returns 200."""
    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/ui/tools/meta-parser/", cookies=cookies)
    assert resp.status_code == 200
    assert "Запустить парсинг" in resp.text


async def test_tool_landing_relevant_url(tools_client, fake_user):
    """GET /ui/tools/relevant-url/ returns 200 with domain field."""
    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/ui/tools/relevant-url/", cookies=cookies)
    assert resp.status_code == 200
    assert "Найти релевантные URL" in resp.text
    assert 'name="domain"' in resp.text


async def test_tool_landing_unknown_slug_returns_404(tools_client, fake_user):
    """GET /ui/tools/unknown-tool/ returns 404."""
    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/ui/tools/unknown-tool/", cookies=cookies)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: job submit
# ---------------------------------------------------------------------------

async def test_tool_submit_creates_job_and_redirects(tools_client, fake_user):
    """POST /ui/tools/commercialization/ creates a job and redirects."""
    fake_db, _ = tools_client
    job_id = uuid.uuid4()

    async def _refresh(obj):
        obj.id = job_id

    fake_db.refresh = AsyncMock(side_effect=_refresh)
    cookies = _jwt_cookie(str(fake_user.id))

    with patch("app.tasks.commerce_check_tasks.run_commerce_check.delay", MagicMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/ui/tools/commercialization/",
                data={"phrases": "купить кроссовки\nкупить ботинки"},
                follow_redirects=False,
                cookies=cookies,
            )
    assert resp.status_code == 303
    assert "/ui/tools/commercialization/" in resp.headers.get("location", "")


async def test_tool_submit_empty_input_returns_422(tools_client, fake_user):
    """POST with empty input returns 422."""
    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/ui/tools/commercialization/",
            data={"phrases": ""},
            follow_redirects=False,
            cookies=cookies,
        )
    assert resp.status_code == 422


async def test_tool_submit_exceeds_limit_returns_422(tools_client, fake_user):
    """POST with more phrases than the tool limit (200) returns 422."""
    phrases = "\n".join([f"phrase {i}" for i in range(201)])
    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/ui/tools/commercialization/",
            data={"phrases": phrases},
            follow_redirects=False,
            cookies=cookies,
        )
    assert resp.status_code == 422


async def test_tool_submit_unknown_slug_returns_404(tools_client, fake_user):
    """POST to unknown slug returns 404."""
    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/ui/tools/unknown-tool/",
            data={"phrases": "test"},
            follow_redirects=False,
            cookies=cookies,
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: job delete
# ---------------------------------------------------------------------------

async def test_tool_delete_removes_job(tools_client, fake_user):
    """DELETE /ui/tools/commercialization/{job_id} removes an owned job."""
    fake_db, _ = tools_client
    job_id = uuid.uuid4()

    fake_job = CommerceCheckJob(
        id=job_id,
        input_phrases=["test phrase"],
        phrase_count=1,
        status="complete",
        user_id=fake_user.id,
    )
    found_result = MagicMock()
    found_result.scalar_one_or_none.return_value = fake_job
    delete_result = MagicMock()
    delete_result.scalar_one_or_none.return_value = None
    fake_db.execute = AsyncMock(side_effect=[found_result, delete_result, delete_result])

    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.request(
            "DELETE",
            f"/ui/tools/commercialization/{job_id}",
            cookies=cookies,
        )
    assert resp.status_code == 200


async def test_tool_delete_other_users_job_returns_404(tools_client, fake_user):
    """DELETE on another user's job returns 404 (ownership check)."""
    fake_db, _ = tools_client
    job_id = uuid.uuid4()

    not_found_result = MagicMock()
    not_found_result.scalar_one_or_none.return_value = None
    fake_db.execute = AsyncMock(return_value=not_found_result)

    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.request(
            "DELETE",
            f"/ui/tools/commercialization/{job_id}",
            cookies=cookies,
        )
    assert resp.status_code == 404
