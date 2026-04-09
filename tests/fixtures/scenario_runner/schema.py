"""Re-export shim — canonical schema lives in app/services/scenario_schema.py.

Kept so Phase 19.1 test imports (`from .schema import Scenario`) continue to work
unchanged. All new code should import directly from app.services.scenario_schema.
"""
from app.services.scenario_schema import *  # noqa: F401,F403
from app.services.scenario_schema import (  # explicit for IDEs / star-import hygiene
    ClickStep,
    ExpectStatusStep,
    ExpectTextStep,
    FillStep,
    HighlightStep,
    OpenStep,
    SayStep,
    Scenario,
    Step,
    TourMeta,
    WaitForClickStep,
    WaitForStep,
)
