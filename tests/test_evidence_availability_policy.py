"""Explicit MVP turbidity availability and existing current forecast contract."""
from copy import deepcopy
from datetime import timedelta
import pytest
from tests.test_decision_engine import fixture, run, T
from src.permit.decision_engine import evaluate_requirement


@pytest.mark.parametrize('failure', ['missing','stale','unit','provider','timestamp','unsupported'])
def test_unavailable_turbidity_excluded_not_pass_or_blocker(failure):
    reviews, env=fixture('turbidity',unit='FNU',threshold=25)
    evidence=env['requirements'][0]['evidence']
    evidence['data_type']='SATELLITE_OBSERVATION'
    if failure=='missing': env['requirements'][0].pop('evidence')
    if failure=='stale':
        evidence['points']=[{**evidence['points'][0],'data_time':(T-timedelta(hours=73)).isoformat()}]
    if failure=='unit':
        for p in evidence['points']: p['unit']='NTU'
    if failure=='provider': env['requirements'][0]['retrieval_status']='FAILED'
    if failure=='unsupported': reviews['requirements'][0]['mapping'][0]['routing']['implemented']=False
    if failure=='timestamp':
        for p in evidence['points']: p['data_time']='invalid'
    before=deepcopy((reviews,env))
    result=run(reviews,env)
    rule=result['current_assessment']['rule_results'][0]
    assert rule['status']=='UNKNOWN' and rule['gating'] is False
    assert rule['availability_policy']=='AVAILABLE_EVIDENCE_ONLY_MVP'
    assert 'excluded from MVP' in rule['explanation']
    assert result['current_assessment']['status']=='WORK'
    assert result['evidence_gaps']==[]
    assert result['candidate_windows']
    assert (reviews,env)==before


@pytest.mark.parametrize('value,state',[(25,'WORK'),(25.01,'STOP')])
def test_available_turbidity_still_gates(value,state):
    reviews,env=fixture('turbidity',unit='FNU',threshold=25,value=value)
    env['requirements'][0]['evidence']['data_type']='SATELLITE_OBSERVATION'
    result=run(reviews,env)['current_assessment']
    assert result['status']==state and result['rule_results'][0]['gating']


@pytest.mark.parametrize('value,present,state',[(1,False,'UNKNOWN'),(3,True,'STOP'),(1,True,'WORK')])
def test_other_gating_constraints_unchanged_when_turbidity_missing(value,present,state):
    reviews,env=fixture(value=value)
    tr,te=fixture('turbidity',unit='FNU',threshold=25)
    row=tr['requirements'][0]
    row['target_id']='environmental_requirement-1-turbidity'
    row['condition_id']='turbidity-source'
    for m in row['mapping']: m['requirement_index']=1
    reviews['requirements'].append(row)
    if not present: env['requirements'][0].pop('evidence')
    assert run(reviews,env)['current_assessment']['status']==state


@pytest.mark.parametrize('variable',['surface_current_speed','eastward_current','northward_current'])
@pytest.mark.parametrize('future,value,state',[(False,.1,'WORK'),(True,.1,'WORK'),(True,2,'STOP')])
def test_native_current_forecast_and_analysis_time_values_are_already_usable(variable,future,value,state):
    reviews,env=fixture(variable,hours=72,step=900,unit='m/s',threshold=1,value=value)
    start=T+timedelta(hours=60) if future else T
    before=deepcopy(env)
    result=evaluate_requirement(reviews['requirements'][0],env,start,start+timedelta(hours=1),T,set())
    assert result['status']==state
    assert result['evidence_references'][0]['data_type']=='MODEL_FORECAST'
    assert result['checks'][0]['values'][0]['valid_time']==start.isoformat()
    assert env==before


def test_current_forecast_missing_remains_unknown():
    reviews,env=fixture('surface_current_speed',hours=72,step=900,unit='m/s')
    env['requirements'][0].pop('evidence')
    result=evaluate_requirement(reviews['requirements'][0],env,T+timedelta(hours=60),T+timedelta(hours=61),T,set())
    assert result['status']=='UNKNOWN' and result['gating'] is True
    assert result['reason_code']=='EVIDENCE_MISSING'
