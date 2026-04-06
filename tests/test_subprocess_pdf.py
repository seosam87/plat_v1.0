"""Tests for subprocess-isolated WeasyPrint PDF renderer.

Tests cover:
- Valid HTML returns PDF bytes starting with %PDF-
- Russian text renders without error
- Timeout raises RuntimeError with "timed out"
- Temp files are cleaned up after success
- Subprocess failure raises RuntimeError with "PDF render failed"
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from unittest.mock import patch

import pytest

try:
    import weasyprint  # noqa: F401
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False

from app.services.subprocess_pdf import render_pdf_in_subprocess


needs_weasyprint = pytest.mark.skipif(
    not HAS_WEASYPRINT,
    reason="weasyprint not installed in test environment",
)


class TestRenderPdfInSubprocess:
    """Tests for the subprocess-isolated WeasyPrint PDF renderer."""

    @needs_weasyprint
    def test_valid_html_returns_pdf_bytes(self):
        """Minimal valid HTML produces PDF bytes starting with %PDF-."""
        html = "<html><body><h1>Test</h1></body></html>"
        result = render_pdf_in_subprocess(html)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"
        assert len(result) > 100  # non-trivial PDF

    @needs_weasyprint
    def test_russian_text_renders(self):
        """Russian text in HTML renders without error, result is %PDF-."""
        html = (
            "<html><body>"
            "<h1>Тестовый отчёт</h1>"
            "<p>Проверка кириллицы в PDF.</p>"
            "</body></html>"
        )
        result = render_pdf_in_subprocess(html)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    @needs_weasyprint
    def test_lenient_html_still_produces_pdf(self):
        """HTML with unclosed tags still produces PDF bytes (WeasyPrint is lenient)."""
        html = "<html><body><p>Unclosed paragraph<p>Another"
        result = render_pdf_in_subprocess(html)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    @needs_weasyprint
    def test_temp_files_cleaned_on_success(self):
        """HTML and PDF temp files are removed after a successful render."""
        html = "<html><body><p>Cleanup test</p></body></html>"
        temp_dir = tempfile.gettempdir()
        before = set(os.listdir(temp_dir))

        render_pdf_in_subprocess(html)

        after = set(os.listdir(temp_dir))
        new_files = after - before
        leftover = [f for f in new_files if f.endswith((".html", ".pdf"))]
        assert len(leftover) == 0, f"Leftover temp files: {leftover}"

    def test_timeout_via_mock(self):
        """Subprocess TimeoutExpired is caught and re-raised as RuntimeError with 'timed out'."""
        with patch(
            "app.services.subprocess_pdf.subprocess.run",
            side_effect=subprocess.TimeoutExpired("cmd", 1),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                render_pdf_in_subprocess("<html></html>", timeout_seconds=1)

    def test_subprocess_failure_raises_runtime_error(self):
        """Non-zero subprocess exit code raises RuntimeError with 'PDF render failed'."""
        mock_result = type("Result", (), {
            "returncode": 1,
            "stderr": "ImportError: No module named weasyprint",
            "stdout": "",
        })()

        with patch(
            "app.services.subprocess_pdf.subprocess.run",
            return_value=mock_result,
        ):
            with pytest.raises(RuntimeError, match="PDF render failed"):
                render_pdf_in_subprocess("<html></html>")

    def test_temp_files_cleaned_on_failure(self):
        """Temp HTML file is removed even when subprocess fails."""
        mock_result = type("Result", (), {
            "returncode": 1,
            "stderr": "error",
            "stdout": "",
        })()

        captured_html_path = []

        def mock_run(*args, **kwargs):
            # Extract the script from the subprocess call to find the html path
            script = args[0][2]  # [sys.executable, "-c", script]
            # The script contains the html path
            import re
            match = re.search(r"filename=r?'([^']+)'", script)
            if match:
                captured_html_path.append(match.group(1))
            return mock_result

        with patch("app.services.subprocess_pdf.subprocess.run", side_effect=mock_run):
            with pytest.raises(RuntimeError):
                render_pdf_in_subprocess("<html></html>")

        # Verify the temp HTML file was cleaned up
        if captured_html_path:
            assert not os.path.exists(captured_html_path[0]), (
                f"Temp file not cleaned up: {captured_html_path[0]}"
            )
