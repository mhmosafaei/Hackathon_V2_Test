from copy import deepcopy
from datetime import datetime,timedelta,timezone
from src.environmental.models import EvaluationInput
from src.environmental.turbidity_reference import attach_reference
from src.environmental.copernicus import products

def fixture():
    now=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
    query=EvaluationInput(analysis_id='run',latitude=54,longitude=-6,start_time=now+timedelta(days=1),end_time=now+timedelta(days=2))
    raw={'provider':'COPERNICUS_MARINE','dataset_id':products()['turbidity']['dataset'],'dataset_name':'Observed TUR','data_type':'SATELLITE_OBSERVATION','retrieved_at':now.isoformat(),'latitude':54.001,'longitude':-6,'distance_km':.1,'requested_coordinates':[54,-6],'points':[{'data_time':(now-timedelta(days=10)).isoformat(),'raw_value':1.112,'unit':'FNU'}]}
    result={'requirements':[{'condition_id':'14','canonical_variable':'turbidity','requirement_text':'Turbidity in FNU','status':'INSUFFICIENT_DATA','provider_diagnostic':{'provider_error_category':'CACHED_EVIDENCE_UNAVAILABLE'}}]}
    return query,raw,result

def test_latest_reference_is_cached_separately_and_does_not_clear_unknown(tmp_path):
    query,raw,result=fixture();original=deepcopy(result);calls=[]
    def provider(request):calls.append(request);return raw
    attach_reference(result,query,tmp_path,allow_download=True,transport=provider)
    reference=result['requirements'][0].pop('historical_reference')
    assert result==original
    assert reference['raw_value']==1.112 and reference['unit']=='FNU'
    assert reference['age_hours']==264
    assert reference['reference_only'] and not reference['qualifies_for_decision']
    assert calls[0].evidence_mode=='historical_reference_only'
    assert list((tmp_path/'references').glob('*.json'))
    def forbidden(request):raise AssertionError('Cached display must not fetch')
    attach_reference(result,query,tmp_path,allow_download=False,transport=forbidden)
    assert result['requirements'][0]['historical_reference']['retrieved_at']==raw['retrieved_at']

def test_incompatible_units_and_distant_samples_cannot_become_displayed_reference(tmp_path):
    query,raw,result=fixture()
    raw['points'][0]['unit']='NTU'
    attach_reference(result,query,tmp_path,allow_download=True,transport=lambda request:raw)
    assert 'historical_reference' not in result['requirements'][0]
    raw['points'][0]['unit']='FNU';raw['distance_km']=6
    attach_reference(result,query,tmp_path,allow_download=True,transport=lambda request:raw)
    assert 'historical_reference' not in result['requirements'][0]
