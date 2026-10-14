"""Offline qualification, literal screening and narrow SST recovery regressions."""
import json
from datetime import datetime, timedelta
import pytest
from tests.test_simple_environment import requirement, analysis, inputs
from tests.test_environmental_sampling import query_evidence
from src.environmental.service import evaluate, derived_sst_checks
from src.environmental.units import convert, canonical_unit


@pytest.mark.parametrize('unit',['deg C','°C','degrees_C','degree_C','degrees C'])
def test_celsius_aliases(unit):
    assert canonical_unit(unit) == '°C'
    assert convert(14.265, 'degrees_C', unit) == 14.265
    with pytest.raises(ValueError):
        convert(14, 'FNU', unit)


@pytest.mark.parametrize('source,target', [('degree', 'degrees'), ('degrees', 'degree'),
                                           ('deg', 'degrees'), ('degrees', 'deg')])
def test_angular_degree_aliases_preserve_value(source, target):
    assert canonical_unit(source) == 'degrees'
    assert canonical_unit(target) == 'degrees'
    assert convert(161.5, source, target) == 161.5


def test_mean_wave_direction_degree_provider_unit_remains_informational(tmp_path):
    r = requirement('mean_wave_direction', condition_id='26', operator=None,
        threshold=None, unit='degrees', evidence_type='reanalysis', depth_requirement=None,
        source_spans=[{'page': 4, 'quotation': 'Mean wave direction shall be recorded in degrees.'}])

    def provider(req):
        e = query_evidence(req)
        e['canonical_variable'] = 'mean_wave_direction'
        e['dataset_variable'] = 'VMDR'
        e['quality_status'] = 'COASTAL_REVIEW_REQUIRED'
        for point in e['points']:
            point.update(raw_value=161.5, unit='degree')
        e['direction_convention'] = 'PROVIDER_DEFINED_NOT_NORMALIZED'
        return e

    row = evaluate(analysis(r), inputs(), tmp_path,
        transports={'COPERNICUS_MARINE': provider})['requirements'][0]
    assert row['status'] == 'INFORMATIONAL'
    assert row['evidence']['retrieval_status'] == 'SUCCESS'
    assert row['evidence']['points'][0]['normalized_value'] == 161.5
    assert row['evidence']['points'][0]['normalized_unit'] == 'degrees'
    assert row['evidence']['direction_convention'] == 'PROVIDER_DEFINED_NOT_NORMALIZED'


@pytest.mark.parametrize('variable,value,threshold,unit',[
    ('significant_wave_height',.846,1.5,'m'),('current_speed',.032,1,'m/s')])
def test_coastal_pass_keeps_qualification(tmp_path,variable,value,threshold,unit):
    r=requirement(variable,operator='>',threshold=threshold,unit=unit,
        source_spans=[{'page':1,'quotation':f'Flag values above {threshold} {unit}.'}])
    def provider(req):
        e=query_evidence(req);e.update(quality_status='COASTAL_REVIEW_REQUIRED',distance_km=.967)
        if variable == 'current_speed':
            start=datetime.fromisoformat(req.provider_query_start)
            end=datetime.fromisoformat(req.provider_query_end)
            e['points']=[{**e['points'][0], 'data_time':(start+timedelta(seconds=n)).isoformat()}
                         for n in range(0,int((end-start).total_seconds())+1,900)]
        for p in e['points']:p.update(raw_value=value,unit=unit)
        return e
    result=evaluate(analysis(r),inputs(),tmp_path,transports={'COPERNICUS_MARINE':provider})
    e=result['requirements'][0]['evidence']
    assert e['retrieval_status']=='SUCCESS' and e['temporal_coverage_status']=='COVERED'
    assert e['spatial_distance_status']=='WITHIN_CONFIGURED_DISTANCE'
    assert e['applicability_status']=='COASTAL_REVIEW_REQUIRED'
    assert e['threshold_evaluation']=='NOT_TRIGGERED'
    assert e['points'][0]['comparison'] is False
    assert 'human review' in e['qualification'] and result['executable_rules']==0


def sst():
    quote='Values below 2 deg C or above 22 deg C shall be flagged for review.'
    return requirement('sea_surface_temperature',operator=None,threshold=None,unit='deg C',
                       source_spans=[{'page':8,'quotation':quote}])


def test_live_shape_sst_two_checks_one_retrieval(tmp_path):
    calls=[];doc=analysis(sst());before=json.dumps(doc,sort_keys=True)
    def provider(req):
        calls.append(req);e=query_evidence(req);e['quality_status']='COASTAL_REVIEW_REQUIRED'
        for p in e['points']:p.update(raw_value=14.265,unit='degrees_C')
        return e
    result=evaluate(doc,inputs(),tmp_path,transports={'COPERNICUS_MARINE':provider})
    assert len(calls)==1 and len(result['evidence_groups'])==1
    checks=result['evidence_groups'][0]['checks']
    assert [(c['operator'],c['threshold']) for c in checks]==[('<',2),('>',22)]
    for c in checks:
        assert c['derivation']['method']=='DERIVED_FROM_VERIFIED_SOURCE_TEXT'
        assert c['evidence']['threshold_evaluation']=='NOT_TRIGGERED'
        assert c['evidence']['points'][0]['normalized_unit']=='°C'
    assert before==json.dumps(doc,sort_keys=True)


@pytest.mark.parametrize('change',[{'source_verified':False}, {'canonical_variable':'wind_speed_10m'},
    {'source_spans':[{'page':8,'quotation':'Values below about 2 deg C or above 22 deg C shall be flagged for review.'}]},
    {'source_spans':[{'page':8,'quotation':'Values below 22 deg C or above 2 deg C shall be flagged for review.'}]}])
def test_ambiguous_sst_not_derived(change):
    assert len(derived_sst_checks({**sst(),**change}))==1


@pytest.mark.parametrize('failure',['time','distance','unit','missing','depth','source'])
def test_real_failures_still_block(tmp_path,failure):
    r=requirement()
    def provider(req):
        e=query_evidence(req);e['quality_status']='COASTAL_REVIEW_REQUIRED'
        if failure=='time': e['points']=e['points'][1:]
        if failure=='distance': e['distance_km']=25
        if failure=='unit': e['points'][0]['unit']='FNU'
        if failure=='missing': e['points'][0]['raw_value']=None
        if failure=='depth': e['depth']=999
        return e
    if failure=='source':r['source_verified']=False
    row=evaluate(analysis(r),inputs(),tmp_path,transports={'COPERNICUS_MARINE':provider})['requirements'][0]
    assert row['status']=='INSUFFICIENT_DATA'
    if row.get('evidence'):assert row['evidence']['threshold_evaluation']=='NOT_DETERMINED'


@pytest.mark.parametrize('value,expected',[(1,'NOT_TRIGGERED'),(3,'TRIGGERED')])
def test_literal_trigger_semantics(tmp_path,value,expected):
    r=requirement(operator='>')
    def provider(req):
        e=query_evidence(req)
        for p in e['points']:p['raw_value']=value
        return e
    e=evaluate(analysis(r),inputs(),tmp_path,transports={'COPERNICUS_MARINE':provider})['requirements'][0]['evidence']
    assert e['threshold_evaluation']==expected
