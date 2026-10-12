"""Outputs from deterministic evaluation, retaining enough evidence to audit a decision."""

from datetime import datetime

from pydantic import Field

from .common import ActionRequired, OperationalStatus, RuleOutcome, SourceRole, SourceType, UtcAwareModel


class RuleResult(UtcAwareModel):
    rule_id: str
    t_start: datetime
    t_end: datetime
    outcome: RuleOutcome
    detail: str
    measured_value: float | None = None
    unit: str | None = None
    threshold: float | None = None
    required_actions: list[ActionRequired] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    condition_id: str | None = None
    source_text: str | None = None
    source_page: int | None = Field(default=None, ge=1)
    evidence_timestamp: datetime | None = None
    evidence_fresh: bool | None = None
    operational_status: OperationalStatus | None = None
    rule_trace: list[str] = Field(default_factory=list)


class EvidenceItem(UtcAwareModel):
    evidence_id: str
    rule_id: str | None = None
    source_type: SourceType
    source_role: SourceRole
    decision_reason: str
    retrieval_time: datetime | None = None
    observation_timestamp: datetime | None = None
    source_text: str | None = None
    page: int | None = Field(default=None, ge=1)
    dataset_id: str | None = None
    measured_value: float | None = None
    unit: str | None = None


class Window(UtcAwareModel):
    start: datetime
    end: datetime
    status: OperationalStatus
    required_actions: list[ActionRequired] = Field(default_factory=list)
    violated: list[str] = Field(default_factory=list)
    satisfied: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
