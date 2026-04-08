"""Pydantic v2 schema for scenario_runner YAML files.

Discriminated union over step types. 6 P0 step types (open/click/fill/
wait_for/expect_text/expect_status) are implemented by the plan-03 executor.
3 reserved types (say/highlight/wait_for_click) are schema-valid but skipped
by the runner with a WARNING log — reserved for the 19.2 tour player so that
a single scenarios/*.yaml file validates under both runners (D-07).
"""
from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class _StepBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenStep(_StepBase):
    op: Literal["open"]
    url: str


class ClickStep(_StepBase):
    op: Literal["click"]
    target: str


class FillStep(_StepBase):
    op: Literal["fill"]
    target: str
    value: str


class WaitForStep(_StepBase):
    op: Literal["wait_for"]
    target: str
    state: Literal["visible", "hidden", "attached"] = "visible"
    timeout: int = 30000


class ExpectTextStep(_StepBase):
    op: Literal["expect_text"]
    target: str
    contains: str


class ExpectStatusStep(_StepBase):
    op: Literal["expect_status"]
    code: int


# --- Reserved for 19.2 tour player (schema-valid, runner skips with warning) ---


class SayStep(_StepBase):
    op: Literal["say"]
    text: str


class HighlightStep(_StepBase):
    op: Literal["highlight"]
    target: str


class WaitForClickStep(_StepBase):
    op: Literal["wait_for_click"]
    target: str


Step = Annotated[
    Union[
        OpenStep,
        ClickStep,
        FillStep,
        WaitForStep,
        ExpectTextStep,
        ExpectStatusStep,
        SayStep,
        HighlightStep,
        WaitForClickStep,
    ],
    Field(discriminator="op"),
]


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: Optional[str] = None
    steps: List[Step] = Field(..., min_length=1)
