"""Offline post-fetch semantics; transports are explicit synthetic stubs."""
from copy import deepcopy
from datetime import datetime,timedelta
import pytest
from tests.test_simple_environment import requirement, analysis, inputs
from tests.test_decision_engine import fixture, run, T
from src.environmental.fixture import mock_evidence
from src.environmental.service import evaluate, map_requirements, canonical_stop_rule, compatible_points
from src.environmental.models import EnvironmentalRequest
from src.environmental.errors import ProviderError
from src.environmental.copernicus import worker
from tests.test_copernicus_current_oxygen_patch import oxygen_dataset, mock_client, request


@pytest.mark.parametrize('variable',['wind_speed_10m','wind_gust','wind_direction_10m','visibility',
    'significant_wave_height','mean_wave_period','mean_wave_direction','surface_current_speed'])
def test_global_depth_never_leaks_to_surface_capabilities(tmp_path,variable):
    calls=[]
    def transport(req):calls.append(req);return mock_evidence(req)
    result=evaluate(analysis(requirement(variable,depth_requirement=None)),inputs(depth=1),tmp_path,
                     transports={'COPERNICUS_MARINE':transport,'ECMWF_FORECAST':transport})
    assert len(calls)==1 and calls[0].depth is None
    assert result['requirements'][0]['request']['depth'] is None
    assert not any('depth' in note.lower() for note in result['requirements'][0]['evidence']['validation_notes'])


@pytest.mark.parametrize('variable,operator,threshold,value,trigger',[
    ('significant_wave_height','>',1.5,1.988,True),('mean_wave_period','>',8,4.79,False),
    ('wind_speed_10m','>',12,12.46,True),('wind_gust','>',18,16.2,False),
    ('visibility','<',1000,11180,False),('surface_current_speed','>',1,.108,False),
    ('dissolved_oxygen','<',6,5.9,True),('dissolved_oxygen','<',6,6,False),('dissolved_oxygen','<',6,6.1,False)])
def test_source_stop_predicate_and_screening(variable,operator,threshold,value,trigger):
    word='greater than' if operator=='>' else 'below'
    passing='<=' if operator=='>' else '>='
    unit='mg/L' if variable=='dissolved_oxygen' else 's' if variable=='mean_wave_period' else 'm/s' if variable in {'wind_speed_10m','wind_gust','surface_current_speed'} else 'm'
    text=f'STOP condition: {variable} {word} {threshold} {unit}. Passing condition: opposite.'
    reviews,env=fixture(variable,operator=passing,threshold=threshold,value=value,unit=unit,source_spans=[{'page':1,'quotation':text}])
    raw=reviews['requirements'][0]['original'];before=deepcopy(raw)
    mapped=map_requirements(analysis(raw))[0]
    assert mapped['operator']==operator and mapped['extracted_threshold']['operator']==passing
    ev=env['requirements'][0]['evidence'];ev['dataset_id']='SYNTHETIC_STOP_RULE'
    req=EnvironmentalRequest(condition_id='source-a',requirement_text=text,canonical_variable=mapped['canonical_variable'],
        coordinates=(54,-6),start_time=ev['coverage']['requested_start'],end_time=ev['coverage']['requested_end'],
        evidence_mode='forecast',provider=ev['provider'],operator=operator,threshold=threshold,threshold_unit=unit,timestep_seconds=3600)
    result=compatible_points(mapped,req,ev,now=T)
    assert result['threshold_evaluation']==('TRIGGERED' if trigger else 'NOT_TRIGGERED')
    assert result['points'][0]['comparison'] is trigger
    assert raw==before


def test_series_trigger_differs_from_displayed_point():
    reviews,env=fixture(value=1,operator='<=',threshold=2,source_spans=[{'page':1,'quotation':'STOP condition: wave greater than 2 m.'}])
    mapped=canonical_stop_rule(reviews['requirements'][0]['original'])
    e=env['requirements'][0]['evidence'];e['dataset_id']='SYNTHETIC_WAVE';e['points'][-2]['raw_value']=3
    req=EnvironmentalRequest(condition_id='source-a',requirement_text='source',canonical_variable='significant_wave_height',
        coordinates=(54,-6),start_time=e['coverage']['requested_start'],end_time=e['coverage']['requested_end'],
        provider='COPERNICUS_MARINE',evidence_mode='forecast',operator='>',threshold=2,threshold_unit='m',timestep_seconds=3600)
    result=compatible_points(mapped,req,e,now=T)
    assert result['points'][0]['comparison'] is False and result['threshold_evaluation']=='TRIGGERED'
    reviews['requirements'][0]['mapping']=map_requirements(analysis(reviews['requirements'][0]['original']))
    assert run(reviews,env,duration_hours=6)['current_assessment']['status']=='STOP'


@pytest.mark.parametrize('level,success',[(1.,True),(.75,True),(1.5,True),(1.51,False)])
def test_oxygen_discovery_after_open_with_partial_failure_metadata(monkeypatch,tmp_path,level,success):
    calls=mock_client(monkeypatch,oxygen_dataset((level,)))
    text='approximately 1 metre below the sea surface'
    raw=requirement('dissolved_oxygen',operator='<',threshold=6,unit='mg/L',depth_requirement=text,
        source_spans=[{'page':1,'quotation':f'Dissolved oxygen at {text}. STOP condition: oxygen below 6 mg/L.'}])
    result=evaluate(analysis(raw),inputs(depth=1),tmp_path,transports={'COPERNICUS_MARINE':worker})
    assert len(calls)==1
    row=result['requirements'][0]
    assert row['request']['depth']==1 and row['request']['requested_depth_mode']=='APPROXIMATE'
    if success:
        assert row['evidence']['selected_depth_m']==level
    else:
        assert row['provider_diagnostic']['provider_error_category']=='DEPTH_TOLERANCE_EXCEEDED'
        assert row['provider_metadata']['returned_depth_levels_m']==[1.51]
        assert row['provider_metadata']['depth_difference_m']==pytest.approx(.51)
        assert row['provider_metadata']['screening_status']=='DEPTH_UNSATISFIED'
        diagnostic=result['diagnostic_groups'][0]['diagnostic_evidence']
        assert diagnostic['screening_status']=='NOT_DETERMINED'
        assert diagnostic['retrieval_status']=='PROVIDER_RESPONSE_OBTAINED'
        assert diagnostic['returned_depth_levels_m']==[1.51]
        assert diagnostic['native_unit']=='mmol m-3'
        assert diagnostic['depth_axis_positive']=='down'
        assert 'evidence' not in row


def test_informational_shared_failure_does_not_contaminate_gating_card(tmp_path,monkeypatch):
    import src.environmental.service as service
    original=service.compatible_points
    def checked(row,req,evidence,**kwargs):
        result=original(row,req,evidence,**kwargs)
        if req.canonical_variable=='surface_current_direction':
            result.update(status='INSUFFICIENT_DATA',validation_notes=['Informational derivation unresolved'])
        return result
    monkeypatch.setattr(service,'compatible_points',checked)
    calls=[]
    def transport(req):
        calls.append(req);ev=mock_evidence(req)
        start=datetime.fromisoformat(req.start_time);end=datetime.fromisoformat(req.end_time)
        ev['points']=[{**ev['points'][0],'data_time':(start+timedelta(seconds=i)).isoformat()} for i in range(0,int((end-start).total_seconds())+1,900)]
        ev['temporal_resolution']=900
        for p in ev['points']:p['component_values']={'uo':.1,'vo':.2}
        return ev
    # Put direction first to exercise order-independent representative selection.
    variables=['surface_current_direction','surface_current_speed','eastward_current','northward_current']
    doc=analysis(*(requirement(v,condition_id=v,threshold=None if i==0 else 1.,operator=None if i==0 else '>',
        unit='m/s',source_spans=[{'page':1,'quotation':'STOP condition: current greater than 1 m/s.'}]) for i,v in enumerate(variables)))
    result=evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':transport})
    assert len(calls)==1
    assert result['requirements'][0]['status']=='INSUFFICIENT_DATA'
    card=result['evidence_groups'][0]
    assert card['status']=='WITHIN_THRESHOLD' and card['canonical_variable']=='surface_current_speed'
    assert card['evidence']['status']=='WITHIN_THRESHOLD'


def test_f09_informational_shared_warning_never_gates():
    reviews,env=fixture();info=deepcopy(reviews['requirements'][0])
    info.update(target_id='environmental_requirement-1-info',decision_relevant_default=False)
    info['original'].update(canonical_variable='surface_current_direction',threshold=None,operator=None)
    info['effective']=deepcopy(info['original'])
    reviews['requirements'].append(info)
    env['requirements'].append({**deepcopy(env['requirements'][0]),'requirement_index':1,'condition_id':info['condition_id'],
                               'status':'INSUFFICIENT_DATA'})
    result=run(reviews,env)['current_assessment']
    assert result['status']=='WORK'
    assert not next(r for r in result['rule_results'] if r['requirement_id']==info['target_id'])['gating']
