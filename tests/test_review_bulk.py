import asyncio
import json
from copy import deepcopy

import httpx
import pytest

from tests.test_review_overlays import fixture
from src.permit.review_overlays import list_reviews, save_review, bulk_approve


def setup(root):
    analysis,path=fixture(root)
    base=analysis['environmental_requirements'][0]
    analysis['environmental_requirements']=[{**deepcopy(base),'condition_id':str(i),'source_verified':i!=1} for i in range(7)]
    path.write_text(json.dumps(analysis))
    return analysis,path


def put(root,analysis,index,state='UNREVIEWED',applicability='UNASSESSED',note='Existing note'):
    row=list_reviews(root,analysis)['requirements'][index]
    return save_review(root,analysis,row['target_id'],{'original_fingerprint':row['original_fingerprint'],
        'state':state,'applicability':applicability,'corrections':{'threshold':10} if state=='CORRECTED' else {},
        'reviewer':'Previous reviewer','note':note})


def test_bulk_preserves_reviewed_applicability_notes_history_and_original(tmp_path):
    analysis,path=setup(tmp_path)
    put(tmp_path,analysis,0,applicability='APPLICABLE')
    put(tmp_path,analysis,2,state='APPROVED')
    put(tmp_path,analysis,3,state='CORRECTED')
    put(tmp_path,analysis,4,state='REJECTED')
    put(tmp_path,analysis,5,applicability='NOT_APPLICABLE',note='Outside scope')
    rows=list_reviews(tmp_path,analysis)['requirements']; before=path.read_bytes(); memory=deepcopy(analysis)
    preserved={r['target_id']:r['review'] for r in rows if r['review'] and r['state']!='UNREVIEWED' or r['applicability']=='NOT_APPLICABLE'}
    result=bulk_approve(tmp_path,analysis,'Bulk reviewer',{r['target_id']:r['original_fingerprint'] for r in rows})
    assert (result['eligible_count'],result['approved_count'],result['skipped_count'],result['failed_count'])==(2,2,5,0)
    assert result['requirements'][1]['state']=='UNREVIEWED'
    assert result['requirements'][0]['applicability']=='APPLICABLE'
    assert result['requirements'][0]['review']['note']=='Existing note'
    assert result['requirements'][0]['review']['reviewed_at'].endswith('+00:00')
    for row in result['requirements']:
        if row['target_id'] in preserved: assert row['review']==preserved[row['target_id']]
    store=tmp_path/'cache'/'simple_reviews'/analysis['document_sha256']/analysis['analysis_id']/'review_overlays.json'
    assert len(json.loads(store.read_text())['history'])==7
    assert path.read_bytes()==before and analysis==memory


def test_conflicts_and_stale_fingerprints_do_not_block_other_eligible_records(tmp_path):
    analysis,_=setup(tmp_path);put(tmp_path,analysis,0)
    store=tmp_path/'cache'/'simple_reviews'/analysis['document_sha256']/analysis['analysis_id']/'review_overlays.json'
    saved=json.loads(store.read_text());next(iter(saved['overlays'].values()))['original_fingerprint']='wrong';store.write_text(json.dumps(saved))
    rows=list_reviews(tmp_path,analysis)['requirements'];expected={r['target_id']:r['original_fingerprint'] for r in rows};expected[rows[2]['target_id']]='stale'
    result=bulk_approve(tmp_path,analysis,'Tester',expected)
    assert result['approved_count']==4 and result['failed_count']==1 and result['skipped_count']==2
    assert result['requirements'][0]['conflict']=='REVIEW_CONFLICT'
    assert result['requirements'][2]['state']=='UNREVIEWED'
    assert next(r for r in result['results'] if r['target_id']==rows[2]['target_id'])['reason']=='REVIEW_FINGERPRINT_CONFLICT'


def test_no_eligible_no_write_and_unknown_target_rejected(tmp_path):
    analysis,_=setup(tmp_path)
    for row in analysis['environmental_requirements']: row['source_verified']=False
    assert bulk_approve(tmp_path,analysis,'Tester',{})['approved_count']==0
    assert not (tmp_path/'cache'/'simple_reviews').exists()
    with pytest.raises(ValueError,match='UNKNOWN_REVIEW_TARGET'):bulk_approve(tmp_path,analysis,'Tester',{'unknown':'hash'})


def test_bulk_atomic_write_failure_retains_previous_store(tmp_path,monkeypatch):
    from src.permit import review_overlays
    analysis,_=setup(tmp_path);put(tmp_path,analysis,0)
    store=tmp_path/'cache'/'simple_reviews'/analysis['document_sha256']/analysis['analysis_id']/'review_overlays.json'
    before=store.read_bytes();rows=list_reviews(tmp_path,analysis)['requirements']
    def fail(*args):raise OSError('test failure')
    monkeypatch.setattr(review_overlays.os,'replace',fail)
    with pytest.raises(OSError):bulk_approve(tmp_path,analysis,'Tester',{r['target_id']:r['original_fingerprint'] for r in rows})
    assert store.read_bytes()==before


def test_invalid_interpretation_skipped_without_blocking_valid_pending(tmp_path):
    analysis,path=setup(tmp_path)
    analysis['environmental_requirements'][0]['operator']='invalid'
    path.write_text(json.dumps(analysis))
    rows=list_reviews(tmp_path,analysis)['requirements']
    assert rows[0]['bulk_eligible'] is False
    result=bulk_approve(tmp_path,analysis,'Tester',{r['target_id']:r['original_fingerprint'] for r in rows})
    assert result['approved_count']==5
    assert result['requirements'][0]['state']=='UNREVIEWED'
    assert result['results'][0]['reason']=='THRESHOLD_UNIT_OPERATOR_REQUIRED'


def test_bulk_api_identity_session_and_no_transport_calls(tmp_path,monkeypatch):
    from src.permit import simple_api
    monkeypatch.setattr(simple_api,'analyze',lambda *a,**k:pytest.fail('No Analyze'))
    monkeypatch.setattr(simple_api,'evaluate',lambda *a,**k:pytest.fail('No Fetch'))
    analysis,path=setup(tmp_path);before=path.read_bytes();app=simple_api.create_app(tmp_path);app.state.analyses[analysis['analysis_id']]=analysis
    rows=list_reviews(tmp_path,analysis)['requirements']
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            body={'analysis_run_id':analysis['analysis_id'],'document_sha256':analysis['document_sha256'],
                  'reviewer':'Tester','targets':{r['target_id']:r['original_fingerprint'] for r in rows}}
            headers={'x-session-id':app.state.boot_id}
            assert (await client.put('/api/reviews/bulk-approve',json=body)).status_code==409
            assert (await client.put('/api/reviews/bulk-approve',headers=headers,json={**body,'document_sha256':'f'*64})).status_code==409
            assert (await client.put('/api/reviews/bulk-approve',headers=headers,json={**body,'analysis_run_id':'c'*32})).status_code==409
            result=await client.put('/api/reviews/bulk-approve',headers=headers,json=body)
            assert result.status_code==200 and result.json()['approved_count']==6
            again=await client.put('/api/reviews/bulk-approve',headers=headers,json=body)
            assert again.json()['approved_count']==0
    asyncio.run(check());assert path.read_bytes()==before
