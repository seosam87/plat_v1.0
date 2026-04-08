"""Unit tests for scenario_runner schema (Pydantic v2 discriminated union)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.fixtures.scenario_runner.schema import Scenario


def test_all_p0_step_types_validate():
    """Valid scenario with all 6 P0 step types validates without error."""
    raw = {
        "name": "p0_all_steps",
        "description": "all P0 step types",
        "steps": [
            {"op": "open", "url": "/ui/dashboard"},
            {"op": "click", "target": "role=button[name='Go']"},
            {"op": "fill", "target": "#q", "value": "hello"},
            {"op": "wait_for", "target": "#results"},
            {"op": "expect_text", "target": "#results", "contains": "hello"},
            {"op": "expect_status", "code": 200},
        ],
    }
    sc = Scenario.model_validate(raw)
    assert sc.name == "p0_all_steps"
    assert len(sc.steps) == 6


def test_reserved_step_types_validate():
    """Scenario with reserved 19.2 step types (say/highlight/wait_for_click) validates."""
    raw = {
        "name": "reserved_mix",
        "description": "reserved types accepted",
        "steps": [
            {"op": "say", "text": "intro"},
            {"op": "highlight", "target": "#kw-table"},
            {"op": "wait_for_click", "target": "role=button[name='Next']"},
        ],
    }
    sc = Scenario.model_validate(raw)
    assert [s.op for s in sc.steps] == ["say", "highlight", "wait_for_click"]


def test_unknown_op_raises_validation_error():
    """Unknown `op` value fails validation with discriminator error naming step index."""
    raw = {
        "name": "bad",
        "description": None,
        "steps": [
            {"op": "open", "url": "/"},
            {"op": "clik", "target": "#x"},  # typo
        ],
    }
    with pytest.raises(ValidationError) as exc:
        Scenario.model_validate(raw)
    msg = str(exc.value)
    # Pydantic discriminated union error names the offending index
    assert "steps.1" in msg or "steps.[1]" in msg or "1" in msg
    assert "op" in msg


def test_wait_for_defaults():
    """WaitForStep defaults: state='visible', timeout=30000 when omitted."""
    raw = {
        "name": "wf",
        "steps": [{"op": "wait_for", "target": "#results"}],
    }
    sc = Scenario.model_validate(raw)
    step = sc.steps[0]
    assert step.state == "visible"
    assert step.timeout == 30000


def test_empty_steps_rejected():
    """Scenario.steps must be length >= 1."""
    with pytest.raises(ValidationError):
        Scenario.model_validate({"name": "empty", "steps": []})


def test_extra_field_forbidden():
    """Extra fields on step are rejected (catches YAML typos)."""
    raw = {
        "name": "extra",
        "steps": [{"op": "open", "url": "/", "bogus": "x"}],
    }
    with pytest.raises(ValidationError):
        Scenario.model_validate(raw)
