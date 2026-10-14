"""Focused source-backed mock tests; no AI/provider network traffic."""
import json
import httpx
import pytest
from pydantic import ValidationError
from src.environmental.service import evaluate, map_requirements
from src.environmental.models import EvaluationInput, EnvironmentalRequest
from src.environmental.ecmwf import retrieve
from tests.test_simple_environment import requirement, analysis, inputs
from tests.test_environmental_sampling import query_evidence


def turbidity(unit='NTU'):
    return requirement('turbidity',operator='>',threshold=25.,unit=unit,
                       evidence_type='unspecified',
                       source_spans=[{'page':1,'quotation':f'Turbidity above 25 {unit} shall be flagged for review.'}])


def fnu(req):
    e=query_evidence(req);e['data_type']='SATELLITE_OBSERVATION'
    for p in e['points']:p.update(raw_value=28,unit='FNU')
    return e


def test_fnu_direct_and_ntu_no_automatic_conversion(tmp_path):
    direct=evaluate(analysis(turbidity('FNU')),inputs(),tmp_path/'direct',transports={'COPERNICUS_MARINE':fnu})['requirements'][0]
    assert direct['comparison_status']=='DIRECTLY_COMPARABLE'
    assert direct['evidence']['threshold_evaluation']=='TRIGGERED'
    blocked=evaluate(analysis(turbidity()),inputs(),tmp_path/'blocked',transports={})['requirements'][0]
    assert blocked['comparison_status']=='MANUAL_FNU_REQUIRED'
    assert blocked['status']=='INSUFFICIENT_DATA' and 'evidence' not in blocked


def test_manual_threshold_separate_persistent_and_cached(tmp_path):
    doc=analysis(turbidity());before=json.dumps(doc,sort_keys=True);calls=[]
    def provider(req):calls.append(req);return fnu(req)
    result=evaluate(doc,inputs(manual_fnu_thresholds={0:27}),tmp_path,transports={'COPERNICUS_MARINE':provider})
    row=result['requirements'][0]
    assert row['comparison_status']=='READY_WITH_MANUAL_FNU'
    assert row['threshold']==25 and row['unit']=='NTU'
    assert row['original_threshold']=={'operator':'>','value':25.,'unit':'NTU'}
    assert row['manual_comparison_threshold']['value']==27 and row['manual_comparison_threshold']['source']=='USER_SUPPLIED'
    assert row['evidence']['threshold_evaluation']=='TRIGGERED'
    assert calls[0].requested_unit=='FNU'
    assert row['evidence']['points'][0]['raw_value']==28 and row['evidence']['points'][0]['unit']=='FNU'
    again=evaluate(doc,inputs(manual_fnu_thresholds={0:30}),tmp_path,transports={'COPERNICUS_MARINE':lambda _:pytest.fail('Must use fresh cached FNU evidence')})
    assert again['requirements'][0]['evidence']['threshold_evaluation']=='NOT_TRIGGERED'
    assert len(calls)==1 and len(list((tmp_path/'manual_comparisons').glob('*.json')))==2
    assert json.dumps(doc,sort_keys=True)==before and result['executable_rules']==0


@pytest.mark.parametrize('value',['',None,0,-1,float('nan'),float('inf'),float('-inf'),True,'27'])
def test_invalid_manual_fnu_rejected(value):
    with pytest.raises(ValidationError):inputs(manual_fnu_thresholds={0:value})


def test_manual_not_used_for_other_variables_or_units(tmp_path):
    row=evaluate(analysis(turbidity('FNU')),inputs(manual_fnu_thresholds={0:99}),tmp_path,
                 transports={'COPERNICUS_MARINE':fnu})['requirements'][0]
    assert 'manual_comparison_threshold' not in row and row['evidence']['points'][0]['threshold']==25


def air():
    return requirement('air_temperature_2m',operator=None,threshold=None,unit='deg C',depth_requirement=None,
        source_spans=[{'page':8,'quotation':'2 m air temperature shall be recorded as informational evidence. Values below -2 deg C or above 25 deg C shall be flagged for review. This condition is informational only.'}])


@pytest.mark.parametrize('name',['air_temperature_2m','air temperature','2 m air temperature','temperature 2m','temperature_2m'])
def test_air_aliases_and_both_verified_checks(name):
    rows=map_requirements(analysis({**air(),'canonical_variable':name}))
    assert len(rows)==2
    assert [(r['operator'],r['threshold']) for r in rows]==[('<',-2),('>',25)]
    assert all(r['canonical_variable']=='air_temperature' and r['routing']['preferred_provider']=='ECMWF_FORECAST' for r in rows)
    assert all(r['original_canonical_variable']==name and r['derivation']['method']=='DERIVED_FROM_VERIFIED_SOURCE_TEXT' for r in rows)


def test_air_single_fetch_two_checks_and_failure_visible(tmp_path):
    calls=[]
    def provider(req):
        calls.append(req);e=query_evidence(req)
        for p in e['points']:p.update(raw_value=10.,unit='°C')
        return e
    result=evaluate(analysis(air()),inputs(),tmp_path/'success',transports={'ECMWF_FORECAST':provider})
    assert len(calls)==1 and calls[0].dataset_variable=='temperature_2m'
    assert len(result['evidence_groups'])==1 and len(result['evidence_groups'][0]['checks'])==2
    assert all(r['evidence']['threshold_evaluation']=='NOT_TRIGGERED' for r in result['requirements'])
    assert all(r['evidence']['points'][0]['normalized_unit']=='°C' for r in result['requirements'])
    failed=evaluate(analysis(air()),inputs(),tmp_path/'failure',transports={})
    assert len(failed['requirements'])==2 and all(r['retrieval_status']=='FAILED' for r in failed['requirements'])
    assert result['executable_rules']==0


def test_adapter_air_field_nearest_and_units():
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(200,json={'latitude':54,'longitude':-6,'hourly_units':{'temperature_2m':'°C'},
            'hourly':{'time':['2026-10-12T00:00','2026-10-12T01:00'],'temperature_2m':[10,11]}})
    req=EnvironmentalRequest(condition_id='1',requirement_text='test',canonical_variable='air_temperature',
        provider='ECMWF_FORECAST',coordinates=(54,-6),evidence_mode='forecast',
        start_time='2026-10-12T00:00:00+00:00',end_time='2026-10-12T01:00:00+00:00')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:e=retrieve(req,client=client)
    assert calls[0].url.params['hourly']=='temperature_2m' and calls[0].url.params['cell_selection']=='nearest'
    assert e['points'][0]['unit']=='°C' and e['dataset_id']=='ecmwf_ifs'


def test_ambiguous_air_remains_unresolved():
    r=air();r['source_spans'][0]['quotation']=r['source_spans'][0]['quotation'].replace('below -2','below about -2')
    mapped=map_requirements(analysis(r))
    assert len(mapped)==1 and mapped[0]['threshold'] is None and 'derivation' not in mapped[0]


def test_air_extraction_normalization_and_persistence(tmp_path):
    import pymupdf
    from src.permit.simple_analysis import analyze
    from src.permit.simple_fixture import mock_request
    r=air();r['source_page']=1;r['source_spans'][0]['page']=1
    raw={k:v for k,v in r.items() if k not in {'source_verified','review_state','executable'}}
    calls=[]
    def extraction(packet):
        calls.append(1);payload=mock_request(packet)
        payload['conditions']=payload['conditions'][:1];payload['environmental_requirements']=[raw]
        return payload
    with pymupdf.open() as pdf:
        pdf.new_page().insert_textbox(pymupdf.Rect(40,40,550,750),'1. '+r['source_spans'][0]['quotation'])
        data=pdf.tobytes()
    doc=analyze(data,'UNOFFICIAL_AIR_TEST.pdf',tmp_path,transport=extraction)
    assert len(calls)==1
    assert doc['environmental_requirements'][0]['canonical_variable']=='air_temperature_2m'
    assert doc['environmental_requirements'][0]['threshold'] is None  # Raw AI interpretation not rewritten.
    assert doc['environmental_requirements'][0]['source_verified']
    assert len(doc['environmental_mapping'])==2
    assert all(r['canonical_variable']=='air_temperature' and not r['executable'] for r in doc['environmental_mapping'])
    saved=json.loads(next(tmp_path.rglob('analysis.json')).read_text(encoding='utf-8'))
    assert saved['environmental_mapping']==doc['environmental_mapping']
