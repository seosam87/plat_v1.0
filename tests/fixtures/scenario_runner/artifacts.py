"""Failure-artifact writer for scenario_runner.

On scenario failure the collector awaits ``save_failure_artifacts`` on the
SAME Playwright Page / BrowserContext that ran the failing scenario (no event
loop reuse — see collector.ScenarioItem.runtest). Writes:

    artifacts/scenarios/{sanitized_scenario_name}/failure.png
    artifacts/scenarios/{sanitized_scenario_name}/trace.zip
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _sanitize(name: str) -> str:
    """Make ``name`` safe for use as a directory component."""
    # Collapse anything non-[A-Za-z0-9._-] to an underscore.
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "scenario"


async def save_failure_artifacts(page: Any, scenario_name: str) -> Path:
    """Write screenshot + trace.zip under artifacts/scenarios/{name}/.

    Returns the output directory path (useful for tests / logging).
    """
    out_dir = Path("artifacts/scenarios") / _sanitize(scenario_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    await page.screenshot(
        path=str(out_dir / "failure.png"), full_page=True
    )
    await page.context.tracing.stop(path=str(out_dir / "trace.zip"))
    return out_dir
