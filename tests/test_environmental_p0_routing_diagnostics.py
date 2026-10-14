"""Offline regressions for the narrow P0 routing/diagnostic patch."""
import pytest

from src.environmental.catalog import canonical
from src.environmental.errors import ProviderError
from src.environmental.router import route
from src.environmental.service import evaluate
from tests.test_simple_environment import analysis, inputs, requirement


@pytest.mark.parametrize("variable", [
    "significant_wave_height", "mean_wave_period", "mean_wave_direction",
])
def test_marine_waves_win_over_reanalysis(variable):
    routed = route(variable, "reanalysis")
    assert routed["preferred_provider"] == "COPERNICUS_MARINE"
    assert routed["implemented"] is True


@pytest.mark.parametrize("raw, expected", [
    ("eastward_current_component_u", "eastward_current"),
    ("northward_current_component_v", "northward_current"),
    ("current_direction_towards", "surface_current_direction"),
])
def test_persisted_component_aliases_reach_marine_router(raw, expected):
    assert canonical(raw) == expected
    routed = route(raw, "reanalysis")
    assert routed["canonical_variable"] == expected
    assert routed["preferred_provider"] == "COPERNICUS_MARINE"
    assert routed["implemented"] is True


def test_atmospheric_reanalysis_remains_era5():
    routed = route("wind_speed_10m", "reanalysis")
    assert routed["preferred_provider"] == "ERA5"
    assert routed["implemented"] is True


def test_direction_derivation_is_towards_clockwise_from_north():
    from src.environmental.service import project_current_or_wave_evidence
    evidence = {"points": [{"component_values": {"uo": 1.0, "vo": 0.0}}]}
    result = project_current_or_wave_evidence(evidence, "surface_current_direction", "current_direction")
    assert result["points"][0]["raw_value"] == pytest.approx(90.0)


def test_wave_direction_is_provider_defined():
    routed = route("mean_wave_direction", "reanalysis")
    assert routed["preferred_provider"] == "COPERNICUS_MARINE"
    assert "provider-defined" in routed["notes"]


def test_turbidity_fnu_maps_to_tur_without_conversion():
    from src.environmental.router import MARINE
    assert MARINE["turbidity"] == ("turbidity", "TUR")
    with pytest.raises(ValueError):
        from src.environmental.units import convert
        convert(1, "FNU", "NTU")


def test_provider_diagnostic_survives_service_result(tmp_path):
    row = requirement("turbidity", unit="FNU", source_spans=[{"page": 1, "quotation": "turbidity"}])
    def failed(_request):
        raise ProviderError("DATASET_OPEN", "Copernicus dataset open failed; no usable evidence returned.")
    result = evaluate(analysis(row), inputs(), tmp_path, transports={"COPERNICUS_MARINE": failed})
    diagnostic = result["requirements"][0]["provider_diagnostic"]
    assert diagnostic["provider_error_category"] == "DATASET_OPEN"
    assert diagnostic["provider_error_message"] == "Copernicus dataset open failed; no usable evidence returned."


def test_missing_copernicus_worker_dependency_has_safe_category(monkeypatch):
    import builtins
    from src.environmental import copernicus
    original_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == 'copernicusmarine':
            raise ModuleNotFoundError("No module named 'copernicusmarine'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', blocked)
    with pytest.raises(ProviderError) as raised:
        copernicus._load_worker_dependencies()
    assert raised.value.category == 'WORKER_DEPENDENCY'
    assert raised.value.safe_message == (
        'Copernicus worker dependency is unavailable; retrieval was not attempted.'
    )


def test_model_extra_outside_source_audit_is_not_routed(tmp_path):
    extra = requirement('environmental_fetch_point_operational_period', condition_id='23',
        evidence_type='manual', source_spans=[{'page': 1, 'quotation': 'Select a point and period.'}])
    valid = requirement('visibility', condition_id='35', evidence_type='forecast',
        source_spans=[{'page': 1, 'quotation': 'Visibility shall be reviewed.'}])
    document = analysis(extra, valid)
    document['environmental_extraction'] = {
        'candidate_conditions': ['35'], 'missing_conditions': [], 'complete': True,
    }
    mapped = evaluate(document, inputs(), tmp_path, transports={})['requirements']
    assert [row['condition_id'] for row in mapped] == ['35']
    assert any(row['condition_id'] == '23' for row in document['environmental_requirements'])
