"""Unit tests for scenario_runner executor skeleton."""
from __future__ import annotations

import asyncio

import pytest

from tests.fixtures.scenario_runner.executor import RESERVED_OPS, run_scenario
from tests.fixtures.scenario_runner.schema import Scenario


def test_reserved_only_scenario_runs_with_warnings(caplog):
    """Scenario with only reserved steps completes and logs a WARNING per step."""
    sc = Scenario.model_validate(
        {
            "name": "reserved_only",
            "steps": [
                {"op": "say", "text": "hi"},
                {"op": "highlight", "target": "#x"},
                {"op": "wait_for_click", "target": "role=button[name='Next']"},
            ],
        }
    )

    # Route loguru through stdlib logging so caplog captures it
    from loguru import logger
    import logging

    class PropagateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), format="{message}", level="WARNING")
    try:
        with caplog.at_level("WARNING"):
            asyncio.run(run_scenario(None, sc))
    finally:
        logger.remove(handler_id)

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 3
    assert all("reserved" in r.getMessage().lower() for r in warnings)


def test_p0_step_requires_page():
    """P0 step dispatch (wired in plan 19.1-03) requires a real Playwright page.

    Passing ``page=None`` raises RuntimeError — this is the contract that
    replaced plan 02's NotImplementedError stub.
    """
    sc = Scenario.model_validate(
        {
            "name": "p0_open",
            "steps": [{"op": "open", "url": "/ui/dashboard"}],
        }
    )
    with pytest.raises(RuntimeError, match="requires a Playwright page"):
        asyncio.run(run_scenario(None, sc))


def test_reserved_ops_constant_covers_all_three():
    assert RESERVED_OPS == {"say", "highlight", "wait_for_click"}
