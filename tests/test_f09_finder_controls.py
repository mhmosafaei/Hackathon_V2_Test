"""Finder request/session wiring; synthetic rules and in-process HTTP only."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import httpx
import pytest
from tests.test_decision_engine import fixture, T
from src.permit.decision_engine import assess, find_windows


def test_api_controls_reach_engine_and_session_without_transports(tmp_path,monkeypatch):
    from src.permit import simple_api
    from src.permit import decision_engine
    reviews,env=fixture(hours=6)
    analysis={'analysis_id':'run','document_sha256':'a'*64}
    monkeypatch.setattr(simple_api,'list_reviews',lambda *args:deepcopy(reviews))
    monkeypatch.setattr(simple_api,'analyze',lambda *a,**k:pytest.fail('Analyze forbidden'))
    monkeypatch.setattr(simple_api,'evaluate',lambda *a,**k:pytest.fail('Provider Fetch forbidden'))
    original=decision_engine.assess
    calls=[]
    def deterministic(*args,**kwargs):
        calls.append(deepcopy(kwargs))
        return original(*args,**kwargs,now=T)
    monkeypatch.setattr(decision_engine,'assess',deterministic)
    app=simple_api.create_app(tmp_path)
    app.state.analyses['run']=analysis
    app.state.environmental_results['run']=env
    before=deepcopy((analysis,env))
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            for start in [T.isoformat(),None]:
                body={'analysis_run_id':'run','document_sha256':'a'*64,'start':start,
                    'horizon_hours':24,'duration_hours':6,'ranking':'longest','include_conditional':True}
                response=await client.post('/api/decision/evaluate',json=body,headers={'x-session-id':app.state.boot_id})
                assert response.status_code==200
                result=response.json()
                assert calls[-1]=={k:v for k,v in body.items() if k not in {'analysis_run_id','document_sha256'}}
                assert result['audit']['requested_start']==start
                assert result['audit']['start']==T.isoformat()
                assert result['audit']['horizon_hours']==24
                assert result['audit']['duration_hours']==6
                assert result['audit']['ranking']=='longest'
                assert result['audit']['include_conditional'] is True
                for _ in range(2):
                    session=(await client.get('/api/session')).json()
                    assert session['decision_result']==result
            assert len(calls)==2
    asyncio.run(check())
    assert (analysis,env)==before
    assert list(tmp_path.iterdir())==[]


def test_horizon_changes_bounds_not_identical_interval_rules():
    reviews,env=fixture(hours=6)
    a=assess(reviews,env,start=T,now=T,horizon_hours=24,duration_hours=2)
    b=assess(reviews,env,start=T,now=T,horizon_hours=72,duration_hours=2)
    assert a['timeline'][-1]['end']==(T+timedelta(hours=24)).isoformat()
    assert b['timeline'][-1]['end']==(T+timedelta(hours=72)).isoformat()
    assert a['timeline'][0]['rule_results']==b['timeline'][0]['rule_results']


def test_duration_ranking_and_conditional_change_only_selection():
    timeline=[{'start':(T+timedelta(hours=a)).isoformat(),'end':(T+timedelta(hours=b)).isoformat(),
        'status':state,'passed_count':1,'unknown_count':int(state=='UNKNOWN'),'primary_reason':'fixture'}
        for a,b,state in [(0,2,'WORK'),(2,3,'STOP'),(3,10,'WORK'),(10,11,'STOP'),(11,17,'UNKNOWN')]]
    before=deepcopy(timeline)
    assert len(find_windows(timeline,2))==2
    assert len(find_windows(timeline,6))==1
    assert find_windows(timeline,2,ranking='earliest')[0]['start']==T.isoformat()
    assert find_windows(timeline,2,ranking='longest')[0]['duration_hours']==7
    with_conditional=find_windows(timeline,6,include_conditional=True)
    assert len(with_conditional)==2 and any(w['type']=='CONDITIONAL' for w in with_conditional)
    assert timeline==before
