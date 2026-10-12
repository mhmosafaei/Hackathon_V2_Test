"""Human-reviewable document conditions. These can never make decisions directly."""

from datetime import date
from typing import Literal

from pydantic import Field

from .common import (
    ActionRequired, AutomationStatus, ConditionType, Confidence, ReviewState, StrictModel,
)


class ExtractedCondition(StrictModel):
    condition_id: str
    document_type: Literal["PERMIT", "CONTRACT"]
    document_id: str
    source_text: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    title: str | None = None
    clause: str | None = None
    section: str | None = None
    description: str | None = None
    condition_type: ConditionType
    variable: str | None = None
    variable_free_text: str | None = None
    operator: str | None = None
    threshold: float | None = None
    threshold_upper: float | None = None
    unit: str | None = None
    duration_hours: float | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    evidence_requirements: list[str] = Field(default_factory=list)
    data_requirements: list[str] = Field(default_factory=list)
    required_action: ActionRequired = ActionRequired.NONE
    confidence: Confidence = Confidence.LOW
    review_required: bool = True
    quote_verified: bool = False
    quote_verification_detail: str | None = None
    automation_status: AutomationStatus | None = None
    review_state: ReviewState = ReviewState.UNREVIEWED
    consequence: str | None = None
    responsible_party: str | None = None
