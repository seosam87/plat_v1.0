"""Integration tests for keyword suggest router (Phase 15 Plan 02)."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.auth.dependencies import get_current_user
from app.main import app
from app.models.suggest_job import SuggestJob
from app.models.user import User, UserRole


@pytest.fixture
def override_user():
    """Override auth dependency so the router sees a stub admin user."""
    fake = User(
        id=uuid.uuid4(),
        username="test_admin",
        email="test@example.com",
        password_hash="x",
        role=UserRole.admin,
        is_active=True,
    )

    async def _fake_user():
        return fake

    app.dependency_overrides[get_current_user] = _fake_user
    yield fake
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _mock_redis_empty():
    """By default, _read_cache returns None (no cache). Individual tests override."""
    with patch(
        "app.routers.keyword_suggest._read_cache",
        new=AsyncMock(return_value=None),
    ) as m:
        yield m


@pytest.fixture(autouse=True)
def _mock_wordstat_token_absent():
    with patch(
        "app.routers.keyword_suggest._has_wordstat_token",
        new=AsyncMock(return_value=False),
    ) as m:
        yield m


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


async def test_index_page_loads(client: AsyncClient, override_user):
    resp = await client.get("/ui/keyword-suggest/")
    assert resp.status_code == 200
    body = resp.text
    assert "Keyword Suggest" in body
    assert "Найти подсказки" in body
    assert "Введите ключевую фразу" in body


# ---------------------------------------------------------------------------
# POST /search
# ---------------------------------------------------------------------------


async def test_search_dispatches_task(client: AsyncClient, override_user, db_session):
    fake_async = MagicMock()
    fake_async.id = "fake-task-id"

    with patch(
        "app.routers.keyword_suggest.fetch_suggest_keywords.delay",
        return_value=fake_async,
    ) as mock_delay:
        resp = await client.post(
            "/ui/keyword-suggest/search",
            data={"seed": "тест", "include_google": "false"},
        )

    assert resp.status_code == 200
    assert "Загружаем подсказки" in resp.text or "Готово" in resp.text
    mock_delay.assert_called_once()


async def test_empty_seed_rejected(client: AsyncClient, override_user):
    resp = await client.post(
        "/ui/keyword-suggest/search",
        data={"seed": "   "},
    )
    # Treated as validation-ish failure in our handler (renders failed partial).
    assert resp.status_code == 200
    assert "Введите ключевую фразу" in resp.text


async def test_search_rate_limit(client: AsyncClient, override_user):
    """11th rapid request should return 429."""
    with patch(
        "app.routers.keyword_suggest.fetch_suggest_keywords.delay",
        return_value=MagicMock(id="t"),
    ):
        statuses = []
        for i in range(12):
            r = await client.post(
                "/ui/keyword-suggest/search",
                data={"seed": f"тест{i}"},
            )
            statuses.append(r.status_code)
    assert 429 in statuses, f"expected a 429 among {statuses}"


# ---------------------------------------------------------------------------
# GET /status/{job_id}
# ---------------------------------------------------------------------------


async def test_status_polling_pending(client: AsyncClient, override_user, db_session):
    job = SuggestJob(
        seed="тест",
        include_google=False,
        status="pending",
        cache_key="suggest:y:тест",
    )
    db_session.add(job)
    await db_session.flush()

    resp = await client.get(f"/ui/keyword-suggest/status/{job.id}")
    assert resp.status_code == 200
    assert 'hx-trigger="load delay:3s"' in resp.text
    assert "Загружаем подсказки" in resp.text


async def test_status_complete_returns_results(
    client: AsyncClient, override_user, db_session
):
    job = SuggestJob(
        seed="тест",
        include_google=False,
        status="complete",
        cache_key="suggest:y:тест",
        cache_hit=True,
        result_count=2,
    )
    db_session.add(job)
    await db_session.flush()

    fake_results = [
        {"keyword": "тест 1", "source": "yandex"},
        {"keyword": "тест 2", "source": "yandex"},
    ]
    with patch(
        "app.routers.keyword_suggest._read_cache",
        new=AsyncMock(return_value=fake_results),
    ):
        resp = await client.get(f"/ui/keyword-suggest/status/{job.id}")

    assert resp.status_code == 200
    assert "тест 1" in resp.text
    assert "тест 2" in resp.text
    assert "Результаты" in resp.text


# ---------------------------------------------------------------------------
# GET /export
# ---------------------------------------------------------------------------


async def test_csv_export(client: AsyncClient, override_user, db_session):
    job = SuggestJob(
        seed="пицца",
        include_google=False,
        status="complete",
        cache_key="suggest:y:пицца",
        cache_hit=True,
    )
    db_session.add(job)
    await db_session.flush()

    fake_results = [
        {"keyword": "пицца доставка", "source": "yandex"},
        {"keyword": "pizza hut", "source": "google"},
    ]
    with patch(
        "app.routers.keyword_suggest._read_cache",
        new=AsyncMock(return_value=fake_results),
    ):
        resp = await client.get(f"/ui/keyword-suggest/export?job_id={job.id}")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.content.decode("utf-8")
    assert body.startswith("\ufeff")  # BOM
    assert "Подсказка" in body
    assert "Яндекс" in body
    assert "Google" in body
    assert "пицца доставка" in body


# ---------------------------------------------------------------------------
# POST /{job_id}/wordstat
# ---------------------------------------------------------------------------


async def test_wordstat_dispatch(client: AsyncClient, override_user, db_session):
    job = SuggestJob(
        seed="тест",
        include_google=False,
        status="complete",
        cache_key="suggest:y:тест",
        cache_hit=True,
    )
    db_session.add(job)
    await db_session.flush()

    # Patch wordstat token -> True
    fake_delay = MagicMock(return_value=MagicMock(id="ws-1"))
    fake_task = MagicMock()
    fake_task.delay = fake_delay

    with patch(
        "app.routers.keyword_suggest._has_wordstat_token",
        new=AsyncMock(return_value=True),
    ), patch.dict(
        "sys.modules",
        {"app.tasks.suggest_tasks": MagicMock(fetch_wordstat_frequency=fake_task)},
    ):
        # NB: the lazy import inside the endpoint does `from app.tasks.suggest_tasks import fetch_wordstat_frequency`
        # Our sys.modules patch replaces the whole module, but fetch_suggest_keywords is also there —
        # keep it referenced via the existing import. Instead patch the attribute on the real module.
        pass

    import app.tasks.suggest_tasks as st_mod

    with patch(
        "app.routers.keyword_suggest._has_wordstat_token",
        new=AsyncMock(return_value=True),
    ), patch.object(st_mod, "fetch_wordstat_frequency", fake_task, create=True):
        resp = await client.post(f"/ui/keyword-suggest/{job.id}/wordstat")

    assert resp.status_code == 200
    assert "Загружаем частотность" in resp.text
    assert "hx-get" in resp.text
    fake_delay.assert_called_once()


async def test_wordstat_dispatch_no_token(
    client: AsyncClient, override_user, db_session
):
    job = SuggestJob(
        seed="тест",
        include_google=False,
        status="complete",
        cache_key="suggest:y:тест",
        cache_hit=True,
    )
    db_session.add(job)
    await db_session.flush()

    with patch(
        "app.routers.keyword_suggest._has_wordstat_token",
        new=AsyncMock(return_value=False),
    ):
        resp = await client.post(f"/ui/keyword-suggest/{job.id}/wordstat")

    assert resp.status_code == 200
    assert "Токен Яндекс.Директ не настроен" in resp.text


async def test_wordstat_dispatch_job_not_ready(
    client: AsyncClient, override_user, db_session
):
    job = SuggestJob(
        seed="тест",
        include_google=False,
        status="pending",
        cache_key="suggest:y:тест",
    )
    db_session.add(job)
    await db_session.flush()

    resp = await client.post(f"/ui/keyword-suggest/{job.id}/wordstat")
    assert resp.status_code == 200
    assert "Сначала дождитесь результатов" in resp.text


# ---------------------------------------------------------------------------
# GET /{job_id}/wordstat-status
# ---------------------------------------------------------------------------


async def test_wordstat_status_polling(client: AsyncClient, override_user, db_session):
    job = SuggestJob(
        seed="тест",
        include_google=False,
        status="complete",
        cache_key="suggest:y:тест",
        cache_hit=True,
    )
    db_session.add(job)
    await db_session.flush()

    fake_results = [{"keyword": "тест 1", "source": "yandex"}]  # no frequency key
    with patch(
        "app.routers.keyword_suggest._read_cache",
        new=AsyncMock(return_value=fake_results),
    ):
        resp = await client.get(f"/ui/keyword-suggest/{job.id}/wordstat-status")

    assert resp.status_code == 200
    assert 'hx-trigger="load delay:3s"' in resp.text
    assert "Загружаем частотность" in resp.text


async def test_wordstat_status_complete(client: AsyncClient, override_user, db_session):
    job = SuggestJob(
        seed="тест",
        include_google=False,
        status="complete",
        cache_key="suggest:y:тест",
        cache_hit=True,
    )
    db_session.add(job)
    await db_session.flush()

    fake_results = [
        {"keyword": "тест 1", "source": "yandex", "frequency": 1200}
    ]
    with patch(
        "app.routers.keyword_suggest._read_cache",
        new=AsyncMock(return_value=fake_results),
    ):
        resp = await client.get(f"/ui/keyword-suggest/{job.id}/wordstat-status")

    assert resp.status_code == 200
    assert "Частотность загружена" in resp.text
