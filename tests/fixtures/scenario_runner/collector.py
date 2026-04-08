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
        # Plan 19.1-03 will replace ``None`` with a Playwright page fetched via
        # ``self._request.getfixturevalue("scenario_page")``. For now the
        # executor accepts None for reserved-only scenarios.
        page = None
        try:
            page = self._request.getfixturevalue("scenario_page")
        except Exception:
            # scenario_page fixture not yet defined (plan 19.1-03); for
            # reserved-only scenarios None is fine.
            pass
        asyncio.run(run_scenario(page, self.scenario))

    def repr_failure(self, excinfo):  # pragma: no cover - surface cleanup
        return f"Scenario {self.name} failed:\n{excinfo.getrepr()}"

    def reportinfo(self):
        return self.path, 0, f"scenario: {self.name}"
