"""Strict local contracts for PermitPulse Intelligence v1.

These models mirror the supplied v1 JSON contracts.  They are intentionally
separate from the legacy permit-condition model: a source-verified candidate,
an authority proposal, a human approval, and an executable rule remain four
different facts.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


DocumentKind = Literal["MARINE_LICENCE", "DECISION_NOTICE", "CONTRACT", "MULTI_INSTRUMENT", "OTHER", "UNKNOWN"]
PageStatus = Literal["PROCESSED_WITH_REQUIREMENTS", "PROCESSED_SOURCE_ONLY", "UNREADABLE", "FAILED", "NOT_PROCESSED"]
StageName = Literal["DOCUMENT_EXTRACTION", "OPERATIONAL_RELEVANCE", "ENVIRONMENTAL_MAPPING", "DATA_FEASIBILITY", "WORK_WINDOW_EVALUATION"]
StageStatus = Literal["NOT_STARTED", "RUNNING", "COMPLETED", "PARTIAL", "BLOCKED", "FAILED", "NOT_APPLICABLE"]
Processor = Literal["OPENAI", "DETERMINISTIC", "MOCK", "NONE"]
SourceKind = Literal["OPERATIVE_INSTRUMENT", "DECISION_NOTICE", "THIRD_PARTY_ADVICE", "ASSESSMENT", "INCORPORATED_DOCUMENT", "DEFINITION", "TABLE", "SCHEDULE", "MAP_GEOMETRY", "HISTORICAL", "OTHER"]
Modality = Literal["MUST", "MUST_NOT", "MAY", "SHOULD", "CONDITIONAL", "DESCRIPTIVE", "UNKNOWN"]
AuthorityStatus = Literal["OPERATIVE", "INCORPORATED", "CONTEXT_ONLY", "UNRESOLVED"]
Verification = Literal["SOURCE_VERIFIED", "SOURCE_NOT_FOUND", "CONTEXT_UNRESOLVED", "PENDING"]
ReviewState = Literal["UNREVIEWED", "APPROVED", "REJECTED", "NEEDS_CLARIFICATION"]
Lifecycle = Literal["GENERAL", "PRE_WORK", "DURING_WORK", "POST_WORK", "MAINTENANCE", "DECOMMISSIONING", "UNKNOWN"]
OperationalRole = Literal["DIRECT_WORK_GATE", "MONITORING_REQUIREMENT", "NOTIFICATION_OR_APPROVAL", "REPORTING_OR_ADMINISTRATION", "EXTERNAL_PREREQUISITE", "NOT_OPERATIONALLY_RELEVANT", "UNRESOLVED"]
Suitability = Literal["NOT_CHECKED", "VERIFIED_SUITABLE", "AVAILABLE_NOT_DECIDING", "UNAVAILABLE", "REQUIRES_LOCAL_MEASUREMENT", "REQUIRES_MANUAL_CONFIRMATION"]


class DocumentRecord(StrictModel):
    document_id: str
    filename: str
    sha256: str
    title: str
    document_kind: DocumentKind = "UNKNOWN"
    issuer: str | None = None
    licence_number: str | None = None
    issued_date: str | None = None
    effective_date: str | None = None
    expiry_date: str | None = None
    physical_pages: int
    example_only: bool = False


class PageCoverage(StrictModel):
    page_number: int
    status: PageStatus
    source_count: int
    requirement_count: int
    errors: list[str] = Field(default_factory=list)


class Coverage(StrictModel):
    physical_pages: int
    processed_pages: int
    source_only_pages: int
    failed_pages: int
    unreadable_pages: int
    page_results: list[PageCoverage]
    numbered_conditions: list[str]
    unlinked_condition_ids: list[str]
    completeness: Literal["COMPLETE_WITH_REVIEW", "PARTIAL", "FAILED", "NOT_STARTED"]


class StageRun(StrictModel):
    stage: StageName
    status: StageStatus
    processor: Processor
    model: str | None = None
    prompt_version: str | None = None
    batches_total: int = 0
    batches_completed: int = 0
    response_ids: list[str] = Field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    elapsed_seconds: float | None = None
    cost_usd: float | None = None
    error_messages: list[str] = Field(default_factory=list)


class SourceRecord(StrictModel):
    source_id: str
    parent_source_id: str | None = None
    section_id: str | None = None
    source_kind: SourceKind
    page_start: int
    page_end: int
    exact_text: str
    source_hash: str
    authority_actor: str | None = None


class Definition(StrictModel):
    term: str
    meaning: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    conflict_detected: bool = False
    review_note: str | None = None


class Requirement(StrictModel):
    requirement_id: str
    parent_condition_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    page_start: int
    page_end: int
    section_id: str | None = None
    exact_quote: str
    summary: str
    actor: str | None = None
    action: str | None = None
    object: str | None = None
    modality: Modality = "UNKNOWN"
    authority_status: AuthorityStatus = "UNRESOLVED"
    authority_basis_source_ids: list[str] = Field(default_factory=list)
    source_verification: Verification = "PENDING"
    atomic_completeness: Literal["COMPLETE", "PARTIAL", "UNRESOLVED"] = "UNRESOLVED"
    temporal_expressions: list[str] = Field(default_factory=list)
    numeric_expressions: list[str] = Field(default_factory=list)
    exception_texts: list[str] = Field(default_factory=list)
    cross_reference_ids: list[str] = Field(default_factory=list)
    lifecycle_phases: list[Lifecycle] = Field(default_factory=lambda: ["UNKNOWN"])
    ambiguity_flags: list[str] = Field(default_factory=list)
    human_review: ReviewState = "UNREVIEWED"


class OperationalAssessment(StrictModel):
    requirement_id: str
    primary_role: OperationalRole
    operational_activities: list[str] = Field(default_factory=list)
    lifecycle_phases: list[str] = Field(default_factory=list)
    is_direct_work_gate: bool = False
    could_block_work: bool = False
    dependency_requirement_ids: list[str] = Field(default_factory=list)
    evidence_categories: list[str] = Field(default_factory=list)
    rationale: str
    uncertainty_reasons: list[str] = Field(default_factory=list)


class ConstraintProposal(StrictModel):
    constraint_id: str
    requirement_id: str
    source_ids: list[str] = Field(default_factory=list)
    group_id: str | None = None
    group_logic: Literal["AND", "OR", "NOT_APPLICABLE", "UNRESOLVED"] = "UNRESOLVED"
    constraint_kind: Literal["NUMERICAL_LIMIT", "SPATIAL_GEOFENCE", "DATE_OR_SEASON", "TIME_OF_DAY", "DURATION", "MONITORING_ONLY", "APPROVAL_PREREQUISITE", "EXTERNAL_CLEARANCE", "OTHER"]
    parameter_key: str | None = None
    operator: Literal["LT", "LTE", "EQ", "GTE", "GT", "NEQ", "INSIDE", "OUTSIDE", "BETWEEN", "PRESENT", "APPROVED", "NONE"] = "NONE"
    value_number: float | None = None
    value_number_max: float | None = None
    value_text: str | None = None
    unit: str | None = None
    averaging_period: str | None = None
    time_scope: str | None = None
    timezone: str | None = None
    spatial_scope: str | None = None
    geometry_source_id: str | None = None
    applicable_activity: str | None = None
    exception_texts: list[str] = Field(default_factory=list)
    source_explicit: bool = False
    gate_role: Literal["WORK_STOP_GATE", "MONITORING_ONLY", "MANUAL_PREREQUISITE", "ADVISORY", "UNRESOLVED"] = "UNRESOLVED"
    approval_status: Literal["PROPOSED", "APPROVED", "REJECTED"] = "PROPOSED"
    human_review: ReviewState = "UNREVIEWED"


class DataNeed(StrictModel):
    data_need_id: str
    requirement_ids: list[str] = Field(default_factory=list)
    constraint_ids: list[str] = Field(default_factory=list)
    parameter_key: str
    parameter_label: str
    domain: Literal["WEATHER", "WAVES", "CURRENTS", "SEA_LEVEL", "WATER_QUALITY", "GEOLOCATION", "CALENDAR", "LOCAL_MEASUREMENT", "EQUIPMENT_OR_MANUAL", "EXTERNAL_CLEARANCE", "OTHER"]
    evidence_kind: Literal["PUBLIC_FORECAST", "MODELLED_PROXY", "REMOTE_OBSERVATION", "DIRECT_LOCAL_MEASUREMENT", "STATIC_GIS", "CALENDAR", "MANUAL_CONFIRMATION", "UNKNOWN"] = "UNKNOWN"
    needed_unit: str | None = None
    needed_depth: str | None = None
    needed_time_resolution: str | None = None
    needed_spatial_resolution: str | None = None
    needed_forecast_horizon: str | None = None
    needed_location: str | None = None
    provider_hints: list[str] = Field(default_factory=list)
    provider_verified: bool = False
    suitability_status: Suitability = "NOT_CHECKED"
    relevance_reason: str


class DataFeasibility(StrictModel):
    data_need_id: str
    provider: str | None = None
    product_id: str | None = None
    variable_name: str | None = None
    status: Suitability = "NOT_CHECKED"
    geographic_coverage: str | None = None
    spatial_resolution: str | None = None
    time_resolution: str | None = None
    depth_coverage: str | None = None
    forecast_horizon: str | None = None
    units: str | None = None
    evidence_type: Literal["FORECAST", "MODEL", "REMOTE_OBSERVATION", "DIRECT_OBSERVATION", "STATIC_GIS", "CALENDAR", "MANUAL", "UNKNOWN"] = "UNKNOWN"
    checked_at: str | None = None
    fit_reason: str


class ReviewFlag(StrictModel):
    flag_id: str
    related_requirement_ids: list[str] = Field(default_factory=list)
    related_source_ids: list[str] = Field(default_factory=list)
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    category: Literal["QUOTE", "AUTHORITY", "DEFINITION", "COVERAGE", "THRESHOLD", "UNIT", "TEMPORAL", "SPATIAL", "DATA_SUITABILITY", "CROSS_REFERENCE", "OTHER"]
    message: str
    status: Literal["OPEN", "RESOLVED", "WAIVED"] = "OPEN"
    recommended_action: str


class WorkWindowStatus(StrictModel):
    status: Literal["NOT_EVALUATED", "BLOCKED", "EVALUATED"] = "NOT_EVALUATED"
    evaluation_ready: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    windows: list[dict] = Field(default_factory=list)


class Audit(StrictModel):
    analysis_version: str
    raw_response_paths: list[str] = Field(default_factory=list)
    source_manifest_path: str | None = None
    api_call_count: int = 0
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_cost_usd: float | None = None
    code_revision: str | None = None
    notes: list[str] = Field(default_factory=list)


class CanonicalAnalysis(StrictModel):
    schema_version: Literal["permitpulse.intelligence.v1"] = "permitpulse.intelligence.v1"
    analysis_id: str
    document: DocumentRecord
    coverage: Coverage
    stage_runs: list[StageRun]
    source_inventory: list[SourceRecord]
    definitions: list[Definition]
    requirements: list[Requirement]
    operational_assessments: list[OperationalAssessment]
    constraint_proposals: list[ConstraintProposal]
    data_needs: list[DataNeed]
    data_feasibility: list[DataFeasibility]
    review_flags: list[ReviewFlag]
    work_windows: WorkWindowStatus
    audit: Audit


class Stage1Requirement(Requirement):
    source_verification: Literal["PENDING"] = "PENDING"
    human_review: Literal["UNREVIEWED"] = "UNREVIEWED"


class Stage1Response(StrictModel):
    document_id: str
    batch_id: str
    page_start: int
    page_end: int
    sources: list[SourceRecord]
    definitions: list[Definition]
    requirements: list[Stage1Requirement]
    unresolved_source_ids: list[str]
    issues: list[str]


class Stage2Response(StrictModel):
    document_id: str
    batch_id: str
    operational_assessments: list[OperationalAssessment]
    unclassified_requirement_ids: list[str]
    issues: list[str]


class Stage3ConstraintProposal(ConstraintProposal):
    approval_status: Literal["PROPOSED"] = "PROPOSED"
    human_review: Literal["UNREVIEWED"] = "UNREVIEWED"


class Stage3DataNeed(DataNeed):
    provider_verified: Literal[False] = False
    suitability_status: Literal["NOT_CHECKED"] = "NOT_CHECKED"


class Stage3Response(StrictModel):
    document_id: str
    batch_id: str
    constraint_proposals: list[Stage3ConstraintProposal]
    data_needs: list[Stage3DataNeed]
    unmapped_requirement_ids: list[str]
    issues: list[str]
