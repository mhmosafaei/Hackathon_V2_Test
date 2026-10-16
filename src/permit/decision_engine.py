"""Deterministic advisory assessment over F04 overlays and existing evidence only.

No transport, extraction, cache writes, or provider dispatch is performed here.
Intervals reuse native samples; no interpolation or resampling is performed.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import re

from src.environmental.catalog import canonical
from src.environmental.service import derived_sst_checks, precipitation_accumulation_semantics, canonical_stop_rule
from src.environmental.units import convert, canonical_unit
from src.environmental.sampling import source_depth
from src.documents.quote_verifier import normalise

DISCLAIMER = ('Advisory evidence/constraint assessment only. This is not regulatory approval, legal compliance, '
              'vessel-master approval, permit-to-work authorization, or safe-to-work certification.')
EXPLANATIONS = {'WORK': 'All applicable evaluated operational constraints pass with sufficient evidence for this interval.',
                'STOP': 'One or more reviewed operational constraints are triggered.',
                'UNKNOWN': 'The available reviewed rules and evidence are insufficient to establish a WORK assessment.'}
NEXT_ACTIONS = {'REVIEW_REQUIRED': 'Complete Human Review.', 'REVIEW_REJECTED_UNRESOLVED': 'Resolve the rejected interpretation in Human Review.',
                'APPLICABILITY_UNASSESSED': 'Explicitly assess applicability in Human Review.',
                'SOURCE_UNVERIFIED': 'Verify the original source quotation and physical page.',
                'EVIDENCE_MISSING': 'Use an explicit Environmental Fetch for the confirmed location and UTC period.',
                'EXTERNAL_EVIDENCE_REQUIRED': 'Supply independently verified external/manual evidence; approval alone does not supply evidence.',
                'DEPTH_UNSATISFIED': 'Obtain evidence satisfying the source-backed requested depth.',
                'UNIT_INCOMPATIBLE': 'Resolve quantity/accumulation compatibility; do not substitute or infer units.',
                'FORECAST_COVERAGE_INSUFFICIENT': 'Select a period covered by valid native evidence.',
                'TEMPORAL_COVERAGE_INSUFFICIENT': 'Resolve native validity, cadence, or timing coverage.',
                'SPATIAL_COVERAGE_INSUFFICIENT': 'Resolve model-point and geographic representativeness.',
                'EVIDENCE_STALE': 'Obtain fresh evidence through a separate explicit action.',
                'PROVIDER_FAILURE': 'Inspect the existing provider diagnostic.',
                'EVIDENCE_UNSUPPORTED': 'A verified supported evidence mapping or external evidence workflow is required.'}


def utc(value):
    result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('UTC_OFFSET_REQUIRED')
    return result.astimezone(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat()


def aggregate(results):
    states = [r['status'] for r in results if r['gating']]
    return 'STOP' if 'STOP' in states else 'UNKNOWN' if 'UNKNOWN' in states or not states else 'WORK'


def problem(notes):
    text = ' '.join(str(n) for n in notes).lower()
    for terms, code in [(['depth'], 'DEPTH_UNSATISFIED'), (['stale', 'future retrieval'], 'EVIDENCE_STALE'),
        (['unit', 'accumulat', 'precipitation evidence'], 'UNIT_INCOMPATIBLE'),
        (['spatial', 'representativeness', 'location', 'selected cell'], 'SPATIAL_COVERAGE_INSUFFICIENT'),
        (['forecast', 'observation evidence mode'], 'FORECAST_COVERAGE_INSUFFICIENT'),
        (['period', 'temporal', 'duration', 'statistic'], 'TEMPORAL_COVERAGE_INSUFFICIENT'),
        (['source'], 'SOURCE_UNVERIFIED')]:
        if any(term in text for term in terms):
            return code
    return 'EVIDENCE_MISSING'


def native_step(evidence):
    value = evidence.get('source_temporal_resolution_seconds') or evidence.get('coverage', {}).get('temporal_resolution_seconds') or evidence.get('temporal_resolution')
    if value == 'hourly':
        return 3600
    if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value > 0:
        return value
    return None


def prerequisite_rows(review_data):
    context = review_data.get('decision_context') or {}
    rows = []
    for name in ('time', 'position'):
        raw = {'prerequisite': name, 'context': context, 'review_rows': review_data['requirements']}
        rows.append({'target_id': f'prerequisite-{name}', 'condition_id': name, 'kind': 'decision_prerequisite',
            'original': raw, 'effective': raw, 'source': {}, 'state': 'SYSTEM_PREREQUISITE',
            'applicability': 'APPLICABLE', 'decision_relevant_default': True,
            'original_fingerprint': '', 'review': None})
    return rows


def _context_reviewed(context, rows):
    quotes = [normalise(s.get('quotation') or '') for s in context.get('source_spans', [])]
    return bool(quotes) and all(quote and any(
        row['state'] == 'APPROVED' and row['applicability'] == 'APPLICABLE'
        and not row.get('conflict') and row['source'].get('source_verified') is True
        and any(quote in normalise(s.get('quotation') or '') for s in row['source'].get('source_spans', []))
        for row in rows) for quote in quotes)


def explicit_utc(value):
    """No date-only, midnight or timezone inference."""
    if not isinstance(value, str):
        raise ValueError('EXPLICIT_UTC_REQUIRED')
    try:
        return utc(value)
    except ValueError:
        return datetime.strptime(value, '%d %B %Y %H:%M UTC').replace(tzinfo=timezone.utc)


def reviewed_validity(rows):
    """Link explicit permit validity to reviewed physical source, not a summary."""
    date = r'(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+\d{2}:\d{2}\s+UTC|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2}))'
    pattern = r'\bvalid\s+(?:only\s+)?from\s+('+date+r')\s+(?:through|to|until)\s+('+date+r')'
    found = {}
    for row in rows:
        if row['kind']!='condition' or row['state']!='APPROVED' or row['applicability']!='APPLICABLE' or row.get('conflict') or row['source'].get('source_verified') is not True:
            continue
        for span in row['source'].get('source_spans', []):
            for match in re.finditer(pattern,re.sub(r'\s+',' ',span.get('quotation') or ''),re.I):
                try:
                    bounds=(explicit_utc(match[1]),explicit_utc(match[2]))
                except ValueError:
                    continue
                found.setdefault(bounds,[]).append({'requirement_id':row['target_id'],'source_span':deepcopy(span)})
    if len(found)!=1:
        return None
    (a,b), provenance=next(iter(found.items()))
    return {'permit_valid_from':stamp(a),'permit_valid_until':stamp(b),'source_verified':True,'reviewed_validity_provenance':provenance}


def redundant_validity_restriction(text, validity):
    """Only the same explicit validity range is redundant, not operating limits."""
    pattern=r'^Permit\s+valid\s+only\s+between\s+(.+?)\s+and\s+(.+?)\.?$'
    match=re.fullmatch(pattern,re.sub(r'\s+',' ',text).strip(),re.I)
    try:
        return bool(match and explicit_utc(match[1])==explicit_utc(validity['permit_valid_from']) and explicit_utc(match[2])==explicit_utc(validity['permit_valid_until']))
    except ValueError:
        return False


def stored_spatial_suitable(evidence):
    if evidence.get('spatial_distance_status')!='WITHIN_CONFIGURED_DISTANCE':
        return False
    if evidence.get('quality_status')=='SUITABLE':
        return True
    if not (evidence.get('provider')=='COPERNICUS_MARINE' and evidence.get('quality_status')=='COASTAL_REVIEW_REQUIRED'
            and evidence.get('applicability_status')=='COASTAL_REVIEW_REQUIRED' and evidence.get('retrieval_status')=='SUCCESS'):
        return False
    try:
        distance=float(evidence['distance_km']);limit=float(evidence['max_representative_distance_km'])
        lat,lon=float(evidence['latitude']),float(evidence['longitude'])
        if not all(math.isfinite(v) for v in (distance,limit,lat,lon)) or not (0<=distance<=limit<=5 and limit>0 and -90<=lat<=90 and -180<=lon<=180):
            return False
    except (KeyError,ValueError,TypeError):
        return False
    return not any(re.search(r'spatial|representativeness|location|selected cell',str(note),re.I)
                   for note in evidence.get('validation_notes', []))


def evaluate_prerequisite(raw, environment, start, end):
    context, rows = raw['context'], raw['review_rows']
    if raw['prerequisite'] == 'time':
        temporal = context.get('temporal_context') or {}
        if not temporal.get('source_verified') or not _context_reviewed(temporal, rows):
            validity=reviewed_validity(rows)
            if not validity:
                return 'NOT_ELIGIBLE_TIME', 'Reviewed, source-verified explicit permit validity is required.', 'UNKNOWN'
            if temporal.get('operation_start') or temporal.get('operation_end'):
                return 'NOT_ELIGIBLE_TIME', 'Operational bounds in an unverified temporal context require review.', 'UNKNOWN'
            restrictions=temporal.get('operation_time_restrictions') or []
            if any(not redundant_validity_restriction(text,validity) for text in restrictions):
                return 'NOT_ELIGIBLE_TIME', 'Additional operational time restrictions remain unresolved.', 'UNKNOWN'
            temporal={**temporal,**validity,'operation_time_restrictions':[]}
        try:
            a, b = explicit_utc(temporal.get('permit_valid_from')), explicit_utc(temporal.get('permit_valid_until'))
            if a >= b or start < a or end > b:
                return 'NOT_ELIGIBLE_TIME', 'Evaluated interval is outside explicit reviewed permit validity.', 'UNKNOWN'
            op_a, op_b = temporal.get('operation_start'), temporal.get('operation_end')
            if temporal.get('operation_time_restrictions') and not (op_a and op_b):
                return 'NOT_ELIGIBLE_TIME', 'Operational time restrictions require explicit supported UTC bounds.', 'UNKNOWN'
            if op_a or op_b:
                if not (op_a and op_b) or start < explicit_utc(op_a) or end > explicit_utc(op_b):
                    return 'NOT_ELIGIBLE_TIME', 'Evaluated interval is outside the explicit operational period.', 'UNKNOWN'
        except (ValueError, TypeError):
            return 'NOT_ELIGIBLE_TIME', 'Explicit timezone-aware validity/operation timestamps are unresolved.', 'UNKNOWN'
        return 'TIME_CONFIRMED', 'Interval lies within reviewed explicit UTC validity and operational bounds.', 'WORK'
    locations = context.get('spatial_context') or []
    if isinstance(locations, dict):
        locations = [locations]
    points = set()
    for location in locations:
        if location.get('geometry_type') != 'point' or not _context_reviewed(location, rows):
            continue
        quote = ' '.join(s.get('quotation') or '' for s in location.get('source_spans', []))
        # Support explicit source decimal-degree hemispheres; never infer a midpoint/CRS.
        match = re.search(r'(?:Latitude\s+)?(\d+(?:\.\d+)?)\s*([NS])\s*,\s*(?:Longitude\s+)?(\d+(?:\.\d+)?)\s*([EW])', quote, re.I)
        if match and re.search(r'\bWGS\s*84\b', quote, re.I):
            lat = float(match[1]) * (-1 if match[2].upper() == 'S' else 1)
            lon = float(match[3]) * (-1 if match[4].upper() == 'W' else 1)
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                points.add((lat, lon))
        elif location.get('point_verified') is True:
            lat, lon = location.get('latitude'), location.get('longitude')
            if isinstance(lat, (int,float)) and isinstance(lon, (int,float)) and -90<=lat<=90 and -180<=lon<=180:
                points.add((lat,lon))
    selected = {tuple(r['request']['coordinates']) for r in (environment or {}).get('requirements', [])
                if isinstance(r.get('request', {}).get('coordinates'), (list,tuple)) and len(r['request']['coordinates'])==2}
    if len(selected) != 1 or not selected.issubset(points):
        return 'POSITION_UNRESOLVED', 'A confirmed selected point consistent with a reviewed source-backed permit point is required; unsupported geometry remains unresolved.', 'UNKNOWN'
    if context.get('geofences'):
        return 'POSITION_UNRESOLVED', 'Geofence containment lacks a verified deterministic geometry evaluator; no containment is inferred.', 'UNKNOWN'
    return 'POSITION_CONFIRMED', 'Explicit selected request position matches a reviewed permitted point; evidence-grid safeguards apply separately.', 'WORK'


def evaluate_requirement(row, environment, start, end, now, linked):
    raw = row['original']
    effective = deepcopy(row.get('effective') or raw)
    if row['kind'] == 'environmental_requirement' and not (row['state']=='CORRECTED' and row.get('review', {}).get('corrections')):
        effective = canonical_stop_rule({**effective, 'source_verified': row['source'].get('source_verified') is True})
    gating = bool(row['decision_relevant_default'])
    result = {'requirement_id': row['target_id'], 'condition_id': row['condition_id'], 'kind': row['kind'],
              'gating': gating, 'review_state': row['state'], 'applicability': row['applicability'],
              'effective_rule': effective, 'source_spans': deepcopy(row['source'].get('source_spans', [])),
              'original_rule': deepcopy(raw),
              'source_verified': row['source'].get('source_verified') is True,
              'original_fingerprint': row['original_fingerprint'], 'review_reference': deepcopy(row.get('review')),
              'start': stamp(start), 'end': stamp(end), 'checks': [], 'evidence_references': []}

    def finish(code, message, status='UNKNOWN'):
        result.update(reason_code=code, explanation=message, status=status,
                      required_action=NEXT_ACTIONS.get(code, 'Inspect the reviewed source and assessment explanation.' if status == 'UNKNOWN' else 'No additional interpretation action for this result.'))
        # Explicit MVP availability policy, not a passing threshold result.
        # Review/source/interpretation blockers are deliberately not waived.
        availability_codes = {'EVIDENCE_MISSING', 'EVIDENCE_STALE', 'EVIDENCE_UNSUPPORTED',
            'PROVIDER_FAILURE', 'NO_COMPATIBLE_ACCESSIBLE_SOURCE', 'STALE_TURBIDITY_EVIDENCE',
            'TEMPORAL_COVERAGE_INSUFFICIENT', 'FORECAST_COVERAGE_INSUFFICIENT',
            'SPATIAL_COVERAGE_INSUFFICIENT', 'UNIT_INCOMPATIBLE', 'DEPTH_UNSATISFIED'}
        if (status == 'UNKNOWN' and result['gating'] and row['kind'] == 'environmental_requirement'
                and canonical(effective.get('canonical_variable')) == 'turbidity' and code in availability_codes):
            result['gating'] = False
            result['availability_policy'] = 'AVAILABLE_EVIDENCE_ONLY_MVP'
            result['availability_diagnostic'] = message
            state = 'stale' if code in {'STALE_TURBIDITY_EVIDENCE', 'EVIDENCE_STALE'} else 'unavailable'
            result['explanation'] = f'Turbidity evidence {state} — excluded from MVP work-window decision for this interval. ' + message
        from .informational_audit import attach_direction_audit
        attach_direction_audit(result, row, environment, start, end)
        return result

    if row['kind'] == 'decision_prerequisite':
        code, message, state = evaluate_prerequisite(raw, environment, start, end)
        result['effective_rule'] = {'requirement': f"Permit {raw['prerequisite']} prerequisite"}
        result['original_rule'] = {'prerequisite': raw['prerequisite'], 'context': deepcopy(raw['context'])}
        if raw['prerequisite']=='time':
            result['reviewed_validity_source']=reviewed_validity(raw['review_rows'])
        return finish(code, message, state)

    mappings = row.get('mapping', [])
    identity = re.fullmatch(r'environmental_requirement-(\d+)-.+', row['target_id'])
    if identity:
        mappings = [m for m in mappings if m.get('requirement_index') == int(identity[1])]
    effective_checks = derived_sst_checks({**effective, 'source_verified': result['source_verified']})
    fetchable = any(m.get('routing', {}).get('preferred_provider') in {'COPERNICUS_MARINE', 'ECMWF_FORECAST'}
                    and m['routing'].get('implemented') is True for m in mappings)
    thresholded = bool(effective_checks) and all(c.get('threshold') is not None and c.get('operator') in {'<','<=','>','>=','=','==','!='} for c in effective_checks)
    eligible = (row['kind'] == 'environmental_requirement' and gating and fetchable and thresholded
                and row['state'] in {'APPROVED','CORRECTED'} and row['applicability'] == 'APPLICABLE'
                and not row.get('conflict'))
    if not eligible:
        if (row['kind'] == 'environmental_requirement' and gating and thresholded and not fetchable
                and canonical(effective.get('canonical_variable')) == 'turbidity'
                and row['state'] in {'APPROVED','CORRECTED'} and row['applicability'] == 'APPLICABLE'
                and not row.get('conflict') and result['source_verified']):
            return finish('EVIDENCE_UNSUPPORTED', 'No compatible configured turbidity source is available.')
        result['gating'] = False
        return finish('OUT_OF_SCOPE_FOR_MVP_DECISION',
            'Retained for review/audit; not a reviewed applicable fetchable Copernicus/ECMWF numerical constraint. Other legal obligations remain unchanged.', 'WORK')

    if row.get('conflict'):
        return finish('REVIEW_CONFLICT', 'Review fingerprint or interpretation conflict requires resolution.')
    if row['applicability'] == 'NOT_APPLICABLE':
        result['gating'] = False
        return finish('NOT_APPLICABLE', 'Explicit reviewer applicability decision; retained in audit.', 'WORK')
    if not gating:
        unsupported = any(not m['routing']['implemented'] and m['routing']['preferred_provider'] != 'EXTERNAL' for m in row.get('mapping', []))
        return finish('EVIDENCE_UNSUPPORTED' if unsupported else 'INFORMATIONAL_ONLY',
                      'Informational or administrative record; it does not independently gate this assessment.', 'WORK')
    if row['state'] == 'UNREVIEWED':
        return finish('REVIEW_REQUIRED', 'Human interpretation review is required.')
    if row['state'] == 'REJECTED':
        return finish('REVIEW_REJECTED_UNRESOLVED', 'Rejected interpretation requires resolution or explicit Not Applicable decision.')
    if row['applicability'] != 'APPLICABLE':
        return finish('APPLICABILITY_UNASSESSED', 'Reviewer applicability is not yet assessed.')
    if not result['source_verified']:
        return finish('SOURCE_UNVERIFIED', 'Source quotation verification is unresolved.')
    if effective.get('threshold_interpretation_error'):
        return finish('INTERPRETATION_REQUIRED', effective['threshold_interpretation_error'])
    if row['kind'] != 'environmental_requirement':
        if row['kind'] == 'condition' and str(row['condition_id']) in linked:
            result['gating'] = False
            return finish('ENVIRONMENTAL_CONSTRAINT_LINKED', 'Physical checks are assessed under the linked environmental requirement(s).', 'WORK')
        return finish('EXTERNAL_EVIDENCE_REQUIRED', 'Verified geographic, operational, or manual evidence is required; review approval is not evidence.')

    # Mapping rows preserve requirement_index. Never join separate source obligations
    # merely because their condition numbers or provider variables happen to match.
    mappings = row.get('mapping', [])
    index = int(row['target_id'].split('-')[1])
    mappings = [m for m in mappings if m.get('requirement_index') == index]
    if not mappings:
        return finish('EVIDENCE_UNSUPPORTED', 'No authoritative environmental mapping exists for this requirement.')
    if mappings[0]['routing']['preferred_provider'] == 'EXTERNAL':
        return finish('EXTERNAL_EVIDENCE_REQUIRED', 'Verified external/manual evidence is required.')
    if not mappings[0]['routing']['implemented']:
        return finish('EVIDENCE_UNSUPPORTED', mappings[0]['routing']['notes'])
    if environment is None:
        if canonical(effective.get('canonical_variable')) == 'significant_wave_height':
            return finish('NO_WAVE_EVIDENCE', 'No stored compatible significant-wave-height evidence is available; the MVP recency policy cannot be evaluated.')
        return finish('EVIDENCE_MISSING', 'Environmental Fetch is required; no session-associated evidence exists.')
    candidates = [r for r in environment.get('requirements', []) if r.get('requirement_index') == index and str(r.get('condition_id')) == str(row['condition_id'])]
    if canonical(effective.get('canonical_variable')) != canonical(raw.get('canonical_variable')):
        return finish('EVIDENCE_MISSING', 'Corrected variable requires evidence for that exact physical variable.')
    if effective.get('geographic_scope') != raw.get('geographic_scope'):
        return finish('SPATIAL_COVERAGE_INSUFFICIENT', 'Corrected geographic scope requires independently validated evidence applicability.')
    if effective.get('temporal_requirement') != raw.get('temporal_requirement'):
        return finish('TEMPORAL_COVERAGE_INSUFFICIENT', 'Corrected timing requires explicit supported validity; no timing interpretation is inferred.')
    effective.update(source_verified=True, routing=mappings[0]['routing'])
    checks = derived_sst_checks(effective)
    if not checks or any(c.get('threshold') is None or c.get('operator') not in {'<', '<=', '>', '>=', '=', '==', '!='} for c in checks):
        return finish('INTERPRETATION_REQUIRED', 'A complete reviewed numerical constraint is required; no threshold is inferred.')
    if len(checks) > 1:
        children = [evaluate_requirement({**row, 'effective': c}, environment, start, end, now, linked) for c in checks]
        state = 'STOP' if any(c['status'] == 'STOP' for c in children) else 'UNKNOWN' if any(c['status'] == 'UNKNOWN' for c in children) else 'WORK'
        primary = next(c for c in children if c['status'] == state)
        result.update(check_results=children, checks=[check for c in children for check in c['checks']],
                      evidence_references=[ref for c in children for ref in c['evidence_references']])
        return finish(primary['reason_code'], primary['explanation'], state)
    all_states = []
    for check in checks:
        mapping = next((m for m in mappings if m.get('operator') == check.get('operator') and m.get('threshold') == check.get('threshold')), mappings[0])
        routing = mapping['routing']
        if routing['preferred_provider'] == 'EXTERNAL':
            return finish('EXTERNAL_EVIDENCE_REQUIRED', 'Verified external/manual evidence is required.')
        if not routing['implemented']:
            return finish('EVIDENCE_UNSUPPORTED', routing['notes'])
        # Corrected thresholds reuse physical evidence, never old comparison booleans.
        candidate = next((c for c in candidates if c.get('operator') == mapping.get('operator') and c.get('threshold') == mapping.get('threshold')), None)
        if candidate is None:
            if canonical(check.get('canonical_variable')) == 'significant_wave_height':
                return finish('NO_WAVE_EVIDENCE', 'Stored evidence for the exact reviewed wave requirement is unavailable.')
            return finish('EVIDENCE_MISSING', 'Evidence for the exact requirement/check is unavailable.')
        if candidate.get('provider_diagnostic') or candidate.get('retrieval_status') == 'FAILED':
            diagnostic = candidate.get('provider_diagnostic', {})
            code = 'DEPTH_UNSATISFIED' if 'DEPTH' in diagnostic.get('provider_error_category', '') else 'PROVIDER_FAILURE'
            variable = canonical(check.get('canonical_variable'))
            category = diagnostic.get('provider_error_category', '')
            if variable == 'turbidity' and category in {'STALE_TURBIDITY_EVIDENCE', 'NO_COMPATIBLE_ACCESSIBLE_SOURCE', 'CONFIGURED_DATASET_UNAVAILABLE'}:
                code = 'STALE_TURBIDITY_EVIDENCE' if category == 'STALE_TURBIDITY_EVIDENCE' else 'NO_COMPATIBLE_ACCESSIBLE_SOURCE'
            if variable == 'dissolved_oxygen' and source_depth({**check, 'routing': routing})[0] == 0 and 'DEPTH' in category:
                code = 'NO_COMPATIBLE_OXYGEN_SOURCE'
            return finish(code, diagnostic.get('provider_error_message', 'Provider retrieval failed.'))
        evidence = candidate.get('evidence')
        if not evidence:
            if canonical(check.get('canonical_variable')) == 'significant_wave_height':
                return finish('NO_WAVE_EVIDENCE', 'No compatible stored wave sample is available under the MVP recency policy.')
            notes = candidate.get('notes_for_evaluation', '')
            if notes == routing.get('notes'):
                notes = ''
            code = problem([notes]) if notes else 'EVIDENCE_MISSING'
            return finish(code, notes or 'Environmental evidence is missing.')
        result['evidence_references'].append({
            'evidence_id': candidate.get('evidence_request_key'), 'provider': evidence.get('provider'),
            'dataset_id': evidence.get('dataset_id'), 'dataset_variable': evidence.get('dataset_variable'),
            'issue_time': evidence.get('forecast_initialization'), 'retrieved_at': evidence.get('retrieved_at'),
            'latitude': evidence.get('latitude'), 'longitude': evidence.get('longitude'), 'distance_km': evidence.get('distance_km'),
            'requested_coordinates': evidence.get('requested_coordinates'), 'spatial_resolution': evidence.get('spatial_resolution'),
            'selected_depth_m': evidence.get('selected_depth_m', evidence.get('depth')), 'requested_depth': evidence.get('requested_depth'),
            'data_type': evidence.get('data_type'),
            'temporal_resolution': evidence.get('temporal_resolution'), 'source_temporal_resolution_seconds': evidence.get('source_temporal_resolution_seconds'),
            'coverage': deepcopy(evidence.get('coverage')), 'spatial_status': evidence.get('spatial_distance_status'),
            'direction_convention': evidence.get('direction_convention'), 'request': deepcopy(candidate.get('request'))})
        result['evidence_references'][-1].update(quality_status=evidence.get('quality_status'),
            applicability_status=evidence.get('applicability_status'),qualification=evidence.get('qualification'),
            max_representative_distance_km=evidence.get('max_representative_distance_km'))
        if evidence.get('provider') != routing['preferred_provider'] or evidence.get('canonical_variable') != canonical(effective.get('canonical_variable')) or not evidence.get('dataset_id'):
            return finish('EVIDENCE_MISSING', 'Provider/dataset/physical-variable provenance does not match the reviewed requirement.')
        try:
            age = (now - utc(evidence['retrieved_at'])).total_seconds()
            if age < 0 or age > 21600 and evidence.get('data_type') != 'REANALYSIS':
                return finish('EVIDENCE_STALE', 'Evidence retrieval is stale or future-dated.')
            if evidence.get('forecast_initialization') and (now - utc(evidence['forecast_initialization'])).total_seconds() > 86400:
                return finish('EVIDENCE_STALE', 'Forecast initialization is stale.')
        except (KeyError, ValueError, TypeError):
            return finish('EVIDENCE_STALE', 'Required retrieval timestamp is unavailable.')
        if not stored_spatial_suitable(evidence):
            return finish('SPATIAL_COVERAGE_INSUFFICIENT', 'Spatial suitability/representativeness remains unresolved.')
        if candidate.get('request', {}).get('coordinates') and list(candidate['request']['coordinates']) != evidence.get('requested_coordinates'):
            return finish('SPATIAL_COVERAGE_INSUFFICIENT', 'Evidence location differs from the confirmed request.')
        depth, depth_error = source_depth({**check, 'routing': routing})
        if depth_error or canonical(effective.get('canonical_variable')) == 'dissolved_oxygen' and depth is None:
            return finish('DEPTH_UNSATISFIED', depth_error or 'Explicit source-backed oxygen depth is required.')
        if depth is not None:
            selected = evidence.get('selected_depth_m', evidence.get('depth'))
            try:
                compatible_depth = selected is not None and math.isfinite(float(selected)) and abs(float(selected) - depth) <= .5
            except (TypeError, ValueError):
                compatible_depth = False
            if not compatible_depth:
                return finish('DEPTH_UNSATISFIED', 'Selected depth does not satisfy the requested depth and 0.5 m tolerance.')
        points = evidence.get('points', [])
        step = native_step(evidence)
        try:
            times = [(utc(p['data_time']), p) for p in points]
            times.sort(key=lambda pair: pair[0])
            coverage = evidence.get('coverage') or {}
            if start < utc(coverage['requested_start']) or end > utc(coverage['requested_end']):
                return finish('FORECAST_COVERAGE_INSUFFICIENT', 'Interval exceeds the confirmed environmental request period.')
        except (KeyError, ValueError, TypeError):
            return finish('TEMPORAL_COVERAGE_INSUFFICIENT', 'Evidence validity timestamps or requested coverage are unavailable.')
        from src.environmental.recency import policy, select
        reference_rule = policy(canonical(check.get('canonical_variable')), depth, wave_height=True)
        if reference_rule:
            expected_modes = {'SATELLITE_OBSERVATION', 'OBSERVATION'} if canonical(check.get('canonical_variable')) == 'turbidity' else {'MODEL_FORECAST'}
            if evidence.get('data_type') not in expected_modes:
                return finish(reference_rule[2], 'Compatible observation/model evidence mode is required by the recency policy.')
            point, reference_metadata = select(points, start, canonical(check.get('canonical_variable')), depth, wave_height=True)
            result['evidence_references'][-1]['recency_policy'] = reference_metadata
            if point is None:
                return finish(reference_metadata['reason_code'], 'Compatible historical/reference evidence is absent or outside the configured maximum age.')
            if (end-utc(point['data_time'])).total_seconds() > reference_rule[0]*3600:
                return finish(reference_rule[1], 'Reference evidence exceeds the configured age limit within this interval; no extended validity is inferred.')
            used = {point['data_time']: point}
        elif not step or step > 21600:
            return finish('TEMPORAL_COVERAGE_INSUFFICIENT', 'Native sampling cannot establish a subdaily work window.')
        if len({t for t,p in times}) != len(times):
            return finish('TEMPORAL_COVERAGE_INSUFFICIENT', 'Duplicate native timestamps require resolution.')
        source_step = evidence.get('source_temporal_resolution_seconds')
        if source_step and any((b[0]-a[0]).total_seconds() < source_step for a,b in zip(times,times[1:])):
            return finish('TEMPORAL_COVERAGE_INSUFFICIENT', 'Provider output is finer than native source resolution; independent finer measurements are not inferred.')
        pairs = [(a,b) for a,b in zip(times,times[1:]) if a[0] < end and b[0] > start]
        if not reference_rule and (not pairs or pairs[0][0][0] > start or pairs[-1][1][0] < end or any((b[0]-a[0]).total_seconds() > step or b[0] <= a[0] for a,b in pairs)):
            return finish('FORECAST_COVERAGE_INSUFFICIENT', 'Native evidence does not cover the whole interval without gaps.')
        if not reference_rule:
            used = {stamp(t): p for a,b in pairs for t,p in (a,b)}
        semantics = precipitation_accumulation_semantics(check)
        if semantics:
            used = {t:p for t,p in used.items() if utc(t) > start}
        notes = [n for p in used.values() for n in p.get('validation_notes', [])]
        if notes:
            return finish(problem(notes), '; '.join(dict.fromkeys(notes)))
        if any(p.get('status') == 'INSUFFICIENT_DATA' for p in used.values()):
            return finish('EVIDENCE_MISSING', 'Evidence points did not pass existing validity screening.')
        values = []
        for t,p in used.items():
            try:
                if isinstance(p.get('raw_value'), bool):
                    return finish('EVIDENCE_MISSING', 'Boolean data is not a physical measurement.')
                if semantics:
                    mode = str(p.get('temporal_semantics') or '').upper()
                    if canonical_unit(p.get('unit')).lower() != 'mm' or p.get('accumulation_interval_seconds') != 3600 or 'ACCUMULATED' not in mode or 'RATE' in mode:
                        return finish('UNIT_INCOMPATIBLE', 'Hourly accumulated quantity and interval metadata are required.')
                    value = float(p['raw_value'])
                else:
                    value = convert(p['raw_value'], p['unit'], check['unit'], variable=canonical(check['canonical_variable']))
                if not math.isfinite(value) or not math.isfinite(float(check['threshold'])):
                    return finish('EVIDENCE_MISSING', 'Nonfinite measurement or threshold.')
            except (KeyError, ValueError, TypeError):
                return finish('UNIT_INCOMPATIBLE', 'Measurement or compatible quantity units are unavailable.')
            threshold = check['threshold']
            source_text = ' '.join(s.get('quotation') or '' for s in row['source'].get('source_spans', []))
            absolute_component = (canonical(check.get('canonical_variable')) in {'eastward_current','northward_current'}
                                  and re.search(r'\babsolute\s+(?:eastward|northward|current|component|value|[UV]\b)', source_text, re.I))
            if absolute_component:
                value = abs(value)  # Signed provider value remains in raw_value.
            triggered = {'>': value > threshold, '>=': value >= threshold, '<': value < threshold,
                         '<=': value <= threshold, '=': value == threshold, '==': value == threshold, '!=': value != threshold}[check['operator']]
            values.append({'valid_time': t, 'value': value, 'unit': check['unit'], 'triggered': triggered,
                           'raw_value': p.get('raw_value'), 'raw_unit': p.get('unit')})
        instantaneous_wave = canonical(check.get('canonical_variable')) == 'significant_wave_height' and not reference_rule
        if instantaneous_wave:
            # Cadence is not a hold-last-value/continuous-validity declaration.
            # Only explicit stored bounds can extend a sample beyond its timestamp.
            spans=[]
            active=[]
            for v in values:
                point=used[v['valid_time']]
                try:
                    a,b=utc(point['valid_start']),utc(point['valid_end'])
                    if point.get('temporal_semantics')!='INTERVAL_VALID' or a>=b:
                        raise ValueError()
                except (KeyError,ValueError,TypeError):
                    if start<=utc(v['valid_time'])<end:
                        active.append(v)
                    continue
                if a<end and b>start:
                    spans.append((max(a,start),min(b,end)))
                    active.append(v)
            observed_trigger=any(v['triggered'] for v in active)
            cursor=start
            for a,b in sorted(spans):
                if a>cursor:
                    break
                cursor=max(cursor,b)
            result['checks'].append({'operator':check['operator'],'threshold':check['threshold'],'unit':check['unit'],
                                     'values':active,'status':'STOP' if observed_trigger else 'WORK' if cursor>=end else 'UNKNOWN',
                                     'temporal_semantics':'EXPLICIT_BOUNDS_OR_NATIVE_INSTANTS'})
            if observed_trigger:
                all_states.append('STOP')
                continue
            if cursor<end:
                return finish('TEMPORAL_COVERAGE_INSUFFICIENT', 'Native wave point samples do not establish continuous passing evidence between timestamps; no hold or transition is inferred.')
            all_states.append('WORK')
            continue
        observed_trigger = any(v['triggered'] and (reference_rule or start <= utc(v['valid_time']) <= end) for v in values)
        if any(v['triggered'] for v in values) and not observed_trigger:
            return finish('TEMPORAL_COVERAGE_INSUFFICIENT', 'A bracketing sample triggers outside this interval; the transition time cannot be inferred.')
        state = 'STOP' if observed_trigger else 'WORK'
        all_states.append(state)
        result['checks'].append({'operator': check['operator'], 'threshold': threshold, 'unit': check['unit'],
                                 'derivation': check.get('derivation'), 'values': values, 'status': state,
                                 **({'recency_policy': reference_metadata} if reference_rule else {})})
    status = 'STOP' if 'STOP' in all_states else 'WORK'
    return finish('CONSTRAINT_TRIGGERED' if status == 'STOP' else 'CONSTRAINT_PASSED',
                  ((f"Recent wave evidence accepted under the configured {reference_metadata['max_age_minutes']}-minute MVP recency policy; not a provider-declared continuous validity interval. "
                    f"Native timestamp {reference_metadata['source_timestamp']}; age {reference_metadata['age_minutes']:g} minutes at {reference_metadata['assessed_time']}.")
                   if reference_rule and canonical(check.get('canonical_variable')) == 'significant_wave_height' else
                   'Historical/reference evidence accepted under the configured recency policy; not a contemporaneous measurement or inferred continuous validity.' if reference_rule else
                   'Reviewed trigger is met by valid native evidence.' if status == 'STOP' else 'All reviewed checks pass on the native evidence covering this interval.'), status)


def evaluate_interval(rows, environment, start, end, now):
    linked = {str(r['condition_id']) for r in rows if r['kind'] == 'environmental_requirement' and r['decision_relevant_default']}
    results = [evaluate_requirement(r, environment, start, end, now, linked) for r in rows]
    state = aggregate(results)
    return {'start': stamp(start), 'end': stamp(end), 'status': state, 'explanation': EXPLANATIONS[state],
            'primary_reason': next((r['reason_code'] for r in results if r['gating'] and r['status'] == state), 'NO_APPLICABLE_CONSTRAINTS'),
            'passed_count': sum(r['gating'] and r['kind'] == 'environmental_requirement' and r['status'] == 'WORK' for r in results),
            'stop_count': sum(r['gating'] and r['status'] == 'STOP' for r in results),
            'unknown_count': sum(r['gating'] and r['status'] == 'UNKNOWN' for r in results),
            'evidence_gap_count': sum(r['gating'] and r['status'] == 'UNKNOWN' for r in results), 'rule_results': results}


def find_windows(timeline, duration_hours, include_conditional=False, ranking='earliest'):
    """Maximal adjacent non-STOP runs; entire run must meet requested duration."""
    runs = []
    run = []
    for item in timeline:
        allowed = item['status'] == 'WORK' or include_conditional and item['status'] == 'UNKNOWN' and item['passed_count'] > 0
        if run and (not allowed or run[-1]['end'] != item['start']):
            runs.append(run); run = []
        if allowed:
            run.append(item)
    if run:
        runs.append(run)
    windows = find_windows(timeline, duration_hours, False, ranking) if include_conditional else []
    for group in runs:
        hours = (utc(group[-1]['end']) - utc(group[0]['start'])).total_seconds()/3600
        if hours < duration_hours:
            continue
        state = 'UNKNOWN' if any(i['status'] == 'UNKNOWN' for i in group) else 'WORK'
        if include_conditional and state == 'WORK':
            continue
        windows.append({'start': group[0]['start'], 'end': group[-1]['end'], 'duration_hours': hours, 'status': state,
                        'type': 'CONDITIONAL' if state == 'UNKNOWN' else 'VERIFIED',
                        'primary_reason': next((i['primary_reason'] for i in group if i['status'] == 'UNKNOWN'), 'CONSTRAINT_PASSED'),
                        'unknown_count': max(i['unknown_count'] for i in group), 'passed_count': min(i['passed_count'] for i in group),
                        'stop_count': 0, 'intervals': [{'start': i['start'], 'end': i['end']} for i in group]})
    return sorted(windows, key=(lambda w: (-w['duration_hours'], w['start'])) if ranking == 'longest' else (lambda w: w['start']))


def assess(review_data, environmental_result=None, *, start=None, horizon_hours=72, duration_hours=4,
           include_conditional=False, ranking='earliest', now=None):
    now = utc(now or datetime.now(timezone.utc))
    requested_start = stamp(utc(start)) if start else None
    start = utc(start) if start else now
    if horizon_hours not in {24,48,72} or duration_hours not in {2,4,6,12} or ranking not in {'earliest','longest'}:
        raise ValueError('INVALID_DECISION_OPTIONS')
    environment = environmental_result if environmental_result and environmental_result.get('analysis_id') == review_data['analysis_run_id'] else None
    rows = deepcopy(review_data['requirements'])
    rows.extend(prerequisite_rows(review_data))
    end = start + timedelta(hours=horizon_hours)
    # Use actual timestamps only. Horizon edges mark requested coverage, not samples.
    boundaries = {start, end}
    evidence_rows=(environment or {}).get('requirements', [])
    point_wave_rows=[r for r in evidence_rows if canonical(r.get('canonical_variable'))=='significant_wave_height'
        and any(row['kind']=='environmental_requirement' and row['state'] in {'APPROVED','CORRECTED'}
                and row['applicability']=='APPLICABLE' and row['decision_relevant_default']
                and row['source'].get('source_verified') is True
                and any(m.get('requirement_index')==r.get('requirement_index')
                        and m.get('threshold') is not None
                        and m.get('routing',{}).get('preferred_provider')=='COPERNICUS_MARINE'
                        and m['routing'].get('implemented') is True for m in row.get('mapping',[])) for row in rows)
        and r.get('evidence',{}).get('points') and not all(p.get('temporal_semantics')=='INTERVAL_VALID'
            and p.get('valid_start') and p.get('valid_end') for p in r['evidence']['points'])]
    # Do not fabricate finer wave transitions from another variable's cadence.
    # Other constraints still evaluate every native sample inside these cells.
    partition_rows=point_wave_rows or evidence_rows
    for row in partition_rows:
        for point in row.get('evidence', {}).get('points', []):
            try:
                t = utc(point['data_time'])
                if start < t < end:
                    boundaries.add(t)
                if canonical(row.get('canonical_variable')) == 'significant_wave_height':
                    from src.environmental.recency import WAVE_HEIGHT_MAX_AGE_MINUTES
                    expiry = t + timedelta(minutes=WAVE_HEIGHT_MAX_AGE_MINUTES)
                    later_native = [utc(p['data_time']) for p in row.get('evidence', {}).get('points', [])]
                    if start < expiry < end and not any(t < native <= expiry for native in later_native):
                        # Policy expiry, not an inferred provider validity or
                        # physical threshold-crossing time.
                        boundaries.add(expiry)
            except (KeyError, ValueError, TypeError):
                pass
    ordered = sorted(boundaries)
    timeline = [evaluate_interval(rows, environment, a, b, now) for a,b in zip(ordered, ordered[1:])]
    current_end = start + timedelta(hours=duration_hours)
    current_parts = [evaluate_interval(rows, environment, utc(i['start']), min(utc(i['end']), current_end), now)
                     for i in timeline if utc(i['start']) < current_end]
    combined = []
    for row in rows:
        parts = [r for i in current_parts for r in i['rule_results'] if r['requirement_id'] == row['target_id']]
        state = 'STOP' if any(r['status'] == 'STOP' for r in parts) else 'UNKNOWN' if any(r['status'] == 'UNKNOWN' for r in parts) else 'WORK'
        primary = next(r for r in parts if r['status'] == state)
        combined.append({**primary, 'start': stamp(start), 'end': stamp(current_end),
                         'has_evidence_gap': any(r['gating'] and r['status'] == 'UNKNOWN' for r in parts),
                         'interval_results': parts, 'checks': [c for r in parts for c in r['checks']],
                         'evidence_references': [e for r in parts for e in r['evidence_references']]})
    current_state = aggregate(combined)
    current = {'start': stamp(start), 'end': stamp(current_end), 'status': current_state,
               'explanation': EXPLANATIONS[current_state], 'rule_results': combined,
               'passed_count': sum(r['gating'] and r['kind'] == 'environmental_requirement' and r['status'] == 'WORK' for r in combined),
               'stop_count': sum(r['gating'] and r['status'] == 'STOP' for r in combined),
               'unknown_count': sum(r['gating'] and r['status'] == 'UNKNOWN' for r in combined),
               'evidence_gap_count': sum(r['has_evidence_gap'] for r in combined)}
    current['primary_reason'] = next((r['reason_code'] for r in combined if r['gating'] and r['status'] == current_state), 'NO_APPLICABLE_CONSTRAINTS')
    windows = find_windows(timeline, duration_hours, include_conditional, ranking)
    evidence_gaps = [next(p for p in r['interval_results'] if p['gating'] and p['status'] == 'UNKNOWN')
                     for r in combined if r['has_evidence_gap']]
    audit = {'analysis_run_id': review_data['analysis_run_id'], 'document_sha256': review_data['document_sha256'],
             'requested_start': requested_start,
             'assessed_at': stamp(now), 'start': stamp(start), 'end': stamp(end), 'horizon_hours': horizon_hours,
             'duration_hours': duration_hours, 'include_conditional': include_conditional, 'ranking': ranking,
             'evaluated_requirement_ids': [r['target_id'] for r in rows],
             'evidence_present': environment is not None, 'assessment_type': 'Advisory / Evidence assessment',
             'interval_semantics': 'Native wave timestamps and MVP recency expiry partition Hs assessments. Each cell uses its start instant and the newest compatible past Hs sample; no cell may extend beyond its policy age limit. This is not provider-declared validity or an inferred crossing time. No interpolation. Outside confirmed coverage remains UNKNOWN.' if point_wave_rows else 'Native timestamp partition; bracketing samples retained without interpolation. Coverage outside the confirmed request remains UNKNOWN.'}
    result = {'current_assessment': current, 'timeline': timeline, 'candidate_windows': windows,
              'evidence_gaps': evidence_gaps, 'audit': audit, 'disclaimer': DISCLAIMER}
    result['assessment_id'] = sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
    return result
