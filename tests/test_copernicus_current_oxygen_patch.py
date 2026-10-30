"""Offline xarray/transport mocks only; no Copernicus or OpenAI requests."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import subprocess

import numpy as np
import pytest
import xarray as xr

from src.environmental import copernicus
from src.environmental.errors import ProviderError
from src.environmental.models import EnvironmentalRequest
from src.environmental.sampling import source_depth, depth_metadata, DEPTH_TOLERANCE_M
from src.environmental.service import evaluate, compatible_points
from tests.test_simple_environment import requirement, analysis, inputs


def request(variable='surface_current_speed', **kwargs):
    return EnvironmentalRequest(condition_id='source',requirement_text='source',canonical_variable=variable,
        coordinates=(54,-6),start_time='2026-10-14T00:00:00Z',end_time='2026-10-14T01:00:00Z',
        evidence_mode='forecast',provider='COPERNICUS_MARINE',timestep_seconds=900,**kwargs)


def vector_dataset():
    times=np.arange(np.datetime64('2026-10-14T00:00'),np.datetime64('2026-10-14T01:01'),np.timedelta64(15,'m'))
    ds=xr.Dataset({'uo':(('time','latitude','longitude'),np.full((5,3,3),-.8)),
                   'vo':(('time','latitude','longitude'),np.full((5,3,3),.6))},
        coords={'time':times,'latitude':[53.99,54,54.01],'longitude':[-6.01,-6,-5.99]})
    for name in ('uo','vo'):ds[name].attrs['units']='m s-1'
    return ds


def wave_dataset():
    times=np.array(['2026-10-14T00:00','2026-10-14T01:00'],dtype='datetime64[m]')
    ds=xr.Dataset({'VHM0':(('time','latitude','longitude'),np.full((2,1,1),1.2)),
                   'VTM02':(('time','latitude','longitude'),np.full((2,1,1),4.5)),
                   'VMDR':(('time','latitude','longitude'),np.full((2,1,1),180.))},
        coords={'time':times,'latitude':[54.],'longitude':[-6.]})
    ds.VHM0.attrs['units']='m'; ds.VTM02.attrs['units']='s'; ds.VMDR.attrs['units']='degrees'
    return ds


def oxygen_dataset(depths=(1.,), unit='mmol m-3'):
    ds=xr.Dataset({'o2':(('time','depth','latitude','longitude'),np.full((1,len(depths),1,1),200.))},
        coords={'time':np.array(['2026-10-14'],dtype='datetime64[D]'),'depth':list(depths),'latitude':[54.],'longitude':[-6.]})
    ds.o2.attrs['units']=unit;ds.depth.attrs.update(units='m',positive='down')
    return ds


def mock_client(monkeypatch, ds):
    calls=[]
    class Client:
        def open_dataset(self, **kwargs):
            calls.append(kwargs)
            return ds.copy(deep=True)
    monkeypatch.setattr(copernicus,'_load_worker_dependencies',lambda:(np,Client()))
    return calls


def test_vector_load_is_batched_point_series_and_native_grid(monkeypatch):
    ds=vector_dataset();calls=mock_client(monkeypatch,ds);loads=[]
    original=xr.Dataset.load
    def loaded(self,*args,**kwargs):
        loads.append(dict(self.sizes));return original(self,*args,**kwargs)
    monkeypatch.setattr(xr.Dataset,'load',loaded)
    evidence=copernicus.worker(request())
    assert len(calls)==1 and calls[0]['variables']==['uo','vo']
    assert calls[0]['dataset_id']=='cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT15M-i'
    assert calls[0]['minimum_latitude']==pytest.approx(53.95)
    assert calls[0]['maximum_latitude']==pytest.approx(54.05)
    assert calls[0]['start_datetime']=='2026-10-14T00:00:00Z'
    assert loads==[{'latitude':3,'longitude':3},{'time':5}]
    assert len(evidence['points'])==5 and evidence['points'][0]['raw_value']==1
    assert evidence['points'][0]['component_values']=={'uo':-.8,'vo':.6}
    assert evidence['points'][0]['component_units']=={'uo':'m s-1','vo':'m s-1'}
    assert evidence['latitude']==54 and evidence['longitude']==-6 and evidence['distance_km']==0


def test_worker_propagates_configured_credentials_without_persisting_them(monkeypatch):
    monkeypatch.setenv('COPERNICUSMARINE_SERVICE_USERNAME', 'offline-user')
    monkeypatch.setenv('COPERNICUSMARINE_SERVICE_PASSWORD', 'offline-password')
    calls = mock_client(monkeypatch, vector_dataset())
    copernicus.worker(request())
    assert calls[0]['username'] == 'offline-user'
    assert calls[0]['password'] == 'offline-password'


def test_wave_worker_fetches_shared_bundle_and_projects_requested_variable(monkeypatch):
    calls = mock_client(monkeypatch, wave_dataset())
    evidence = copernicus.worker(request('mean_wave_period'))
    assert calls[0]['variables'] == ['VHM0', 'VTM02', 'VMDR']
    assert evidence['points'][0]['source_values']['VTM02'] == 4.5
    projected = copernicus.project_current_or_wave_evidence(evidence, 'mean_wave_period', 'VTM02')
    assert projected['points'][0]['raw_value'] == 4.5
    assert projected['points'][0]['unit'] == 's'


def test_wave_bundle_preserves_independent_threshold_evaluations(tmp_path, monkeypatch):
    evaluation_inputs = inputs()
    ds = wave_dataset().assign_coords(time=np.array([
        np.datetime64(evaluation_inputs.start_time.replace(tzinfo=None)),
        np.datetime64(evaluation_inputs.end_time.replace(tzinfo=None)),
    ]))
    calls = mock_client(monkeypatch, ds)
    raw = [
        requirement('significant_wave_height', condition_id='3', threshold=1.0, operator='>', unit='m',
                    source_spans=[{'page': 1, 'quotation': 'Wave height above 1 m.'}]),
        requirement('mean_wave_period', condition_id='4', threshold=5.0, operator='>', unit='s',
                    source_spans=[{'page': 1, 'quotation': 'Wave period above 5 s.'}]),
        requirement('mean_wave_direction', condition_id='5', threshold=None, operator=None, unit='degrees',
                    source_spans=[{'page': 1, 'quotation': 'Wave direction in degrees.'}]),
    ]
    result = evaluate(analysis(*raw), evaluation_inputs, tmp_path, transports={'COPERNICUS_MARINE': copernicus.worker})
    assert len(calls) == 1
    rows = {row['condition_id']: row for row in result['requirements']}
    assert rows['3']['evidence']['points'][0]['normalized_unit'] == 'm'
    assert rows['4']['evidence']['points'][0]['normalized_unit'] == 's'
    assert rows['3']['evidence']['points'][0]['comparison'] is True
    assert rows['4']['evidence']['points'][0]['comparison'] is False
    assert rows['5']['evidence']['points'][0]['normalized_unit'] == 'degrees'
    assert rows['5']['evidence']['points'][0]['raw_value'] == 180.0


def test_four_current_requirements_share_one_transport(tmp_path):
    calls=[]
    def transport(req):
        calls.append(req)
        from src.environmental.fixture import mock_evidence
        ev=mock_evidence(req)
        start=datetime.fromisoformat(req.start_time);end=datetime.fromisoformat(req.end_time)
        ev['points']=[{**ev['points'][0],'data_time':(start+timedelta(seconds=i)).isoformat()} for i in range(0,int((end-start).total_seconds())+1,900)]
        ev['temporal_resolution']=900
        for p in ev['points']:p['component_values']={'uo':-.8,'vo':.6}
        return ev
    variables=['surface_current_speed','eastward_current','northward_current','surface_current_direction']
    doc=analysis(*(requirement(v,condition_id=str(i+9),threshold=None if i==3 else .6,
        operator=None if i==3 else '>',unit='m/s',depth_requirement='surface',
        source_spans=[{'page':1,'quotation':'Absolute current component greater than 0.6 m/s.'}]) for i,v in enumerate(variables)))
    result=evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':transport})
    assert len(calls)==1 and len(result['evidence_groups'])==1
    assert {c['condition_id'] for c in result['evidence_groups'][0]['checks']}=={'9','10','11','12'}
    points=[r['evidence']['points'][0] for r in result['requirements']]
    assert points[0]['raw_value']==1 and points[1]['raw_value']==-.8 and points[2]['raw_value']==.6
    assert points[1]['comparison'] is True and points[2]['comparison'] is False
    assert points[3]['status']=='INFORMATIONAL'
    assert points[3]['normalized_unit']=='degrees'
    assert result['evidence_groups'][0]['status']!='INSUFFICIENT_DATA'
    assert result['evidence_groups'][0]['gating_condition_ids']==['9','10','11']
    assert result['evidence_groups'][0]['informational_condition_ids']==['12']


@pytest.mark.parametrize('u,v,expected',[(1,0,90),(0,1,0),(-1,0,270),(0,-1,180)])
def test_direction_towards_and_signed_provenance(u,v,expected):
    source={'points':[{'component_values':{'uo':u,'vo':v}}]}
    projected=copernicus.project_current_or_wave_evidence(source,'surface_current_direction','current_direction')
    assert projected['points'][0]['raw_value']==expected
    assert projected['direction_convention']=='TOWARDS_CLOCKWISE_FROM_NORTH'
    assert projected['points'][0]['component_values']=={'uo':u,'vo':v}
    assert source['points'][0]=={'component_values':{'uo':u,'vo':v}}


def test_timeout_is_bounded_and_no_retry(monkeypatch):
    calls=[]
    def timeout(*args,**kwargs):
        calls.append(kwargs);raise subprocess.TimeoutExpired('safe',60)
    monkeypatch.setattr(copernicus.subprocess,'run',timeout)
    with pytest.raises(ProviderError) as caught:copernicus.retrieve(request())
    assert caught.value.category=='TIMEOUT' and 'phase is unknown' in caught.value.safe_message
    assert len(calls)==1 and calls[0]['timeout']==60


def test_worker_exit_diagnostic_is_sanitized_and_structured(monkeypatch):
    class Completed:
        returncode = 1
        stdout = ''
    monkeypatch.setattr(copernicus.subprocess, 'run', lambda *args, **kwargs: Completed())
    with pytest.raises(ProviderError) as caught:
        copernicus.retrieve(request())
    assert caught.value.category == 'WORKER_RUNTIME'
    assert caught.value.metadata == {
        'failure_stage': 'WORKER_STARTUP_OR_EXIT',
        'worker_exit_code': 1,
        'dataset_id': request().dataset_id,
        'dataset_variable': request().dataset_variable,
    }


@pytest.mark.parametrize('prefix',['approximately','about','around'])
def test_approximate_depth_source_parsing(prefix):
    text=f'{prefix} 1 metre below the sea surface'
    r=requirement('dissolved_oxygen',depth_requirement=text,source_spans=[{'page':1,'quotation':f'Oxygen at {text} below 6 mg/L.'}])
    r['routing']={'preferred_provider':'COPERNICUS_MARINE'}
    assert source_depth(r)==(1.,None)
    assert depth_metadata(r)=={'requested_depth_mode':'APPROXIMATE','depth_tolerance_m':.5}


@pytest.mark.parametrize('depths,selected',[((1.,),1.),((.6,1.4),1.4),((1.5,),1.5)])
def test_native_depth_within_tolerance(monkeypatch,depths,selected):
    calls=mock_client(monkeypatch,oxygen_dataset(depths))
    result=copernicus.worker(request('dissolved_oxygen',depth=1,requested_depth_mode='APPROXIMATE'))
    assert result['selected_depth_m']==selected
    assert result['depth_difference_m']==pytest.approx(abs(selected-1))
    assert result['requested_depth_mode']=='APPROXIMATE' and result['depth_tolerance_m']==DEPTH_TOLERANCE_M
    assert result['points'][0]['raw_value']==200 and result['points'][0]['unit']=='mmol m-3'
    assert 'supportive' in result['notes']
    assert calls[0]['minimum_depth']==.5 and calls[0]['maximum_depth']==1.5
    assert calls[0]['variables']==['o2'] and calls[0]['coordinates_selection_method']=='outside'


@pytest.mark.parametrize('case,category',[('outside','DEPTH_TOLERANCE_EXCEEDED'),('axis','DEPTH_AXIS_MISSING'),('metadata','DEPTH_METADATA_INVALID'),('nan','DEPTH_METADATA_INVALID')])
def test_invalid_depth_fails_closed(monkeypatch,case,category):
    ds=oxygen_dataset((2.,) if case=='outside' else (float('nan'),) if case=='nan' else (1.,))
    if case=='axis':ds=ds.isel(depth=0,drop=True)
    if case=='metadata':ds.depth.attrs['units']='unknown'
    mock_client(monkeypatch,ds)
    with pytest.raises(ProviderError) as caught:copernicus.worker(request('dissolved_oxygen',depth=1))
    assert caught.value.category==category


@pytest.mark.parametrize('native,unit,trigger',[(180.,'mmol m-3',True),(200.,'mmol m-3',False),(6.,'mg/L',False),(200.,'unknown',None)])
def test_oxygen_native_unit_conversion_and_screening(native,unit,trigger):
    from tests.test_decision_engine import fixture,T
    reviews,env=fixture('dissolved_oxygen',unit='mg/L',threshold=6,operator='<',value=native,
        depth_requirement='approximately 1 metre below the sea surface',
        source_spans=[{'page':1,'quotation':'Dissolved oxygen approximately 1 metre below the sea surface below 6 mg/L.'}])
    r=reviews['requirements'][0]['original'];e=env['requirements'][0]['evidence']
    e.update(dataset_id='SYNTHETIC_OXYGEN',selected_depth_m=1)
    for p in e['points']:p['unit']=unit
    req=request('dissolved_oxygen',depth=1,operator='<',threshold=6,threshold_unit='mg/L')
    req.start_time=e['coverage']['requested_start'];req.end_time=e['coverage']['requested_end']
    req.timestep_seconds=3600  # This synthetic unit-only series is hourly.
    result=compatible_points(r,req,e,now=T)
    assert result['threshold_evaluation']==('NOT_DETERMINED' if trigger is None else 'TRIGGERED' if trigger else 'NOT_TRIGGERED'), result['validation_notes']
    assert result['points'][0]['raw_value']==native and result['points'][0]['unit']==unit
    assert result['points'][0]['normalized_unit']=='mg/L'
    if trigger is None:
        assert 'Provider unit incompatible with permit requirement' in result['validation_notes']


def test_unknown_oxygen_unit_rejected():
    from src.environmental.units import convert
    with pytest.raises(ValueError):convert(200,'unknown','mg/L',variable='dissolved_oxygen')
