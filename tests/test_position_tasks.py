"""Unit tests for diagnostics in position_tasks.py.

Tests verify that check_positions always returns a `diagnostics` key explaining
what happened during the check, covering all major failure modes.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_keyword(engine_value: str | None = "yandex", phrase: str = "test keyword"):
    """Create a mock Keyword object."""
    kw = MagicMock()
    kw.id = uuid.uuid4()
    kw.phrase = phrase
    if engine_value is not None:
        kw.engine = MagicMock()
        kw.engine.value = engine_value
    else:
        kw.engine = None
    return kw


def _make_db_context(keywords=None):
    """Return a get_sync_db context-manager mock that returns the given keywords list."""
    if keywords is None:
        keywords = []

    mock_session = MagicMock()
    mock_session.execute.return_value.scalars.return_value.all.return_value = keywords
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    return mock_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCheckPositionsDiagnostics:
    """Verify that check_positions always includes a diagnostics key."""

    def test_site_guard_skip_includes_diagnostics(self):
        """site_active_guard early-return path includes diagnostics key with warning level."""
        from app.tasks.position_tasks import check_positions

        with patch("app.tasks.position_tasks.site_active_guard") as mock_guard:
            mock_guard.return_value = {
                "status": "skipped",
                "reason": "site not found",
                "site_id": "test-site-id",
            }
            result = check_positions("test-site-id")

        assert "diagnostics" in result, "diagnostics key must be present on guard early-return"
        assert isinstance(result["diagnostics"], list)
        assert len(result["diagnostics"]) >= 1
        assert any(d["level"] == "warning" for d in result["diagnostics"]), \
            "Guard skip should produce a warning-level diagnostic"
        assert any("skipped" in d["message"].lower() for d in result["diagnostics"]), \
            "Diagnostic message should mention skipped"

    def test_no_keywords_returns_warning_diagnostic(self):
        """No keywords for a site produces warning diagnostic with helpful message."""
        from app.tasks.position_tasks import check_positions

        site_id = str(uuid.uuid4())
        db_ctx = _make_db_context(keywords=[])

        with (
            patch("app.tasks.position_tasks.site_active_guard", return_value=None),
            patch("app.tasks.position_tasks.get_sync_db", return_value=db_ctx),
        ):
            result = check_positions(site_id)

        assert "diagnostics" in result, "diagnostics key must be present"
        assert result["positions_written"] == 0
        diag_messages = [d["message"] for d in result["diagnostics"]]
        assert any("No keywords" in m or "no keywords" in m.lower() for m in diag_messages), \
            f"Expected 'No keywords' message, got: {diag_messages}"
        assert any(d["level"] == "warning" for d in result["diagnostics"]), \
            "No-keywords diagnostic should be warning level"

    def test_google_skipped_returns_warning_diagnostic(self):
        """Google keywords skipped when DataForSEO not configured produces warning diagnostic."""
        from app.tasks.position_tasks import check_positions

        site_id = str(uuid.uuid4())
        google_kw = _make_keyword(engine_value="google", phrase="buy shoes")
        db_ctx = _make_db_context(keywords=[google_kw])

        mock_settings = MagicMock()
        mock_settings.DATAFORSEO_LOGIN = None
        mock_settings.DATAFORSEO_PASSWORD = None
        mock_settings.POSITION_DROP_THRESHOLD = 10

        with (
            patch("app.tasks.position_tasks.site_active_guard", return_value=None),
            patch("app.tasks.position_tasks.get_sync_db", return_value=db_ctx),
            patch("app.config.settings", mock_settings),
            patch("app.tasks.position_tasks._send_drop_alerts", return_value=0),
        ):
            result = check_positions(site_id)

        assert "diagnostics" in result, "diagnostics key must be present"
        diag_messages = [d["message"] for d in result["diagnostics"]]
        assert any("Google" in m and "skipped" in m.lower() for m in diag_messages), \
            f"Expected Google-skipped diagnostic, got: {diag_messages}"

    def test_success_path_includes_diagnostics_key(self):
        """Successful check_positions returns diagnostics key (list type)."""
        from app.tasks.position_tasks import check_positions

        site_id = str(uuid.uuid4())
        yandex_kw = _make_keyword(engine_value="yandex", phrase="купить диван")
        db_ctx = _make_db_context(keywords=[yandex_kw])

        mock_settings = MagicMock()
        mock_settings.DATAFORSEO_LOGIN = None
        mock_settings.DATAFORSEO_PASSWORD = None
        mock_settings.POSITION_DROP_THRESHOLD = 10

        with (
            patch("app.tasks.position_tasks.site_active_guard", return_value=None),
            patch("app.tasks.position_tasks.get_sync_db", return_value=db_ctx),
            patch("app.config.settings", mock_settings),
            patch("app.tasks.position_tasks._check_via_xmlproxy", return_value=3),
            patch("app.tasks.position_tasks._send_drop_alerts", return_value=0),
        ):
            result = check_positions(site_id)

        assert "diagnostics" in result, "diagnostics key must always be in result"
        assert isinstance(result["diagnostics"], list), "diagnostics must be a list"
        assert result["positions_written"] == 3

    def test_xmlproxy_missing_creds_produces_error_diagnostic(self):
        """_check_via_xmlproxy with no credentials appends error-level diagnostic."""
        from app.tasks.position_tasks import _check_via_xmlproxy

        diagnostics = []

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)

        task_mock = MagicMock()

        with (
            patch("app.tasks.position_tasks.get_sync_db", return_value=mock_db),
            patch("app.tasks.position_tasks._check_via_xmlproxy.__module__"),
        ):
            # Patch the credential service to return no credentials
            with patch("app.services.service_credential_service.get_credential_sync", return_value=None):
                written = _check_via_xmlproxy(task_mock, "test-site-id", [], diagnostics)

        assert written == 0
        assert len(diagnostics) >= 1, "diagnostics list should have at least one entry"
        assert any(d["level"] == "error" for d in diagnostics), \
            f"Expected error-level diagnostic for missing creds, got: {diagnostics}"
        assert any("XMLProxy" in d["message"] and "credentials" in d["message"].lower() for d in diagnostics), \
            f"Diagnostic should mention XMLProxy credentials, got: {diagnostics}"
