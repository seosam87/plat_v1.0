"""Subprocess-isolated WeasyPrint PDF rendering.

WeasyPrint has a known memory leak (GitHub issues #2130, #1977) that causes
Celery worker processes to grow unboundedly. This module mitigates it by
rendering PDFs in a child process that exits after rendering, freeing all
WeasyPrint-allocated memory back to the OS.

Decision reference: D-12 (Phase 14 CONTEXT.md)
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from loguru import logger


def render_pdf_in_subprocess(html_string: str, timeout_seconds: int = 120) -> bytes:
    """Render HTML to PDF via WeasyPrint in a separate child process.

    The child process imports weasyprint, renders the HTML file, writes PDF
    bytes to a temp file, and exits — freeing all leaked memory. The parent
    reads the PDF bytes from disk and returns them.

    Args:
        html_string: Full HTML document string (UTF-8).
        timeout_seconds: Max seconds to wait before killing the child process.

    Returns:
        PDF file bytes.

    Raises:
        RuntimeError: If subprocess returns non-zero exit code or times out.
    """
    # Write HTML to a temp file to avoid pipe size limits on large documents
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as html_f:
        html_f.write(html_string)
        html_path = html_f.name

    pdf_path = html_path.replace(".html", ".pdf")

    # Minimal child script: import weasyprint, render, write PDF, exit
    script = (
        f"import weasyprint\n"
        f"doc = weasyprint.HTML(filename={html_path!r})\n"
        f"doc.write_pdf({pdf_path!r})\n"
    )

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if result.returncode != 0:
            stderr_excerpt = result.stderr[:500] if result.stderr else "(no stderr)"
            logger.error(
                "PDF subprocess failed",
                returncode=result.returncode,
                stderr=stderr_excerpt,
            )
            raise RuntimeError(
                f"PDF render failed (exit {result.returncode}): {result.stderr[:300]}"
            )

        pdf_bytes = Path(pdf_path).read_bytes()
        logger.debug(
            "PDF rendered successfully in subprocess",
            size_bytes=len(pdf_bytes),
            html_path=html_path,
        )
        return pdf_bytes

    except subprocess.TimeoutExpired:
        logger.error(
            "PDF subprocess timed out",
            timeout_seconds=timeout_seconds,
            html_path=html_path,
        )
        raise RuntimeError(
            f"PDF render timed out after {timeout_seconds}s"
        )
    finally:
        # Always clean up temp files, even on error
        Path(html_path).unlink(missing_ok=True)
        Path(pdf_path).unlink(missing_ok=True)
