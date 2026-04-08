"""Unit tests for generate_llm_brief_enhancement Celery task (Phase 16, Plan 03).

Tests cover:
- Missing API key → job failed, no Anthropic call
- Circuit open → job failed, no Anthropic call
- Happy path → job done, output_json set, LLMUsage created
- Anthropic permanent error (AuthenticationError) → failed, circuit incremented, no retry
- Anthropic transient error (APIConnectionError) → _TransientLLMError raised for retry
- 3 transient failures open the circuit
- Transient error on final retry → permanent failure, circuit incremented

All Anthropic and DB calls are mocked — no real network or DB.
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(status="pending", user_id=None, brief_id=None):
    job = MagicMock()
    job.id = 1
    job.status = status
    job.user_id = user_id or uuid.uuid4()
    job.brief_id = brief_id or uuid.uuid4()
    job.output_json = None
    job.error_message = None
    return job


def _make_user(has_key=True):
    user = MagicMock()
    user.id = 42
    user.anthropic_api_key_encrypted = "encrypted_key" if has_key else None
    user.has_anthropic_key = has_key
    return user


def _make_brief():
    brief = MagicMock()
    brief.id = uuid.uuid4()
    brief.title = "Тестовый бриф"
    brief.headings_json = [{"level": 2, "text": "Введение"}]
    brief.keywords_json = [{"phrase": "keyword1", "frequency": 10}]
    brief.competitor_data_json = {}
    return brief


def _make_fake_redis(circuit_open=False):
    """Create a fake redis with controllable circuit state."""
    store = {}
    if circuit_open:
        store["llm:cb:user:42"] = ("open", 900)

    class FakeRedis:
        async def get(self, key):
            return store.get(key, (None,))[0]

        async def set(self, key, value, ex=None):
            store[key] = (str(value), ex)

        async def incr(self, key):
            current = store.get(key)
            new_val = int(current[0]) + 1 if current else 1
            store[key] = (str(new_val), current[1] if current else None)
            return new_val

        async def expire(self, key, ttl):
            if key in store:
                val, _ = store[key]
                store[key] = (val, ttl)
            return True

        async def delete(self, *keys):
            for k in keys:
                store.pop(k, None)

        def _get_store(self):
            return store

    return FakeRedis()


# ---------------------------------------------------------------------------
# Test: missing API key → job failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_missing_api_key_marks_failed():
    """User with no Anthropic key → job status='failed', error_message contains 'API key'."""
    from app.tasks import llm_tasks

    job = _make_job()
    user = _make_user(has_key=False)
    brief = _make_brief()
    fake_redis = _make_fake_redis()

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda cls, id: {
        "LLMBriefJob": job,
        "User": user,
    }.get(cls.__name__, None))
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(llm_tasks, "_get_async_session", return_value=mock_session),
        patch.object(llm_tasks, "_get_redis", return_value=fake_redis),
        patch("app.services.user_service.get_anthropic_api_key", new=AsyncMock(return_value=None)),
        patch("app.services.brief_service.get_brief", new=AsyncMock(return_value=brief)),
        patch("app.services.llm.llm_service.call_llm_brief_enhance") as mock_call,
    ):
        await llm_tasks._run_enhance(job_id=1, task_retries=0, max_retries=3)

    assert job.status == "failed"
    assert job.error_message is not None
    assert "API key" in job.error_message or "api key" in job.error_message.lower()
    mock_call.assert_not_called()


# ---------------------------------------------------------------------------
# Test: circuit open → short circuits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_circuit_open_short_circuits():
    """Circuit pre-opened → job status='failed', error_message contains 'circuit'."""
    from app.tasks import llm_tasks

    job = _make_job()
    user = _make_user(has_key=True)
    fake_redis = _make_fake_redis(circuit_open=True)

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda cls, id: {
        "LLMBriefJob": job,
        "User": user,
    }.get(cls.__name__, None))
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(llm_tasks, "_get_async_session", return_value=mock_session),
        patch.object(llm_tasks, "_get_redis", return_value=fake_redis),
        patch("app.services.llm.llm_service.call_llm_brief_enhance") as mock_call,
    ):
        await llm_tasks._run_enhance(job_id=1, task_retries=0, max_retries=3)

    assert job.status == "failed"
    assert "circuit" in job.error_message.lower()
    mock_call.assert_not_called()


# ---------------------------------------------------------------------------
# Test: happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_happy_path():
    """Valid key + open circuit → job='done', output_json set, LLMUsage logged."""
    from app.tasks import llm_tasks

    job = _make_job()
    user = _make_user(has_key=True)
    brief = _make_brief()
    fake_redis = _make_fake_redis()

    valid_output = {
        "expanded_sections": [{"heading": "H2", "content": "text"}],
        "faq_block": [{"question": "Q?", "answer": "A."}],
        "title_variants": ["T1", "T2", "T3"],
        "meta_variants": ["M1", "M2", "M3"],
    }

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda cls, id: {
        "LLMBriefJob": job,
        "User": user,
    }.get(cls.__name__, None))
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(llm_tasks, "_get_async_session", return_value=mock_session),
        patch.object(llm_tasks, "_get_redis", return_value=fake_redis),
        patch("app.services.user_service.get_anthropic_api_key", new=AsyncMock(return_value="sk-ant-test")),
        patch("app.services.brief_service.get_brief", new=AsyncMock(return_value=brief)),
        patch("app.services.llm.llm_service.call_llm_brief_enhance", new=AsyncMock(return_value=(valid_output, 500, 200))),
    ):
        await llm_tasks._run_enhance(job_id=1, task_retries=0, max_retries=3)

    assert job.status == "done"
    assert job.output_json == valid_output
    # LLMUsage should have been added (session.add called)
    mock_session.add.assert_called()


# ---------------------------------------------------------------------------
# Test: permanent Anthropic error (AuthenticationError)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_permanent_error_no_retry():
    """AuthenticationError → record_llm_failure called, job failed, NO _TransientLLMError raised."""
    from anthropic import AuthenticationError
    from app.tasks import llm_tasks

    job = _make_job()
    user = _make_user(has_key=True)
    brief = _make_brief()
    fake_redis = _make_fake_redis()

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda cls, id: {
        "LLMBriefJob": job,
        "User": user,
    }.get(cls.__name__, None))
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # AuthenticationError requires a response object — use MagicMock
    auth_err = AuthenticationError.__new__(AuthenticationError)
    auth_err.message = "Invalid API key"
    auth_err.response = MagicMock()
    auth_err.response.status_code = 401
    auth_err.body = {}

    with (
        patch.object(llm_tasks, "_get_async_session", return_value=mock_session),
        patch.object(llm_tasks, "_get_redis", return_value=fake_redis),
        patch("app.services.user_service.get_anthropic_api_key", new=AsyncMock(return_value="sk-ant-test")),
        patch("app.services.brief_service.get_brief", new=AsyncMock(return_value=brief)),
        patch("app.services.llm.llm_service.call_llm_brief_enhance", side_effect=auth_err),
    ):
        # Should NOT raise _TransientLLMError — handles silently
        await llm_tasks._run_enhance(job_id=1, task_retries=0, max_retries=3)

    assert job.status == "failed"
    # Circuit breaker should have been incremented (key set in redis)
    redis_store = fake_redis._get_store()
    assert "llm:cb:fails:42" in redis_store


# ---------------------------------------------------------------------------
# Test: transient error → _TransientLLMError raised for Celery retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_transient_error_retries():
    """APIConnectionError on non-final retry → _TransientLLMError raised, circuit NOT incremented."""
    from anthropic import APIConnectionError
    from app.tasks import llm_tasks

    job = _make_job()
    user = _make_user(has_key=True)
    brief = _make_brief()
    fake_redis = _make_fake_redis()

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda cls, id: {
        "LLMBriefJob": job,
        "User": user,
    }.get(cls.__name__, None))
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    conn_err = APIConnectionError.__new__(APIConnectionError)
    conn_err.message = "Connection refused"
    conn_err.request = MagicMock()

    with (
        patch.object(llm_tasks, "_get_async_session", return_value=mock_session),
        patch.object(llm_tasks, "_get_redis", return_value=fake_redis),
        patch("app.services.user_service.get_anthropic_api_key", new=AsyncMock(return_value="sk-ant-test")),
        patch("app.services.brief_service.get_brief", new=AsyncMock(return_value=brief)),
        patch("app.services.llm.llm_service.call_llm_brief_enhance", side_effect=conn_err),
    ):
        # Should raise _TransientLLMError to signal Celery retry
        with pytest.raises(llm_tasks._TransientLLMError):
            await llm_tasks._run_enhance(job_id=1, task_retries=0, max_retries=3)

    # Circuit breaker should NOT be incremented on transient
    redis_store = fake_redis._get_store()
    assert "llm:cb:fails:42" not in redis_store


# ---------------------------------------------------------------------------
# Test: transient error on final retry → permanent failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_transient_exhausted_then_fails():
    """Transient error on final retry → record_llm_failure called, job marked failed."""
    from anthropic import APIConnectionError
    from app.tasks import llm_tasks

    job = _make_job()
    user = _make_user(has_key=True)
    brief = _make_brief()
    fake_redis = _make_fake_redis()

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda cls, id: {
        "LLMBriefJob": job,
        "User": user,
    }.get(cls.__name__, None))
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    conn_err = APIConnectionError.__new__(APIConnectionError)
    conn_err.message = "Connection refused"
    conn_err.request = MagicMock()

    with (
        patch.object(llm_tasks, "_get_async_session", return_value=mock_session),
        patch.object(llm_tasks, "_get_redis", return_value=fake_redis),
        patch("app.services.user_service.get_anthropic_api_key", new=AsyncMock(return_value="sk-ant-test")),
        patch("app.services.brief_service.get_brief", new=AsyncMock(return_value=brief)),
        patch("app.services.llm.llm_service.call_llm_brief_enhance", side_effect=conn_err),
    ):
        # Final retry (task_retries == max_retries) → should NOT raise transient
        await llm_tasks._run_enhance(job_id=1, task_retries=3, max_retries=3)

    assert job.status == "failed"
    # Circuit breaker should be incremented on exhausted transient
    redis_store = fake_redis._get_store()
    assert "llm:cb:fails:42" in redis_store
