"""Provider regressions are synthetic/offline. Historical live caches stay untouched."""
from copy import deepcopy
from datetime import timedelta
import json
import httpx
import pytest
from tests.test_simple_environment import requirement, analysis, inputs
from src.environmental.models import EnvironmentalRequest
from src.environmental.service import evaluate, compatible_points
from src.environmental.router import route
from src.environmental.errors import ProviderError, diagnostic
from src.environmental.fixture import mock_evidence


def request(variable='significant_wave_height', **kwargs):
    return EnvironmentalRequest(condition_id='1',requirement_text='synthetic',canonical_variable=variable,
        coordinates=(54,-6),start_time='2026-10-12T16:05:00+00:00',end_time='2026-10-14T16:05:00+00:00',
        evidence_mode='forecast',provider='COPERNICUS_MARINE',**kwargs)


@pytest.mark.parametrize('variable,count,minutes,first,last',[
    ('significant_wave_height',48,60,'2026-10-12T17:00:00+00:00','2026-10-14T16:00:00+00:00'),
    ('surface_current_speed',192,15,'2026-10-12T16:15:00+00:00','2026-10-14T16:00:00+00:00')])
def test_real_run_period_shape_remains_incomplete(variable,count,minutes,first,last):
    from datetime import datetime
    req=request(variable);evidence=mock_evidence(req)
    start=datetime.fromisoformat(first)
    evidence['points']=[dict(data_time=(start+timedelta(minutes=i*minutes)).isoformat(),raw_value=.1,unit='m') for i in range(count)]
    result=compatible_points(requirement(threshold=None),req,evidence)
    assert result['status']=='INSUFFICIENT_DATA' and len(result['points'])==count
    assert result['coverage']['actual_start']==first and result['coverage']['actual_end']==last
    assert 'Requested period not fully covered' in ';'.join(result['validation_notes'])


def test_safe_diagnostics_persist_without_secrets(tmp_path):
    def fail(req): raise RuntimeError('authentication failed password=SECRET https://user:SECRET@host/private/path')
    result=evaluate(analysis(requirement()),inputs(),tmp_path,transports={'COPERNICUS_MARINE':fail})
    row=result['requirements'][0];safe=json.dumps(row)
    assert 'SECRET' not in safe and 'private/path' not in safe
    assert row['provider_diagnostic']['provider_error_category']=='AUTHENTICATION'
    assert row['provider_diagnostic']['dataset_id']=='cmems_mod_nws_wav_anfc_1.5km_PT1H-i'
    assert row['retrieval_status']=='FAILED' and next((tmp_path/'errors').glob('*.json')).exists()


def test_missing_transport_is_not_unexplained_keyerror(tmp_path):
    row=evaluate(analysis(requirement('wind_speed_10m')),inputs(),tmp_path,transports={})['requirements'][0]
    assert row['provider_diagnostic']['provider_error_category']=='TRANSPORT_UNAVAILABLE'


def test_turbidity_ntu_rejected_before_provider_request(monkeypatch):
    import copernicusmarine
    from src.environmental.copernicus import worker
    monkeypatch.setattr(copernicusmarine,'open_dataset',lambda **k:pytest.fail('No FNU/NTU substitution request permitted'))
    with pytest.raises(ProviderError,match='FNU, not required NTU'):
        worker(request('turbidity',requested_unit='NTU'))


def test_oxygen_requires_explicit_depth_before_request(monkeypatch):
    import copernicusmarine
    from src.environmental.copernicus import worker
    monkeypatch.setattr(copernicusmarine,'open_dataset',lambda **k:pytest.fail('No implicit depth'))
    with pytest.raises(ProviderError,match='explicit compatible depth'):
        worker(request('dissolved_oxygen',requested_unit='mg/L'))


@pytest.mark.parametrize('variable', ['wind_speed_10m','wind_gust_10m_forecast'])
def test_ecmwf_scalar_and_gust_fields(variable):
    from src.environmental.ecmwf import retrieve
    name=route(variable)['canonical_variable'];field='wind_gusts_10m' if name=='wind_gust' else 'wind_speed_10m'
    req=request(name);req.provider='ECMWF_FORECAST'
    calls=[]
    def handler(r):
        calls.append(r);assert r.url.params['hourly']==field
        return httpx.Response(200,json={'latitude':54,'longitude':-6,'hourly_units':{field:'m/s'},
            'hourly':{'time':['2026-10-12T17:00'],field:[12.3]}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:result=retrieve(req,client=client)
    assert len(calls)==1 and result['points'][0]['raw_value']==12.3
    assert result['points'][0]['unit']=='m/s' and result['forecast_initialization'] is None


def test_ecmwf_missing_variable_field_has_precise_safe_reason():
    from src.environmental.ecmwf import retrieve
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'hourly':{'time':[]}}))) as client:
        with pytest.raises(ProviderError,match='missing hourly time or requested variable: wind_speed_10m'):
            retrieve(request('wind_speed_10m'),client=client)


def test_provenance_does_not_fetch_or_disappear(tmp_path):
    row=evaluate(analysis(requirement('environmental_evidence_provenance',threshold=None)),inputs(),tmp_path,
        transports={'COPERNICUS_MARINE':lambda r:pytest.fail('Not a physical variable')})['requirements'][0]
    assert row['status']=='INFORMATIONAL' and row['retrieval_status']=='NOT_APPLICABLE'


def test_unverified_sst_remains_blocked(tmp_path):
    row=evaluate(analysis(requirement('sea_surface_temperature',source_verified=False,threshold=None)),inputs(),tmp_path,
        transports={'COPERNICUS_MARINE':lambda r:pytest.fail('Unverified quotation must stay gated')})['requirements'][0]
    assert row['status']=='INSUFFICIENT_DATA' and 'Source verification required' in row['notes_for_evaluation']


def test_partial_marine_override_keeps_weather_transport(tmp_path, monkeypatch):
    from src.permit.simple_api import create_app
    from fastapi.testclient import TestClient
    import src.permit.simple_api as module
    seen=[]
    def fake_evaluate(a,i,p,*,transports,reuse_downloaded=False):seen.append(transports);return {'requirements':[]}
    monkeypatch.setattr(module,'evaluate',fake_evaluate)
    app=create_app(tmp_path,environmental_transports={'COPERNICUS_MARINE':lambda r:None})
    app.state.analyses['isolated-test']=analysis(requirement('wind_speed_10m'))
    with TestClient(app) as client:
        boot=client.get('/api/session').json()['boot_id']
        r=client.post('/api/environmental',json=inputs().model_dump(mode='json'),headers={'x-session-id':boot})
    assert r.status_code==200 and 'ECMWF_FORECAST' in seen[0]


def test_current_worker_keeps_vector_components_and_magnitude(monkeypatch):
    import numpy as np
    import xarray as xr
    import copernicusmarine
    from src.environmental.copernicus import worker
    ds=xr.Dataset({'uo':(('time','latitude','longitude'),np.array([[[.3]]])),
                   'vo':(('time','latitude','longitude'),np.array([[[.4]]]))},
        coords={'time':np.array(['2026-10-12T17:00'],dtype='datetime64[m]'),'latitude':[54.],'longitude':[-6.]})
    ds['uo'].attrs['units']='m/s';ds['vo'].attrs['units']='m/s'
    calls=[]
    def opened(**kwargs):calls.append(kwargs);return ds
    monkeypatch.setattr(copernicusmarine,'open_dataset',opened)
    result=worker(request('surface_current_speed'))
    assert calls[0]['variables']==['uo','vo'] and len(calls)==1
    assert result['points'][0]['raw_value']==pytest.approx(.5)
    assert result['points'][0]['component_values']=={'uo':.3,'vo':.4}
    assert result['quality_status']=='COASTAL_REVIEW_REQUIRED'
