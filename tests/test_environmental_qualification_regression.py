"""Actual extraction spellings and masked reference-series regression fixtures."""
from copy import deepcopy
from datetime import timedelta
import pytest
from src.environmental.service import evaluate, compatible_points
from src.environmental.sampling import source_depth
from src.environmental.models import EnvironmentalRequest
from src.environmental.fixture import mock_evidence
from tests.test_simple_environment import requirement, analysis, inputs
from tests.test_decision_engine import T


@pytest.mark.parametrize('variable,unit,depth_text',[
    ('wind_speed_10m','m/s','10 m height'),('wind_gust','m/s','10 m height'),
    ('visibility','m',None),('significant_wave_height','m','surface'),
    ('surface_current_speed','m/s','surface')])
def test_global_zero_does_not_become_atmospheric_or_2d_depth(tmp_path,variable,unit,depth_text):
    raw=requirement(variable,unit=unit,operator='>',threshold=5,depth_requirement=depth_text,
        source_spans=[{'page':1,'quotation':f'STOP condition: {variable} > 5 {unit}.'}])
    calls=[]
    def transport(request):
        calls.append(request)
        return mock_evidence(request)
    result=evaluate(analysis(raw),inputs(depth=0),tmp_path,
        transports={'COPERNICUS_MARINE':transport,'ECMWF_FORECAST':transport})
    row=result['requirements'][0]
    assert len(calls)==1 and calls[0].depth is None
    assert row['request']['depth'] is None
    assert row['evidence']['requested_depth_m'] is None
    assert 'depth' not in row['notes_for_evaluation'].lower()


def test_do_source_model_level_wrapper_preserves_zero_and_original_text(tmp_path,monkeypatch):
    import numpy as np
    from src.environmental.copernicus import worker
    from tests.test_copernicus_current_oxygen_patch import oxygen_dataset,mock_client
    text='sea-surface model level (0 m below sea surface)'
    raw=requirement('dissolved_oxygen',unit='mg/L',operator='<',threshold=6,depth_requirement=text,
        source_spans=[{'page':1,'quotation':f'Dissolved oxygen at the {text}. STOP condition: dissolved oxygen < 6 mg/L.'}])
    before=deepcopy(raw)
    request=inputs(depth=0)
    ds=oxygen_dataset((0.,))
    ds=ds.assign_coords(time=np.array([(request.start_time-timedelta(hours=6)).replace(tzinfo=None)],dtype='datetime64[ns]'))
    calls=mock_client(monkeypatch,ds)
    result=evaluate(analysis(raw),request,tmp_path,transports={'COPERNICUS_MARINE':worker})
    row=result['requirements'][0]
    assert len(result['requirements'])==1
    assert row['routing']['preferred_provider']=='COPERNICUS_MARINE'
    assert len(calls)==1 and calls[0]['minimum_depth']==0
    assert row['request']['depth']==row['evidence']['selected_depth_m']==0
    assert row['evidence']['recency_policy']['age_hours']==6
    assert row['evidence']['threshold_evaluation']=='NOT_TRIGGERED'
    assert row['evidence']['data_type']=='MODEL_FORECAST'
    assert raw==before


def test_wrapper_without_source_support_and_wrong_weather_height_fail_closed():
    raw=requirement('dissolved_oxygen',depth_requirement='sea-surface model level (0 m below sea surface)',
        source_spans=[{'page':1,'quotation':'0 m below sea surface.'}],routing={'preferred_provider':'COPERNICUS_MARINE'})
    assert source_depth(raw)[0] is None
    wind=requirement('wind_speed_10m',depth_requirement='50 m height',routing={'preferred_provider':'ECMWF_FORECAST'})
    assert source_depth(wind)[1]


@pytest.mark.parametrize('age,expected',[(24,'NOT_TRIGGERED'),(72,'NOT_TRIGGERED'),(72.001,'NOT_DETERMINED')])
def test_masked_tur_points_do_not_contaminate_selected_reference(age,expected):
    raw=requirement('turbidity',unit='FNU',operator='>',threshold=25,depth_requirement=None,evidence_type='observation',
        source_spans=[{'page':1,'quotation':'STOP condition: turbidity > 25 FNU.'}])
    request=EnvironmentalRequest(condition_id='1',requirement_text='Turbidity',canonical_variable='turbidity',
        provider='COPERNICUS_MARINE',coordinates=(54,-6),start_time=T.isoformat(),end_time=(T+timedelta(hours=2)).isoformat(),
        provider_query_start=(T-timedelta(hours=73)).isoformat(),provider_query_end=(T+timedelta(hours=2)).isoformat(),
        evidence_mode='observation',operator='>',requested_unit='FNU',timestep_seconds=86400)
    original_time=(T-timedelta(hours=age)).isoformat()
    evidence={'provider':'COPERNICUS_MARINE','dataset_id':'configured-TUR','canonical_variable':'turbidity',
        'data_type':'SATELLITE_OBSERVATION','quality_status':'SUITABLE','requested_coordinates':[54,-6],
        'latitude':54,'longitude':-6,'distance_km':0,'retrieved_at':T.isoformat(),
        'points':[{'data_time':T.isoformat(),'raw_value':None,'unit':'FNU'},
                  {'data_time':original_time,'raw_value':1.1488773822784424,'unit':'FNU'}]}
    before=deepcopy(evidence)
    result=compatible_points(raw,request,evidence,now=T)
    assert result['threshold_evaluation']==expected
    if age<=72:
        assert result['status']=='WITHIN_THRESHOLD'
        assert result['validation_notes']==[]
        assert result['points'][0]['data_time']==original_time
        assert result['points'][0]['comparison'] is False
        assert result['points'][1]['validation_notes']==['Missing required value or invalid timestamp']
    else:
        assert result['recency_policy']['reason_code']=='STALE_TURBIDITY_EVIDENCE'
    assert evidence==before
