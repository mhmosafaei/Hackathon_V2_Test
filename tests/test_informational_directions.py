"""Verified existing direction paths; local xarray fixtures and no network."""
from copy import deepcopy
from datetime import timedelta
import math
import numpy as np
import pytest
import xarray as xr
from src.environmental import copernicus
from src.environmental.catalog import canonical
from src.environmental.router import route, MARINE
from src.environmental.errors import ProviderError
from src.environmental.models import EvaluationInput
from src.environmental.service import evaluate
from tests.test_simple_environment import requirement, analysis
from tests.test_copernicus_current_oxygen_patch import vector_dataset, mock_client, request
from tests.test_decision_engine import fixture, run, T


def waves():
    ds=xr.Dataset({'VHM0':(('time','latitude','longitude'),np.array([[[1.2]],[[1.3]]])),
                   'VTM02':(('time','latitude','longitude'),np.array([[[4.]],[[4.1]]])),
                   'VMDR':(('time','latitude','longitude'),np.array([[[241.]],[[242.]]]))},
        coords={'time':np.array(['2026-10-14T00:00','2026-10-14T01:00'],dtype='datetime64[m]'),
                'latitude':[54.],'longitude':[-6.]})
    ds.VHM0.attrs['units']='m'; ds.VTM02.attrs['units']='s'
    ds.VMDR.attrs.update(units='degree',long_name='Mean wave direction from',standard_name='sea_surface_wave_from_direction')
    return ds


@pytest.mark.parametrize('alias,expected',[
    ('wave_direction_degrees','mean_wave_direction'),
    ('current_direction_towards_true_north','surface_current_direction'),
    ('current_direction_degrees_towards_true_north','surface_current_direction')])
def test_actual_alias_reaches_existing_implemented_path(alias,expected):
    assert canonical(alias)==expected
    assert route(alias)['preferred_provider']=='COPERNICUS_MARINE'
    assert route(alias)['implemented']


def test_wave_direction_native_value_and_provider_convention_unchanged(monkeypatch):
    ds=waves(); calls=mock_client(monkeypatch,ds)
    out=copernicus.worker(request('mean_wave_direction',requested_unit='degrees'))
    assert MARINE['mean_wave_direction']==('waves','VMDR')
    assert calls[0]['variables']==['VHM0','VTM02','VMDR']
    assert out['points'][0]['raw_value']==241 and out['points'][0]['unit']=='degree'
    assert out['points'][0]['data_time']=='2026-10-14T00:00:00+00:00'
    assert out['direction_metadata']==ds.VMDR.attrs
    assert out['direction_convention']=='PROVIDER_DEFINED_NOT_NORMALIZED'
    assert out['latitude']==54 and out['longitude']==-6 and out['distance_km']==0


def test_missing_provider_wave_variable_fails_without_fabrication(monkeypatch):
    mock_client(monkeypatch,waves().rename({'VMDR':'OTHER'}))
    with pytest.raises(ProviderError) as exc: copernicus.worker(request('mean_wave_direction'))
    assert exc.value.category=='VARIABLE_LOOKUP'


@pytest.mark.parametrize('u,v,expected',[(0,1,0),(1,0,90),(0,-1,180),(-1,0,270),(-.8,.6,306.86989764584405)])
def test_towards_formula_native_components_and_speed_unchanged(u,v,expected):
    source={'provider':'COPERNICUS_MARINE','latitude':54,'longitude':-6,'depth':None,
        'points':[{'data_time':T.isoformat(),'component_values':{'uo':u,'vo':v}}]}
    original=deepcopy(source)
    direction=copernicus.project_current_or_wave_evidence(source,'surface_current_direction','current_direction')
    point=direction['points'][0]
    assert point['raw_value']==pytest.approx(expected) and 0<=point['raw_value']<360
    assert point['data_time']==T.isoformat() and point['component_values']=={'uo':u,'vo':v}
    assert point['derived_from']==['uo','vo']
    assert direction['direction_convention']=='TOWARDS_CLOCKWISE_FROM_NORTH'
    assert point['derivation']['method']=='ATAN2_U_V_TOWARDS_CLOCKWISE_FROM_NORTH'
    speed=copernicus.project_current_or_wave_evidence(source,'surface_current_speed','current_speed')
    assert speed['points'][0]['raw_value']==pytest.approx(math.hypot(u,v))
    assert source==original


@pytest.mark.parametrize('mismatch',['time','point','depth'])
def test_mismatched_uv_contexts_never_produce_direction(monkeypatch,mismatch):
    ds=vector_dataset()
    if mismatch=='time':
        ds['uo'].values[1:]=np.nan;ds['vo'].values[0]=np.nan
    elif mismatch=='point':
        ds['uo'].values[:,:,1:]=np.nan;ds['vo'].values[:,:,:1]=np.nan
    else:
        ds=ds.expand_dims(depth=[0.,1.]).transpose('time','depth','latitude','longitude').copy(deep=True)
        ds['uo'].values[:,1]=np.nan;ds['vo'].values[:,0]=np.nan
    mock_client(monkeypatch,ds)
    with pytest.raises(ProviderError):
        copernicus.worker(request('surface_current_direction',depth=0 if mismatch=='depth' else None))


def test_separate_or_missing_component_records_are_not_joined():
    source={'points':[{'data_time':T.isoformat(),'component_values':{'uo':1}},
        {'data_time':(T+timedelta(minutes=15)).isoformat(),'component_values':{'vo':1}}]}
    result=copernicus.project_current_or_wave_evidence(source,'surface_current_direction','current_direction')
    assert all(point['raw_value'] is None for point in result['points'])


@pytest.mark.parametrize('direction_alias',['current_direction_degrees_towards_true_north','current_direction_towards_true_north'])
def test_aliases_are_informational_and_current_direction_reuses_one_uv_bundle(tmp_path,monkeypatch,direction_alias):
    calls=[]
    class Client:
        def open_dataset(self,**kwargs):
            calls.append(kwargs)
            return (waves() if kwargs['variables']==['VHM0','VTM02','VMDR'] else vector_dataset()).copy(deep=True)
    monkeypatch.setattr(copernicus,'_load_worker_dependencies',lambda:(np,Client()))
    raw=[requirement(alias,condition_id=str(i),threshold=None,operator=None,unit='degrees',depth_requirement=None,
        source_spans=[{'page':1,'quotation':'Direction in degrees is informational only.'}]) for i,alias in enumerate([
            'wave_direction_degrees',direction_alias])]
    raw.append(requirement('eastward_current',condition_id='u',unit='m/s',threshold=.6,operator='>',depth_requirement=None,
        source_spans=[{'page':1,'quotation':'Absolute eastward current greater than 0.6 m/s.'}]))
    before=deepcopy(raw)
    inputs=EvaluationInput(analysis_id='isolated-test',latitude=54,longitude=-6,start_time=T,end_time=T+timedelta(hours=1))
    out=evaluate(analysis(*raw),inputs,tmp_path,transports={'COPERNICUS_MARINE':copernicus.worker})
    assert len(calls)==2 and sum(call['variables']==['uo','vo'] for call in calls)==1
    for row in out['requirements'][:2]:
        assert row['status']=='INFORMATIONAL' and row['threshold'] is None
        assert row['evidence']['points'][0]['normalized_unit']=='degrees'
    assert raw==before


@pytest.mark.parametrize('alias',['wave_direction_degrees','current_direction_degrees_towards_true_north'])
def test_missing_informational_direction_does_not_gate_f09(alias):
    reviews,env=fixture(); expected=run(reviews,env)['current_assessment']['status']
    info=deepcopy(reviews['requirements'][0])
    info.update(target_id='informational-direction',decision_relevant_default=False)
    info['original'].update(canonical_variable=alias,threshold=None,operator=None)
    info['effective']=deepcopy(info['original'])
    reviews['requirements'].append(info)
    out=run(reviews,env)['current_assessment']
    assert out['status']==expected=='WORK'
    assert not next(r for r in out['rule_results'] if r['requirement_id']=='informational-direction')['gating']
