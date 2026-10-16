"""Recency rules use native synthetic evidence only, never live transports."""
from copy import deepcopy
from datetime import timedelta
import pytest
from src.environmental.recency import select
from src.permit.decision_engine import evaluate_requirement
from tests.test_decision_engine import fixture, T


def point(age, unit='FNU', value=24):
    return {'data_time':(T-timedelta(hours=age)).isoformat(),'raw_value':value,'unit':unit}


@pytest.mark.parametrize('age',[0,24,71+59/60,72])
def test_turbidity_inclusive_age_and_native_timestamp(age):
    p=point(age); selected, audit=select([p],T,'turbidity')
    assert selected is p and audit['age_hours']==pytest.approx(age)
    assert audit['source_timestamp']==p['data_time']
    assert 'valid_start' not in selected and 'valid_end' not in selected


@pytest.mark.parametrize('variable,depth,age,code',[
    ('turbidity',None,72.001,'STALE_TURBIDITY_EVIDENCE'),
    ('dissolved_oxygen',0,24.001,'STALE_OXYGEN_EVIDENCE')])
def test_stale_reference_fails_closed(variable,depth,age,code):
    p=point(age,'FNU' if variable=='turbidity' else 'mg/L')
    selected,audit=select([p],T,variable,depth)
    assert selected is None and audit['reason_code']==code


def test_latest_compatible_observation_not_future_or_ntu():
    points=[point(30),point(24),point(-1),point(1,'NTU')]
    selected,_=select(points,T,'turbidity')
    assert selected is points[1]
    assert select([point(1,'NTU')],T,'turbidity')[0] is None


@pytest.mark.parametrize('age',[6,24])
def test_zero_depth_model_daily_age_inclusive(age):
    p=point(age,'mmol m-3',200)
    selected,audit=select([p],T,'dissolved_oxygen',0)
    assert selected is p and audit['age_hours']==age


@pytest.mark.parametrize('variable,depth,age,value,state',[
    ('turbidity',None,24,26,'STOP'),('turbidity',None,24,25,'WORK'),
    ('turbidity',None,73,24,'UNKNOWN'),
    ('dissolved_oxygen',0,6,5.9,'STOP'),('dissolved_oxygen',0,6,6,'WORK'),
    ('dissolved_oxygen',0,25,7,'UNKNOWN')])
def test_f09_reference_threshold_and_provenance(variable,depth,age,value,state):
    unit='FNU' if variable=='turbidity' else 'mg/L'
    operator='>' if variable=='turbidity' else '<'
    threshold=25 if variable=='turbidity' else 6
    text=f'{variable}' + (' at 0 m below sea surface.' if depth == 0 else '.') + f' STOP condition: {variable} {operator} {threshold} {unit}.'
    reviews,env=fixture(variable,unit=unit,operator=operator,threshold=threshold,
        depth_requirement='0 m below sea surface' if depth==0 else None,
        source_spans=[{'page':1,'quotation':text}])
    evidence=env['requirements'][0]['evidence']
    evidence.update(points=[point(age,unit,value)],temporal_resolution=86400,
        selected_depth_m=depth,requested_depth_m=depth,
        data_type='SATELLITE_OBSERVATION' if variable=='turbidity' else 'MODEL_FORECAST')
    evidence['coverage']['temporal_resolution_seconds']=86400
    before=deepcopy((reviews,env))
    result=evaluate_requirement(reviews['requirements'][0],env,T,T+timedelta(hours=2),T,set())
    assert result['status']==state
    assert result['evidence_references'][0]['recency_policy']['source_timestamp']==evidence['points'][0]['data_time']
    assert (reviews,env)==before


def test_service_lookback_is_bounded_single_dispatch_and_reference_screened(tmp_path):
    from src.environmental.service import evaluate
    from tests.test_simple_environment import requirement, analysis, inputs
    from datetime import datetime, timezone
    now=datetime.now(timezone.utc)
    calls=[]
    def transport(request):
        calls.append(request)
        reference=datetime.fromisoformat(request.start_time)
        return {'canonical_variable':'turbidity','provider':'COPERNICUS_MARINE',
            'dataset_id':request.dataset_id,'dataset_variable':'TUR','data_type':'SATELLITE_OBSERVATION',
            'retrieved_at':now.isoformat(),'requested_coordinates':[54,-6],
            'latitude':54,'longitude':-6,'distance_km':0,'quality_status':'SUITABLE',
            'points':[{'data_time':(reference-timedelta(hours=24)).isoformat(),'raw_value':2,'unit':'FNU'}]}
    raw=requirement('turbidity',unit='FNU',operator='>',threshold=25,evidence_type='observation',
        requirement_text='Turbidity > 25 FNU.',source_spans=[{'page':1,'quotation':'Turbidity > 25 FNU.'}])
    result=evaluate(analysis(raw),inputs(),tmp_path,transports={'COPERNICUS_MARINE':transport})
    assert len(calls)==1
    assert (datetime.fromisoformat(calls[0].start_time)-datetime.fromisoformat(calls[0].provider_query_start)).total_seconds()==72*3600
    evidence=result['requirements'][0]['evidence']
    assert evidence['threshold_evaluation']=='NOT_TRIGGERED'
    assert evidence['temporal_coverage_status']=='REFERENCE_EVIDENCE_ONLY'
    assert evidence['recency_policy']['age_hours']==24


def test_reference_must_not_extend_past_age_limit_inside_work_interval():
    from tests.test_oxygen_native_cadence import oxygen
    reviews,env=oxygen(86400)
    env['requirements'][0]['evidence']['points']=[point(23,'mg/L',7)]
    result=evaluate_requirement(reviews['requirements'][0],env,T,T+timedelta(hours=2),T,set())
    assert result['status']=='UNKNOWN'
    assert result['reason_code']=='STALE_OXYGEN_EVIDENCE'


def test_oxygen_observation_cannot_be_relabelled_modelled():
    from tests.test_oxygen_native_cadence import oxygen
    reviews,env=oxygen(86400)
    env['requirements'][0]['evidence']['data_type']='OBSERVATION'
    result=evaluate_requirement(reviews['requirements'][0],env,T,T+timedelta(hours=2),T,set())
    assert result['status']=='UNKNOWN'
    assert result['reason_code']=='NO_COMPATIBLE_OXYGEN_SOURCE'
