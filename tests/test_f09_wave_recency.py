"""Stored Hs fixtures only. No extraction, providers, or production writes."""
from copy import deepcopy
from datetime import timedelta
import pytest
from src.environmental.recency import policy, select
from src.permit.decision_engine import evaluate_requirement
from tests.test_decision_engine import fixture, run, T


def wave(age, value=1.5):
    return {'data_time':(T-timedelta(minutes=age)).isoformat(), 'raw_value':value, 'unit':'m'}


def evaluate(points, end=None):
    text='STOP condition: significant wave height > 1.5 m.'
    reviews, env=fixture(threshold=1.5,operator='>',source_spans=[{'page':1,'quotation':text}])
    env['requirements'][0]['evidence']['points']=deepcopy(points)
    before=deepcopy((reviews,env))
    result=evaluate_requirement(reviews['requirements'][0],env,T,end or T,T,set())
    assert (reviews,env)==before
    return result


@pytest.mark.parametrize('age',[0,60,90])
def test_passing_native_sample_age_inclusive_at_assessment_instant(age):
    p=wave(age)
    result=evaluate([p])
    assert result['status']=='WORK'
    audit=result['evidence_references'][0]['recency_policy']
    assert audit['age_minutes']==age and audit['max_age_minutes']==90
    assert audit['source_timestamp']==p['data_time']
    assert result['checks'][0]['values'][0]['raw_value']==1.5
    assert 'provider-declared' in result['explanation']
    assert 'valid_start' not in p and 'valid_end' not in p


def test_expired_sample_unknown():
    result=evaluate([wave(90.01)])
    assert result['status']=='UNKNOWN' and result['reason_code']=='STALE_WAVE_EVIDENCE'


@pytest.mark.parametrize('age',[0,60,90])
def test_triggered_sample_stop(age):
    assert evaluate([wave(age,1.5001)])['status']=='STOP'


def test_latest_compatible_sample_only_no_interpolation_or_future_use():
    points=[wave(60,2),wave(0,1),wave(-60,3),wave(1,float('nan'))]
    result=evaluate(points)
    assert result['status']=='WORK'
    values=result['checks'][0]['values']
    assert len(values)==1 and values[0]['value']==1
    assert values[0]['valid_time']==points[1]['data_time']
    assert evaluate([wave(-1)])['reason_code']=='NO_WAVE_EVIDENCE'
    assert evaluate([])['reason_code']=='NO_WAVE_EVIDENCE'


def test_no_interval_carry_beyond_expiry():
    result=evaluate([wave(60)],T+timedelta(minutes=31))
    assert result['status']=='UNKNOWN' and result['reason_code']=='STALE_WAVE_EVIDENCE'


def test_wave_period_and_provider_service_policies_unchanged():
    assert policy('mean_wave_period',wave_height=True) is None
    assert policy('significant_wave_height') is None
    assert policy('turbidity')==(72,'STALE_TURBIDITY_EVIDENCE','NO_COMPATIBLE_ACCESSIBLE_SOURCE')
    assert policy('dissolved_oxygen',0)==(24,'STALE_OXYGEN_EVIDENCE','NO_COMPATIBLE_OXYGEN_SOURCE')


def test_timeline_stops_at_policy_expiry_without_inferred_crossing():
    reviews, env=fixture(hours=6)
    env['requirements'][0]['evidence']['points']=[wave(0,1)]
    result=run(reviews,env)
    assert result['timeline'][0]['end']==(T+timedelta(minutes=90)).isoformat()
    assert result['timeline'][0]['status']=='WORK'
    assert result['timeline'][1]['status']=='UNKNOWN'
