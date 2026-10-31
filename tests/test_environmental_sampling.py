"""All retrievals injected: no live OpenAI, Copernicus or weather calls."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import httpx
import pytest
from tests.test_simple_environment import requirement, analysis, inputs, approve_synthetic_point
from src.environmental.service import evaluate, compatible_points
from src.environmental.fixture import mock_evidence
from src.environmental.sampling import timestep_bounds, weather_spatial_limit, source_depth
from src.environmental.catalog import canonical
from src.environmental.router import route
from src.environmental.models import EnvironmentalRequest, EvaluationInput

FIXTURE = json.loads((Path(__file__).parent/'fixtures/synthetic_environment_requirements.json').read_text())


def fixture_requirement(index):
    c = FIXTURE['conditions'][index]
    return requirement(c['variable'],condition_id=c['id'],requirement_text=c['text'],
        operator=c['operator'],threshold=c['threshold'],unit=c['unit'],depth_requirement=c['depth'],
        source_spans=[{'page':1,'quotation':c['text']}],evidence_type='unspecified')


@pytest.mark.parametrize('seconds,start,end',[
    (3600,'16:00','17:00'),(900,'16:30','16:45'),(86400,'00:00','00:00')])
def test_outward_utc_bounds(seconds,start,end):
    a,b=timestep_bounds('2026-10-12T16:41:00Z','2026-10-13T16:41:00Z',seconds)
    assert a[11:16]==start and b[11:16]==end
    assert datetime.fromisoformat(a)<=datetime.fromisoformat('2026-10-12T16:41:00+00:00')
    assert datetime.fromisoformat(b)>=datetime.fromisoformat('2026-10-13T16:41:00+00:00')


def test_exact_boundaries_not_expanded():
    assert timestep_bounds('2026-01-01T16:00:00Z','2026-01-01T17:00:00Z',3600)==('2026-01-01T16:00:00+00:00','2026-01-01T17:00:00+00:00')


def query_evidence(req):
    # Mock provider returns actual query endpoints, not invented local interpolation.
    clone=req.model_copy(update={'start_time':req.provider_query_start,'end_time':req.provider_query_end})
    return mock_evidence(clone)


@pytest.mark.parametrize('truncated',[False,True])
def test_actual_bracketing_not_tolerance(tmp_path,truncated):
    now=datetime.now(timezone.utc).replace(minute=41,second=0,microsecond=0)
    i=EvaluationInput(analysis_id='isolated-test',latitude=54,longitude=-6,start_time=now,end_time=now+timedelta(hours=24))
    calls=[]
    def provider(req):
        calls.append(req);e=query_evidence(req)
        if truncated:e['points']=e['points'][1:-1]
        return e
    row=evaluate(analysis(requirement()),i,tmp_path,transports={'COPERNICUS_MARINE':provider})['requirements'][0]
    assert row['status']==('INSUFFICIENT_DATA' if truncated else 'WITHIN_THRESHOLD')
    assert calls[0].provider_query_start[11:16]==now.strftime('%H:00')
    coverage=row['evidence']['coverage']
    assert coverage['requested_start']!=coverage['provider_query_start']
    assert coverage['actual_start']==row['evidence']['points'][0]['data_time']
    assert coverage['temporal_resolution_seconds']==3600


def test_synthetic_fnu_and_real_ntu_never_convert(tmp_path):
    calls=[]
    def provider(req):
        calls.append(req);e=query_evidence(req)
        e['data_type']='SATELLITE_OBSERVATION'
        return e
    fnu=fixture_requirement(0)
    row=evaluate(analysis(fnu),inputs(),tmp_path/'fnu',transports={'COPERNICUS_MARINE':provider})['requirements'][0]
    assert row['evidence']['points'][0]['normalized_unit']=='FNU'
    assert row['evidence']['points'][0]['comparison'] is False
    assert row['evidence']['data_type']=='SATELLITE_OBSERVATION'
    ntu={**fnu,'unit':'NTU','source_spans':[{'page':1,'quotation':'Turbidity greater than 25 NTU.'}]}
    row=evaluate(analysis(ntu),inputs(),tmp_path/'ntu',transports={'COPERNICUS_MARINE':provider})['requirements'][0]
    assert row['status']=='INSUFFICIENT_DATA' and 'FNU' in row['notes_for_evaluation'] and len(calls)==1


def test_oxygen_source_depth_routes_and_no_silent_surface(tmp_path):
    calls=[]
    def provider(req):calls.append(req);return query_evidence(req)
    r=fixture_requirement(1)
    row=evaluate(analysis(r),inputs(),tmp_path,transports={'COPERNICUS_MARINE':provider})['requirements'][0]
    assert calls[0].depth==1 and row['request']['depth']==1
    assert 'not equivalent to required in-situ monitoring' in row['requirement_text']
    assert row['routing']['preferred_provider']=='COPERNICUS_MARINE'
    r['depth_requirement']=None
    row=evaluate(analysis(r),inputs(),tmp_path/'missing',transports={'COPERNICUS_MARINE':provider})['requirements'][0]
    assert 'Explicit depth required' in row['notes_for_evaluation'] and len(calls)==1


def test_real_in_situ_obligation_stays_external_with_caveat(tmp_path):
    r=fixture_requirement(1)
    r['source_spans'][0]['quotation']+=' Required in-situ monitoring shall continue.'
    row=evaluate(analysis(r),inputs(),tmp_path,transports={})['requirements'][0]
    assert row['status']=='EXTERNAL_EVIDENCE_REQUIRED'


def test_unquoted_depth_and_conflicting_override_block_fetch(tmp_path):
    r=fixture_requirement(1)
    for field,value in [('depth_requirement','2 m below sea surface')]:
        row=evaluate(analysis({**r,field:value}),inputs(),tmp_path,transports={})['requirements'][0]
        assert 'depth interpretation requires review' in row['notes_for_evaluation']
    row=evaluate(analysis(r),inputs(depth=2),tmp_path,transports={})['requirements'][0]
    assert 'conflicts with source depth' in row['notes_for_evaluation']


@pytest.mark.parametrize('variable,quote', [
    ('wind_speed_10m', '10 m wind speed shall be assessed.'),
    ('wind_gust', 'Wind gust at 10 m above sea surface shall be assessed.'),
    ('wind_direction_10m', '10 m wind direction shall be recorded.'),
])
def test_source_backed_atmospheric_height_above_sea_surface_is_not_marine_depth(variable, quote):
    row = {'depth_requirement': '10 m above sea surface',
           'routing': {'preferred_provider': 'ECMWF_FORECAST', 'canonical_variable': variable},
           'source_spans': [{'quotation': quote}]}
    assert source_depth(row) == (None, None)


def test_ambiguous_atmospheric_height_remains_blocked():
    row = {'depth_requirement': '10 m somewhere above water',
           'routing': {'preferred_provider': 'ECMWF_FORECAST', 'canonical_variable': 'wind_speed_10m'},
           'source_spans': [{'quotation': '10 m wind speed shall be assessed.'}]}
    depth, error = source_depth(row)
    assert depth is None
    assert 'depth interpretation requires review' in error


def test_dissolved_oxygen_surface_alias_routes_to_configured_marine_oxygen():
    assert canonical('dissolved_oxygen_surface') == 'dissolved_oxygen'
    routed = route('dissolved_oxygen_surface')
    assert routed['canonical_variable'] == 'dissolved_oxygen'
    assert routed['preferred_provider'] == 'COPERNICUS_MARINE'
    assert routed['implemented'] is True


def test_modelled_oxygen_conversion_provenance_keeps_both_units(tmp_path):
    r=fixture_requirement(1)
    def provider(req):
        e=query_evidence(req)
        for p in e['points']:p.update(raw_value=200.,unit='mmol m-3')
        return e
    row=evaluate(analysis(r),inputs(),tmp_path,transports={'COPERNICUS_MARINE':provider})['requirements'][0]
    p=row['evidence']['points'][0]
    assert p['raw_value']==200 and p['unit']=='mmol m-3'
    assert p['normalized_value']==pytest.approx(6.3996) and p['normalized_unit']=='mg/L'


def test_oxygen_exact_depth_passed_to_toolbox(monkeypatch):
    import numpy as np
    import xarray as xr
    import copernicusmarine
    from src.environmental.copernicus import worker
    calls=[]
    ds=xr.Dataset({'o2':(('time','depth','latitude','longitude'),np.array([[[[200.]]]]))},
        coords={'time':np.array(['2026-10-12T00:00'],dtype='datetime64[m]'),'depth':[1.],'latitude':[54.],'longitude':[-6.]})
    ds['o2'].attrs['units']='mmol m-3'
    ds['depth'].attrs.update(units='m', positive='down')
    def opened(**kw):calls.append(kw);return ds
    monkeypatch.setattr(copernicusmarine,'open_dataset',opened)
    req=EnvironmentalRequest(condition_id='test',requirement_text='test',canonical_variable='dissolved_oxygen',
        coordinates=(54,-6),depth=1,provider='COPERNICUS_MARINE',evidence_mode='forecast',
        start_time='2026-10-12T16:41:00Z',end_time='2026-10-13T16:41:00Z',
        provider_query_start='2026-10-12T00:00:00Z',provider_query_end='2026-10-14T00:00:00Z')
    e=worker(req)
    assert calls[0]['minimum_depth']==.5 and calls[0]['maximum_depth']==1.5
    assert calls[0]['coordinates_selection_method']=='outside'
    assert calls[0]['start_datetime']==req.provider_query_start
    assert e['points'][0]['unit']=='mmol m-3' and 'supportive' in e['notes']
    from src.environmental.units import convert
    assert convert(200,'mmol m-3','mg/L',variable='dissolved_oxygen')==pytest.approx(6.3996)


def test_explicit_depth_survives_single_extraction_persistence_and_api(tmp_path):
    import pymupdf
    from fastapi.testclient import TestClient
    from src.permit.simple_api import create_app
    from src.permit.simple_fixture import mock_request
    r=fixture_requirement(1);r['condition_id']='1'
    for key in ('source_verified','review_state','executable'):r.pop(key)
    with pymupdf.open() as pdf:
        pdf.new_page().insert_textbox(pymupdf.Rect(50,50,550,750),
            'Synthetic work point: WGS84 latitude 54.1 longitude -6.1.\n1. '+r['requirement_text'])
        data=pdf.tobytes()
    extraction_calls=[];provider_calls=[]
    def transport(packet):
        extraction_calls.append(1)
        payload=mock_request(packet);payload['conditions']=payload['conditions'][:1]
        payload['environmental_requirements']=[r]
        return payload
    def provider(req):provider_calls.append(req);return query_evidence(req)
    with TestClient(create_app(tmp_path,transport=transport,environmental_transports={'COPERNICUS_MARINE':provider})) as client:
        boot=client.get('/api/session').json()['boot_id']
        headers={'x-session-id':boot,'x-filename':'UNOFFICIAL_SOFTWARE_TEST.pdf'}
        response=client.post('/api/analyze',content=data,headers=headers)
        assert response.status_code==200
        doc=response.json()
        assert doc['environmental_requirements'][0]['depth_requirement']=='1 metre below sea surface'
        assert doc['environmental_requirements'][0]['source_verified']
        stored=json.loads(next(tmp_path.rglob('analysis.json')).read_text())
        assert stored['environmental_requirements'][0]['depth_requirement']=='1 metre below sea surface'
        options=inputs().model_dump(mode='json');options['analysis_id']=doc['analysis_id']
        approve_synthetic_point(client, doc, headers)
        options['latitude'], options['longitude'] = 54.1, -6.1
        evidence=client.post('/api/environmental',json=options,headers=headers)
        assert evidence.status_code==200 and provider_calls[0].depth==1
        assert len(extraction_calls)==1 and evidence.json()['executable_rules']==0


@pytest.mark.parametrize('fallback',[False,True])
@pytest.mark.parametrize('variable',['wind_speed_10m','wind_gust'])
def test_hres_and_explicit_coarse_fallback(variable,fallback):
    from src.environmental.ecmwf import retrieve
    calls=[];field='wind_gusts_10m' if variable=='wind_gust' else variable
    def handler(req):
        calls.append(req)
        if fallback and len(calls)==1:return httpx.Response(400,json={'reason':'model unavailable'})
        return httpx.Response(200,json={'latitude':54.05,'longitude':-6,'hourly_units':{field:'m/s'},
            'hourly':{'time':['2026-10-12T16:00','2026-10-12T17:00'],field:[1,2]}})
    req=EnvironmentalRequest(condition_id='1',requirement_text='test',canonical_variable=variable,provider='ECMWF_FORECAST',
        coordinates=(54,-6),evidence_mode='forecast',start_time='2026-10-12T16:00:00+00:00',end_time='2026-10-12T17:00:00+00:00')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:e=retrieve(req,client=client)
    assert calls[0].url.params['models']=='ecmwf_ifs'
    assert all(c.url.params['cell_selection']=='nearest' for c in calls)
    assert e['cell_selection']=='nearest' and 'Approximate' in e['spatial_check_basis']
    assert e['dataset_id']==('ecmwf_ifs025' if fallback else 'ecmwf_ifs')
    assert len(calls)==(2 if fallback else 1)
    assert e['requested_coordinates']==[54,-6] and e['latitude']==54.05
    assert e['distance_km']>5  # Within nominal HRES half diagonal, not a universal 5 km test.
    assert e['quality_status']=='SUITABLE'
    assert bool(e['fallback_reason'])==fallback


def test_hres_distance_rule_conservative_and_grid_specific():
    assert weather_spatial_limit('ecmwf_ifs',54)==pytest.approx(9/2**.5)
    assert 5<weather_spatial_limit('ecmwf_ifs',54)<7
    assert weather_spatial_limit('ecmwf_ifs025',54)<20
    assert weather_spatial_limit('unknown',54) is None


def test_distant_coarse_weather_stays_insufficient(tmp_path):
    def provider(req):
        e=query_evidence(req)
        e.update(dataset_id='ecmwf_ifs025',distance_km=25.5,quality_status='SUITABLE')
        return e
    row=evaluate(analysis(requirement('wind_speed_10m',depth_requirement=None)),inputs(),tmp_path,
        transports={'ECMWF_FORECAST':provider})['requirements'][0]
    assert row['status']=='INSUFFICIENT_DATA'
    assert 'model/grid representativeness' in row['notes_for_evaluation']


def test_sst_fetch_once_two_checks_one_group_and_cache(tmp_path):
    calls=[]
    def provider(req):
        calls.append(req);e=query_evidence(req)
        for p in e['points']:p.update(raw_value=14.3,unit='C')
        return e
    doc=analysis(fixture_requirement(6),fixture_requirement(7))
    original=json.dumps(doc,sort_keys=True)
    result=evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':provider})
    assert len(calls)==1 and len(result['requirements'])==2 and len(result['evidence_groups'])==1
    checks=result['evidence_groups'][0]['checks']
    assert len(checks)==2 and [c['evidence']['points'][0]['comparison'] for c in checks]==[False,False]
    assert result['executable_rules']==0 and json.dumps(doc,sort_keys=True)==original
    again=evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':lambda r:pytest.fail('Reuse persisted evidence')})
    assert len(again['evidence_groups'])==1


def test_identical_failed_retrieval_not_retried(tmp_path):
    calls=[]
    def fail(req):calls.append(req);raise RuntimeError('offline failure')
    result=evaluate(analysis(fixture_requirement(6),fixture_requirement(7)),inputs(),tmp_path,transports={'COPERNICUS_MARINE':fail})
    assert len(calls)==1 and len(result['requirements'])==2
    assert all(r['status']=='INSUFFICIENT_DATA' for r in result['requirements'])
