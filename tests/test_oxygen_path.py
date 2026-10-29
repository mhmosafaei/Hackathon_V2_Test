"""Oxygen-only end-to-end regressions. All AI/provider responses are mocked."""
import json
from datetime import datetime, timezone, timedelta
import numpy as np
import pymupdf
import pytest
import xarray as xr
from fastapi.testclient import TestClient
from src.environmental.copernicus import worker, products
from src.environmental.errors import ProviderError
from src.environmental.service import evaluate, map_requirements
from src.permit.simple_api import create_app
from src.permit.simple_fixture import mock_request
from tests.test_environmental_sampling import fixture_requirement
from tests.test_simple_environment import analysis, inputs, approve_synthetic_point


def oxygen():
    return {**fixture_requirement(1), 'condition_id':'1'}


def test_oxygen_daily_3d_extraction_persistence_provider_api(tmp_path,monkeypatch):
    import copernicusmarine
    r=oxygen()
    extracted={k:v for k,v in r.items() if k not in {'source_verified','review_state','executable'}}
    calls=[];extraction_calls=[]
    def opened(**kwargs):
        calls.append(kwargs)
        start=datetime.fromisoformat(kwargs['start_datetime'])
        end=datetime.fromisoformat(kwargs['end_datetime'])
        times=[start+timedelta(days=i) for i in range((end-start).days+1)]
        ds=xr.Dataset({'o2':(('time','depth','latitude','longitude'),np.full((len(times),1,1,1),200.))},
            coords={'time':np.array([t.replace(tzinfo=None) for t in times],dtype='datetime64[s]'),
                    'depth':[1.], 'latitude':[54.], 'longitude':[-6.]})
        ds.o2.attrs['units']='mmol m-3'
        return ds
    monkeypatch.setattr(copernicusmarine,'open_dataset',opened)
    def extraction(packet):
        extraction_calls.append(1)
        payload=mock_request(packet);payload['conditions']=payload['conditions'][:1]
        payload['environmental_requirements']=[extracted]
        payload['environmental_extraction']={
            'candidate_count':1,'returned_record_count':1,'extracted_count':1,
            'missing_count':0,'candidate_conditions':['1'],'extracted_conditions':['1'],
            'missing_conditions':[],'incomplete_records':[],'complete':True,
        }
        return payload
    with pymupdf.open() as pdf:
        pdf.new_page().insert_textbox(pymupdf.Rect(40,40,550,750),
            'Synthetic work point: WGS84 latitude 54.1 longitude -6.1.\n'
            'Significant wave height shall not exceed 2.5 m during works.\n1. '+r['requirement_text'])
        data=pdf.tobytes()
    with TestClient(create_app(tmp_path,transport=extraction,
                            environmental_transports={'COPERNICUS_MARINE':worker})) as client:
        headers={'x-session-id':client.get('/api/session').json()['boot_id'],
                 'x-filename':'UNOFFICIAL_OXYGEN_SOFTWARE_TEST.pdf'}
        response=client.post('/api/analyze',content=data,headers=headers)
        assert response.status_code==200
        doc=response.json();item=doc['environmental_requirements'][0]
        assert (item['operator'],item['threshold'],item['unit'])==('<',6.,'mg/L')
        assert item['depth_requirement']=='1 metre below sea surface' and item['source_verified']
        stored=json.loads(next(tmp_path.rglob('analysis.json')).read_text(encoding='utf-8'))
        assert stored['environmental_requirements']==doc['environmental_requirements']
        period=inputs().model_dump(mode='json');period['analysis_id']=doc['analysis_id']
        approve_synthetic_point(client, doc, headers)
        period['latitude'],period['longitude']=54.1,-6.1
        period['start_time']=datetime.now(timezone.utc).replace(hour=12,minute=0,second=0,microsecond=0).isoformat()
        period['end_time']=(datetime.fromisoformat(period['start_time'])+timedelta(hours=24)).isoformat()
        result=client.post('/api/environmental',json=period,headers=headers)
        assert result.status_code==200
        body=result.json();row=body['requirements'][0];e=row['evidence']
        assert len(extraction_calls)==len(calls)==1
        assert row['routing']['preferred_provider']=='COPERNICUS_MARINE'
        assert calls[0]['dataset_id']=='cmems_mod_nws_bgc-o2_anfc_7km-3D_P1D-m'
        assert calls[0]['variables']==['o2']
        assert calls[0]['minimum_depth']==calls[0]['maximum_depth']==row['request']['depth']==1
        assert e['depth']==1 and e['requested_depth']==1
        assert e['temporal_resolution']==row['request']['timestep_seconds']==86400
        assert e['temporal_coverage_status']=='COVERED' and e['retrieval_status']=='SUCCESS'
        assert e['quality_status']=='COASTAL_REVIEW_REQUIRED'
        assert e['data_type']=='MODEL_FORECAST'
        assert 'supportive' in e['notes'] and 'not equivalent' in e['notes']
        assert 'cannot resolve subdaily excursions' in e['notes']
        p=e['points'][0]
        assert p['raw_value']==200 and p['unit']=='mmol m-3'
        assert p['normalized_value']==pytest.approx(6.3996) and p['normalized_unit']=='mg/L'
        assert e['threshold_evaluation']=='NOT_TRIGGERED'
        assert item['review_state']=='UNREVIEWED' and not item['executable']
        assert body['executable_rules']==0


def test_absent_source_requirement_never_invented(tmp_path):
    doc=analysis();doc['environmental_requirements']=[]
    result=evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':lambda _:pytest.fail('No source requirement')})
    assert result['requirements']==[] and result['executable_rules']==0


def test_oxygen_mapping_and_missing_depth_visible(tmp_path):
    r=oxygen();r['depth_requirement']=None
    mapped=map_requirements(analysis(r))[0]
    assert mapped['routing']['preferred_provider']=='COPERNICUS_MARINE'
    assert products()['oxygen']['dataset']=='cmems_mod_nws_bgc-o2_anfc_7km-3D_P1D-m'
    row=evaluate(analysis(r),inputs(),tmp_path,transports={})['requirements'][0]
    assert row['canonical_variable']=='dissolved_oxygen'
    assert row['status']=='INSUFFICIENT_DATA' and 'Explicit depth required' in row['notes_for_evaluation']
    assert 'request' not in row  # No surface default and no provider dispatch.


@pytest.mark.parametrize('category',['DEPTH_SELECTION','VARIABLE_LOOKUP','TEMPORAL_COVERAGE','SPATIAL_COVERAGE','UNIT_INCOMPATIBLE','PROVIDER_RUNTIME'])
def test_oxygen_failures_remain_in_api_result(tmp_path,category):
    def fail(_):raise ProviderError(category,'Oxygen evidence unavailable: '+category)
    body=evaluate(analysis(oxygen()),inputs(),tmp_path,transports={'COPERNICUS_MARINE':fail})
    assert len(body['requirements'])==1
    row=body['requirements'][0]
    assert row['status']=='INSUFFICIENT_DATA' and row['retrieval_status']=='FAILED'
    assert row['provider_diagnostic']['provider_error_category']==category
    assert row['provider_diagnostic']['dataset_id']=='cmems_mod_nws_bgc-o2_anfc_7km-3D_P1D-m'
    assert row['provider_diagnostic']['variable']=='o2'
    assert body['executable_rules']==0
