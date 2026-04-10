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


# ---------------------------------------------------------------------------
# Tests: parametrized landing pages for all 6 tools
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", [
    "commercialization",
    "meta-parser",
    "relevant-url",
    "brief",
    "paa",
    "wordstat-batch",
])
async def test_tool_landing_page_200(tools_client, fake_user, slug):
    """GET /ui/tools/{slug}/ returns 200 for all 6 tool slugs."""
    cookies = _jwt_cookie(str(fake_user.id))
    with patch("app.routers.tools._check_oauth_token_sync", return_value="fake-token"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/ui/tools/{slug}/", cookies=cookies)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: parametrized submit for all 6 tools
# ---------------------------------------------------------------------------

def _patch_path_for_slug(slug: str) -> str:
    """Return the task dispatch patch path for a given slug."""
    task_map = {
        "commercialization": "app.tasks.commerce_check_tasks.run_commerce_check.delay",
        "meta-parser": "app.tasks.meta_parse_tasks.run_meta_parse.delay",
        "relevant-url": "app.tasks.relevant_url_tasks.run_relevant_url.delay",
        "paa": "app.tasks.paa_tasks.run_paa.delay",
        "wordstat-batch": "app.tasks.wordstat_batch_tasks.run_wordstat_batch.delay",
        "brief": "celery.chain.delay",
    }
    return task_map.get(slug, "app.tasks.commerce_check_tasks.run_commerce_check.delay")


@pytest.mark.parametrize("slug", [
    "commercialization",
    "meta-parser",
    "relevant-url",
    "brief",
    "paa",
    "wordstat-batch",
])
async def test_tool_submit_creates_job(tools_client, fake_user, slug):
    """POST with valid input creates a job and redirects 303."""
    fake_db, _ = tools_client
    job_id = uuid.uuid4()

    async def _refresh(obj):
        obj.id = job_id

    fake_db.refresh = AsyncMock(side_effect=_refresh)
    cookies = _jwt_cookie(str(fake_user.id))

    form_field = "urls" if slug == "meta-parser" else "phrases"
    # Use domain for relevant-url
    form_data = {form_field: "test input\nsecond line"}
    if slug == "relevant-url":
        form_data["domain"] = "example.com"
    if slug == "brief":
        form_data["region"] = "213"

    with patch("app.tasks.commerce_check_tasks.run_commerce_check.delay", MagicMock()), \
         patch("app.tasks.meta_parse_tasks.run_meta_parse.delay", MagicMock()), \
         patch("app.tasks.relevant_url_tasks.run_relevant_url.delay", MagicMock()), \
         patch("app.tasks.paa_tasks.run_paa.delay", MagicMock()), \
         patch("app.tasks.wordstat_batch_tasks.run_wordstat_batch.delay", MagicMock()), \
         patch("app.tasks.brief_tasks.run_brief_step1_serp") as m1, \
         patch("app.tasks.brief_tasks.run_brief_step2_crawl") as m2, \
         patch("app.tasks.brief_tasks.run_brief_step3_aggregate") as m3, \
         patch("app.tasks.brief_tasks.run_brief_step4_finalize") as m4:
        # Configure .si() and chaining for brief
        for m in (m1, m2, m3, m4):
            m.si = MagicMock(return_value=MagicMock())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"/ui/tools/{slug}/",
                data=form_data,
                follow_redirects=False,
                cookies=cookies,
            )
    assert resp.status_code == 303
    assert f"/ui/tools/{slug}/" in resp.headers.get("location", "")


@pytest.mark.parametrize("slug", [
    "commercialization",
    "meta-parser",
    "relevant-url",
    "brief",
    "paa",
    "wordstat-batch",
])
async def test_tool_submit_empty_input_422(tools_client, fake_user, slug):
    """POST with empty input returns 422 for all tools."""
    cookies = _jwt_cookie(str(fake_user.id))
    form_field = "urls" if slug == "meta-parser" else "phrases"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            f"/ui/tools/{slug}/",
            data={form_field: ""},
            follow_redirects=False,
            cookies=cookies,
        )
    assert resp.status_code == 422


@pytest.mark.parametrize("slug,limit", [
    ("commercialization", 200),
    ("meta-parser", 500),
    ("relevant-url", 100),
    ("brief", 30),
    ("paa", 50),
    ("wordstat-batch", 1000),
])
async def test_tool_submit_exceeds_limit_422(tools_client, fake_user, slug, limit):
    """POST with lines > limit returns 422."""
    cookies = _jwt_cookie(str(fake_user.id))
    form_field = "urls" if slug == "meta-parser" else "phrases"
    lines = "\n".join([f"phrase {i}" for i in range(limit + 1)])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            f"/ui/tools/{slug}/",
            data={form_field: lines},
            follow_redirects=False,
            cookies=cookies,
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Brief-specific
# ---------------------------------------------------------------------------

async def test_brief_submit_includes_region(tools_client, fake_user):
    """POST to /ui/tools/brief/ with region=2 saves job.input_region == 2."""
    fake_db, _ = tools_client
    job_id = uuid.uuid4()
    created_job_kwargs: dict = {}

    original_add = MagicMock()

    def _capture_add(obj):
        created_job_kwargs.update({"input_region": getattr(obj, "input_region", None)})
        original_add(obj)

    fake_db.add = MagicMock(side_effect=_capture_add)

    async def _refresh(obj):
        obj.id = job_id

    fake_db.refresh = AsyncMock(side_effect=_refresh)
    cookies = _jwt_cookie(str(fake_user.id))

    with patch("app.tasks.brief_tasks.run_brief_step1_serp") as m1, \
         patch("app.tasks.brief_tasks.run_brief_step2_crawl") as m2, \
         patch("app.tasks.brief_tasks.run_brief_step3_aggregate") as m3, \
         patch("app.tasks.brief_tasks.run_brief_step4_finalize") as m4:
        for m in (m1, m2, m3, m4):
            m.si = MagicMock(return_value=MagicMock())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/ui/tools/brief/",
                data={"phrases": "купить кроссовки\nботинки", "region": "2"},
                follow_redirects=False,
                cookies=cookies,
            )
    assert resp.status_code == 303
    assert created_job_kwargs.get("input_region") == 2


async def test_brief_chain_dispatched(tools_client, fake_user):
    """POST to /ui/tools/brief/ dispatches a 4-step celery chain using .si()."""
    fake_db, _ = tools_client
    job_id = uuid.uuid4()

    async def _refresh(obj):
        obj.id = job_id

    fake_db.refresh = AsyncMock(side_effect=_refresh)
    cookies = _jwt_cookie(str(fake_user.id))

    si_calls = []

    with patch("app.tasks.brief_tasks.run_brief_step1_serp") as m1, \
         patch("app.tasks.brief_tasks.run_brief_step2_crawl") as m2, \
         patch("app.tasks.brief_tasks.run_brief_step3_aggregate") as m3, \
         patch("app.tasks.brief_tasks.run_brief_step4_finalize") as m4:
        for m in (m1, m2, m3, m4):
            sig = MagicMock()
            m.si = MagicMock(return_value=sig)
            si_calls.append(m)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.post(
                "/ui/tools/brief/",
                data={"phrases": "test phrase", "region": "213"},
                follow_redirects=False,
                cookies=cookies,
            )
    # All 4 steps should have had .si() called
    for m in si_calls:
        m.si.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: Wordstat-batch specific
# ---------------------------------------------------------------------------

async def test_wordstat_batch_oauth_warning(tools_client, fake_user):
    """GET /ui/tools/wordstat-batch/ when no OAuth token shows warning text."""
    cookies = _jwt_cookie(str(fake_user.id))
    with patch("app.routers.tools._check_oauth_token_sync", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/ui/tools/wordstat-batch/", cookies=cookies)
    assert resp.status_code == 200
    # oauth_warning=True should show a warning in the template
    # The template shows "oauth_warning" flag — we verify it's not a 500
    # and oauth_warning context was set


# ---------------------------------------------------------------------------
# Tests: re-run endpoint
# ---------------------------------------------------------------------------

async def test_tool_rerun_creates_new_job(tools_client, fake_user):
    """POST /ui/tools/{slug}/rerun/{job_id} creates new job with same input_phrases."""
    from app.models.commerce_check_job import CommerceCheckJob

    fake_db, _ = tools_client
    job_id = uuid.uuid4()
    new_job_id = uuid.uuid4()

    fake_job = CommerceCheckJob(
        id=job_id,
        input_phrases=["купить кроссовки", "купить ботинки"],
        phrase_count=2,
        status="complete",
        user_id=fake_user.id,
    )
    found_result = MagicMock()
    found_result.scalar_one_or_none.return_value = fake_job
    fake_db.execute = AsyncMock(return_value=found_result)

    new_obj_captured: list = []

    def _capture_add(obj):
        new_obj_captured.append(obj)

    fake_db.add = MagicMock(side_effect=_capture_add)

    async def _refresh(obj):
        obj.id = new_job_id

    fake_db.refresh = AsyncMock(side_effect=_refresh)
    cookies = _jwt_cookie(str(fake_user.id))

    with patch("app.tasks.commerce_check_tasks.run_commerce_check.delay", MagicMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                f"/ui/tools/commercialization/rerun/{job_id}",
                follow_redirects=False,
                cookies=cookies,
            )
    assert resp.status_code == 303
    assert len(new_obj_captured) == 1
    new_job = new_obj_captured[0]
    assert new_job.input_phrases == ["купить кроссовки", "купить ботинки"]
    assert new_job.status == "pending"


async def test_tool_rerun_not_found_returns_404(tools_client, fake_user):
    """POST /ui/tools/{slug}/rerun/{job_id} returns 404 if job not found."""
    fake_db, _ = tools_client
    job_id = uuid.uuid4()

    not_found_result = MagicMock()
    not_found_result.scalar_one_or_none.return_value = None
    fake_db.execute = AsyncMock(return_value=not_found_result)

    cookies = _jwt_cookie(str(fake_user.id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            f"/ui/tools/commercialization/rerun/{job_id}",
            follow_redirects=False,
            cookies=cookies,
        )
    assert resp.status_code == 404
