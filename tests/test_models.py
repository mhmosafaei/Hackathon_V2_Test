from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models.environmental import EnvironmentalObservation
from src.models.common import DataType, QualityStatus, SourceType


def test_environmental_observation_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        EnvironmentalObservation(
            variable="wind_speed", value=3, unit="m/s", timestamp=datetime(2026, 10, 8),
            provider="fixture", source_type=SourceType.OPEN_METEO_ECMWF,
            data_type=DataType.FORECAST, quality_status=QualityStatus.AVAILABLE,
            provenance_label="fixture",
        )


def test_environmental_observation_accepts_aware_timestamp() -> None:
    result = EnvironmentalObservation(
        variable="wind_speed", value=3, unit="m/s", timestamp=datetime.now(timezone.utc),
        provider="fixture", source_type=SourceType.OPEN_METEO_ECMWF,
        data_type=DataType.FORECAST, quality_status=QualityStatus.AVAILABLE,
        provenance_label="fixture",
    )
    assert result.value == 3
