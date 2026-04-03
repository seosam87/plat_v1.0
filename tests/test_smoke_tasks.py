"""Unit tests for the smoke_tasks Celery task."""
from __future__ import annotations

from unittest.mock import patch, MagicMock


def test_run_ui_smoke_test_registered():
    """Task must be registered in celery_app with correct name."""
    # Import smoke_tasks first to trigger task registration via @celery_app.task decorator
    import app.tasks.smoke_tasks  # noqa: F401
    from app.celery_app import celery_app
    assert "app.tasks.smoke_tasks.run_ui_smoke_test" in celery_app.tasks


def test_run_ui_smoke_test_returns_summary_on_success():
    """Task returns {total, errors, ok} dict when all routes pass."""
    from app.tasks.smoke_tasks import run_ui_smoke_test

    mock_results = [
        {"url": "/ui/dashboard", "status": 200, "ok": True, "error": None, "skipped": False},
        {"url": "/ui/sites", "status": 200, "ok": True, "error": None, "skipped": False},
    ]

    with patch("app.tasks.smoke_tasks.asyncio.run", return_value=mock_results), \
         patch("app.tasks.smoke_tasks.send_message_sync", return_value=True), \
         patch("app.tasks.smoke_tasks.is_configured", return_value=True):
        result = run_ui_smoke_test.run()  # .run() bypasses Celery machinery

    assert result["total"] == 2
    assert result["errors"] == 0
    assert result["ok"] is True


def test_run_ui_smoke_test_reports_errors():
    """Task returns ok=False and errors count when some routes fail."""
    from app.tasks.smoke_tasks import run_ui_smoke_test

    mock_results = [
        {"url": "/ui/dashboard", "status": 200, "ok": True, "error": None, "skipped": False},
        {"url": "/ui/broken", "status": 500, "ok": False, "error": "Internal Server Error", "skipped": False},
    ]

    sent_messages = []

    with patch("app.tasks.smoke_tasks.asyncio.run", return_value=mock_results), \
         patch("app.tasks.smoke_tasks.send_message_sync", side_effect=lambda msg: sent_messages.append(msg) or True), \
         patch("app.tasks.smoke_tasks.is_configured", return_value=True):
        result = run_ui_smoke_test.run()

    assert result["total"] == 2
    assert result["errors"] == 1
    assert result["ok"] is False
    # Telegram message must mention the failing URL
    assert len(sent_messages) == 1
    assert "/ui/broken" in sent_messages[0]
    assert "500" in sent_messages[0]


def test_run_ui_smoke_test_no_telegram_when_unconfigured():
    """Task does not call send_message_sync when Telegram is not configured."""
    from app.tasks.smoke_tasks import run_ui_smoke_test

    mock_results = [{"url": "/ui/dashboard", "status": 200, "ok": True, "error": None, "skipped": False}]

    with patch("app.tasks.smoke_tasks.asyncio.run", return_value=mock_results), \
         patch("app.tasks.smoke_tasks.send_message_sync") as mock_send, \
         patch("app.tasks.smoke_tasks.is_configured", return_value=False):
        run_ui_smoke_test.run()

    mock_send.assert_not_called()
