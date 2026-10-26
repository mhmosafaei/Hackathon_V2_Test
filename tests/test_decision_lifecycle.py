"""Ten mandatory constraints, explicit synthetic qualification, no live calls."""
from copy import deepcopy
from datetime import timedelta
import pytest
from src.permit.decision_engine import assess
from tests.test_decision_engine import fixture, T


def ten_requirements():
    cases=[('significant_wave_height',1.,1.5,'>','m'),('mean_wave_period',4.59,8.,'>','s'),
        ('wind_speed_10m',9.86,12.,'>','m/s'),('wind_gust',14.6,18.,'>','m/s'),
        ('surface_current_speed',.0253,1.,'>','m/s'),('eastward_current',.008,.6,'>','m/s'),
        ('northward_current',.024,.6,'>','m/s'),('visibility',4200,1000,'<','m'),
        ('turbidity',1.149,25,'>','FNU'),('dissolved_oxygen',7.96,6,'<','mg/L')]
    reviews,environment=fixture(hours=72)
    context_rows=reviews['requirements'][1:]
    reviews['requirements']=[];environment['requirements']=[]
    for index,(variable,value,threshold,operator,unit) in enumerate(cases):
        depth='0 m below sea surface' if variable=='dissolved_oxygen' else None
        text=f'{variable} '+('at 0 m below sea surface. ' if depth else '')+f'STOP condition: {variable} {operator} {threshold} {unit}.'
        step=86400 if variable in {'turbidity','dissolved_oxygen'} else 900 if variable in {'surface_current_speed','eastward_current','northward_current'} else 3600
        source,env=fixture(variable,hours=72,step=step,value=value,threshold=threshold,operator=operator,unit=unit,
            depth_requirement=depth,source_spans=[{'page':1,'quotation':text}])
        row=source['requirements'][0];row['condition_id']=f'source-{index}'
        row['target_id']=f'environmental_requirement-{index}-fixture'
        for mapping in row['mapping']: mapping.update(requirement_index=index,condition_id=row['condition_id'])
        record=env['requirements'][0];record.update(requirement_index=index,condition_id=row['condition_id'])
        record['request'].update(start_time=T.isoformat(),end_time=(T+timedelta(hours=72)).isoformat())
        evidence=record['evidence']
        evidence.update(selected_depth_m=0 if depth else None,
            data_type='SATELLITE_OBSERVATION' if variable=='turbidity' else 'MODEL_FORECAST',
            retrieval_status='SUCCESS',temporal_coverage_status='COVERED')
        for point in evidence['points']:
            point.update(normalized_unit=unit,normalized_value=point['raw_value'])
        reviews['requirements'].append(row);environment['requirements'].append(record)
    reviews['requirements'].extend(context_rows)
    return reviews,environment


@pytest.mark.parametrize('scenario,expected',[('UNKNOWN','UNKNOWN'),('STOP','STOP'),('WORK','WORK')])
def test_ten_requirement_lifecycle(scenario,expected):
    reviews,env=ten_requirements()
    if scenario=='UNKNOWN':
        for row in reviews['requirements'][:10]: row['applicability']='UNASSESSED'
    if scenario=='STOP':
        env['requirements'][0]['evidence']['points'][0]['raw_value']=1.9940000947
        env['requirements'][-1].pop('evidence')  # STOP must override simultaneous UNKNOWN.
    before=deepcopy((reviews,env))
    result=assess(reviews,env,start=T,now=T,horizon_hours=72,duration_hours=4)
    current=result['current_assessment']
    assert current['status']==expected
    assert current['start']==T.isoformat() and current['end']==(T+timedelta(hours=4)).isoformat()
    assert result['timeline'][-1]['end']==(T+timedelta(hours=72)).isoformat()
    diagnostics=[r['diagnostics'] for r in current['rule_results'] if r.get('diagnostics')]
    assert len(diagnostics)==10
    assert all(d['requested_interval']=={'start':T.isoformat(),'end':(T+timedelta(hours=4)).isoformat()} for d in diagnostics)
    assert all(d['evidence_availability']=='AVAILABLE' for d in diagnostics[:-1])
    if scenario=='UNKNOWN':
        assert current['unknown_count']==10 and not result['candidate_windows']
        assert all(d['evidence_eligibility']=='NOT_EVALUATED_REVIEW_BLOCKED' for d in diagnostics)
        assert all(d['issues'][0]['code']=='APPLICABILITY_UNASSESSED' for d in diagnostics)
    if scenario=='STOP':
        assert current['unknown_count']==1 and current['stop_count']>=1
        assert current['rule_results'][0]['violation_summary']['first_violation_timestamp']==T.isoformat()
    if scenario=='WORK':
        assert current['passed_count']==10 and current['unknown_count']==0
        assert all(d['threshold_result']=='WORK' for d in diagnostics)
        assert result['candidate_windows'] and all(w['duration_hours']>=4 for w in result['candidate_windows'])
    assert (reviews,env)==before


def test_diagnostics_distinguish_inventory_from_provider_failure_and_source_review():
    reviews,env=ten_requirements()
    for row in reviews['requirements'][:10]: row['applicability']='UNASSESSED'
    failed=env['requirements'][8]
    failed.pop('evidence')
    failed['provider_diagnostic']={'provider_error_category':'NO_COMPATIBLE_ACCESSIBLE_SOURCE',
        'provider_error_message':'No compatible unmasked FNU evidence.', 'provider':'COPERNICUS_MARINE'}
    result=assess(reviews,env,start=T,now=T,duration_hours=4)
    turbidity=result['current_assessment']['rule_results'][8]['diagnostics']
    assert turbidity['evidence_availability']=='RETRIEVAL_FAILED'
    assert [i['code'] for i in turbidity['issues']]==['APPLICABILITY_UNASSESSED','NO_COMPATIBLE_ACCESSIBLE_SOURCE']
    assert turbidity['threshold_result']=='NOT_EVALUATED'


def test_historical_october_13_stop_retains_native_violation_timestamp():
    reviews,env=ten_requirements()
    instant=T-timedelta(days=1)
    from datetime import datetime
    for record in env['requirements']:
        ev=record['evidence']
        ev['retrieved_at']=instant.isoformat()
        for p in ev['points']:
            for key in ('data_time','valid_start','valid_end'):
                if p.get(key): p[key]=(datetime.fromisoformat(p[key])-timedelta(days=1)).isoformat()
        for key in list(ev['coverage']):
            if key.endswith(('start','end')):
                ev['coverage'][key]=(datetime.fromisoformat(ev['coverage'][key])-timedelta(days=1)).isoformat()
        for key in ('start_time','end_time'):
            record['request'][key]=(datetime.fromisoformat(record['request'][key])-timedelta(days=1)).isoformat()
    env['requirements'][0]['evidence']['points'][0]['raw_value']=1.9940000947
    env['requirements'][-1].pop('evidence')
    result=assess(reviews,env,start=instant,now=instant,duration_hours=4)
    assert result['current_assessment']['status']=='STOP'
    wave=result['timeline'][0]['rule_results'][0]
    assert wave['violation_summary']['first_violation_timestamp']=='2026-10-13T00:00:00+00:00'
    assert wave['checks'][0]['operator']=='>' and wave['checks'][0]['threshold']==1.5
    assert result['current_assessment']['unknown_count']>=1
