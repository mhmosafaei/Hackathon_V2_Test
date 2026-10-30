from datetime import datetime,timezone,timedelta
import json
import pytest
from src.environmental.download_cache import prepare_cache,normalized,period_available
from src.environmental.service import evaluate
from src.environmental.fixture import mock_evidence
from tests.test_simple_environment import analysis,requirement,inputs

def test_same_downloaded_period_reuses_old_values_and_never_retries_missing_variables(tmp_path):
    query=inputs()
    document=analysis(requirement('wind_speed_10m',unit='m/s'))
    evaluate(document,query,tmp_path,transports={'ECMWF_FORECAST':mock_evidence})
    path=next(tmp_path.glob('*.json'))
    cached=json.loads(path.read_text())
    old_time=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
    cached['evidence']['retrieved_at']=old_time
    path.write_text(json.dumps(cached))
    calls=[]
    def provider(request): calls.append(request);raise AssertionError('Provider must not be called')
    document['environmental_requirements'].append(requirement('wind_gust',unit='m/s',condition_id='2'))
    result=evaluate(document,query,tmp_path,transports={'ECMWF_FORECAST':provider},reuse_downloaded=True)
    assert result['reused_downloaded_period']
    assert calls==[]
    assert result['requirements'][0]['cache_state']=='CACHED'
    assert result['requirements'][0]['evidence']['retrieved_at']==old_time
    assert result['requirements'][1]['provider_diagnostic']['provider_error_category']=='CACHED_EVIDENCE_UNAVAILABLE'
    assert json.loads(path.read_text())['evidence']['retrieved_at']==old_time

def test_a_different_period_still_uses_normal_retrieval(tmp_path):
    query=inputs();document=analysis(requirement('wind_speed_10m',unit='m/s'))
    evaluate(document,query,tmp_path,transports={'ECMWF_FORECAST':mock_evidence})
    changed=query.model_copy(update={'start_time':query.start_time+timedelta(hours=4),'end_time':query.end_time+timedelta(hours=4)})
    calls=[]
    def provider(request): calls.append(request);return mock_evidence(request)
    result=evaluate(document,changed,tmp_path,transports={'ECMWF_FORECAST':provider},reuse_downloaded=True)
    assert not result['reused_downloaded_period']
    assert len(calls)==1

def test_timezone_equivalent_cache_requests_match_without_shifting_source_values():
    utc={'provider_query_start':'2026-10-31T00:00:00Z','provider_query_end':'2026-11-03T00:00:00Z'}
    offset={'provider_query_start':'2026-10-31T01:00:00+01:00','provider_query_end':'2026-11-03T01:00:00+01:00'}
    assert normalized(utc)==normalized(offset)

def test_migrates_existing_downloads_with_live_mock_separation_and_rejects_path_traversal(tmp_path):
    original=tmp_path/'cache/simple_environment/old-session/run'
    original.mkdir(parents=True)
    for name,dataset in [('real','real-dataset'),('mock','SYNTHETIC-OFFLINE-FIXTURE')]:
        (original/f'{name}.json').write_text(json.dumps({'retrieval':{},'evidence':{'dataset_id':dataset,'retrieved_at':'2026-10-30T12:00Z'}}))
    saved=prepare_cache(tmp_path,'run')
    assert [p.name for p in saved.glob('*.json')]==['real.json']
    assert (original/'real.json').exists()
    assert [p.name for p in prepare_cache(tmp_path,'run',mock=True).glob('*.json')]==['mock.json']
    with pytest.raises(ValueError): prepare_cache(tmp_path,'../other')
