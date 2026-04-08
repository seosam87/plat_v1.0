"""Repo-root conftest.

Registers the Phase 19.1 scenario_runner collector plugin at the root level
so that ``pytest --collect-only scenarios/`` (outside the ``tests/`` tree)
loads the custom YAML collector. The same plugin is also registered in
``tests/conftest.py`` for the normal unit-test path; pytest de-dupes.
"""

pytest_plugins = ["tests.fixtures.scenario_runner.collector"]

# Re-export ``scenario_runner`` fixtures at the repo root so items collected
# from ``scenarios/*.yaml`` (which live outside the ``tests/`` tree and do
# NOT auto-load ``tests/fixtures/scenario_runner/conftest.py``) can still
# resolve ``scenario_page`` / ``scenario_browser`` / ``storage_state``.
# pytest discovers fixtures by scanning conftest module globals, so a plain
# ``from ... import *`` is sufficient.
from tests.fixtures.scenario_runner.conftest import (  # noqa: E402,F401
    base_url,
    scenario_page,
)
