"""Offline linkage-only tests: no transports and no artifact writes."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import pytest
from tests.test_decision_engine import fixture,run,T
from src.permit.decision_engine import reviewed_validity,assess


def reviewed_time_fixture():
    reviews,environment=fixture()
    quote='This synthetic permit is valid only from 1 October 2026 00:00 UTC through 31 October 2028 23:59 UTC. No evaluation outside this interval shall produce a WORK result.'
    row=reviews['requirements'][1]
    row['condition_id']='arbitrary-validity-id'
    row['source']={'source_verified':True,'source_spans':[{'page':3,'quotation':quote}]}
    reviews['decision_context']['temporal_context']={'source_verified':False,
        'source_spans':[{'page':1,'quotation':'Unreviewed summary'}],
        'operation_time_restrictions':['Permit valid only between 1 October 2026 00:00 UTC and 31 October 2028 23:59 UTC']}
    return reviews,environment


def test_reviewed_clause_links_validity_without_summary_review():
    reviews,env=reviewed_time_fixture();before=deepcopy((reviews,env))
    current=run(reviews,env)['current_assessment']
    time=next(r for r in current['rule_results'] if r['condition_id']=='time')
    assert time['status']=='WORK' and time['reason_code']=='TIME_CONFIRMED'
    assert time['reviewed_validity_source']['reviewed_validity_provenance'][0]['source_span']['page']==3
    assert (reviews,env)==before


def test_reviewed_validity_outside_bounds_is_non_work():
    reviews,env=reviewed_time_fixture()
    current=assess(reviews,env,start=T.replace(year=2029),now=T)['current_assessment']
    assert next(r for r in current['rule_results'] if r['condition_id']=='time')['reason_code']=='NOT_ELIGIBLE_TIME'
    assert current['status']!='WORK'


@pytest.mark.parametrize('change',['unreviewed','unverified','additional_restriction'])
def test_time_linkage_fails_closed(change):
    reviews,env=reviewed_time_fixture()
    if change=='unreviewed':reviews['requirements'][1]['state']='UNREVIEWED'
    elif change=='unverified':reviews['requirements'][1]['source']['source_verified']=False
    else:reviews['decision_context']['temporal_context']['operation_time_restrictions'].append('Night work prohibited')
    current=run(reviews,env)['current_assessment']
    assert next(r for r in current['rule_results'] if r['condition_id']=='time')['status']=='UNKNOWN'


def coastal_fixture():
    reviews,env=fixture()
    ev=env['requirements'][0]['evidence']
    ev.update(quality_status='COASTAL_REVIEW_REQUIRED',applicability_status='COASTAL_REVIEW_REQUIRED',
        retrieval_status='SUCCESS',max_representative_distance_km=5,distance_km=.96,
        qualification='Coastal applicability requires human review; advisory model evidence only.')
    return reviews,env


def test_stored_qualified_spatial_result_is_consumed_and_preserved():
    reviews,env=coastal_fixture();result=run(reviews,env)['current_assessment']
    assert result['status']=='WORK'
    reference=result['rule_results'][0]['evidence_references'][0]
    assert reference['qualification']==env['requirements'][0]['evidence']['qualification']
    assert reference['quality_status']=='COASTAL_REVIEW_REQUIRED'


@pytest.mark.parametrize('change',['missing_result','missing_limit','outside','unresolved','warning','bad_point'])
def test_unqualified_coastal_spatial_result_remains_unknown(change):
    reviews,env=coastal_fixture();ev=env['requirements'][0]['evidence']
    if change=='missing_result':ev.pop('spatial_distance_status')
    elif change=='missing_limit':ev.pop('max_representative_distance_km')
    elif change=='outside':ev['distance_km']=6
    elif change=='unresolved':ev['applicability_status']='UNRESOLVED'
    elif change=='warning':ev['validation_notes']=['Spatial representativeness unresolved']
    else:ev['latitude']=float('nan')
    result=run(reviews,env)['current_assessment']
    assert result['status']=='UNKNOWN' and result['rule_results'][0]['reason_code']=='SPATIAL_COVERAGE_INSUFFICIENT'


def test_position_and_stop_precedence_unchanged():
    reviews,env=coastal_fixture()
    env['requirements'][0]['evidence']['points'][0]['raw_value']=3
    reviews['decision_context']['spatial_context']=[]
    current=run(reviews,env)['current_assessment']
    assert current['status']=='STOP'
    assert next(r for r in current['rule_results'] if r['condition_id']=='position')['status']=='UNKNOWN'


def test_actual_persisted_review_link_read_only():
    from src.permit.persisted_analysis import load_persisted_analysis
    from src.permit.review_overlays import list_reviews
    digest='8fcffc25fbf2c29a56bcf33eb02725d57cafeb1135263bea9ee75062b2a6f552'
    run_id='eaec3e9838a64e34813b1e65f70788e0'
    folder=Path('cache/simple_analysis')/digest/run_id
    review=Path('cache/simple_reviews')/digest/run_id/'review_overlays.json'
    if not folder.exists():pytest.skip('Local persisted acceptance fixture absent')
    before={p:p.read_bytes() for p in [*folder.iterdir(),review] if p.is_file()}
    analysis=load_persisted_analysis(Path('.'),digest,run_id)
    validity=reviewed_validity(list_reviews(Path('.'),analysis)['requirements'])
    assert validity['permit_valid_from']=='2026-10-01T00:00:00+00:00'
    assert before=={p:p.read_bytes() for p in before}
