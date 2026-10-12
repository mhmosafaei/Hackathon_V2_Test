"""Reviewable contract-weather clauses; extraction is never itself executable."""
from enum import StrEnum
from pydantic import Field
from .common import Confidence, StrictModel

class ContractReviewState(StrEnum):
    UNREVIEWED='UNREVIEWED'
    CONFIRMED='CONFIRMED'
    REJECTED='REJECTED'

class RiskAllocation(StrEnum):
    CONTRACTOR='CONTRACTOR'
    EMPLOYER='EMPLOYER'
    SHARED='SHARED'
    UNSPECIFIED='UNSPECIFIED'

class ContractWeatherClause(StrictModel):
    clause_id: str
    document_id: str
    source_text: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    environmental_variable: str | None = None
    operator: str | None = None
    threshold: float | None = None
    unit: str | None = None
    continuous_hours: float | None = Field(default=None,ge=0)
    reference_period: str | None = None
    location: str | None = None
    evidence_requirements: list[str] = Field(default_factory=list)
    consequence: str | None = None
    risk_allocation: RiskAllocation = RiskAllocation.UNSPECIFIED
    confidence: Confidence = Confidence.LOW
    quote_verified: bool = False
    review_required: bool = True
    review_state: ContractReviewState = ContractReviewState.UNREVIEWED
    ambiguity: str | None = None
