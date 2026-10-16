"""Offline transports only. No credential or network access in these tests."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from types import SimpleNamespace as NS
import httpx
import pytest
from fastapi.testclient import TestClient
from src.environmental.catalog import CATALOG, FAMILIES
from src.environmental.router import route
from src.environmental.units import convert
from src.environmental.models import EvaluationInput, EnvironmentalRequest
from src.environmental.service import evaluate, map_requirements, compatible_points
from src.environmental.fixture import mock_evidence
from src.permit.simple_api import create_app
from src.permit.simple_analysis import analyze, response_schema
from src.permit.simple_fixture import mock_request
from tests.test_simple_permit import pdf_bytes


def requirement(variable='significant_wave_height', **updates):
    return {'condition_id': '1', 'source_page': 1, 'requirement_text': 'Wave height shall not exceed 2.5 m.',
        'variable': variable, 'canonical_variable': variable, 'operator': '<=', 'threshold': 2.5, 'unit': 'm',
        'temporal_requirement': None, 'depth_requirement': 'surface', 'geographic_scope': None,
        'evidence_type': 'forecast', 'explicit_requirement': True, 'notes': None,
        'source_spans': [{'page': 1, 'quotation': 'Wave height shall not exceed 2.5 m.'}],
        'source_verified': True, 'review_state': 'UNREVIEWED', 'executable': False, **updates}


def analysis(*requirements, geofences=None):
    return {'analysis_id': 'isolated-test', 'environmental_requirements': list(requirements), 'geofences': geofences or []}


def inputs(**updates):
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return EvaluationInput(analysis_id='isolated-test', latitude=54, longitude=-6,
        start_time=start, end_time=start+timedelta(hours=2), **updates)


@pytest.mark.parametrize('variable,mode,provider', [
    ('wind_speed_10m','forecast','ECMWF_FORECAST'), ('significant_wave_height','forecast','COPERNICUS_MARINE'),
    ('surface_current_speed','forecast','COPERNICUS_MARINE'), ('wind_speed_10m','historical','ERA5'),
    ('ais_status','unspecified','EXTERNAL'), ('dissolved_oxygen','local_sensor','EXTERNAL'),
    ('turbidity','laboratory','EXTERNAL'), ('unknown_magic','forecast','UNAVAILABLE'),
    ('weather_window','forecast','DERIVED'), ('pm10','forecast','CAMS'),
    ('wave_direction','forecast','COPERNICUS_MARINE'), ('dissolved oxygen','forecast','COPERNICUS_MARINE'),
    ('oxygen','forecast','COPERNICUS_MARINE'), ('eastward current','forecast','COPERNICUS_MARINE'),
    ('northward current','forecast','COPERNICUS_MARINE'), ('visibility','forecast','ECMWF_FORECAST')])
def test_routes(variable, mode, provider):
    assert route(variable, mode)['preferred_provider'] == provider


def test_catalogue_complete_and_unsupported_not_claimed():
    assert len(CATALOG) == sum(len(v) for v in FAMILIES.values())
    assert all(name in CATALOG for name in ['sea_ice_drift_direction','metocean_return_period','under_keel_clearance','ammonium'])
    assert not route('salinity')['implemented']
    assert route('visibility')['implemented']
    assert route('significant_wave_height','historical')['preferred_provider'] == 'COPERNICUS_MARINE'
    assert route('significant_wave_height','historical')['implemented']
    assert route('weather_window')['potential_source_variables']


@pytest.mark.parametrize('value,source,target,expected', [
    (1,'m/s','knots',1.94384449), (273.15,'K','°C',0), (101325,'Pa','hPa',1013.25),
    (1,'m','cm',100), (2,'hours','minutes',120), (1,'g/m3','mg/L',1)])
def test_units(value, source, target, expected):
    assert convert(value,source,target) == pytest.approx(expected)


@pytest.mark.parametrize('source,target', [('NTU','mg/L'),('FNU','NTU'),('psu','mg/L')])
def test_incompatible_units(source,target):
    with pytest.raises(ValueError): convert(1,source,target)


def test_oxygen_conversion_is_specific():
    assert convert(100,'mmol/m3','mg/L',variable='dissolved_oxygen') == pytest.approx(3.1998)
    with pytest.raises(ValueError): convert(100,'mmol/m3','mg/L',variable='nitrate')


@pytest.mark.parametrize('missing', ['location','time'])
def test_missing_inputs_do_not_fetch(tmp_path, missing):
    options = inputs().model_dump()
    if missing == 'location': options.update(latitude=None,longitude=None)
    else: options.update(start_time=None,end_time=None)
    result = evaluate(analysis(requirement()), EvaluationInput(**options), tmp_path,
        transports={'COPERNICUS_MARINE': lambda r: pytest.fail('No request permitted')})
    assert result['requirements'][0]['status'] == 'INSUFFICIENT_DATA'


def test_route_not_reduced_to_midpoint_and_geofence_preserved(tmp_path):
    g = {'type':'route','coordinates_or_boundary':'source-defined route', 'source_pages':[2]}
    doc = analysis(requirement(),geofences=[g]); original = deepcopy(doc)
    result = evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':lambda r:pytest.fail('Route requires sampling')})
    assert 'Spatial sampling strategy required' in result['requirements'][0]['notes_for_evaluation']
    assert doc == original


def test_multiple_evidence_cache_and_threshold(tmp_path):
    doc = analysis(requirement(),requirement('ais_status',evidence_type='ais'))
    calls=[]
    def transport(r): calls.append(r); return mock_evidence(r)
    result=evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':transport})
    assert [r['status'] for r in result['requirements']] == ['WITHIN_THRESHOLD','EXTERNAL_EVIDENCE_REQUIRED']
    assert result['executable_rules']==0 and len(calls)==1
    again=evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':lambda r:pytest.fail('Use cache')})
    assert again['requirements'][0]['cache_state']=='CACHED'
    other = deepcopy(doc); other['analysis_id']='another-document'
    evaluate(other,inputs(),tmp_path,transports={'COPERNICUS_MARINE':transport})
    assert len(calls)==2


@pytest.mark.parametrize('case', ['threshold','informational','units','stale','gap','model','depth','numeric','null','statistic','variable','source_unit'])
def test_evidence_compatibility(tmp_path,case):
    r=requirement(); doc=analysis(r)
    if case=='depth':
        r.update(variable='dissolved_oxygen',canonical_variable='dissolved_oxygen',depth_requirement='1 metre below sea surface',unit='mg/L',
                 source_spans=[{'page':1,'quotation':'Dissolved oxygen at 1 metre below sea surface shall not exceed 2.5 mg/L.'}])
    def transport(request):
        e=mock_evidence(request)
        if case=='threshold':
            for p in e['points']: p['raw_value']=3
        if case=='units':
            for p in e['points']: p['unit']='NTU'
        if case=='stale': e['retrieved_at']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        if case=='gap': e['points']=e['points'][:1]
        if case=='model': e['data_type']='SATELLITE_OBSERVATION'
        if case=='depth': e['depth']=15
        if case=='null': e['points'][0]['raw_value']=None
        if case=='variable': e['canonical_variable']='wind_speed_10m'
        return e
    if case=='informational': r['threshold']=None; r['operator']=None
    if case=='numeric': r['threshold']=99
    if case=='statistic': r['temporal_requirement']='95th percentile'
    if case=='source_unit': r['unit']='cm'
    result=evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':transport})['requirements'][0]
    assert result['status']==('THRESHOLD_EXCEEDED' if case=='threshold' else 'INFORMATIONAL' if case=='informational' else 'INSUFFICIENT_DATA')


def test_oxygen_failure_does_not_destroy_successful_evidence(tmp_path):
    def transport(r):
        if r.canonical_variable=='dissolved_oxygen': raise RuntimeError('secret must not leak')
        return mock_evidence(r)
    result=evaluate(analysis(requirement(),requirement('dissolved_oxygen')),inputs(),tmp_path,
        transports={'COPERNICUS_MARINE':transport})
    assert result['requirements'][0]['status']=='WITHIN_THRESHOLD'
    assert result['requirements'][1]['status']=='INSUFFICIENT_DATA'
    assert 'secret' not in json.dumps(result)
    assert len(list(tmp_path.glob('*.json')))==1


def test_schema_single_request_preserves_environment(tmp_path):
    calls=[]
    def transport(packet):
        calls.append(1); result=mock_request(packet)
        r=requirement(); [r.pop(k) for k in ['source_verified','review_state','executable']]
        r['source_spans']=[{'page':1,'quotation':packet['pages'][0].text.strip()}]
        result['environmental_requirements']=[r]
        return result
    result=analyze(pdf_bytes(),'test.pdf',tmp_path,transport=transport)
    assert calls==[1] and result['environmental_requirements'][0]['source_verified']
    # The synthetic PDF contains no environmental source candidates.  The
    # authoritative candidate audit therefore excludes this model-returned
    # environmental record from deterministic mapping while preserving it in
    # the raw extraction for audit.
    assert result['environmental_extraction']['candidate_conditions'] == []
    assert result['environmental_mapping'] == []
    schema=response_schema()['properties']['environmental_requirements']['items']
    assert schema['additionalProperties'] is False
    assert 'null' in schema['properties']['threshold']['type']


def test_api_fetch_is_explicit_isolated_and_restart_empty(tmp_path):
    calls=[]; providers=[]
    def transport(packet):
        calls.append(1); result=mock_request(packet)
        r=requirement(); [r.pop(k) for k in ['source_verified','review_state','executable']]
        r['source_spans']=[{'page':1,'quotation':packet['pages'][0].text.strip()}]
        result['environmental_requirements']=[r]; return result
    def provider(request): providers.append(1); return mock_evidence(request)
    client=TestClient(create_app(tmp_path,transport=transport,environmental_transports={'COPERNICUS_MARINE':provider}))
    boot=client.get('/api/session').json()['boot_id']; headers={'x-session-id':boot,'x-filename':'test.pdf'}
    doc=client.post('/api/analyze',content=pdf_bytes(),headers=headers).json()
    assert calls==[1] and providers==[]
    options=inputs().model_dump(mode='json'); options['analysis_id']=doc['analysis_id']
    result=client.post('/api/environmental',json=options,headers=headers)
    assert result.status_code==200 and providers==[1] and calls==[1]
    assert result.json()['executable_rules']==0
    restored_session=client.get('/api/session')
    assert restored_session.status_code==200
    assert restored_session.json()['environmental_result']['analysis_id']==doc['analysis_id']
    assert restored_session.json()['environmental_result']['evidence_groups'] == result.json()['evidence_groups']
    assert providers==[1]
    assert client.post('/api/environmental',json={**options,'analysis_id':'wrong-doc'},headers=headers).status_code==404
    new=TestClient(create_app(tmp_path,transport=transport))
    assert new.post('/api/environmental',json=options,headers=headers).status_code==409
    assert providers==[1]


def test_ecmwf_uses_selected_variable_and_era5_is_not_forecast():
    from src.environmental.ecmwf import retrieve
    request=EnvironmentalRequest(condition_id='1',requirement_text='source',canonical_variable='wind_speed_10m',
        coordinates=(54,-6),start_time='2026-01-01T00:00:00+00:00',end_time='2026-01-01T01:00:00+00:00',
        evidence_mode='historical',provider='ERA5')
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(200,json={'latitude':54,'longitude':-6,'hourly_units':{'wind_speed_10m':'m/s'},
            'hourly':{'time':['2026-01-01T00:00','2026-01-01T01:00'],'wind_speed_10m':[1,None]}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=retrieve(request,client=client,historical=True)
    assert len(calls)==1 and calls[0].url.params['hourly']=='wind_speed_10m'
    assert calls[0].url.params['models']=='era5'
    assert result['data_type']=='REANALYSIS' and result['points'][1]['raw_value'] is None


def test_empty_requirements_and_bad_times_make_no_provider_calls(tmp_path):
    assert evaluate(analysis(), inputs(),tmp_path,transports={})['requirements']==[]
    options=inputs().model_dump(); options['end_time']=options['start_time']+timedelta(days=3)
    with pytest.raises(ValueError): EvaluationInput(**options)


def test_local_measurements_cannot_be_misrouted_by_ai_evidence_label(tmp_path):
    r = requirement('dissolved_oxygen')
    r['source_spans'] = [{'page':1,'quotation':'In-situ dissolved oxygen monitoring required at local sensors.'}]
    assert map_requirements(analysis(r))[0]['routing']['preferred_provider']=='EXTERNAL'
    result=evaluate(analysis(r),inputs(),tmp_path,transports={})
    assert result['requirements'][0]['status']=='EXTERNAL_EVIDENCE_REQUIRED'


@pytest.mark.parametrize('quote', [
    'Modelled oxygen is supportive only and is not equivalent to required in-situ monitoring.',
    'Modelled oxygen is supportive only and is not\nequivalent to required in-situ monitoring.',
    'Modelled oxygen is supportive only and is not  \t equivalent to required in-situ monitoring.',
])
def test_negated_in_situ_wording_does_not_override_provider_mapping(quote):
    r = requirement('dissolved_oxygen', evidence_type='unspecified',
                    source_spans=[{'page': 5, 'quotation': quote}])
    mapped = map_requirements(analysis(r))[0]
    assert mapped['routing']['preferred_provider'] == 'COPERNICUS_MARINE'
    assert mapped['routing']['implemented'] is True
    assert mapped['source_spans'][0]['quotation'] == quote


def test_affirmative_in_situ_requirement_remains_external():
    r = requirement('dissolved_oxygen', evidence_type='unspecified',
                    source_spans=[{'page': 5, 'quotation': 'In-situ dissolved oxygen monitoring is required.'}])
    mapped = map_requirements(analysis(r))[0]
    assert mapped['routing']['preferred_provider'] == 'EXTERNAL'
    assert mapped['status'] == 'EXTERNAL_EVIDENCE_REQUIRED'


def test_dissolved_oxygen_suffix_alias_remains_marine_implemented():
    r = requirement('dissolved_oxygen_1m_below_surface', evidence_type='unspecified',
                    depth_requirement='1 metre below sea surface')
    mapped = map_requirements(analysis(r))[0]
    assert mapped['canonical_variable'] == 'dissolved_oxygen'
    assert mapped['routing']['preferred_provider'] == 'COPERNICUS_MARINE'
    assert mapped['routing']['implemented'] is True
    assert mapped['depth_requirement'] == '1 metre below sea surface'


def test_threshold_boundary_and_unknown_do_not_become_zero(tmp_path):
    def transport(request):
        e=mock_evidence(request)
        for p in e['points']: p['raw_value']=2.5
        return e
    assert evaluate(analysis(requirement()),inputs(),tmp_path/'a',transports={'COPERNICUS_MARINE':transport})['requirements'][0]['status']=='WITHIN_THRESHOLD'
    r=requirement(operator='<',source_spans=[{'page':1,'quotation':'STOP condition: wave height >= 2.5 m.'}])
    assert evaluate(analysis(r),inputs(),tmp_path/'b',transports={'COPERNICUS_MARINE':transport})['requirements'][0]['status']=='THRESHOLD_EXCEEDED'
    assert map_requirements(analysis(requirement(threshold=None)))[0]['threshold'] is None


def test_source_calendar_requirement_is_not_overridden_by_user_period(tmp_path):
    r=requirement(temporal_requirement='after an incident in January 2027')
    result=evaluate(analysis(r),inputs(),tmp_path,transports={'COPERNICUS_MARINE':lambda r:pytest.fail('Calendar scope unresolved')})
    assert result['requirements'][0]['status']=='INSUFFICIENT_DATA'
    assert 'calendar/event' in result['requirements'][0]['notes_for_evaluation']


def test_official_marine_worker_mocked_xarray(monkeypatch):
    import numpy as np
    import xarray as xr
    import src.environmental.copernicus as module
    import copernicusmarine
    monkeypatch.setenv('COPERNICUSMARINE_SERVICE_USERNAME','offline-user')
    monkeypatch.setenv('COPERNICUSMARINE_SERVICE_PASSWORD','offline-password')
    ds=xr.Dataset({'VHM0':(('time','latitude','longitude'),np.array([[[np.nan,1.2]],[[np.nan,1.3]]]))},
        coords={'time':np.array(['2026-01-01T00:00','2026-01-01T01:00'],dtype='datetime64[m]'),
                'latitude':[54.0],'longitude':[-6.0,-5.99]})
    ds['VHM0'].attrs['units']='m'; calls=[]
    def open_dataset(**kwargs): calls.append(kwargs); return ds
    monkeypatch.setattr(copernicusmarine,'open_dataset',open_dataset)
    request=EnvironmentalRequest(condition_id='1',requirement_text='source',canonical_variable='significant_wave_height',
        coordinates=(54,-6),start_time='2026-01-01T00:00:00+00:00',end_time='2026-01-01T01:00:00+00:00',
        evidence_mode='forecast',provider='COPERNICUS_MARINE')
    result=module.worker(request)
    assert len(calls)==1 and calls[0]['variables']==['VHM0']
    assert result['longitude']==-5.99 and result['points'][0]['raw_value']==1.2
    assert result['quality_status']=='COASTAL_REVIEW_REQUIRED'
    assert 'offline-password' not in json.dumps(result)


def test_provider_request_count_is_bounded(tmp_path):
    # Distinct source-backed depths produce distinct evidence, unlike repeated IDs.
    doc=analysis(*[requirement('dissolved_oxygen',condition_id=str(i),unit='mg/L',depth_requirement=f'{i} m below sea surface',
        source_spans=[{'page':1,'quotation':f'Dissolved oxygen shall not exceed 2.5 mg/L at {i} m below sea surface.'}]) for i in range(15)])
    calls=[]
    def transport(request): calls.append(1); return mock_evidence(request)
    result=evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':transport})
    assert len(calls)==12 and len(result['requirements'])==15
    assert all(r['status']=='INSUFFICIENT_DATA' for r in result['requirements'][12:])
