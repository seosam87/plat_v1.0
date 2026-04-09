"""Backward-compat + TourMeta tests for the relocated scenario schema."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.services.scenario_schema import Scenario, TourMeta

SCENARIOS_DIR = Path(__file__).resolve().parents[3] / "scenarios"


def _load(name: str) -> Scenario:
    raw = yaml.safe_load((SCENARIOS_DIR / name).read_text())
    return Scenario.model_validate(raw)


def test_existing_scenario_01_has_no_tour():
    sc = _load("01-suggest-to-results.yaml")
    assert sc.tour is None
    assert sc.name == "suggest-to-results"


def test_existing_scenario_02_has_no_tour():
    sc = _load("02-site-form-submit.yaml")
    assert sc.tour is None


def test_tour_meta_parses():
    sc = Scenario.model_validate(
        {
            "name": "t",
            "steps": [{"op": "say", "text": "hi"}],
            "tour": {"entry_url": "/ui/x", "title": "T"},
        }
    )
    assert isinstance(sc.tour, TourMeta)
    assert sc.tour.entry_url == "/ui/x"
    assert sc.tour.intro is None


def test_tour_meta_rejects_extra_field():
    with pytest.raises(ValidationError):
        Scenario.model_validate(
            {
                "name": "t",
                "steps": [{"op": "say", "text": "hi"}],
                "tour": {"entry_url": "/ui/x", "title": "T", "extra": 1},
            }
        )
