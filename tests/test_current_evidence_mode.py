"""Focused regression tests for current/future marine evidence mode handling."""

from datetime import datetime, timezone

from src.environmental.models import EnvironmentalRequest
from src.environmental.service import compatible_points


def _requirement():
    return {
        "source_verified": True,
        "explicit_requirement": True,
        "operator": ">",
        "threshold": 1.0,
        "unit": "m/s",
        "source_spans": [{"page": 1, "quotation": "Current speed greater than 1.0 m/s shall be flagged."}],
    }


def _request(mode: str, start: str, end: str):
    return EnvironmentalRequest(
        condition_id="29",
        requirement_text="Surface current speed shall be reviewed.",
        canonical_variable="surface_current_speed",
        operator=">",
        threshold=1.0,
        threshold_unit="m/s",
        coordinates=(54.023, -5.9275),
        start_time=start,
        end_time=end,
        evidence_mode=mode,
        provider="COPERNICUS_MARINE",
        dataset_id="cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT15M-i",
        dataset_variable="current_speed",
        requested_unit="m/s",
        provider_query_start=start,
        provider_query_end=end,
        timestep_seconds=900,
    )


def _evidence(request, retrieved_at="2026-10-12T20:00:00+00:00"):
    return {
        "provider": request.provider,
        "dataset_id": request.dataset_id,
        "canonical_variable": request.canonical_variable,
        "data_type": "MODEL_FORECAST",
        "retrieved_at": retrieved_at,
        "quality_status": "COASTAL_REVIEW_REQUIRED",
        "requested_coordinates": list(request.coordinates),
        "distance_km": 0.9,
        "points": [
            {"data_time": "2026-10-12T22:00:00+00:00", "raw_value": 0.3, "unit": "m/s"},
            {"data_time": "2026-10-12T23:00:00+00:00", "raw_value": 0.4, "unit": "m/s"},
        ],
    }


def test_future_reanalysis_label_uses_forecast_evidence_without_historical_blocker():
    req = _request("reanalysis", "2026-10-12T22:00:00+00:00", "2026-10-12T23:00:00+00:00")
    result = compatible_points(_requirement(), req, _evidence(req), now=datetime(2026, 10, 12, 20, tzinfo=timezone.utc))
    assert result["temporal_coverage_status"] == "COVERED"
    assert result["status"] == "WITHIN_THRESHOLD"
    assert result["threshold_evaluation"] == "NOT_TRIGGERED"
    assert "Historical evidence required" not in result["validation_notes"]


def test_historical_interval_keeps_historical_safeguard():
    req = _request("reanalysis", "2026-10-12T18:00:00+00:00", "2026-10-12T19:00:00+00:00")
    result = compatible_points(_requirement(), req, _evidence(req), now=datetime(2026, 10, 12, 20, tzinfo=timezone.utc))
    assert result["status"] == "INSUFFICIENT_DATA"
    assert "Historical evidence required" in result["validation_notes"]
    assert result["threshold_evaluation"] == "NOT_DETERMINED"


def test_timezone_aware_evaluation_clock_is_required():
    req = _request("forecast", "2026-10-12T22:00:00+00:00", "2026-10-12T23:00:00+00:00")
    try:
        compatible_points(_requirement(), req, _evidence(req), now=datetime(2026, 10, 12, 20))
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive evaluation clock must be rejected")
