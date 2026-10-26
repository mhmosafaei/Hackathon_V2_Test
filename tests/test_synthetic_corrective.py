"""Offline source/decision-scope regressions. No transports are used."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from src.permit.simple_analysis import (_is_environmental_measurement_candidate,
    apply_source_verification, identify_environmental_source_candidates,
    assess_environmental_extraction_completeness)
from src.environmental.service import source_numeric_values, map_requirements, compatible_points
from src.environmental.models import EnvironmentalRequest
from src.permit.persisted_analysis import _load_persisted_pages
from tests.test_decision_engine import fixture, run, T


@pytest.mark.parametrize('text',[
    'Significant wave height (Hs) shall be assessed. Hs greater than 1.5 m.',
    'Mean wave period shall be assessed in seconds. STOP if greater than 8 s.',
    'Wave direction shall be recorded in provider degrees.',
    '10 m wind speed shall be assessed. STOP above 12 m/s.',
    'Wind gust shall be assessed independently. STOP above 18 m/s.',
    'Wind direction shall be recorded in degrees.',
    'Current speed shall be assessed. STOP above 1 m/s.',
    'Eastward current U shall be retained separately. Absolute U above 0.6 m/s.',
    'Northward current V shall be retained separately. Absolute V above 0.6 m/s.',
    'Current direction may be derived and is informational.',
    'Visibility shall be assessed. STOP below 1,000 m.',
    'Suspended solid particles / turbidity shall be assessed. STOP above 25 FNU.',
    'Dissolved oxygen shall be assessed at 1 m. STOP below 6 mg/L.',
])
def test_generic_measurement_candidates(text):
    assert _is_environmental_measurement_candidate(text)


@pytest.mark.parametrize('text',[
    'PermitPulse shall not infer visibility from weather proxies. PermitPulse shall not treat provider availability as evidence.',
    'A WORK result means only that reviewed wave constraints passed. It does not constitute authorization.',
    'Wave variables may share a retrieval to avoid redundant provider requests.',
    'Evidence limitations: wave forecast evidence is advisory and does not authorize work.',
    'Provider-policy: current data availability is not deciding evidence.',
])
def test_software_policy_not_measurement(text):
    assert not _is_environmental_measurement_candidate(text)


def test_numeric_formatting_is_exact():
    assert source_numeric_values('below 1,000 m and 1.5 m') == [1000,1.5]
    assert 100 not in source_numeric_values('1,000 m')
    assert 15 not in source_numeric_values('1.5 m')
    assert not source_numeric_values('1,00 m')


@pytest.mark.parametrize('quote,threshold,valid',[
    ('Visibility below 1,000 m.',1000,True),('Visibility below 1,000 m.',100,False),
    ('Visibility below 1.5 m.',1.5,True),('Visibility below 1.5 m.',15,False)])
def test_numeric_source_verification_in_screening(quote,threshold,valid):
    reviews,env=fixture('visibility',threshold=threshold,source_spans=[{'page':1,'quotation':quote}])
    original=reviews['requirements'][0]['original'];before=deepcopy(original)
    ev=env['requirements'][0]['evidence'];ev['dataset_id']='SYNTHETIC_VISIBILITY'
    request=EnvironmentalRequest(condition_id='source-a',requirement_text=quote,canonical_variable='visibility',
        operator='<',threshold=threshold,threshold_unit='m',coordinates=(54,-6),start_time=ev['coverage']['requested_start'],
        end_time=ev['coverage']['requested_end'],evidence_mode='forecast',provider='ECMWF_FORECAST')
    result=compatible_points(original,request,ev,now=T)
    assert ('Numeric threshold not supported by cited text' not in result['validation_notes']) is valid
    assert original==before


def test_verified_absolute_current_constraint_retains_signed_value():
    reviews,env=fixture('eastward_current',value=-3,unit='m/s',source_spans=[{'page':1,'quotation':'Absolute eastward component greater than 2 m/s.'}])
    current=run(reviews,env)['current_assessment']
    assert current['status']=='STOP'
    value=current['rule_results'][0]['checks'][0]['values'][0]
    assert value['raw_value']==-3 and value['value']==3


def test_cross_page_source_unique_preserves_original_and_idempotence():
    pages=[SimpleNamespace(page_number=1,text='Repeated header\nPage 1\n4. Turbidity\nSuspended solids shall be assessed.'),
           SimpleNamespace(page_number=2,text='Repeated header\nPage 2\nTurbidity above 25 FNU triggers STOP.')]
    quote='4. Turbidity\nSuspended solids shall be assessed.\n\nTurbidity above 25 FNU triggers STOP.'
    a={'conditions':[{'number':'4','source_spans':[{'page':1,'quotation':'4. Turbidity'}]}],
       'environmental_requirements':[{'condition_id':'4','source_page':2,'source_spans':[{'page':2,'quotation':quote}]}]}
    apply_source_verification(a,pages);r=a['environmental_requirements'][0]
    assert r['source_verified'] and r['model_declared_source_page']==2
    assert r['source_spans'][0]['quotation']==quote
    assert [s['page'] for s in r['verified_source_spans']]==[1,2]
    before=deepcopy(a);apply_source_verification(a,pages);assert a==before


@pytest.mark.parametrize('quote',['Absent text','Duplicate text'])
def test_unresolved_quotes_fail_closed(quote):
    pages=[SimpleNamespace(page_number=n,text='Duplicate text') for n in (1,2)]
    a={'conditions':[{'number':'4','source_spans':[{'page':1,'quotation':'Duplicate text'}]}],
       'environmental_requirements':[{'condition_id':'4','source_page':1,'source_spans':[{'page':1,'quotation':quote}]}]}
    apply_source_verification(a,pages)
    assert not a['environmental_requirements'][0]['source_verified']


@pytest.mark.parametrize('provider,implemented',[('EXTERNAL',True),('UNAVAILABLE',False),('ERA5',True),('CDS',True),('CAMS',True),('COPERNICUS_MARINE',False)])
def test_required_numerical_capability_failure_remains_gating(provider,implemented):
    reviews,env=fixture();row=deepcopy(reviews['requirements'][0])
    row['target_id']='environmental_requirement-1-extra';row['mapping'][0]['requirement_index']=1
    row['mapping'][0]['routing'].update(preferred_provider=provider,implemented=implemented)
    reviews['requirements'].append(row)
    result=run(reviews,env)['current_assessment']
    assert result['status']=='UNKNOWN'
    blocked=next(r for r in result['rule_results'] if r['requirement_id']==row['target_id'])
    assert blocked['gating'] is True
    assert blocked['reason_code'] in {'EXTERNAL_EVIDENCE_REQUIRED','EVIDENCE_UNSUPPORTED','NO_WAVE_EVIDENCE'}


@pytest.mark.parametrize('variable',['significant_wave_height','wind_gust'])
def test_fetchable_missing_evidence_unknown(variable):
    reviews,env=fixture(variable);env['requirements'][0].pop('evidence')
    assert run(reviews,env)['current_assessment']['status']=='UNKNOWN'


@pytest.mark.parametrize('mutation',['time_missing','time_outside','time_naive','position_missing','position_outside','unreviewed_position','geometry_unresolved'])
def test_time_position_prerequisites(mutation):
    reviews,env=fixture();context=reviews['decision_context']
    if mutation=='time_missing':context.pop('temporal_context')
    elif mutation=='time_outside':context['temporal_context']['permit_valid_until']='2026-10-13T00:00:00Z'
    elif mutation=='time_naive':context['temporal_context']['permit_valid_from']='2026-10-01'
    elif mutation=='position_missing':context.pop('spatial_context')
    elif mutation=='position_outside':env['requirements'][0]['request']['coordinates']=[0,0]
    elif mutation=='unreviewed_position':reviews['requirements'][-1]['state']='UNREVIEWED'
    else:context['geofences']=[{'type':'polygon'}]
    assert run(reviews,env)['current_assessment']['status']=='UNKNOWN'


def test_existing_synthetic_replay_is_read_only():
    folder=Path('cache/simple_analysis/761f59e14aa4898bf4d4dd4cf7b0fe02cd88cf9e84eeca2b5eb58c3818c498e7/b6d61776375e47e5bce8ab2956a53f1f')
    if not folder.exists():pytest.skip('Local persisted fixture not present')
    before={p:p.read_bytes() for p in folder.iterdir() if p.is_file()}
    analysis=json.loads(before[folder/'analysis.json']);pages=_load_persisted_pages(folder/'input.txt')
    candidates=identify_environmental_source_candidates(pages)
    assert [c['condition_id'] for c in candidates]==[str(n) for n in range(3,16)]
    audit=assess_environmental_extraction_completeness(candidates,analysis['environmental_requirements'])
    assert audit['missing_conditions']==['3','4','6','7','12'] and not audit['complete']
    analysis['environmental_extraction']=audit
    apply_source_verification(analysis,pages,reset_review_state=False)
    mapped=map_requirements(analysis)
    oxygen=next(r for r in mapped if r['canonical_variable']=='dissolved_oxygen')
    assert oxygen['routing']['preferred_provider']=='COPERNICUS_MARINE'
    assert oxygen['depth_requirement']=='approximately 1 metre below the sea surface'
    assert next(r for r in mapped if r['canonical_variable']=='turbidity')['source_verified']
    assert before=={p:p.read_bytes() for p in before}
