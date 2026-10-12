"""Normalised environmental evidence and its provenance."""

from datetime import datetime

from pydantic import Field

from .common import DataType, QualityStatus, Representativeness, SourceRole, SourceType, UtcAwareModel


class SourceBinding(UtcAwareModel):
    source_type: SourceType
    role: SourceRole
    capability_id: str | None = None
    deciding: bool = False


class EnvironmentalObservation(UtcAwareModel):
    variable: str
    value: float
    unit: str
    timestamp: datetime
    provider: str
    source_type: SourceType
    data_type: DataType
    quality_status: QualityStatus
    provenance_label: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    dataset_id: str | None = None
    product_id: str | None = None
    retrieval_time: datetime | None = None
    selected_grid_latitude: float | None = Field(default=None, ge=-90, le=90)
    selected_grid_longitude: float | None = Field(default=None, ge=-180, le=180)
    grid_distance_km: float | None = Field(default=None, ge=0)
    spatial_representativeness: Representativeness = Representativeness.UNKNOWN
