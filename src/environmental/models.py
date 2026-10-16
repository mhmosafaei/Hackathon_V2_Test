"""Source-backed requirements and normalized, non-authorizing requests."""
from typing import Literal, Annotated
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .limits import ENVIRONMENTAL_MAX_FETCH_HOURS

Status = Literal['WITHIN_THRESHOLD', 'THRESHOLD_EXCEEDED', 'INSUFFICIENT_DATA',
                 'INFORMATIONAL', 'EXTERNAL_EVIDENCE_REQUIRED']


class EvaluationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    analysis_id: str
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    start_time: datetime | None = None
    end_time: datetime | None = None
    depth: float | None = Field(None, ge=0, le=10000)
    point_scope_confirmed: bool = False
    manual_fnu_thresholds: dict[int, Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def bounded(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Both coordinates are required')
        if self.start_time is not None or self.end_time is not None:
            if not self.start_time or not self.end_time:
                raise ValueError('Both UTC times are required')
            if self.start_time.utcoffset() is None or self.end_time.utcoffset() is None:
                raise ValueError('Times must have a UTC offset')
            hours = (self.end_time - self.start_time).total_seconds() / 3600
            if not 0 < hours <= ENVIRONMENTAL_MAX_FETCH_HOURS:
                raise ValueError(f'Select a positive period of at most {ENVIRONMENTAL_MAX_FETCH_HOURS} hours')
        return self


class EnvironmentalRequest(BaseModel):
    condition_id: str
    requirement_text: str
    canonical_variable: str
    operator: str | None = None
    threshold: float | None = None
    threshold_unit: str | None = None
    geographic_scope: str | None = None
    coordinates: tuple[float, float] | None = None
    start_time: str | None = None
    end_time: str | None = None
    depth: float | None = None
    requested_depth_mode: str | None = None
    depth_tolerance_m: float | None = None
    evidence_mode: str
    provider: str
    dataset_id: str | None = None
    dataset_variable: str | None = None
    requested_unit: str | None = None
    comparison_unit: str | None = None
    required_accumulation_interval_seconds: int | None = None
    temporal_semantics: str | None = None
    provider_query_start: str | None = None
    provider_query_end: str | None = None
    timestep_seconds: int | None = None
