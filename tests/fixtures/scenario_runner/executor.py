"""Async executor skeleton for scenario_runner.

Plan 19.1-02 delivers the dispatch-shaped skeleton:
- Reserved 19.2 step types (say/highlight/wait_for_click) are skipped with a
  WARNING log so a single YAML file validates and runs (with gaps) under both
  the 19.1 test runner and the future 19.2 tour player (D-07).
- P0 step types raise NotImplementedError; plan 19.1-03 wires real Playwright
  operations into the dispatch slots.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from .schema import Scenario


RESERVED_OPS: set[str] = {"say", "highlight", "wait_for_click"}


async def run_scenario(page: Any, scenario: "Scenario") -> None:
    """Execute a parsed Scenario against a Playwright ``page``.

    ``page`` may be ``None`` for scenarios consisting solely of reserved
    step types (useful for collector unit tests that do not launch a browser).
    """
    for idx, step in enumerate(scenario.steps):
        if step.op in RESERVED_OPS:
            logger.warning(
                f"scenario={scenario.name} step[{idx}] op='{step.op}' "
                f"reserved for 19.2 tour player — skipping"
            )
            continue
        # P0 step dispatch wired in plan 19.1-03 (Playwright runtime).
        raise NotImplementedError(
            f"step op='{step.op}' not yet wired — see plan 19.1-03"
        )
