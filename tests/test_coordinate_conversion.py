"""Offline-only coordinate endpoint/SDK mocks. Never invokes environmental providers."""
from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletion
from src.permit.simple_api import create_app
from src.permit.coordinate_conversion import convert, validate_response, response_schema
from src.documents.extractor import CandidateResponseError

LOCATION = dict(location_name='Burren Roundabout, Warrenpoint, County Down',
    coordinates_original='IGR 312890E 319096N', coordinate_system='IGR',
    easting=312890, northing=319096, geometry_type='point', source_verified=True)
RESULT = dict(source_coordinate_system='Irish Grid', source_coordinate_system_identifier='EPSG:29903',
    source_coordinates=LOCATION['coordinates_original'], wgs84=dict(latitude=54.108618, longitude=-6.274707),
    status='converted', confidence='high', notes='Synthetic mocked conversion; confirm datum.')


def sdk(result=None, finish='stop', refusal=None):
    return ChatCompletion.model_validate(dict(id='offline-response',created=0,model='gpt-4.1-mini',object='chat.completion',
        usage=dict(prompt_tokens=250,completion_tokens=100,total_tokens=350),
        choices=[dict(index=0,finish_reason=finish,message=dict(role='assistant',content=json.dumps(result or RESULT),refusal=refusal))]))


def test_endpoint_one_request_minimum_source_cache_and_independent_provenance(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_MODEL','gpt-4.1-mini')
    calls=[]
    def transport(packet): calls.append(packet);return sdk()
    app=create_app(tmp_path,transport=lambda p: None,coordinate_transport=transport)
    original=dict(analysis_id='offline-fixture', spatial_context=[deepcopy(LOCATION)])
    app.state.analyses['offline-fixture']=original
    before=deepcopy(original)
    with TestClient(app) as client:
        boot=client.get('/api/session').json()['boot_id']; headers={'x-session-id':boot}
        body=dict(analysis_id='offline-fixture',location_index=0)
        assert not calls
        r=client.post('/api/coordinates/convert',json=body,headers=headers)
        assert r.status_code==200 and r.json()['usable']
        assert len(calls)==1 and calls[0]['coordinates_original']==LOCATION['coordinates_original']
        assert calls[0]['coordinate_system']=='IGR' and set(calls[0])=={
            'location_name','coordinates_original','coordinate_system','easting','northing'}
        assert client.post('/api/coordinates/convert',json=body,headers=headers).json()==r.json()
        assert len(calls)==1
        assert client.post('/api/coordinates/convert',json={**body,'force':True},headers=headers).status_code==200
        assert len(calls)==2
        assert client.post('/api/coordinates/convert',json=body,headers={'x-session-id':'stale'}).status_code==409
        assert len(calls)==2
    assert original==before
    files=list((tmp_path/'cache/coordinate_conversions/offline-fixture').glob('*/conversion.json'))
    assert len(files)==2
    ledger=json.loads(next((tmp_path/'cache/coordinate_conversions').rglob('dispatch_ledger.json')).read_text())
    assert ledger['request_cap']==1 and len(ledger['dispatches'])==1
    assert ledger['dispatches'][0]['actual_input_tokens']==250


@pytest.mark.parametrize('change',[
    {'wgs84':{'latitude':None,'longitude':-6}}, {'wgs84':{'latitude':91,'longitude':-6}},
    {'wgs84':{'latitude':54,'longitude':181}}, {'wgs84':{'latitude':float('nan'),'longitude':-6}},
    {'wgs84':{'latitude':float('inf'),'longitude':-6}}, {'confidence':'medium'}, {'confidence':'low'},
    {'status':'failed'}, {'status':'requires_review'}, {'source_coordinates':'unrelated coordinates'},
    {'source_coordinate_system_identifier':None}])
def test_unusable_responses_remain_gated(change):
    result=validate_response(sdk({**deepcopy(RESULT),**change}),'gpt-4.1-mini',LOCATION['coordinates_original'])
    assert not result['usable']


@pytest.mark.parametrize('change',[
    {'wgs84':{'latitude':'54','longitude':-6}}, {'wgs84':{'latitude':True,'longitude':-6}},
    {'status':'approved'}, {'confidence':'certain'}])
def test_strict_schema_rejects_wrong_types_enums(change):
    with pytest.raises(CandidateResponseError,match='SCHEMA_VIOLATION'):
        validate_response(sdk({**deepcopy(RESULT),**change}),'gpt-4.1-mini',LOCATION['coordinates_original'])


@pytest.mark.parametrize('finish,refusal,error',[
    ('length',None,'INCOMPLETE_OUTPUT'),('stop','refused','REFUSED_OUTPUT')])
def test_completion_gates(finish,refusal,error):
    with pytest.raises(CandidateResponseError,match=error):
        validate_response(sdk(finish=finish,refusal=refusal),'gpt-4.1-mini',LOCATION['coordinates_original'])


def test_live_adapter_one_sdk_call_strict_schema_no_retry(tmp_path, monkeypatch):
    from types import SimpleNamespace as NS
    import src.permit.coordinate_conversion as service
    monkeypatch.setenv('OPENAI_MODEL','gpt-4.1-mini');monkeypatch.setenv('OPENAI_API_KEY','offline-placeholder')
    calls=[]; configurations=[]
    def dispatch(**kwargs): calls.append(kwargs);return sdk()
    def client(**kwargs):
        configurations.append(kwargs)
        return NS(chat=NS(completions=NS(create=dispatch)),close=lambda:None)
    monkeypatch.setattr(service,'direct_openai_client',client)
    assert convert(LOCATION,tmp_path)['usable']
    assert configurations==[{'timeout':60.0,'max_retries':0}] and len(calls)==1
    assert calls[0]['response_format']['json_schema']['strict'] is True
    assert calls[0]['response_format']['json_schema']['schema']==response_schema()
    assert json.loads(calls[0]['messages'][1]['content'])['coordinates_original']==LOCATION['coordinates_original']


def test_api_failure_no_retry_safe_error_preserved_reservation(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_MODEL','gpt-4.1-mini')
    calls=[]
    def failing(packet): calls.append(1);raise RuntimeError('private SDK diagnostic must not be logged')
    with pytest.raises(RuntimeError,match='COORDINATE_API_ERROR'):
        convert(LOCATION,tmp_path,transport=failing)
    ledger=next(tmp_path.rglob('dispatch_ledger.json')).read_text()
    assert len(calls)==1 and 'OUTCOME_UNKNOWN' in ledger and 'private SDK' not in ledger
    assert json.loads(ledger)['dispatches'][0]['reserved_cost_usd']>0


def test_mock_app_cannot_accidentally_dispatch_live_conversion(tmp_path):
    app=create_app(tmp_path,transport=lambda p:None)
    app.state.analyses['fixture']={'spatial_context':[LOCATION]}
    with TestClient(app) as client:
        boot=client.get('/api/session').json()['boot_id']
        response=client.post('/api/coordinates/convert',json={'analysis_id':'fixture','location_index':0},headers={'x-session-id':boot})
    assert response.status_code==409 and not list(tmp_path.rglob('dispatch_ledger.json'))
