"""Safety regressions: synthetic source/model/provider fixtures only."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import json
from hashlib import sha256
import httpx
import pymupdf
import pytest

from src.permit.decision_engine import assess, evaluate_requirement
from tests.test_decision_engine import fixture, run, T


def test_known_wave_exceedance_stop_and_violation_audit():
    reviews,env=fixture(value=1.994,threshold=1.5)
    result=run(reviews,env)
    assert result['current_assessment']['status']=='STOP'
    rule=result['timeline'][0]['rule_results'][0]
    assert rule['violation_summary']['first_violation_timestamp']==T.isoformat()
    assert rule['violation_summary']['maximum_value']==1.994
    assert rule['checks'][0]['values'][0]['raw_value']==1.994


@pytest.mark.parametrize('fault,code',[
    ('applicability','APPLICABILITY_UNASSESSED'),('review','REVIEW_REQUIRED'),
    ('mapping','EVIDENCE_UNSUPPORTED'),('threshold','INTERPRETATION_REQUIRED')])
def test_zero_evaluated_required_numerical_rules_cannot_work(fault,code):
    reviews,env=fixture(value=1.994,threshold=1.5)
    row=reviews['requirements'][0]
    if fault=='applicability': row['applicability']='UNASSESSED'
    if fault=='review': row['state']='UNREVIEWED'
    if fault=='mapping': row['mapping']=[]
    if fault=='threshold': row['effective']['threshold']=None;row['effective']['operator']=None
    result=run(reviews,env)
    assert result['current_assessment']['status']=='UNKNOWN'
    assert result['current_assessment']['passed_count']==0
    assert result['current_assessment']['unknown_count']>=1
    assert result['timeline'][0]['rule_results'][0]['reason_code']==code
    assert not result['candidate_windows']


def test_wind_trigger_inside_twelve_hour_window_breaks_candidate():
    reviews,env=fixture('wind_speed_10m',hours=12,unit='m/s',threshold=12,value=9.86)
    env['requirements'][0]['evidence']['points'][6]['raw_value']=12.1
    result=run(reviews,env,duration_hours=12,horizon_hours=24)
    assert result['current_assessment']['status']=='STOP'
    assert not result['candidate_windows']
    assert any(cell['status']=='STOP' for cell in result['timeline'] if cell['start'] <= (T+timedelta(hours=6)).isoformat())


def test_clip_only_to_explicit_request_bounds_never_extend_windows():
    reviews,env=fixture(hours=48)
    env['requirements'][0]['request'].update(start_time=T.isoformat(),end_time=(T+timedelta(hours=48)).isoformat())
    result=run(reviews,env,duration_hours=12,horizon_hours=72)
    assert result['timeline'][-1]['end']==(T+timedelta(hours=48)).isoformat()
    assert result['audit']['clipped_to_confirmed_request'] is True
    assert all(window['end']<=result['audit']['end'] for window in result['candidate_windows'])
    env['requirements'][0]['request']['end_time']=(T+timedelta(hours=1)).isoformat()
    assert run(reviews,env,duration_hours=12)['current_assessment']['status']=='UNKNOWN'


@pytest.mark.parametrize('mutation',['evidence','mapping','review'])
def test_offline_pdf_ingestion_reviews_evidence_api_and_invalidation(tmp_path,monkeypatch,mutation):
    from src.permit.simple_analysis import analyze, response_schema
    from src.permit.simple_fixture import mock_request
    from src.permit import simple_api, decision_engine
    from src.permit.review_overlays import list_reviews, save_review
    text='1. Significant wave height shall be assessed in metres. STOP condition: significant wave height > 1.5 m.'
    pdf=pymupdf.open();pdf.new_page().insert_textbox((40,40,550,300),text)
    content=pdf.tobytes();pdf.close()
    calls=[]
    def model(packet):
        calls.append(1)
        response=mock_request(packet)
        quote=packet['pages'][0].text.strip()
        response['conditions']=response['conditions'][:1]
        record={**fixture(threshold=1.5)[0]['requirements'][0]['original'],
            'condition_id':'1','requirement_text':text,'source_spans':[{'page':1,'quotation':quote}]}
        response['environmental_requirements']=[{key:record.get(key) for key in response_schema()['properties']['environmental_requirements']['items']['properties']}]
        return response
    analysis=analyze(content,'offline.pdf',tmp_path,transport=model)
    analysis['document_sha256']=sha256(content).hexdigest()  # Same API response identity enrichment.
    assert len(calls)==1 and analysis['environmental_extraction']['complete']
    raw_reviews=list_reviews(tmp_path,analysis)
    for row in raw_reviews['requirements']:
        save_review(tmp_path,analysis,row['target_id'],{'state':'APPROVED','applicability':'APPLICABLE',
            'original_fingerprint':row['original_fingerprint'],'reviewer':'Offline tester','note':'Source checked','corrections':{}})
    # Supply explicitly verified time/position prerequisite fixtures; never infer geometry.
    context=fixture()[0]['decision_context']
    actual_reviews=list_reviews(tmp_path,analysis)
    actual_reviews['decision_context']=context
    # Match prerequisite source review references through fixture reviewed context rows.
    actual_reviews['requirements'].extend(fixture()[0]['requirements'][1:])
    _,env=fixture(value=1.994,threshold=1.5)
    env['analysis_id']=analysis['analysis_id']
    env['requirements'][0].update(condition_id='1',threshold=1.5)
    monkeypatch.setattr(simple_api,'list_reviews',lambda *_:deepcopy(actual_reviews))
    original=decision_engine.assess
    monkeypatch.setattr(decision_engine,'assess',lambda *a,**k:original(*a,**k,now=T))
    app=simple_api.create_app(tmp_path)
    app.state.analyses[analysis['analysis_id']]=analysis
    app.state.environmental_results[analysis['analysis_id']]=env
    path=tmp_path/'cache'/'simple_analysis'/analysis['document_sha256']/analysis['analysis_id']/'analysis.json'
    before=path.read_bytes()
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            body={'analysis_run_id':analysis['analysis_id'],'document_sha256':analysis['document_sha256'],
                  'start':T.isoformat(),'horizon_hours':24,'duration_hours':4}
            response=await client.post('/api/decision/evaluate',json=body,headers={'x-session-id':app.state.boot_id})
            assert response.status_code==200
            result=response.json()
            assert result['current_assessment']['status']=='STOP'
            assert (await client.get('/api/session')).json()['decision_result']==result
            if mutation=='evidence': env['requirements'][0]['evidence']['points'][0]['raw_value']=1
            if mutation=='mapping': actual_reviews['requirements'][1]['mapping']=[]
            if mutation=='review': actual_reviews['requirements'][1]['applicability']='UNASSESSED'
            session=(await client.get('/api/session')).json()
            assert session['decision_result'] is None
            assert session['invalidated_assessment_id']==result['assessment_id']
    asyncio.run(check())
    assert path.read_bytes()==before
