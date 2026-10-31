"""Pure synthetic state: no extraction, providers, or persisted production artifacts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import asyncio
import json

import httpx
import pytest

from src.permit.decision_engine import assess, find_windows
from src.environmental.service import map_requirements

T = datetime(2026, 10, 14, tzinfo=timezone.utc)


def fixture(variable='significant_wave_height', hours=6, step=3600, value=1., **extra):
    raw={'condition_id':'source-a','requirement_text':'Values above 2 m trigger review.',
         'variable':variable,'canonical_variable':variable,'threshold':2.,'operator':'>','unit':'m',
         'source_page':1,'source_spans':[{'page':1,'quotation':'Values above 2 m trigger review.'}],
         'source_verified':True,'explicit_requirement':True,'evidence_type':'forecast',**extra}
    mappings=map_requirements({'environmental_requirements':[raw]})
    row={'target_id':'environmental_requirement-0-fingerprint','kind':'environmental_requirement',
         'condition_id':'source-a','state':'APPROVED','applicability':'APPLICABLE','original':raw,
         'effective':deepcopy(raw),'source':deepcopy(raw),'conflict':None,'original_fingerprint':'fingerprint',
         'review':{'reviewed_at':T.isoformat()},'decision_relevant_default':True,'mapping':mappings}
    points=[{'data_time':(T+timedelta(seconds=i)).isoformat(),'raw_value':value,'unit':raw['unit'],
             'status':'WITHIN_THRESHOLD','validation_notes':[]} for i in range(0,hours*3600+1,step)]
    if variable=='significant_wave_height':
        for point in points:
            point.update(temporal_semantics='INTERVAL_VALID',valid_start=point['data_time'],
                         valid_end=(datetime.fromisoformat(point['data_time'])+timedelta(seconds=step)).isoformat())
    evidence={'provider':mappings[0]['routing']['preferred_provider'],'canonical_variable':mappings[0]['canonical_variable'],
        'dataset_id':'OFFLINE_FIXTURE','dataset_variable':'fixture','retrieved_at':T.isoformat(),
        'data_type':'MODEL_FORECAST','quality_status':'SUITABLE','spatial_distance_status':'WITHIN_CONFIGURED_DISTANCE',
        'requested_coordinates':[54,-6],'latitude':54,'longitude':-6,'distance_km':0,
        'temporal_resolution':step,'coverage':{'requested_start':T.isoformat(),'requested_end':(T+timedelta(hours=hours)).isoformat(),
        'temporal_resolution_seconds':step,'actual_start':T.isoformat(),'actual_end':(T+timedelta(hours=hours)).isoformat()},'points':points}
    env={'analysis_id':'run','requirements':[{**m,'request':{'coordinates':[54,-6]},'evidence':deepcopy(evidence),'evidence_request_key':'fixture-id','retrieval_status':'FETCHED'} for m in mappings]}
    reviews={'analysis_run_id':'run','document_sha256':'a'*64,'requirements':[row],
             'review_progress':{'complete':True}}
    time={'permit_valid_from':'2026-10-01T00:00:00Z','permit_valid_until':'2026-12-01T00:00:00Z','source_verified':True,
          'source_spans':[{'page':1,'quotation':'Explicit UTC validity'}]}
    position={'geometry_type':'point','point_verified':True,'latitude':54,'longitude':-6,
              'source_spans':[{'page':1,'quotation':'Explicit WGS84 position'}]}
    reviews['decision_context']={'temporal_context':time,'spatial_context':[position]}
    for label,context in [('validity',time),('position',position)]:
        reviews['requirements'].append({**deepcopy(row),'target_id':label,'kind':'condition','decision_relevant_default':False,
            'source':{'source_verified':True,'source_spans':context['source_spans']}})
    return reviews,env


def run(reviews,env,**options):
    return assess(reviews,env,start=T,now=T,**options)


@pytest.mark.parametrize('value,expected', [(1.112,'WORK'),(26.,'STOP')])
def test_explicit_demo_turbidity_compares_assumption_and_preserves_source(value,expected):
    reviews,env=fixture('turbidity',unit='FNU',threshold=25.,evidence_type='observation',
        requirement_text='STOP condition: turbidity greater than 25 FNU.')
    row=env['requirements'][0]
    row.pop('evidence')
    row['request']={'coordinates':[54,-6],'start_time':T.isoformat(),'end_time':(T+timedelta(hours=24)).isoformat()}
    row['historical_reference']={'raw_value':value,'unit':'FNU','data_time':(T-timedelta(days=11)).isoformat(),
        'reference_only':True,'qualifies_for_decision':False,'dataset_id':'OBSERVATION_FIXTURE'}
    before=deepcopy((reviews,env))
    normal=run(reviews,env)
    assert normal['current_assessment']['rule_results'][0]['status']=='UNKNOWN'
    result=run(reviews,env,demo_turbidity=True)
    assert result['current_assessment']['status']==expected
    assert result['audit']['demo_turbidity'] and result['audit']['demo_assumptions']
    assert result['current_assessment']['rule_results'][0]['reason_code']=='PLANNING_TURBIDITY_ASSUMPTION'
    assert bool(result['candidate_windows'])==(expected=='WORK')
    assert (reviews,env)==before
    reviews['requirements'][0]['source']['source_verified']=False
    assert run(reviews,env,demo_turbidity=True)['current_assessment']['status']=='UNKNOWN'


def test_all_pass_work_and_original_unchanged():
    reviews,env=fixture();before=deepcopy((reviews,env));result=run(reviews,env)
    assert result['current_assessment']['status']=='WORK'
    assert result['candidate_windows'][0]['duration_hours']==6
    assert (reviews,env)==before


def test_configured_2d_surface_current_does_not_require_an_absent_vertical_axis():
    from src.environmental.copernicus import products
    reviews,env=fixture('surface_current_speed',unit='m/s',depth_requirement='surface')
    evidence=env['requirements'][0]['evidence']
    evidence.update(dataset_id=products()['currents']['dataset'],selected_depth_m=None,depth=None)
    assert run(reviews,env)['current_assessment']['status']=='WORK'
    evidence['dataset_id']='UNVERIFIED_2D_PRODUCT'
    assert run(reviews,env)['current_assessment']['status']=='UNKNOWN'


@pytest.mark.parametrize('variable',['significant_wave_height','wind_gust'])
def test_triggered_wave_or_gust_stop(variable):
    reviews,env=fixture(variable,value=3)
    assert run(reviews,env)['current_assessment']['status']=='STOP'


@pytest.mark.parametrize('field,value,code',[
    ('state','UNREVIEWED','REVIEW_REQUIRED'),('state','REJECTED','REVIEW_REJECTED_UNRESOLVED'),
    ('applicability','UNASSESSED','APPLICABILITY_UNASSESSED'),('conflict','conflict','REVIEW_CONFLICT')])
def test_review_gates(field,value,code):
    reviews,env=fixture();reviews['requirements'][0][field]=value
    result=run(reviews,env)['current_assessment']
    assert result['status']=='UNKNOWN' and result['rule_results'][0]['reason_code']==code


def test_not_applicable_and_informational_never_stop():
    reviews,env=fixture(value=3);extra=deepcopy(reviews['requirements'][0]);extra.update(target_id='info',decision_relevant_default=False)
    reviews['requirements'].append(extra);reviews['requirements'][0]['applicability']='NOT_APPLICABLE'
    result=run(reviews,env)['current_assessment']
    assert result['stop_count']==0
    assert all(not r['gating'] for r in result['rule_results'] if r['kind']!='decision_prerequisite')


def test_stop_precedes_unknown_and_missing_evidence():
    reviews,env=fixture(value=3);extra=deepcopy(reviews['requirements'][0]);extra.update(target_id='unreviewed',state='UNREVIEWED')
    reviews['requirements'].append(extra)
    result=run(reviews,env)['current_assessment'];assert result['status']=='STOP' and result['unknown_count']==1
    assert run(reviews,None)['current_assessment']['status']=='UNKNOWN'


def test_corrected_threshold_recomputed_from_values_not_old_screening():
    reviews,env=fixture(value=1.5);row=reviews['requirements'][0];row['state']='CORRECTED';row['effective']['threshold']=1
    assert run(reviews,env)['current_assessment']['status']=='STOP'
    assert row['original']['threshold']==2


@pytest.mark.parametrize('mutation,code',[
    ('source','SOURCE_UNVERIFIED'),('unsupported','EVIDENCE_UNSUPPORTED'),('unit','NO_WAVE_EVIDENCE'),
    ('stale','EVIDENCE_STALE'),('provider','PROVIDER_FAILURE'),('spatial','SPATIAL_COVERAGE_INSUFFICIENT'),
    ('missing','NO_WAVE_EVIDENCE'),('coverage','STALE_WAVE_EVIDENCE')])
def test_invalid_evidence_unknown(mutation,code):
    reviews,env=fixture();row=reviews['requirements'][0];ev=env['requirements'][0]['evidence']
    if mutation=='source':row['source']['source_verified']=False
    elif mutation=='unsupported':row['mapping'][0]['routing']['implemented']=False
    elif mutation=='unit':ev['points'][0]['unit']='NTU'
    elif mutation=='stale':ev['retrieved_at']=(T-timedelta(hours=7)).isoformat()
    elif mutation=='provider':env['requirements'][0]['retrieval_status']='FAILED'
    elif mutation=='spatial':ev['quality_status']='COASTAL_REVIEW_REQUIRED'
    elif mutation=='missing':env['requirements'][0].pop('evidence')
    elif mutation=='coverage':ev['points']=ev['points'][:2]
    result=run(reviews,env)['current_assessment']
    assert result['status']=='UNKNOWN' and result['rule_results'][0]['reason_code']==code


def test_unsupported_informational_does_not_block_another_passing_rule():
    reviews,env=fixture();extra=deepcopy(reviews['requirements'][0]);extra.update(target_id='info',decision_relevant_default=False)
    extra['mapping'][0]['routing']['implemented']=False;reviews['requirements'].append(extra)
    assert run(reviews,env)['current_assessment']['status']=='WORK'


def test_external_evidence_not_satisfied_by_approval():
    reviews,env=fixture();reviews['requirements'][0]['mapping'][0]['routing']['preferred_provider']='EXTERNAL'
    assert run(reviews,env)['current_assessment']['rule_results'][0]['reason_code']=='EXTERNAL_EVIDENCE_REQUIRED'


def test_oxygen_depth_tolerance_preserved():
    reviews,env=fixture('dissolved_oxygen',unit='mg/L',depth_requirement='1 metre below sea surface',
        source_spans=[{'page':1,'quotation':'Oxygen at 1 metre below sea surface above 2 mg/L.'}])
    env['requirements'][0]['evidence']['selected_depth_m']=1.6
    assert run(reviews,env)['current_assessment']['rule_results'][0]['reason_code']=='DEPTH_UNSATISFIED'


@pytest.mark.parametrize('value,state',[(-3,'STOP'),(10,'WORK'),(26,'STOP')])
def test_multi_threshold_temperature(value,state):
    text='Values below -2 deg C or above 25 deg C shall be flagged for review'
    reviews,env=fixture('air_temperature',value=value,threshold=None,operator=None,unit='deg C',
                        source_spans=[{'page':1,'quotation':text}])
    result=run(reviews,env)['current_assessment'];assert result['status']==state
    assert len(result['rule_results'][0]['interval_results'][0]['checks'])==2


@pytest.mark.parametrize('mode,interval,state',[('ACCUMULATED_OVER_PRECEDING_HOUR',3600,'WORK'),
    ('RATE',3600,'UNKNOWN'),('INSTANTANEOUS',3600,'UNKNOWN'),('ACCUMULATED',1800,'UNKNOWN'),('ACCUMULATED',86400,'UNKNOWN'),('',None,'UNKNOWN')])
def test_precipitation_semantics(mode,interval,state):
    reviews,env=fixture('precipitation',unit='mm',requirement_text='Hourly accumulated precipitation above 2 mm in a one-hour interval.')
    for p in env['requirements'][0]['evidence']['points']:p.update(temporal_semantics=mode,accumulation_interval_seconds=interval)
    assert run(reviews,env)['current_assessment']['status']==state


def test_native_three_hour_resolution_no_hourly_samples_invented():
    reviews,env=fixture('mean_wave_period',unit='s',step=10800);result=run(reviews,env,duration_hours=6)
    assert result['current_assessment']['status']=='WORK'
    assert len(result['timeline'])==3 # two native cells and uncovered horizon
    times={v['valid_time'] for r in result['timeline'][0]['rule_results'] for c in r['checks'] for v in c['values']}
    assert times=={T.isoformat(),(T+timedelta(hours=3)).isoformat()} # Native period brackets only; no hourly values invented.
    assert result['timeline'][-1]['status']=='UNKNOWN'


def test_finer_provider_output_does_not_become_independent_native_evidence():
    reviews,env=fixture()
    env['requirements'][0]['evidence']['source_temporal_resolution_seconds']=10800
    result=run(reviews,env)
    assert result['current_assessment']['status']=='UNKNOWN'
    assert not result['candidate_windows']


def test_known_stop_preserved_when_later_requested_coverage_is_missing():
    reviews,env=fixture(hours=2,value=3)
    result=run(reviews,env,duration_hours=4)
    assert result['current_assessment']['status']=='STOP'
    assert result['timeline'][-1]['status']=='UNKNOWN'
    assert result['current_assessment']['evidence_gap_count']==1
    assert result['evidence_gaps'][0]['reason_code']=='FORECAST_COVERAGE_INSUFFICIENT'


@pytest.mark.parametrize('field,code',[('geographic_scope','SPATIAL_COVERAGE_INSUFFICIENT'),('temporal_requirement','TEMPORAL_COVERAGE_INSUFFICIENT')])
def test_changed_scope_cannot_reuse_incompatible_evidence(field,code):
    reviews,env=fixture();reviews['requirements'][0]['effective'][field]='New reviewed scope'
    assert run(reviews,env)['current_assessment']['rule_results'][0]['reason_code']==code


def test_missing_final_point_and_foreign_run_evidence_remain_unknown():
    reviews,env=fixture(hours=6);env['requirements'][0]['evidence']['points'].pop()
    assert not run(reviews,env,duration_hours=6)['candidate_windows']
    env['analysis_id']='other-run'
    assert run(reviews,env)['current_assessment']['status']=='UNKNOWN'


@pytest.mark.parametrize('hours,expected',[(5,0),(6,1)])
def test_required_six_hours_entire_duration(hours,expected):
    reviews,env=fixture(hours=hours);result=run(reviews,env,duration_hours=6)
    assert len(result['candidate_windows'])==expected
    if expected:assert result['candidate_windows'][0]['end']==(T+timedelta(hours=6)).isoformat()


def test_stop_splits_windows_and_conditional_toggle():
    reviews,env=fixture();env['requirements'][0]['evidence']['points'][2]['raw_value']=3
    assert not run(reviews,env,duration_hours=6)['candidate_windows']
    reviews,env=fixture();extra=deepcopy(reviews['requirements'][0]);extra.update(target_id='environmental_requirement-1-fingerprint')
    extra['mapping'][0]['requirement_index']=1;reviews['requirements'].append(extra)
    assert not run(reviews,env,duration_hours=6)['candidate_windows']
    windows=run(reviews,env,duration_hours=6,include_conditional=True)['candidate_windows']
    assert len(windows)==1 and windows[0]['status']=='UNKNOWN'


def test_ranking_deterministic_and_empty_rules_fail_closed():
    intervals=[{'start':(T+timedelta(hours=a)).isoformat(),'end':(T+timedelta(hours=b)).isoformat(),
        'status':s,'passed_count':1,'unknown_count':0,'primary_reason':'CONSTRAINT_PASSED'} for a,b,s in [(0,2,'WORK'),(2,3,'STOP'),(3,7,'WORK')]]
    assert find_windows(intervals,2,ranking='earliest')[0]['duration_hours']==2
    assert find_windows(intervals,2,ranking='longest')[0]['duration_hours']==4
    assert run({'analysis_run_id':'run','document_sha256':'a'*64,'requirements':[]},None)['current_assessment']['status']=='UNKNOWN'


def test_decision_api_only_reads_review_and_session_evidence(tmp_path,monkeypatch):
    from tests.test_review_overlays import fixture as write_fixture
    from src.permit import simple_api
    monkeypatch.setattr(simple_api,'analyze',lambda *a,**k:pytest.fail('No Analyze'))
    monkeypatch.setattr(simple_api,'evaluate',lambda *a,**k:pytest.fail('No Fetch'))
    analysis,path=write_fixture(tmp_path);before=path.read_bytes();app=simple_api.create_app(tmp_path);app.state.analyses[analysis['analysis_id']]=analysis
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            body={'analysis_run_id':analysis['analysis_id'],'document_sha256':analysis['document_sha256']}
            assert (await client.post('/api/decision/evaluate',json=body)).status_code==409
            response=await client.post('/api/decision/evaluate',headers={'x-session-id':app.state.boot_id},json=body)
            assert response.status_code==409 and response.json()['error']=='HUMAN_REVIEW_INCOMPLETE'
            assert response.json()['review_progress']['remaining']>0
            assert analysis['analysis_id'] not in app.state.decisions
    asyncio.run(check());assert path.read_bytes()==before
