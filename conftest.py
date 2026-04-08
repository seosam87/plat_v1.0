"""Repo-root conftest.

Registers the Phase 19.1 scenario_runner collector plugin at the root level
so that ``pytest --collect-only scenarios/`` (outside the ``tests/`` tree)
loads the custom YAML collector. The same plugin is also registered in
``tests/conftest.py`` for the normal unit-test path; pytest de-dupes.
"""

pytest_plugins = ["tests.fixtures.scenario_runner.collector"]
