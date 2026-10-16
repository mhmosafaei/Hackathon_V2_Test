"""Explicit MVP Hs recency: no provider validity, interpolation, or live calls."""
from copy import deepcopy
from datetime import timedelta
from tests.test_decision_engine import fixture,run,T


def point_waves(values):
    reviews,env=fixture(hours=len(values)-1,value=values[0])
    for point,value in zip(env['requirements'][0]['evidence']['points'],values):
        for key in ('temporal_semantics','valid_start','valid_end'):point.pop(key,None)
        point['raw_value']=value
    # Unrelated finer native samples must not create fictitious wave transitions.
    env['requirements'].append({'canonical_variable':'surface_current_direction','requirement_index':99,
        'evidence':{'points':[{'data_time':(T+timedelta(minutes=i)).isoformat()} for i in range(0,121,15)]}})
    return reviews,env


def test_hourly_triggered_wave_partition_not_alternating():
    reviews,env=point_waves([3,3,3]);before=deepcopy((reviews,env))
    result=run(reviews,env,duration_hours=2,horizon_hours=24)
    assert [(i['start'],i['end']) for i in result['timeline'][:2]]==[
        (T.isoformat(),(T+timedelta(hours=1)).isoformat()),
        ((T+timedelta(hours=1)).isoformat(),(T+timedelta(hours=2)).isoformat())]
    assert [i['status'] for i in result['timeline'][:2]]==['STOP','STOP']
    assert result['current_assessment']['status']=='STOP'
    assert (reviews,env)==before


def test_next_boundary_trigger_does_not_contaminate_previous_cell():
    reviews,env=point_waves([1,1,3])
    result=run(reviews,env,duration_hours=2)
    assert [i['status'] for i in result['timeline'][:2]]==['WORK','WORK']
    assert result['current_assessment']['status']=='WORK'


def test_point_passes_use_explicit_mvp_policy_not_provider_validity():
    reviews,env=point_waves([1,1,1])
    result=run(reviews,env,duration_hours=2)
    assert result['current_assessment']['status']=='WORK'
    assert 'MVP recency policy' in result['current_assessment']['rule_results'][0]['explanation']


def test_mixed_native_instants_preserve_stop_precedence():
    reviews,env=point_waves([1,3,1])
    result=run(reviews,env,duration_hours=2)
    assert [i['status'] for i in result['timeline'][:2]]==['WORK','STOP']
    assert result['current_assessment']['status']=='STOP'


def test_explicit_validity_can_support_finer_partition_without_hold_assumption():
    reviews,env=fixture(hours=2,value=1)
    env['requirements'].append({'canonical_variable':'surface_current_direction','requirement_index':99,
        'evidence':{'points':[{'data_time':(T+timedelta(minutes=i)).isoformat()} for i in range(0,121,15)]}})
    result=run(reviews,env,duration_hours=2)
    assert len(result['timeline'][:8])==8
    assert all(i['status']=='WORK' for i in result['timeline'][:8])
