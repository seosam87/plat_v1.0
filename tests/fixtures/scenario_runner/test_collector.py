"""Unit tests for scenario_runner pytest collector.

Uses pytest's ``pytester`` fixture to spawn an isolated pytest run so the
collector plugin can be exercised against temporary scenarios/*.yaml files
without affecting the outer test session.
"""
from __future__ import annotations

import pytest

pytest_plugins = ["pytester"]


CONFTEST = """
pytest_plugins = ["tests.fixtures.scenario_runner.collector"]
"""

GOOD_YAML = """\
name: inline_fixture
description: inline collector test
steps:
  - op: say
    text: "hi"
"""

BAD_YAML = """\
name: broken
steps:
  - op: clik
    target: "#x"
"""


def test_collects_scenario_yaml_as_item(pytester: pytest.Pytester):
    pytester.makepyfile(conftest=CONFTEST)
    scenarios = pytester.mkdir("scenarios")
    (scenarios / "ok.yaml").write_text(GOOD_YAML)

    result = pytester.runpytest("--collect-only", "scenarios/", "-q")
    result.stdout.fnmatch_lines(["*inline_fixture*"])
    assert result.ret == 0


def test_malformed_yaml_fails_collection_with_named_error(pytester: pytest.Pytester):
    pytester.makepyfile(conftest=CONFTEST)
    scenarios = pytester.mkdir("scenarios")
    (scenarios / "bad.yaml").write_text(BAD_YAML)

    result = pytester.runpytest("--collect-only", "scenarios/")
    # Non-zero exit indicates collection error
    assert result.ret != 0
    combined = "\n".join(result.stdout.lines + result.stderr.lines)
    assert "bad.yaml" in combined
    # The pydantic error should reference the offending step / op
    assert "clik" in combined or "op" in combined


def test_non_scenarios_dir_not_collected(pytester: pytest.Pytester):
    """YAML files outside a 'scenarios' directory must not be collected."""
    pytester.makepyfile(conftest=CONFTEST)
    other = pytester.mkdir("not_scenarios")
    (other / "ok.yaml").write_text(GOOD_YAML)

    result = pytester.runpytest("--collect-only", "not_scenarios/", "-q")
    # No items collected; exit code 5 = no tests collected
    assert "inline_fixture" not in result.stdout.str()


def test_reserved_only_scenario_collected(pytester: pytest.Pytester):
    """A scenario with only reserved (19.2) step types must still collect.

    Plan 19.1-05 removed the committed scenarios/_test_fixture.yaml; this
    test now writes the equivalent reserved-only fixture inline via pytester
    so the collector contract is still exercised without a committed stub.
    """
    RESERVED_YAML = (
        "name: collector_smoke\n"
        "description: collector unit-test fixture — reserved steps only\n"
        "steps:\n"
        "  - op: say\n"
        "    text: \"collector works\"\n"
    )
    pytester.makepyfile(conftest=CONFTEST)
    scenarios = pytester.mkdir("scenarios")
    (scenarios / "_reserved.yaml").write_text(RESERVED_YAML)

    result = pytester.runpytest("--collect-only", "scenarios/", "-q")
    result.stdout.fnmatch_lines(["*collector_smoke*"])
    assert result.ret == 0
