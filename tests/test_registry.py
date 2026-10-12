from pathlib import Path

import pytest

from src.mapping.capability_registry import (
    derive_automation_status, dissolved_oxygen_mmol_m3_to_mg_l, load_registry,
)
from src.models.common import AutomationStatus, SourceType


def test_registry_loads() -> None:
    registry = load_registry(Path("config/environmental_data_sources.json"))
    assert "wind_speed" in registry.capabilities


def test_local_sensor_requirement_is_external_data_required() -> None:
    assert derive_automation_status(
        variable="dissolved_oxygen", required_source=SourceType.LOCAL_SENSOR,
        has_deciding_adapter=True,
    ) is AutomationStatus.EXTERNAL_DATA_REQUIRED


def test_do_conversion() -> None:
    assert dissolved_oxygen_mmol_m3_to_mg_l(100) == pytest.approx(3.2)
