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
    # Fixture integration: ScenarioItem is a custom pytest.Item (not a
    # pytest.Function), so pytest does not wire _fixtureinfo/_request for
    # us. We build a minimal FuncFixtureInfo that requests ``scenario_page``
    # (function-scoped), and use the private TopRequest to actually resolve
    # the closure in setup(). This matches how pytest.Function does it.
    def __init__(self, *, scenario: Scenario, **kw):
        super().__init__(**kw)
        self.scenario = scenario
        self.funcargs: dict = {}
        from _pytest.fixtures import FuncFixtureInfo, TopRequest

        fm = self.session._fixturemanager
        try:
            closure, arg2fixturedefs = fm.getfixtureclosure(
                parentnode=self,
                initialnames=("scenario_page",),
                ignore_args=(),
            )
        except TypeError:
            closure, arg2fixturedefs = fm.getfixtureclosure(
                ("scenario_page",), self, ignore_args=set()
            )
        self._fixtureinfo = FuncFixtureInfo(
            argnames=("scenario_page",),
            initialnames=("scenario_page",),
            names_closure=list(closure),
            name2fixturedefs=arg2fixturedefs,
        )
        # pytest looks up item.fixturenames when filling fixtures; the
        # fixture error formatter also pokes at item.obj.
        self.fixturenames = self._fixtureinfo.names_closure
        self.obj = lambda scenario_page=None: None
        self._request = TopRequest(self, _ispytest=True)

    def setup(self) -> None:
        self._request._fillfixtures()

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
            # capture. The Page is bound to the loop owned by the
            # scenario_page fixture (stashed on ``page._scenario_loop``);
            # we reuse that loop so run_scenario + save_failure_artifacts
            # + tracing.stop all operate on the same Playwright objects.
            try:
                await run_scenario(page, scenario)
            except Exception:
                await save_failure_artifacts(page, scenario.name)
                raise
            else:
                await page.context.tracing.stop()

        loop = getattr(page, "_scenario_loop", None)
        if loop is None:
            asyncio.run(_run_with_artifacts())
        else:
            loop.run_until_complete(_run_with_artifacts())

    def repr_failure(self, excinfo):  # pragma: no cover - surface cleanup
        return f"Scenario {self.name} failed:\n{excinfo.getrepr()}"

    def reportinfo(self):
        return self.path, 0, f"scenario: {self.name}"
