"""Native oxygen validity fixtures only: no transports or persisted writes."""
from copy import deepcopy

from tests.test_decision_engine import fixture, run


def oxygen(step):
    reviews, env = fixture('dissolved_oxygen', hours=48, step=step, value=7.,
        unit='mg/L', threshold=6., operator='<', depth_requirement='0 m below sea surface',
        source_spans=[{'page':1,'quotation':'Modelled dissolved oxygen at 0 m below sea surface. STOP condition: dissolved oxygen < 6 mg/L.'}])
    evidence=env['requirements'][0]['evidence']
    evidence.update(selected_depth_m=0., requested_depth=0., requested_depth_m=0.)
    return reviews, env


def test_daily_oxygen_uses_explicit_recency_policy_without_interpolation():
    reviews, env=oxygen(86400)
    before=deepcopy((reviews,env))
    result=run(reviews,env)
    row=result['current_assessment']['rule_results'][0]
    assert row['status']=='WORK'
    assert 'recency policy' in row['explanation']
    assert (reviews,env)==before


def test_compatible_subdaily_zero_depth_model_evidence_remains_assessable():
    reviews,env=oxygen(3600)
    result=run(reviews,env)
    assert result['current_assessment']['status']=='WORK'
    evidence=env['requirements'][0]['evidence']
    assert evidence['selected_depth_m']==evidence['requested_depth_m']==0.
    assert evidence['data_type']=='MODEL_FORECAST'
    assert len(evidence['points'])==49
