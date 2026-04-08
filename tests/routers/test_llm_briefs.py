"""Router tests for LLM brief enhancement endpoints (Task 2, Plan 16-04).

Covered cases:
1. test_enhance_without_key_returns_400
2. test_enhance_with_key_creates_job_and_returns_polling_partial
3. test_poll_pending_returns_polling_div
4. test_poll_done_returns_preview
5. test_poll_failed_returns_error
6. test_accept_done_job
7. test_circuit_open_returns_429
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.password import hash_password
from app.dependencies import get_db
from app.main import app
from app.models.analytics import AnalysisSession, ContentBrief, SessionStatus
from app.models.llm_brief_job import LLMBriefJob
from app.models.user import User, UserRole
from app.services.user_service import set_anthropic_api_key

pytestmark = pytest.mark.asyncio

_BRIEF_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeee11")
_SESSION_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccc0011")
_SITE_ID = uuid.UUID("11111111-1111-1111-1111-111111111101")


async def _make_user(db: AsyncSession, email: str = "llm_test@example.com") -> User:
    user = User(
        username="llm_tester",
        email=email,
        password_hash=hash_password("test"),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_brief(db: AsyncSession, site_id=None, session_id=None) -> ContentBrief:
    """Create a minimal ContentBrief for testing."""
    from app.models.site import Site, ConnectionStatus
    from datetime import datetime, timezone

    if site_id is None:
        site_id = _SITE_ID
        db.add(Site(
            id=site_id,
            name="LLM Test Site",
            url="https://llm-test.example.com",
            connection_status=ConnectionStatus.unknown,
            is_active=True,
        ))
        await db.flush()

    if session_id is None:
        session_id = _SESSION_ID
        db.add(AnalysisSession(
            id=session_id,
            site_id=site_id,
            name="llm-test-session",
            status=SessionStatus.draft,
            keyword_ids=[],
            keyword_count=0,
        ))
        await db.flush()

    brief = ContentBrief(
        id=_BRIEF_ID,
        session_id=session_id,
        site_id=site_id,
        title="LLM Test Brief",
        keywords_json=[],
    )
    db.add(brief)
    await db.flush()
    return brief


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_enhance_without_key_returns_400(client: AsyncClient, db_session: AsyncSession):
    """User without Anthropic key → POST /briefs/{id}/llm-enhance → 400."""
    user = await _make_user(db_session, "llm1@example.com")
    await _make_brief(db_session)

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    try:
        resp = await client.post(f"/briefs/{_BRIEF_ID}/llm-enhance")
        assert resp.status_code == 400
        assert "Настройте Anthropic API key" in resp.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_enhance_with_key_creates_job_and_returns_polling_partial(
    client: AsyncClient, db_session: AsyncSession
):
    """User with key → POST creates LLMBriefJob (pending) + returns polling div."""
    user = await _make_user(db_session, "llm2@example.com")
    await set_anthropic_api_key(db_session, user, "sk-ant-test-key")
    await _make_brief(db_session)

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override

    # Monkeypatch Celery task .delay() to avoid real task dispatch
    mock_delay = MagicMock(return_value=None)
    with patch("app.routers.llm_briefs.generate_llm_brief_enhancement", create=True) as mock_task:
        mock_task.delay = mock_delay

        # Also patch the import inside the route
        with patch("app.tasks.llm_tasks.generate_llm_brief_enhancement") as patched_task:
            patched_task.delay = mock_delay
            try:
                resp = await client.post(f"/briefs/{_BRIEF_ID}/llm-enhance")
                assert resp.status_code == 200
                assert "hx-get" in resp.text
                assert "генерация" in resp.text
                # LLMBriefJob should exist in DB
                from sqlalchemy import select
                result = await db_session.execute(
                    select(LLMBriefJob).where(LLMBriefJob.brief_id == _BRIEF_ID)
                )
                job = result.scalar_one_or_none()
                assert job is not None
                assert job.status == "pending"
            finally:
                app.dependency_overrides.pop(get_current_user, None)


async def test_poll_pending_returns_polling_div(client: AsyncClient, db_session: AsyncSession):
    """GET /briefs/llm-jobs/{id} with pending job → contains 'генерация'."""
    user = await _make_user(db_session, "llm3@example.com")
    await _make_brief(db_session)

    job = LLMBriefJob(user_id=user.id, brief_id=_BRIEF_ID, status="pending")
    db_session.add(job)
    await db_session.flush()

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    try:
        resp = await client.get(f"/briefs/llm-jobs/{job.id}")
        assert resp.status_code == 200
        assert "генерация" in resp.text
        assert "hx-trigger" in resp.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_poll_done_returns_preview(client: AsyncClient, db_session: AsyncSession):
    """GET with done job → returns preview with 3 sections + Accept button."""
    user = await _make_user(db_session, "llm4@example.com")
    await _make_brief(db_session)

    output = {
        "expanded_sections": [{"heading": "H2: Test", "content": "Test content"}],
        "faq_block": [{"question": "What?", "answer": "This."}],
        "title_variants": ["Title variant 1"],
        "meta_variants": ["Meta variant 1"],
    }
    job = LLMBriefJob(
        user_id=user.id,
        brief_id=_BRIEF_ID,
        status="done",
        output_json=output,
    )
    db_session.add(job)
    await db_session.flush()

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    try:
        resp = await client.get(f"/briefs/llm-jobs/{job.id}")
        assert resp.status_code == 200
        # Should have 3 sections
        assert "Расширенные разделы" in resp.text
        assert "FAQ блок" in resp.text
        assert "Title" in resp.text
        # Accept button
        assert "Принять" in resp.text
        # No polling trigger
        assert "every 2s" not in resp.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_poll_failed_returns_error(client: AsyncClient, db_session: AsyncSession):
    """GET with failed job → returns error block + Regenerate button."""
    user = await _make_user(db_session, "llm5@example.com")
    await _make_brief(db_session)

    job = LLMBriefJob(
        user_id=user.id,
        brief_id=_BRIEF_ID,
        status="failed",
        error_message="API key invalid",
    )
    db_session.add(job)
    await db_session.flush()

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    try:
        resp = await client.get(f"/briefs/llm-jobs/{job.id}")
        assert resp.status_code == 200
        assert "API key invalid" in resp.text
        assert "Повторить" in resp.text
        assert "every 2s" not in resp.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_accept_done_job(client: AsyncClient, db_session: AsyncSession):
    """POST /briefs/llm-jobs/{id}/accept → 200, status=accepted, returns merged HTML."""
    user = await _make_user(db_session, "llm6@example.com")
    await _make_brief(db_session)

    output = {
        "expanded_sections": [{"heading": "H2: Accept test", "content": "Accepted content"}],
        "faq_block": [],
        "title_variants": [],
        "meta_variants": [],
    }
    job = LLMBriefJob(
        user_id=user.id,
        brief_id=_BRIEF_ID,
        status="done",
        output_json=output,
    )
    db_session.add(job)
    await db_session.flush()

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    try:
        resp = await client.post(f"/briefs/llm-jobs/{job.id}/accept")
        assert resp.status_code == 200
        assert "принято" in resp.text.lower() or "AI улучшения приняты" in resp.text
        # Verify DB status
        await db_session.refresh(job)
        assert job.status == "accepted"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_circuit_open_returns_429(client: AsyncClient, db_session: AsyncSession):
    """Pre-set Redis circuit key → POST returns 429."""
    user = await _make_user(db_session, "llm7@example.com")
    await set_anthropic_api_key(db_session, user, "sk-ant-test-key")
    await _make_brief(db_session)

    async def _override():
        return user

    # Mock is_circuit_open to return True
    async def _mock_circuit_open(redis, user_id):
        return True

    app.dependency_overrides[get_current_user] = _override

    with patch("app.services.llm.llm_service.is_circuit_open", _mock_circuit_open):
        try:
            resp = await client.post(f"/briefs/{_BRIEF_ID}/llm-enhance")
            assert resp.status_code == 429
            assert "LLM временно недоступен" in resp.text
        finally:
            app.dependency_overrides.pop(get_current_user, None)
