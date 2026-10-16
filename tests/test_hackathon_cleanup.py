"""Post-baseline cleanup checks: local fixtures only, no provider calls."""
from copy import deepcopy
from datetime import timedelta, timezone
import pytest
from pydantic import ValidationError
from src.environmental.models import EvaluationInput
from src.environmental.limits import ENVIRONMENTAL_MAX_FETCH_HOURS, MAX_EVIDENCE_POINTS
from src.environmental.recency import TURBIDITY_MAX_AGE_HOURS, OXYGEN_MAX_AGE_HOURS, WAVE_HEIGHT_MAX_AGE_MINUTES
from src.environmental.service import evaluate, map_requirements
from src.environmental.fixture import mock_evidence
from tests.test_simple_environment import requirement, analysis
from tests.test_decision_engine import fixture, run, T


@pytest.mark.parametrize('hours',[48,72])
def test_fetch_accepts_boundary(hours):
    request=EvaluationInput(analysis_id='fixture',start_time=T,end_time=T+timedelta(hours=hours))
    assert request.end_time-request.start_time==timedelta(hours=hours)
    assert ENVIRONMENTAL_MAX_FETCH_HOURS==72


@pytest.mark.parametrize('delta',[timedelta(hours=72,microseconds=1),timedelta(hours=-1),timedelta(0)])
def test_invalid_fetch_period_rejected(delta):
    with pytest.raises(ValidationError):
        EvaluationInput(analysis_id='fixture',start_time=T,end_time=T+delta)


def test_offsets_preserved_and_naive_times_rejected():
    offset=timezone(timedelta(hours=3))
    start=T.astimezone(offset)
    request=EvaluationInput(analysis_id='fixture',start_time=start,end_time=start+timedelta(hours=72))
    assert request.start_time.utcoffset()==timedelta(hours=3)
    with pytest.raises(ValidationError):
        EvaluationInput(analysis_id='fixture',start_time=T.replace(tzinfo=None),end_time=T+timedelta(hours=72))


@pytest.mark.parametrize('variable,provider,step,expected_count',[
    ('surface_current_speed','COPERNICUS_MARINE',900,289),
    ('wind_speed_10m','ECMWF_FORECAST',3600,73)])
def test_72h_requested_window_reaches_provider_without_truncation(tmp_path,variable,provider,step,expected_count):
    raw=requirement(variable,operator='>',threshold=5,unit='m/s',depth_requirement=None,
        source_spans=[{'page':1,'quotation':f'STOP condition: {variable} > 5 m/s.'}])
    calls=[]
    def transport(request):
        calls.append(request)
        evidence=mock_evidence(request)
        evidence['points']=[{'data_time':(T+timedelta(seconds=i)).isoformat(),'raw_value':1,'unit':'m/s',
            'component_values':{'uo':.6,'vo':.8}} for i in range(0,72*3600+1,step)]
        return evidence
    inp=EvaluationInput(analysis_id='isolated-test',latitude=54,longitude=-6,start_time=T,end_time=T+timedelta(hours=72))
    out=evaluate(analysis(raw),inp,tmp_path,transports={provider:transport})
    assert len(calls)==1
    assert calls[0].start_time==T.isoformat() and calls[0].end_time==(T+timedelta(hours=72)).isoformat()
    evidence=out['requirements'][0]['evidence']
    assert len(evidence['points'])==expected_count and MAX_EVIDENCE_POINTS>=289
    assert evidence['temporal_coverage_status']=='COVERED'


@pytest.mark.parametrize('variable,depth,lookback,unit',[
    ('turbidity',None,72,'FNU'),('dissolved_oxygen',0,24,'mg/L')])
def test_reference_lookbacks_remain_separate_from_72h_fetch(tmp_path,variable,depth,lookback,unit):
    raw=requirement(variable,operator='>',threshold=5,unit=unit,
        depth_requirement='0 m below sea surface' if depth==0 else None,
        source_spans=[{'page':1,'quotation':f'{variable} at 0 m below sea surface. STOP condition: {variable} > 5 {unit}.'}])
    calls=[]
    def transport(request):
        calls.append(request)
        return mock_evidence(request)
    evaluate(analysis(raw),EvaluationInput(analysis_id='isolated-test',latitude=54,longitude=-6,depth=depth,
        start_time=T,end_time=T+timedelta(hours=72)),tmp_path,transports={'COPERNICUS_MARINE':transport})
    from datetime import datetime
    assert len(calls)==1
    assert datetime.fromisoformat(calls[0].provider_query_start)==T-timedelta(hours=lookback)
    assert calls[0].end_time==(T+timedelta(hours=72)).isoformat()
    assert (TURBIDITY_MAX_AGE_HOURS,OXYGEN_MAX_AGE_HOURS,WAVE_HEIGHT_MAX_AGE_MINUTES)==(72,24,90)


@pytest.mark.parametrize('variable,provider,condition,value',[
    ('mean_wave_direction','COPERNICUS_MARINE','5',241),
    ('surface_current_direction','COPERNICUS_MARINE','12',90),
    ('wind_direction_10m','ECMWF_FORECAST','8',180)])
@pytest.mark.parametrize('present',[True,False])
def test_informational_audit_links_existing_evidence_without_changing_decision(variable,provider,condition,value,present):
    reviews,env=fixture(); baseline=run(reviews,env)['current_assessment']
    raw=requirement(variable,condition_id=condition,threshold=None,operator=None,unit='degrees',depth_requirement=None,
        source_spans=[{'page':1,'quotation':'Direction is informational, in degrees.'}])
    mapping={**map_requirements(analysis(raw))[0],'requirement_index':1}
    info={**deepcopy(reviews['requirements'][0]),'target_id':'environmental_requirement-1-audit',
        'condition_id':condition,'decision_relevant_default':False,'original':raw,'effective':raw,'source':raw,'mapping':[mapping]}
    reviews['requirements'].append(info)
    if present:
        source_point={'data_time':T.isoformat(),'raw_value':value,'unit':'degree','status':'INFORMATIONAL','validation_notes':[]}
        if variable=='surface_current_direction':
            source_point.update(derived_from=['uo','vo'],component_values={'uo':1,'vo':0},
                derivation={'method':'ATAN2_U_V_TOWARDS_CLOCKWISE_FROM_NORTH'})
        evidence={**deepcopy(env['requirements'][0]['evidence']),'canonical_variable':variable,'provider':provider,
            'dataset_variable':'VMDR' if variable=='mean_wave_direction' else 'current_direction' if variable=='surface_current_direction' else 'wind_direction_10m',
            'points':[source_point],'direction_convention':'TOWARDS_CLOCKWISE_FROM_NORTH' if variable=='surface_current_direction' else 'PROVIDER_DEFINED_NOT_NORMALIZED'}
        env['requirements'].append({**mapping,'evidence':evidence,'retrieval_status':'FETCHED','evidence_request_key':'existing-evidence'})
    before=deepcopy((reviews,env))
    out=run(reviews,env)['current_assessment']
    row=next(r for r in out['rule_results'] if r['requirement_id']==info['target_id'])
    assert not row['gating'] and row['checks']==[]
    assert out['status']==baseline['status']=='WORK'
    assert (out['passed_count'],out['stop_count'],out['unknown_count'])==(baseline['passed_count'],baseline['stop_count'],baseline['unknown_count'])
    assert len(out['rule_results'])==len(baseline['rule_results'])+1
    audit=row['informational_evidence']
    if present:
        assert audit['status']=='INFORMATIONAL' and audit['points'][0]['value']==value
        assert audit['points'][0]['valid_time']==T.isoformat()
        assert audit['provenance']['provider']==provider
        assert audit['derived']==(variable=='surface_current_direction')
    else:
        assert audit['status']=='UNAVAILABLE' and not audit['points']
    assert (reviews,env)==before
