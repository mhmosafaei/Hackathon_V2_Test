"""Confirmed rules and three-valued groups used by the deterministic evaluator."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from .common import AutomationStatus, StrictModel, UtcAwareModel
from .environmental import SourceBinding


class RuleKind(StrEnum):
    INSTANT = "INSTANT"
    DURATION = "DURATION"
    STATE = "STATE"
    CALENDAR = "CALENDAR"
    DARKNESS = "DARKNESS"
    WORKABILITY = "WORKABILITY"
    MANUAL_GATE = "MANUAL_GATE"


class GroupOperator(StrEnum):
    AND = "AND"
    OR = "OR"


class ExecutableRule(UtcAwareModel):
    rule_id: str
    source_condition_id: str
    variable: str | None = None
    operator: str | None = None
    threshold: float | None = None
    threshold_upper: float | None = None
    unit: str | None = None
    timezone: str = "Europe/London"
    kind: RuleKind
    duration_hours: float | None = Field(default=None, ge=0)
    applicable_start_date: str | None = None
    applicable_end_date: str | None = None
    required_evidence: list[str] = Field(default_factory=list)
    source_page: int | None = Field(default=None, ge=1)
    source_clause: str | None = None
    source_text: str | None = None
    edit_diff: str | None = None
    source_bindings: list[SourceBinding] = Field(default_factory=list)
    automation_status: AutomationStatus
    active: bool = True
    confirmed_by_user: str
    confirmed_at: datetime

    @model_validator(mode="after")
    def confirmed_rule_needs_identity(self) -> "ExecutableRule":
        if not self.confirmed_by_user.strip():
            raise ValueError("confirmed_by_user cannot be blank")
        return self


class RuleGroup(StrictModel):
    group_id: str
    operator: GroupOperator
    members: list[str] = Field(min_length=1)
    title: str | None = None
    min_continuous_hours: float | None = Field(default=None, ge=0)
