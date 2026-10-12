"""Registry access and safe unit conversions; no API calls are made here."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from src.models.common import AutomationStatus, SourceType


class CapabilityRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    capabilities: dict[str, dict]


def load_registry(path: str | Path) -> CapabilityRegistry:
    with Path(path).open("r", encoding="utf-8") as handle:
        return CapabilityRegistry.model_validate(json.load(handle))


def derive_automation_status(
    *, variable: str | None, required_source: SourceType | None, has_deciding_adapter: bool
) -> AutomationStatus:
    """Classify capability without ever treating unsupported evidence as a PASS."""
    if required_source in {SourceType.LOCAL_SENSOR, SourceType.AIS_GNSS, SourceType.LAB_RESULT}:
        return AutomationStatus.EXTERNAL_DATA_REQUIRED
    if required_source in {SourceType.MANUAL_INPUT, SourceType.AUTHORITY_APPROVAL}:
        return AutomationStatus.MANUAL_INPUT_REQUIRED
    if variable is None:
        return AutomationStatus.NOT_EVALUABLE
    return AutomationStatus.AUTOMATIC if has_deciding_adapter else AutomationStatus.NOT_EVALUABLE


def spm_g_m3_to_mg_l(value: float) -> float:
    return value


def dissolved_oxygen_mmol_m3_to_mg_l(value: float) -> float:
    return value * 0.032


def metres_per_second_to_knots(value: float) -> float:
    return value * 1.943844
