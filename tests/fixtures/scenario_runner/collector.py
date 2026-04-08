"""pytest collector that turns ``scenarios/*.yaml`` into pytest items.

Registered as a plugin via ``pytest_plugins = ["tests.fixtures.scenario_runner.collector"]``
in the top-level ``tests/conftest.py``. Each YAML file directly under a
``scenarios`` directory becomes one ``ScenarioItem``; the item's ``runtest``
hands off to the async :func:`run_scenario` executor (plan 19.1-02 skeleton;
real Playwright operations land in plan 19.1-03).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from .artifacts import save_failure_artifacts
from .executor import run_scenario
from .schema import Scenario


def pytest_collect_file(parent, file_path: Path):
    # Gate: only YAML files whose immediate parent directory is named
    # ``scenarios``. Everything else (fixtures, data files) is ignored.
    if file_path.suffix == ".yaml" and file_path.parent.name == "scenarios":
        return ScenarioFile.from_parent(parent, path=file_path)
    return None


class ScenarioFile(pytest.File):
    def collect(self):
        raw = yaml.safe_load(self.path.read_text())
        scenario = Scenario.model_validate(raw)
        yield ScenarioItem.from_parent(
            self, name=scenario.name, scenario=scenario
        )


class ScenarioItem(pytest.Item):
    def __init__(self, *, scenario: Scenario, **kw):
        super().__init__(**kw)
        self.scenario = scenario

    def runtest(self) -> None:
        # Reserved-only scenarios can run without a browser — fall back to
        # page=None if the scenario_page fixture is unavailable (e.g. the
        # collector unit tests that don't launch Playwright).
        try:
            page = self._request.getfixturevalue("scenario_page")
        except Exception:
            asyncio.run(run_scenario(None, self.scenario))
            return

        scenario = self.scenario

        async def _run_with_artifacts() -> None:
            # SINGLE event loop wrapping scenario run + failure artifact
            # capture. The Page is bound to the loop/context created by the
            # scenario_page fixture; a second asyncio.run would operate on a
            # closed loop / closed Page and raise "Event loop is closed" or
            # "Page is already closed". By awaiting both run_scenario and
            # save_failure_artifacts inside ONE helper we guarantee they
            # share the same loop and the same Page/Context instance.
            try:
                await run_scenario(page, scenario)
            except Exception:
                await save_failure_artifacts(page, scenario.name)
                raise
            else:
                # Success path: stop tracing without writing trace.zip.
                await page.context.tracing.stop()

        asyncio.run(_run_with_artifacts())

    def repr_failure(self, excinfo):  # pragma: no cover - surface cleanup
        return f"Scenario {self.name} failed:\n{excinfo.getrepr()}"

    def reportinfo(self):
        return self.path, 0, f"scenario: {self.name}"
