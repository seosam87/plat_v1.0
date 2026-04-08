"""Unit tests for save_failure_artifacts — no real browser."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from tests.fixtures.scenario_runner.artifacts import (
    _sanitize,
    save_failure_artifacts,
)


def _mock_page() -> MagicMock:
    page = MagicMock(name="page")
    page.screenshot = AsyncMock()
    page.context = MagicMock(name="context")
    page.context.tracing = MagicMock(name="tracing")
    page.context.tracing.stop = AsyncMock()
    return page


def test_sanitize_replaces_unsafe_chars() -> None:
    assert _sanitize("foo / bar baz") == "foo_bar_baz"
    assert _sanitize("01-suggest-to-results") == "01-suggest-to-results"
    assert _sanitize("") == "scenario"


def test_save_failure_artifacts_writes_expected_paths(tmp_path, monkeypatch) -> None:
    # Run in a tempdir so the real `artifacts/` tree isn't created.
    monkeypatch.chdir(tmp_path)
    page = _mock_page()

    out_dir = asyncio.run(
        save_failure_artifacts(page, "suggest to results")
    )

    expected = tmp_path / "artifacts" / "scenarios" / "suggest_to_results"
    assert out_dir == Path("artifacts/scenarios/suggest_to_results")
    assert expected.exists()

    page.screenshot.assert_awaited_once()
    screenshot_kwargs = page.screenshot.await_args.kwargs
    assert screenshot_kwargs["path"] == str(
        Path("artifacts/scenarios/suggest_to_results/failure.png")
    )
    assert screenshot_kwargs["full_page"] is True

    page.context.tracing.stop.assert_awaited_once()
    trace_kwargs = page.context.tracing.stop.await_args.kwargs
    assert trace_kwargs["path"] == str(
        Path("artifacts/scenarios/suggest_to_results/trace.zip")
    )
