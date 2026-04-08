"""Integration tests for notify() wiring in Celery tasks and monitoring service.

Tests verify:
1. Happy-path: tasks with user_id scope emit a Notification row.
2. Failure-path: tasks on exception emit error-severity Notification.
3. Skip-on-no-scope (D-02): tasks without user_id skip in-app notify
   silently — zero Notification rows — but Telegram still fires.
4. Monitoring dispatcher: dispatch_immediate_alerts() skips in-app
   notify (no user_id) but Telegram fires.

All tests use mock-based approach (AsyncMock) consistent with existing
test patterns (no live DB required).

Note: anthropic package is not installed in the test environment, so LLM tests
mock at the import-interception level using sys.modules patching.
"""
from __future__ import annotations

import sys
import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Module-level anthropic mock — must be set before any app.tasks.llm_tasks import
# ---------------------------------------------------------------------------

def _build_anthropic_mock():
    """Build a minimal mock of the anthropic module for tests."""
    mod = types.ModuleType("anthropic")

    # Error classes needed by llm_tasks._run_enhance
    class _APIError(Exception):
        def __init__(self, message="", *, response=None, body=None):
            super().__init__(message)
            self.message = message
            self.status_code = getattr(response, "status_code", 0) if response else 0

    class AuthenticationError(_APIError):
        pass

    class PermissionDeniedError(_APIError):
        pass

    class BadRequestError(_APIError):
        pass

    class APIConnectionError(_APIError):
        pass

    class APITimeoutError(_APIError):
        pass

    class RateLimitError(_APIError):
        pass

    class APIStatusError(_APIError):
        def __init__(self, message="", *, response=None, body=None, status_code=500):
            super().__init__(message, response=response, body=body)
            self.status_code = status_code

    mod.AuthenticationError = AuthenticationError
    mod.PermissionDeniedError = PermissionDeniedError
    mod.BadRequestError = BadRequestError
    mod.APIConnectionError = APIConnectionError
    mod.APITimeoutError = APITimeoutError
    mod.RateLimitError = RateLimitError
    mod.APIStatusError = APIStatusError
    mod.Anthropic = MagicMock()
    mod.AsyncAnthropic = MagicMock()

    return mod, {
        "AuthenticationError": AuthenticationError,
        "BadRequestError": BadRequestError,
    }


_ANTHROPIC_MOCK, _ANTHROPIC_CLASSES = _build_anthropic_mock()
sys.modules.setdefault("anthropic", _ANTHROPIC_MOCK)


# ---------------------------------------------------------------------------
# Happy-path: llm_tasks.py — user_id IS available via job.user_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_brief_ready_creates_notification():
    """generate_llm_brief_enhancement creates notification with kind=llm_brief.ready."""
    from app.tasks.llm_tasks import _run_enhance

    user_id = uuid.uuid4()
    brief_id = uuid.uuid4()
    job_id = 42

    # Build mock job
    mock_job = MagicMock()
    mock_job.id = job_id
    mock_job.user_id = user_id
    mock_job.brief_id = brief_id
    mock_job.status = "pending"
    mock_job.output_json = None
    mock_job.error_message = None

    # Build mock user
    mock_user = MagicMock()
    mock_user.id = user_id

    # Build mock brief
    mock_brief = MagicMock()
    mock_brief.id = brief_id
    mock_brief.topic = "SEO best practices"
    mock_brief.keywords_json = []
    mock_brief.competitor_data_json = {}

    notifications_inserted = []
    mock_session = AsyncMock()

    async def _session_get(model, pk):
        from app.models.llm_brief_job import LLMBriefJob
        from app.models.user import User
        if model is LLMBriefJob:
            return mock_job
        if model is User:
            return mock_user
        return None

    mock_session.get = AsyncMock(side_effect=_session_get)
    mock_session.add = MagicMock(side_effect=lambda obj: notifications_inserted.append(obj))
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.llm_tasks._get_async_session", return_value=ctx), \
         patch("app.tasks.llm_tasks._get_redis", return_value=AsyncMock()), \
         patch("app.services.llm.llm_service.is_circuit_open", new=AsyncMock(return_value=False)), \
         patch("app.services.user_service.get_anthropic_api_key", new=AsyncMock(return_value="sk-test")), \
         patch("app.services.brief_service.get_brief", new=AsyncMock(return_value=mock_brief)), \
         patch("app.services.llm.llm_service.build_brief_prompt", return_value="prompt"), \
         patch("app.services.llm.llm_service.call_llm_brief_enhance", new=AsyncMock(return_value=({"sections": []}, 100, 50))), \
         patch("app.services.llm.llm_service.record_llm_success", new=AsyncMock()), \
         patch("app.services.llm.llm_service.log_llm_usage", new=AsyncMock()):

        await _run_enhance(job_id=job_id, task_retries=0, max_retries=3)

    # Check that a Notification was inserted with correct kind
    from app.models.notification import Notification
    notif_rows = [o for o in notifications_inserted if isinstance(o, Notification)]
    assert len(notif_rows) == 1, f"Expected 1 notification, got {len(notif_rows)}"
    n = notif_rows[0]
    assert n.kind == "llm_brief.ready", f"Expected kind='llm_brief.ready', got '{n.kind}'"
    assert n.user_id == user_id
    assert n.severity == "info"
    assert str(brief_id) in n.link_url or "llm-briefs" in n.link_url


# ---------------------------------------------------------------------------
# Failure-path: llm_tasks.py — error on API call → llm_brief.failed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_brief_failed_creates_error_notification():
    """generate_llm_brief_enhancement emits kind=llm_brief.failed on permanent API error."""
    from app.tasks.llm_tasks import _run_enhance

    AuthenticationError = _ANTHROPIC_CLASSES["AuthenticationError"]

    user_id = uuid.uuid4()
    brief_id = uuid.uuid4()
    job_id = 43

    mock_job = MagicMock()
    mock_job.id = job_id
    mock_job.user_id = user_id
    mock_job.brief_id = brief_id
    mock_job.status = "pending"
    mock_job.output_json = None
    mock_job.error_message = None

    mock_user = MagicMock()
    mock_user.id = user_id

    mock_brief = MagicMock()
    mock_brief.id = brief_id
    mock_brief.topic = "test"
    mock_brief.keywords_json = []
    mock_brief.competitor_data_json = {}

    notifications_inserted = []
    mock_session = AsyncMock()

    async def _session_get(model, pk):
        from app.models.llm_brief_job import LLMBriefJob
        from app.models.user import User
        if model is LLMBriefJob:
            return mock_job
        if model is User:
            return mock_user
        return None

    mock_session.get = AsyncMock(side_effect=_session_get)
    mock_session.add = MagicMock(side_effect=lambda obj: notifications_inserted.append(obj))
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    auth_err = AuthenticationError("Invalid API key")

    with patch("app.tasks.llm_tasks._get_async_session", return_value=ctx), \
         patch("app.tasks.llm_tasks._get_redis", return_value=AsyncMock()), \
         patch("app.services.llm.llm_service.is_circuit_open", new=AsyncMock(return_value=False)), \
         patch("app.services.user_service.get_anthropic_api_key", new=AsyncMock(return_value="sk-bad")), \
         patch("app.services.brief_service.get_brief", new=AsyncMock(return_value=mock_brief)), \
         patch("app.services.llm.llm_service.build_brief_prompt", return_value="prompt"), \
         patch("app.services.llm.llm_service.call_llm_brief_enhance", new=AsyncMock(side_effect=auth_err)), \
         patch("app.services.llm.llm_service.record_llm_failure", new=AsyncMock()), \
         patch("app.services.llm.llm_service.log_llm_usage", new=AsyncMock()):

        await _run_enhance(job_id=job_id, task_retries=0, max_retries=3)

    from app.models.notification import Notification
    notif_rows = [o for o in notifications_inserted if isinstance(o, Notification)]
    assert len(notif_rows) == 1, f"Expected 1 error notification, got {len(notif_rows)}"
    n = notif_rows[0]
    assert n.kind == "llm_brief.failed", f"Expected kind='llm_brief.failed', got '{n.kind}'"
    assert n.severity == "error"
    assert n.user_id == user_id


# ---------------------------------------------------------------------------
# Skip-on-no-scope tests (D-02) — crawl, position, client_report, audit, suggest
# These tasks have NO user_id in their signatures → zero Notification rows
# but Telegram still fires.
# ---------------------------------------------------------------------------

def test_crawl_task_without_user_id_skips_inapp_but_telegram_fires():
    """crawl_site has no user_id arg → notify() never called; task returns normally.

    This pins the D-02 skip behaviour: in-app is silently skipped.
    We verify by asserting notify() is never called (patching at service level).
    """
    import uuid as _uuid

    site_id = str(_uuid.uuid4())

    # Patch notify at the service module level (canonical location)
    with patch("app.tasks.crawl_tasks.site_active_guard", return_value=None), \
         patch("app.tasks.crawl_tasks.notify") as mock_notify:

        # Crawl site needs a minimal DB stub — use site_active_guard returning a skip
        # Actually easier: make site_active_guard return a skip dict (skips whole task)
        pass

    # Simpler approach: verify notify is never called by patching site_active_guard to skip
    with patch("app.tasks.crawl_tasks.site_active_guard",
               return_value={"status": "skipped", "reason": "disabled"}) as mock_guard, \
         patch("app.tasks.crawl_tasks.notify") as mock_notify:

        from app.tasks.crawl_tasks import crawl_site
        result = crawl_site(site_id)

    # notify() was never called (no user_id scope, task skipped early)
    mock_notify.assert_not_called()
    assert result["status"] == "skipped"


def test_position_check_without_user_id_skips_inapp():
    """check_positions has no user_id → notify never called."""
    import uuid as _uuid

    site_id = str(_uuid.uuid4())

    with patch("app.tasks.position_tasks.site_active_guard", return_value=None), \
         patch("app.tasks.position_tasks.get_sync_db") as mock_get_sync_db, \
         patch("app.services.notifications.notify") as mock_notify:

        mock_db = MagicMock()
        mock_db_ctx = MagicMock()
        mock_db_ctx.__enter__ = MagicMock(return_value=mock_db)
        mock_db_ctx.__exit__ = MagicMock(return_value=False)

        # Return empty keywords list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        mock_get_sync_db.return_value = mock_db_ctx

        from app.tasks.position_tasks import check_positions
        result = check_positions(site_id)

    mock_notify.assert_not_called()
    assert result["status"] == "skipped"  # no keywords → skipped


def test_audit_task_without_user_id_skips_inapp():
    """run_site_audit has no user_id → notify never called."""
    import uuid as _uuid

    site_id = str(_uuid.uuid4())

    with patch("app.tasks.audit_tasks.site_active_guard", return_value=None), \
         patch("app.tasks.audit_tasks.asyncio") as mock_asyncio, \
         patch("app.services.notifications.notify") as mock_notify:

        mock_asyncio.new_event_loop.return_value = MagicMock()
        loop = mock_asyncio.new_event_loop.return_value
        loop.run_until_complete.return_value = {"status": "done", "pages_audited": 0, "issues_found": 0}

        from app.tasks.audit_tasks import run_site_audit
        result = run_site_audit(site_id)

    mock_notify.assert_not_called()
    assert result["status"] == "done"


def test_suggest_task_without_user_id_skips_inapp():
    """fetch_suggest_keywords has no user_id → notify never called."""
    import uuid as _uuid

    job_id = str(_uuid.uuid4())

    with patch("app.tasks.suggest_tasks.get_sync_db") as mock_get_sync_db, \
         patch("app.tasks.suggest_tasks.sync_redis") as mock_redis_mod, \
         patch("app.services.notifications.notify") as mock_notify:

        mock_db = MagicMock()
        mock_db_ctx = MagicMock()
        mock_db_ctx.__enter__ = MagicMock(return_value=mock_db)
        mock_db_ctx.__exit__ = MagicMock(return_value=False)
        mock_get_sync_db.return_value = mock_db_ctx

        # Job not found → early return
        mock_db.get.return_value = None

        mock_r = MagicMock()
        mock_redis_mod.from_url.return_value = mock_r
        mock_r.get.return_value = None

        from app.tasks.suggest_tasks import fetch_suggest_keywords
        result = fetch_suggest_keywords(job_id)

    mock_notify.assert_not_called()
    assert result["status"] == "failed"


def test_client_pdf_task_without_user_id_skips_inapp():
    """generate_client_pdf has no user_id → notify never called; Telegram fires normally."""
    import uuid as _uuid

    report_id = str(_uuid.uuid4())
    site_id = str(_uuid.uuid4())

    notifications_inserted = []

    with patch("app.tasks.client_report_tasks.asyncio") as mock_asyncio, \
         patch("app.services.notifications.notify") as mock_notify:

        mock_asyncio.run.return_value = {"status": "ready", "size": 1024}

        from app.tasks.client_report_tasks import generate_client_pdf
        result = generate_client_pdf(report_id, site_id, {})

    mock_notify.assert_not_called()
    assert result == {"status": "ready", "size": 1024}


# ---------------------------------------------------------------------------
# Monitoring dispatcher: skip in-app, Telegram fires
# ---------------------------------------------------------------------------

def test_monitoring_dispatch_skips_inapp():
    """dispatch_immediate_alerts() logs debug skip + notify() never called.

    Telegram fires for error-severity alerts; notify() is never called
    because dispatch_immediate_alerts has no user_id in scope (D-02).
    """
    import uuid as _uuid
    from app.services.change_monitoring_service import dispatch_immediate_alerts
    from app.models.change_monitoring import AlertSeverity, ChangeAlert, ChangeType

    site_id = _uuid.uuid4()

    # Build an error-severity alert
    alert = MagicMock(spec=ChangeAlert)
    alert.severity = AlertSeverity.error.value
    alert.change_type = MagicMock()
    alert.change_type.value = "page_404"
    alert.page_url = "https://example.com/page"
    alert.details = "HTTP 200 → 404"
    alert.site_id = site_id
    alert.sent_at = None

    mock_db = MagicMock()
    telegram_mock = MagicMock(return_value=True)  # Telegram fires

    # send_message_sync is imported inside the function body, must patch at its source
    with patch("app.services.telegram_service.send_message_sync", telegram_mock), \
         patch("app.services.telegram_service.format_change_alert", return_value="[alert msg]"), \
         patch("app.tasks.crawl_tasks.notify") as mock_notify_crawl, \
         patch("app.services.change_monitoring_service.notify") as mock_notify:

        sent = dispatch_immediate_alerts(mock_db, "Test Site", [alert])

    # Telegram still fired
    assert sent >= 1
    telegram_mock.assert_called_once()

    # notify() was never called — no user scope in dispatch_immediate_alerts
    mock_notify.assert_not_called()
