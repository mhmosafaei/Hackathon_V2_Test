import asyncio
import json
from copy import deepcopy

import httpx
import pytest

from src.permit.review_overlays import list_reviews, save_review
from src.permit.persisted_analysis import load_persisted_analysis


def fixture(root, digest='a'*64, run='b'*32):
    record = {'condition_id':'x','requirement_text':'Wind above 12 m/s', 'variable':'wind speed',
              'canonical_variable':'wind_speed_10m','operator':'>','threshold':12,'unit':'m/s',
              'source_page':1,'source_spans':[{'page':1,'quotation':'Wind above 12 m/s'}],
              'source_verified':False,'evidence_type':'forecast','review_state':'UNREVIEWED','executable':False}
    analysis = {'analysis_id':run,'document_sha256':digest,'conditions':[], 'environmental_requirements':[record],
                'environmental_extraction':{'complete':True,'candidate_conditions':['x']},'geofences':[]}
    folder=root/'cache'/'simple_analysis'/digest/run
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'analysis.json').write_text(json.dumps(analysis),encoding='utf-8')
    (folder/'manifest.json').write_text(json.dumps({'run_id':run,'document_sha256':digest}),encoding='utf-8')
    return analysis, folder/'analysis.json'


def save(root, analysis, **extra):
    row=list_reviews(root,analysis)['requirements'][0]
    data={'state':'APPROVED','applicability':'UNASSESSED','reviewer':'Tester','note':'',
          'corrections':{},'original_fingerprint':row['original_fingerprint'],**extra}
    return save_review(root,analysis,row['target_id'],data)['requirements'][0]


@pytest.mark.parametrize('state',['APPROVED','CORRECTED','REJECTED','UNREVIEWED'])
def test_states_persist_without_mutation(tmp_path,state):
    analysis,path=fixture(tmp_path); before=path.read_bytes(); memory=deepcopy(analysis)
    assert list_reviews(tmp_path,analysis)['requirements'][0]['state']=='UNREVIEWED'
    changes={'threshold':10} if state=='CORRECTED' else {}
    row=save(tmp_path,analysis,state=state,corrections=changes)
    restored=load_persisted_analysis(tmp_path,analysis['document_sha256'],analysis['analysis_id'])
    again=list_reviews(tmp_path,restored)['requirements'][0]
    assert again['state']==state
    assert again['applicability']=='UNASSESSED'
    assert row['original']['threshold']==12
    assert row['original']['source_verified'] is False
    if state=='CORRECTED': assert row['effective']['threshold']==10
    if state=='REJECTED': assert row['effective'] is None
    assert path.read_bytes()==before and analysis==memory


def test_applicability_independent_and_note_required(tmp_path):
    analysis,_=fixture(tmp_path)
    with pytest.raises(ValueError,match='NOTE_REQUIRED'):save(tmp_path,analysis,applicability='NOT_APPLICABLE')
    row=save(tmp_path,analysis,state='REJECTED',applicability='NOT_APPLICABLE',note='Outside selected scope')
    assert row['applicability']=='NOT_APPLICABLE'
    assert save(tmp_path,analysis,state='REJECTED')['applicability']=='UNASSESSED'


@pytest.mark.parametrize('changes',[{'threshold':'bad'},{'threshold':float('nan')},{'threshold':float('inf')},
    {'threshold':True},{'source_verified':True},{'source_page':4},{'operator':'nonsense'},{'unit':''},
    {'unit':None},{'canonical_variable':None},{'variable':[]},{'operator':[]},{'threshold':10,'operator':None}])
def test_invalid_corrections_rejected(tmp_path,changes):
    analysis,_=fixture(tmp_path)
    with pytest.raises(ValueError):save(tmp_path,analysis,state='CORRECTED',corrections=changes)


def test_fingerprint_conflict(tmp_path):
    analysis,path=fixture(tmp_path)
    with pytest.raises(ValueError,match='FINGERPRINT'):save(tmp_path,analysis,original_fingerprint='wrong')
    save(tmp_path,analysis)
    store=tmp_path/'cache'/'simple_reviews'/analysis['document_sha256']/analysis['analysis_id']/'review_overlays.json'
    data=json.loads(store.read_text()); next(iter(data['overlays'].values()))['original_fingerprint']='wrong'
    store.write_text(json.dumps(data))
    assert list_reviews(tmp_path,analysis)['requirements'][0]['conflict']=='REVIEW_CONFLICT'
    with pytest.raises(ValueError,match='CONFLICT'):save(tmp_path,analysis)


def test_identity_isolation_and_malformed_store(tmp_path):
    analysis,_=fixture(tmp_path); save(tmp_path,analysis)
    for digest,run in [('c'*64,'b'*32),('a'*64,'d'*32)]:
        other,_=fixture(tmp_path,digest,run)
        assert list_reviews(tmp_path,other)['requirements'][0]['state']=='UNREVIEWED'
    store=tmp_path/'cache'/'simple_reviews'/analysis['document_sha256']/analysis['analysis_id']/'review_overlays.json'
    store.write_text('[]')
    with pytest.raises(ValueError,match='MALFORMED'):list_reviews(tmp_path,analysis)


def test_relevance_thresholds_informational_and_embedded_checks(tmp_path):
    analysis,path=fixture(tmp_path)
    assert list_reviews(tmp_path,analysis)['requirements'][0]['decision_relevant_default']
    doc=json.loads(path.read_text()); row=doc['environmental_requirements'][0]
    row.update(threshold=None,operator=None,requirement_text='Direction is informational')
    path.write_text(json.dumps(doc))
    assert not list_reviews(tmp_path,doc)['requirements'][0]['decision_relevant_default']
    row.update(requirement_text='Temperature below -2 deg C or above 25 deg C flagged for review')
    path.write_text(json.dumps(doc))
    assert list_reviews(tmp_path,doc)['requirements'][0]['decision_relevant_default']


def test_api_offline_session_unknown_target_and_cross_analysis(tmp_path,monkeypatch):
    from src.permit import simple_api
    monkeypatch.setattr(simple_api,'analyze',lambda *a,**k:pytest.fail('No Analyze'))
    monkeypatch.setattr(simple_api,'evaluate',lambda *a,**k:pytest.fail('No provider fetch'))
    analysis,path=fixture(tmp_path); before=path.read_bytes()
    app=simple_api.create_app(tmp_path); app.state.analyses[analysis['analysis_id']]=analysis
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            url=f"/api/reviews?analysis_id={analysis['analysis_id']}"
            assert (await client.get(url)).status_code==409
            headers={'x-session-id':app.state.boot_id}
            response=await client.get(url,headers=headers); assert response.status_code==200
            row=response.json()['requirements'][0]
            body={'analysis_run_id':analysis['analysis_id'],'document_sha256':analysis['document_sha256'],
                  'review':{'original_fingerprint':row['original_fingerprint'],'state':'APPROVED',
                            'applicability':'APPLICABLE','corrections':{},'reviewer':'Tester','note':''}}
            assert (await client.put('/api/reviews/'+row['target_id'],headers=headers,json=body)).status_code==200
            assert (await client.put('/api/reviews/unknown',headers=headers,json=body)).status_code==422
            body['document_sha256']='f'*64
            assert (await client.put('/api/reviews/'+row['target_id'],headers=headers,json=body)).status_code==409
    asyncio.run(check()); assert path.read_bytes()==before


def test_api_restart_restore_reloads_overlay_without_providers(tmp_path,monkeypatch):
    from src.permit import simple_api
    monkeypatch.setattr(simple_api,'analyze',lambda *a,**k:pytest.fail('No Analyze'))
    monkeypatch.setattr(simple_api,'evaluate',lambda *a,**k:pytest.fail('No Fetch'))
    analysis,path=fixture(tmp_path); before=path.read_bytes()
    save(tmp_path,analysis,state='CORRECTED',corrections={'threshold':10})
    app=simple_api.create_app(tmp_path)
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            headers={'x-session-id':app.state.boot_id}
            restored=await client.post('/api/restore',headers=headers,json={'document_sha256':analysis['document_sha256'],'analysis_run_id':analysis['analysis_id']})
            assert restored.status_code==200
            response=await client.get('/api/reviews',headers=headers,params={'analysis_id':analysis['analysis_id']})
            row=response.json()['requirements'][0]
            assert row['state']=='CORRECTED' and row['effective']['threshold']==10
            assert row['source']['source_verified'] is False
    asyncio.run(check()); assert path.read_bytes()==before


def test_atomic_failure_preserves_previous_review_and_history(tmp_path,monkeypatch):
    from src.permit import review_overlays
    analysis,_=fixture(tmp_path); save(tmp_path,analysis)
    path=tmp_path/'cache'/'simple_reviews'/analysis['document_sha256']/analysis['analysis_id']/'review_overlays.json'
    before=path.read_bytes()
    def fail(*args): raise OSError('test failure')
    monkeypatch.setattr(review_overlays.os,'replace',fail)
    with pytest.raises(OSError):save(tmp_path,analysis,state='REJECTED')
    assert path.read_bytes()==before and not list(path.parent.glob('*.tmp'))
    assert len(json.loads(path.read_text())['history'])==1
