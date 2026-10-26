"""Read-only evidence inventory beside authoritative rule evaluation.

Stored provider screening is not a decision or an approval. This module does not
retrieve evidence, amend review state, or evaluate thresholds independently.
"""
from copy import deepcopy
from datetime import datetime, timezone
import re

from src.environmental.catalog import canonical

TITLES = {'significant_wave_height':'Significant wave height', 'mean_wave_period':'Mean wave period',
    'wind_speed_10m':'Wind speed 10m', 'wind_gust':'Wind gust', 'surface_current_speed':'Surface current speed',
    'eastward_current':'Eastward current component U', 'northward_current':'Northward current component V',
    'visibility':'Visibility', 'turbidity':'Turbidity', 'dissolved_oxygen':'Dissolved oxygen'}
REVIEW_CODES = {'REVIEW_REQUIRED','REVIEW_REJECTED_UNRESOLVED','REVIEW_CONFLICT',
    'APPLICABILITY_UNASSESSED','SOURCE_UNVERIFIED','INTERPRETATION_REQUIRED'}


def attach_requirement_diagnostics(result, row, environment, start, end, now, spatial_suitable):
    if row['kind'] != 'environmental_requirement':
        return
    variable = canonical(result['effective_rule'].get('canonical_variable'))
    identity = re.fullmatch(r'environmental_requirement-(\d+)-.+', row['target_id'])
    index = int(identity[1]) if identity else None
    matches = [r for r in (environment or {}).get('requirements', [])
        if index is not None and r.get('requirement_index') == index
        and str(r.get('condition_id')) == str(row['condition_id'])
        and canonical(r.get('canonical_variable')) == variable]
    record = matches[0] if len(matches)==1 else {}
    evidence = record.get('evidence') or {}
    points = evidence.get('points') or []
    units = lambda key: sorted({str(p[key]) for p in points if p.get(key) is not None})
    mappings = [m for m in row.get('mapping', []) if m.get('requirement_index') == index]
    diagnostic = record.get('provider_diagnostic') or {}
    code = result['reason_code']
    eligibility = ('NOT_EVALUATED_REVIEW_BLOCKED' if code in REVIEW_CODES else
        'ACCEPTED_FOR_INTERVAL' if result['gating'] and result['status'] in {'WORK','STOP'} else
        'NOT_ELIGIBLE' if result['gating'] else 'NON_GATING')
    parsed_times = []
    for point in points:
        try:
            moment=datetime.fromisoformat(point['data_time'].replace('Z','+00:00'))
            if moment.utcoffset() is not None:
                parsed_times.append(moment.astimezone(timezone.utc))
        except (KeyError, ValueError, TypeError):
            pass
    age = None
    try:
        retrieved=datetime.fromisoformat(evidence['retrieved_at'].replace('Z','+00:00'))
        if retrieved.utcoffset() is not None:
            age=(now-retrieved).total_seconds()/3600
    except (KeyError, ValueError, TypeError):
        pass
    issues = [{'code':code, 'explanation':result['explanation'], 'action':result['required_action']}]
    if diagnostic:
        issues.append({'code':diagnostic.get('provider_error_category','PROVIDER_FAILURE'),
            'explanation':diagnostic.get('provider_error_message','Provider retrieval failed.'),
            'action':'Inspect the retained provider diagnostic; no usable evidence is implied.'})
    elif not points and code not in {'EVIDENCE_MISSING','NO_WAVE_EVIDENCE'}:
        issues.append({'code':'EVIDENCE_MISSING','explanation':'No linked native evidence points are present.',
            'action':'Use explicit Fetch only after confirming the source requirement, location and UTC period.'})
    if not result['source_verified'] and code!='SOURCE_UNVERIFIED':
        issues.append({'code':'SOURCE_UNVERIFIED','explanation':'Source quotation verification remains unresolved.',
            'action':'Verify the source quotation and physical page; approval alone does not verify a source.'})
    if not mappings:
        issues.append({'code':'MAPPING_MISSING','explanation':'No mapping for this exact source requirement.',
            'action':'Resolve deterministic requirement mapping; do not infer another source.'})
    result['diagnostics'] = {'condition_id':str(row['condition_id']),
        'title':TITLES.get(variable, variable.replace('_',' ').capitalize()),
        'canonical_variable':variable, 'review_status':row['state'], 'applicability_status':row['applicability'],
        'source_verified':result['source_verified'],
        'evidence_availability':'AVAILABLE' if points else 'RETRIEVAL_FAILED' if diagnostic else 'MISSING',
        'evidence_eligibility':eligibility, 'point_count':len(points),
        'provider':evidence.get('provider') or diagnostic.get('provider') or (mappings[0].get('routing',{}).get('preferred_provider') if mappings else None),
        'dataset_id':evidence.get('dataset_id') or diagnostic.get('dataset_id'),
        'dataset_variable':evidence.get('dataset_variable') or diagnostic.get('variable'),
        'evidence_id':record.get('evidence_request_key'),
        'native_units':units('unit'), 'normalized_units':units('normalized_unit'),
        'requested_interval':{'start':start.isoformat(),'end':end.isoformat()},
        'coverage':deepcopy(evidence.get('coverage') or {}),
        'native_time_range':{'start':min(parsed_times).isoformat() if parsed_times else None,
                             'end':max(parsed_times).isoformat() if parsed_times else None},
        'stored_temporal_status':evidence.get('temporal_coverage_status'),
        'stored_spatial_status':evidence.get('quality_status'),
        'stored_spatial_criterion_satisfied':spatial_suitable(evidence) if evidence else False,
        'coastal_review_flag_retained':evidence.get('quality_status')=='COASTAL_REVIEW_REQUIRED',
        'distance_km':evidence.get('distance_km'), 'selected_depth_m':evidence.get('selected_depth_m',evidence.get('depth')),
        'retrieved_at':evidence.get('retrieved_at'), 'retrieval_age_hours':age,
        'stored_threshold_screening':evidence.get('threshold_evaluation'),
        'threshold_result':result['status'] if result['checks'] else 'NOT_EVALUATED',
        'validation_notes':deepcopy(evidence.get('validation_notes') or []),
        'issues':issues,
        'qualification':'Stored evidence inventory is not review acceptance or continuous validity. Rule status/reason is authoritative.'}
