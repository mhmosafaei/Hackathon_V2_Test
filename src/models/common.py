"""Controlled vocabularies and base validation shared across models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator


class ConditionType(StrEnum):
    INSTANT_THRESHOLD = "INSTANT_THRESHOLD"
    DURATION_THRESHOLD = "DURATION_THRESHOLD"
    STATE_TRANSITION = "STATE_TRANSITION"
    RANGE = "RANGE"
    ROLLING_LIMIT = "ROLLING_LIMIT"
    CALENDAR_RESTRICTION = "CALENDAR_RESTRICTION"
    TIME_WINDOW = "TIME_WINDOW"
    GEOFENCE = "GEOFENCE"
    EQUIPMENT_STATE = "EQUIPMENT_STATE"
    DOCUMENT_APPROVAL = "DOCUMENT_APPROVAL"
    REPORTING_DEADLINE = "REPORTING_DEADLINE"
    EVENT_TRIGGER = "EVENT_TRIGGER"
    OPERATING_METHOD = "OPERATING_METHOD"
    MONITORING_OBLIGATION = "MONITORING_OBLIGATION"
    WEATHER_DOWNTIME = "WEATHER_DOWNTIME"
    WORKABILITY_WINDOW = "WORKABILITY_WINDOW"
    WEATHER_RISK_ALLOCATION = "WEATHER_RISK_ALLOCATION"
    OTHER = "OTHER"


class SourceType(StrEnum):
    COPERNICUS = "COPERNICUS"
    OPEN_METEO_ECMWF = "OPEN_METEO_ECMWF"
    OPEN_METEO_ERA5 = "OPEN_METEO_ERA5"
    ERA5_CDS = "ERA5_CDS"
    LOCAL_SENSOR = "LOCAL_SENSOR"
    AIS_GNSS = "AIS_GNSS"
    CALENDAR = "CALENDAR"
    GIS = "GIS"
    LAB_RESULT = "LAB_RESULT"
    AUTHORITY_APPROVAL = "AUTHORITY_APPROVAL"
    MANUAL_INPUT = "MANUAL_INPUT"
    PROJECT_SYSTEM = "PROJECT_SYSTEM"
    DOCUMENT = "DOCUMENT"
    UNKNOWN = "UNKNOWN"


class SourceRole(StrEnum):
    PRIMARY_COMPLIANCE = "PRIMARY_COMPLIANCE"
    SUPPORTIVE = "SUPPORTIVE"
    PREDICTIVE = "PREDICTIVE"
    CONTROL = "CONTROL"
    REFERENCE = "REFERENCE"


class AutomationStatus(StrEnum):
    AUTOMATIC = "AUTOMATIC"
    EXTERNAL_DATA_REQUIRED = "EXTERNAL_DATA_REQUIRED"
    MANUAL_INPUT_REQUIRED = "MANUAL_INPUT_REQUIRED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class OperationalStatus(StrEnum):
    YES = "YES"
    NO = "NO"
    WARN = "WARN"
    STOP = "STOP"
    RESUME = "RESUME"
    UNKNOWN = "UNKNOWN"


class RuleOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DataType(StrEnum):
    OBSERVATION = "OBSERVATION"
    ANALYSIS = "ANALYSIS"
    FORECAST = "FORECAST"
    HISTORICAL = "HISTORICAL"


class QualityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    STALE = "STALE"
    MISSING = "MISSING"
    ERROR = "ERROR"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Representativeness(StrEnum):
    GOOD = "GOOD"
    MODERATE = "MODERATE"
    POOR = "POOR"
    UNKNOWN = "UNKNOWN"


class ReviewState(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EDITED_CONFIRMED = "EDITED_CONFIRMED"


class ActionRequired(StrEnum):
    NONE = "NONE"
    REPORT = "REPORT"
    NOTIFY = "NOTIFY"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    MANUAL_CONFIRMATION = "MANUAL_CONFIRMATION"
    PROVIDE_EXTERNAL_EVIDENCE = "PROVIDE_EXTERNAL_EVIDENCE"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UtcAwareModel(StrictModel):
    @field_validator("*", mode="after")
    @classmethod
    def reject_naive_datetimes(cls, value: object) -> object:
        if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("datetimes must be timezone-aware")
        return value
