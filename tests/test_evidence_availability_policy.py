"""Explicit MVP turbidity availability and existing current forecast contract."""
from copy import deepcopy
from datetime import timedelta
import pytest
from tests.test_decision_engine import fixture, run, T
from src.permit.decision_engine import evaluate_requirement


@pytest.mark.parametrize('failure', ['missing','stale','unit','provider','timestamp','unsupported'])
def test_unavailable_mandatory_turbidity_fails_closed(failure):
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
    assert rule['status']=='UNKNOWN' and rule['gating'] is True
    assert rule['mvp_evidence_excluded'] is True
    assert result['current_assessment']['status']=='WORK'
    assert not result['evidence_gaps']
    assert result['current_assessment']['warnings']
    assert not result['candidate_windows'] or result['candidate_windows'][0]['status']=='WORK'
    assert (reviews,env)==before


@pytest.mark.parametrize('value,state',[(25,'WORK'),(25.01,'STOP')])
def test_available_turbidity_still_gates(value,state):
    reviews,env=fixture('turbidity',unit='FNU',threshold=25,value=value)
    env['requirements'][0]['evidence']['data_type']='SATELLITE_OBSERVATION'
    result=run(reviews,env)['current_assessment']
    assert result['status']==state and result['rule_results'][0]['gating']


@pytest.mark.parametrize('value,present,state',[(1,False,'UNKNOWN'),(3,True,'STOP'),(1,True,'UNKNOWN')])
def test_other_gating_constraints_unchanged_when_turbidity_missing(value,present,state):
    reviews,env=fixture(value=value)
    tr,te=fixture('turbidity',unit='FNU',threshold=25)
    row=tr['requirements'][0]
    row['target_id']='environmental_requirement-1-turbidity'
    row['condition_id']='turbidity-source'
    for m in row['mapping']: m['requirement_index']=1
    reviews['requirements'].append(row)
    if not present: env['requirements'][0].pop('evidence')
    # The turbidity row is excluded only when its own evidence is unavailable;
    # the independent source row retains normal STOP/UNKNOWN semantics.
    expected = 'STOP' if value == 3 else 'UNKNOWN' if not present else 'WORK'
    assert run(reviews,env)['current_assessment']['status']==expected


def test_missing_turbidity_plus_other_unknown_remains_unknown():
    reviews, env = fixture()
    tr, te = fixture('turbidity', unit='FNU', threshold=25)
    row = tr['requirements'][0]
    row['target_id'] = 'environmental_requirement-1-turbidity'
    row['condition_id'] = 'turbidity-source'
    for mapping in row['mapping']:
        mapping['requirement_index'] = 1
    reviews['requirements'].append(row)
    env['requirements'].append({**te['requirements'][0], 'requirement_index': 1})
    env['requirements'][1].pop('evidence')
    reviews['requirements'][0]['applicability'] = 'UNASSESSED'
    result = run(reviews, env)
    assert result['current_assessment']['status'] == 'UNKNOWN'
    assert any(r['reason_code'] == 'APPLICABILITY_UNASSESSED' for r in result['evidence_gaps'])


def test_missing_turbidity_with_passing_numerical_gate_is_work_with_warning():
    reviews, env = fixture()
    tr, te = fixture('turbidity', unit='FNU', threshold=25)
    row = tr['requirements'][0]
    row['target_id'] = 'environmental_requirement-1-turbidity'
    row['condition_id'] = 'turbidity-source'
    for mapping in row['mapping']:
        mapping['requirement_index'] = 1
    reviews['requirements'].append(row)
    env['requirements'].append({**te['requirements'][0], 'requirement_index': 1})
    env['requirements'][1].pop('evidence')
    result = run(reviews, env)
    assert result['current_assessment']['status'] == 'WORK'
    assert result['current_assessment']['warnings'] == [
        'Turbidity evidence unavailable — excluded from MVP decision under the evidence-availability policy. This is not a passing turbidity result or authorization to work.'
    ]


def test_missing_turbidity_does_not_override_wave_stop():
    reviews, env = fixture(value=3)
    tr, te = fixture('turbidity', unit='FNU', threshold=25)
    row = tr['requirements'][0]
    row['target_id'] = 'environmental_requirement-1-turbidity'; row['condition_id'] = 'turbidity-source'
    for mapping in row['mapping']: mapping['requirement_index'] = 1
    reviews['requirements'].append(row); env['requirements'].append({**te['requirements'][0], 'requirement_index': 1})
    env['requirements'][1].pop('evidence')
    assert run(reviews, env)['current_assessment']['status'] == 'STOP'


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
