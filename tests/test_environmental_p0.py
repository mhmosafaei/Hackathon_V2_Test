"""Focused offline regressions for the environmental P0 capability contract."""
from datetime import datetime, timezone, timedelta
import httpx
import pytest
import sys

from src.environmental.capabilities import capability_matrix
from src.environmental.ecmwf import retrieve
from src.environmental.router import route
from src.environmental.models import EnvironmentalRequest
from src.environmental.service import evaluate
from tests.test_simple_environment import analysis, inputs, requirement


def test_p0_matrix_has_all_fourteen_without_fetching():
    matrix = capability_matrix()
    assert len(matrix) == 15
    assert {item['implementation_status'] for item in matrix} == {'SUPPORTED', 'PARTIAL', 'UNAVAILABLE'}
    assert {item['canonical_variable'] for item in matrix} >= {
        'significant_wave_height', 'mean_wave_period', 'mean_wave_direction',
        'eastward_current', 'northward_current', 'surface_current_speed',
        'current_speed', 'current_direction', 'wind_speed_10m', 'wind_direction_10m',
        'wind_gust', 'precipitation', 'turbidity', 'visibility', 'air_temperature', 'sea_surface_height'}


@pytest.mark.parametrize('alias', ['dissolved_oxygen', 'dissolved oxygen', 'oxygen'])
def test_oxygen_aliases_route_to_one_canonical_variable(alias):
    routed = route(alias)
    assert routed['canonical_variable'] == 'dissolved_oxygen'
    assert routed['preferred_provider'] == 'COPERNICUS_MARINE'
    assert routed['implemented']


@pytest.mark.parametrize('variable,source_variable', [
    ('mean_wave_period', 'VTM02'), ('mean_wave_direction', 'VMDR')])
def test_wave_period_and_direction_route_to_verified_source_variables(variable, source_variable):
    routed = route(variable)
    assert routed['preferred_provider'] == 'COPERNICUS_MARINE'
    assert routed['implemented']
    from src.environmental.router import MARINE
    assert MARINE[variable][1] == source_variable


def test_visibility_uses_explicit_provider_field_and_metres():
    request = EnvironmentalRequest(condition_id='v', requirement_text='visibility',
        canonical_variable='visibility', provider='ECMWF_FORECAST', coordinates=(54, -6),
        evidence_mode='forecast', start_time='2026-10-12T12:00:00+00:00',
        end_time='2026-10-12T13:00:00+00:00')
    def handler(r):
        assert r.url.params['hourly'] == 'visibility'
        return httpx.Response(200, json={'latitude':54, 'longitude':-6,
            'hourly_units':{'visibility':'m'},
            'hourly':{'time':['2026-10-12T12:00','2026-10-12T13:00'], 'visibility':[1200, 1100]}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = retrieve(request, client=client)
    assert [point['unit'] for point in result['points']] == ['m', 'm']


def test_visibility_missing_units_is_explicit_failure():
    request = EnvironmentalRequest(condition_id='v', requirement_text='visibility',
        canonical_variable='visibility', provider='ECMWF_FORECAST', coordinates=(54, -6),
        evidence_mode='forecast', start_time='2026-10-12T12:00:00+00:00',
        end_time='2026-10-12T13:00:00+00:00')
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
        'latitude':54, 'longitude':-6, 'hourly_units':{},
        'hourly':{'time':['2026-10-12T12:00'], 'visibility':[1200]}}))) as client:
        with pytest.raises(Exception, match='source units'):
            retrieve(request, client=client)


def test_precipitation_preserves_hourly_accumulation_semantics():
    request = EnvironmentalRequest(condition_id='p', requirement_text='rain',
        canonical_variable='precipitation', provider='ECMWF_FORECAST', coordinates=(54, -6),
        evidence_mode='forecast', start_time='2026-10-12T12:00:00+00:00',
        end_time='2026-10-12T13:00:00+00:00')
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
        'latitude':54, 'longitude':-6, 'hourly_units':{'precipitation':'mm'},
        'hourly':{'time':['2026-10-12T12:00'], 'precipitation':[5.0]}}))) as client:
        result = retrieve(request, client=client)
    assert result['points'][0]['unit'] == 'mm'
    assert result['points'][0]['accumulation_interval_seconds'] == 3600
    assert result['points'][0]['temporal_semantics'] == 'ACCUMULATED_OVER_PRECEDING_HOUR'
    assert 'accumulated' in result['notes']


def test_shared_current_bundle_projects_u_and_v_without_extra_provider_calls(tmp_path):
    calls = []
    rows = []
    for name in ('eastward_current', 'northward_current', 'surface_current_speed', 'surface_current_direction'):
        rows.append(requirement(name, requirement_text=f'{name} source value', operator=None,
            threshold=None, unit='m/s' if name not in {'surface_current_direction'} else 'degrees',
            depth_requirement=None, source_spans=[{'page':1, 'quotation':f'{name} source value'}]))
    def provider(request):
        calls.append(request)
        start = request.start_time
        return {'canonical_variable':request.canonical_variable, 'provider':'COPERNICUS_MARINE',
            'dataset_id':'SYNTHETIC-CURRENT', 'dataset_name':'synthetic current bundle',
            'dataset_variable':'uo,vo', 'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'data_type':'MODEL_FORECAST', 'latitude':54, 'longitude':-6,
            'requested_coordinates':[54,-6], 'distance_km':0, 'depth':None,
            'quality_status':'SUITABLE', 'spatial_resolution':'synthetic',
            'points':[{'data_time':start, 'raw_value':0.3, 'unit':'m/s',
                       'component_values':{'uo':0.3, 'vo':0.4}, 'derived_from':['uo','vo']}],
            'notes':'synthetic'}
    result = evaluate(analysis(*rows), inputs(), tmp_path, transports={'COPERNICUS_MARINE':provider})
    assert len(calls) == 1
    assert [r['evidence']['points'][0]['raw_value'] for r in result['requirements']] == [0.3, 0.4, pytest.approx(0.5), pytest.approx(36.869897)]
    assert result['executable_rules'] == 0


def test_explicit_condition_scope_dispatches_only_condition_40(tmp_path):
    calls = []
    fnu = requirement('turbidity', condition_id='40', operator='>', threshold=25,
        unit='FNU', evidence_type='reanalysis', depth_requirement=None,
        source_spans=[{'page': 5, 'quotation': 'Turbidity greater than 25 FNU.'}])
    ntu = requirement('turbidity', condition_id='41', operator='>', threshold=25,
        unit='NTU', evidence_type='manual', depth_requirement=None,
        source_spans=[{'page': 5, 'quotation': 'Turbidity greater than 25 NTU.'}])
    other = requirement('significant_wave_height', condition_id='24', depth_requirement=None)

    def provider(req):
        calls.append(req)
        from tests.test_environmental_sampling import query_evidence
        evidence = query_evidence(req)
        evidence['canonical_variable'] = 'turbidity'
        evidence['dataset_variable'] = 'TUR'
        evidence['quality_status'] = 'COASTAL_REVIEW_REQUIRED'
        for point in evidence['points']:
            point.update(raw_value=12.0, unit='FNU')
        return evidence

    result = evaluate(analysis(fnu, ntu, other), inputs(), tmp_path,
        transports={'COPERNICUS_MARINE': provider}, condition_ids={'40'})
    assert [row['condition_id'] for row in result['requirements']] == ['40']
    assert len(calls) == 1 and calls[0].canonical_variable == 'turbidity'
    assert calls[0].requested_unit == 'FNU'
    assert result['requirements'][0]['comparison_status'] == 'DIRECTLY_COMPARABLE'
    assert result['executable_rules'] == 0


def test_scoped_copernicus_evaluation_does_not_import_weather_connectors(tmp_path):
    """Explicit transports avoid optional ECMWF/ERA5 imports in scoped mode."""
    fnu = requirement('turbidity', condition_id='40', operator='>', threshold=25,
        unit='FNU', evidence_type='reanalysis', depth_requirement=None,
        source_spans=[{'page': 5, 'quotation': 'Turbidity greater than 25 FNU.'}])
    weather_modules = {name: sys.modules.pop(name, None) for name in (
        'src.environmental.ecmwf', 'src.environmental.era5')}
    try:
        def provider(req):
            from tests.test_environmental_sampling import query_evidence
            evidence = query_evidence(req)
            evidence['canonical_variable'] = 'turbidity'
            evidence['dataset_variable'] = 'TUR'
            for point in evidence['points']:
                point['unit'] = 'FNU'
            return evidence
        evaluate(analysis(fnu), inputs(), tmp_path,
            transports={'COPERNICUS_MARINE': provider}, condition_ids={'40'})
        assert 'src.environmental.ecmwf' not in sys.modules
        assert 'src.environmental.era5' not in sys.modules
    finally:
        for name, module in weather_modules.items():
            if module is not None:
                sys.modules[name] = module


def test_empty_explicit_condition_scope_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='scope cannot be empty'):
        evaluate(analysis(), inputs(), tmp_path, transports={}, condition_ids=set())
