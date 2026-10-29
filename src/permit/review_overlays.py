"""F04 overlays over immutable extraction records; no extraction or provider calls."""
import json
import math
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import RLock
from uuid import uuid4

LOCK = RLock()
STATES = {'UNREVIEWED', 'APPROVED', 'CORRECTED', 'REJECTED'}
APPLICABILITY = {'UNASSESSED', 'APPLICABLE', 'NOT_APPLICABLE'}
FIELDS = {
    'condition': {'requirement', 'important_limit', 'timing'},
    'environmental_requirement': {'variable', 'canonical_variable', 'operator', 'threshold', 'unit',
                                  'temporal_requirement', 'depth_requirement', 'geographic_scope'},
    'geofence': {'description', 'restriction'},
    'spatial_context': set(),
}
ARRAYS = {'condition': 'conditions', 'environmental_requirement': 'environmental_requirements', 'geofence': 'geofences', 'spatial_context': 'spatial_context'}


def fingerprint(record):
    return sha256(json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def context(root, analysis):
    digest, run = analysis.get('document_sha256', ''), analysis.get('analysis_id', '')
    if not re.fullmatch('[0-9a-f]{64}', digest) or not re.fullmatch('[0-9a-f]{32,64}', run):
        raise ValueError('INVALID_REVIEW_IDENTITY')
    folder = Path(root) / 'cache' / 'simple_analysis' / digest / run
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    original = json.loads((folder / 'analysis.json').read_text(encoding='utf-8'))
    if manifest.get('document_sha256') != digest or manifest.get('run_id') != run or original.get('analysis_id') != run:
        raise ValueError('REVIEW_IDENTITY_CONFLICT')
    path = Path(root) / 'cache' / 'simple_reviews' / digest / run / 'review_overlays.json'
    return original, path


def validate_review(data, kind, original):
    allowed = {'original_fingerprint', 'state', 'applicability', 'corrections', 'reviewer', 'note'}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError('INVALID_REVIEW_FIELDS')
    if not isinstance(data.get('state'), str) or not isinstance(data.get('applicability'), str) or data['state'] not in STATES or data['applicability'] not in APPLICABILITY:
        raise ValueError('INVALID_REVIEW_STATE')
    if not isinstance(data.get('reviewer'), str) or not data['reviewer'].strip():
        raise ValueError('REVIEWER_REQUIRED')
    if not isinstance(data.get('note', ''), str):
        raise ValueError('INVALID_REVIEW_NOTE')
    if data['applicability'] == 'NOT_APPLICABLE' and not data.get('note', '').strip():
        raise ValueError('APPLICABILITY_NOTE_REQUIRED')
    changes = data.get('corrections', {})
    if not isinstance(changes, dict) or set(changes) - FIELDS[kind]:
        raise ValueError('INVALID_CORRECTION_FIELDS')
    if data['state'] != 'CORRECTED' and changes or data['state'] == 'CORRECTED' and not changes:
        raise ValueError('INVALID_CORRECTION_STATE')
    for key, value in changes.items():
        if key == 'threshold':
            if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value)):
                raise ValueError('INVALID_THRESHOLD')
        elif key == 'operator':
            if value is not None and (not isinstance(value, str) or value not in {'<', '<=', '>', '>=', '=', '==', 'BETWEEN'}):
                raise ValueError('INVALID_OPERATOR')
            if value == 'BETWEEN':
                raise ValueError('RANGE_CORRECTION_NOT_SUPPORTED')
        elif value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError('INVALID_CORRECTION_VALUE')
        elif value is None and key in {'variable', 'canonical_variable', 'requirement', 'restriction', 'description'}:
            raise ValueError('REQUIRED_CORRECTION_VALUE')
    effective = {**original, **changes}
    if kind == 'environmental_requirement' and effective.get('threshold') is not None:
        if not effective.get('unit') or not str(effective['unit']).strip() or effective.get('operator') not in {'<', '<=', '>', '>=', '=', '=='}:
            raise ValueError('THRESHOLD_UNIT_OPERATOR_REQUIRED')


def relevance(record, kind):
    if kind == 'spatial_context':
        return True
    if kind == 'geofence':
        return True
    if kind == 'condition':
        return record.get('category') in {'Positioning / Geographic', 'Operational / Safety'}
    text = ' '.join(str(record.get(k) or '') for k in ('requirement_text', 'temporal_requirement')).lower()
    return record.get('threshold') is not None or bool(re.search(r'\b(?:below|above|greater than|less than)\s*-?\d', text))


def targets(original):
    return {f'{kind}-{index}-{fingerprint(record)[:16]}': (kind, index, record)
            for kind, array in ARRAYS.items() for index, record in enumerate(original.get(array, []))}


def read_store(path):
    if not path.exists():
        return {'schema_version': 'permitpulse.review-store.v1', 'overlays': {}, 'history': []}
    try:
        store = json.loads(path.read_text(encoding='utf-8'))
        if store.get('schema_version') != 'permitpulse.review-store.v1' or not isinstance(store.get('overlays'), dict) or not isinstance(store.get('history'), list) or any(not isinstance(v, dict) or not v for v in store['overlays'].values()):
            raise ValueError()
        return store
    except (ValueError, TypeError, AttributeError, OSError):
        raise ValueError('MALFORMED_REVIEW_STORE') from None


def review_progress(rows):
    """Human interpretation and applicability completion, separate from evidence quality."""
    def resolved(row):
        return (not row.get('conflict')
                and row['state'] in {'APPROVED', 'CORRECTED'}
                and row['applicability'] in {'APPLICABLE', 'NOT_APPLICABLE'}
                and (row['applicability'] != 'NOT_APPLICABLE'
                     or bool((row.get('review') or {}).get('note', '').strip())))
    total = len(rows)
    remaining = sum(not resolved(row) for row in rows)
    return {'total': total, 'resolved': total - remaining,
            'remaining': remaining, 'complete': total > 0 and remaining == 0}


def list_reviews(root, analysis):
    original, path = context(root, analysis)
    store = read_store(path)
    rows = []
    for target_id, (kind, index, raw) in targets(original).items():
        overlay = store['overlays'].get(target_id)
        conflict = None
        if overlay:
            try:
                if overlay.get('original_fingerprint') != fingerprint(raw) or overlay.get('analysis_run_id') != analysis['analysis_id'] or overlay.get('document_sha256') != analysis['document_sha256'] or overlay.get('target') != {'kind': kind, 'id': target_id}:
                    raise ValueError('REVIEW_FINGERPRINT_CONFLICT')
                validate_review({k: overlay[k] for k in ('original_fingerprint', 'state', 'applicability', 'corrections', 'reviewer', 'note')}, kind, raw)
            except (ValueError, KeyError, AttributeError):
                conflict = 'REVIEW_CONFLICT'
        state = overlay['state'] if overlay and not conflict else 'UNREVIEWED'
        effective = deepcopy(raw) if state == 'APPROVED' else {**deepcopy(raw), **overlay['corrections']} if state == 'CORRECTED' else None
        current = analysis.get(ARRAYS[kind], [])
        source = current[index] if index < len(current) else raw
        mapping = [r for r in analysis.get('environmental_mapping', []) if str(r.get('condition_id')) == str(raw.get('condition_id'))] if kind == 'environmental_requirement' else []
        rows.append({'target_id': target_id, 'kind': kind, 'condition_id': raw.get('condition_id', raw.get('number', raw.get('name', raw.get('location_name')))),
                     'original_fingerprint': fingerprint(raw), 'original': raw, 'source': source, 'mapping': mapping,
                     'review': overlay if not conflict else None, 'state': state, 'conflict': conflict,
                     'applicability': overlay['applicability'] if overlay and not conflict else 'UNASSESSED',
                     'effective': effective, 'decision_relevant_default': relevance(raw, kind),
                     'correction_fields': sorted(FIELDS[kind])})
    if set(store['overlays']) - set(targets(original)):
        raise ValueError('REVIEW_TARGET_CONFLICT')
    for row in rows:
        row['bulk_blocker'] = bulk_blocker(row)
        row['bulk_eligible'] = row['bulk_blocker'] is None
    decision_context = {key: deepcopy(analysis.get(key)) for key in ('temporal_context','spatial_context','geofences')}
    for row in rows:
        if row['kind'] == 'spatial_context' and row['state'] == 'APPROVED' and row['applicability'] == 'APPLICABLE' and row['source'].get('source_verified') is True:
            decision_context['spatial_context'][targets(original)[row['target_id']][1]]['point_verified'] = True
    return {'analysis_run_id': analysis['analysis_id'], 'document_sha256': analysis['document_sha256'], 'requirements': rows,
            'review_progress': review_progress(rows), 'decision_context': decision_context}


def bulk_blocker(row):
    if row['kind'] == 'spatial_context':
        return 'SPATIAL_REVIEW_REQUIRES_EXPLICIT_ACTION'
    if row['conflict']:
        return 'REVIEW_CONFLICT'
    if row['state'] != 'UNREVIEWED':
        return 'ALREADY_REVIEWED'
    if row['applicability'] == 'NOT_APPLICABLE':
        return 'NOT_APPLICABLE'
    if (row.get('review') or {}).get('corrections'):
        return 'EXISTING_CORRECTIONS'
    if row['source'].get('source_verified') is not True:
        return 'SOURCE_UNVERIFIED'
    try:
        validate_review({'state': 'APPROVED', 'applicability': row['applicability'],
                         'reviewer': 'Local reviewer', 'note': '', 'corrections': {}}, row['kind'], row['original'])
    except ValueError as exc:
        return str(exc)
    return None


def approved_spatial_points(review_data):
    """Return only explicitly approved, source-backed point coordinates."""
    points = set()
    for row in review_data.get('requirements', []):
        source = row.get('source', {})
        if (row.get('kind') == 'spatial_context' and row.get('state') == 'APPROVED'
                and row.get('applicability') == 'APPLICABLE'
                and source.get('source_verified') is True and source.get('geometry_type') == 'point'):
            lat, lon = source.get('latitude'), source.get('longitude')
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and -90 <= lat <= 90 and -180 <= lon <= 180:
                points.add((lat, lon))
    return points


def write_store(path, store):
    """Single atomic replacement shared by individual and bulk review saves."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{uuid4().hex}.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as handle:
            handle.write(json.dumps(store, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def bulk_approve(root, analysis, reviewer, expected):
    """Approve the explicitly confirmed snapshot; skip unsafe records individually."""
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError('REVIEWER_REQUIRED')
    if not isinstance(expected, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in expected.items()):
        raise ValueError('INVALID_BULK_TARGETS')
    with LOCK:
        _, path = context(root, analysis)
        current = list_reviews(root, analysis)
        store = read_store(path)
        known = {row['target_id'] for row in current['requirements']}
        if set(expected) - known:
            raise ValueError('UNKNOWN_REVIEW_TARGET')
        results = []
        eligible_count = 0
        for row in current['requirements']:
            target_id = row['target_id']
            reason = row['bulk_blocker']
            if reason:
                results.append({'target_id': target_id, 'status': 'SKIPPED', 'reason': reason})
                continue
            if target_id not in expected:
                results.append({'target_id': target_id, 'status': 'SKIPPED', 'reason': 'NOT_CONFIRMED'})
                continue
            eligible_count += 1
            if expected[target_id] != row['original_fingerprint']:
                results.append({'target_id': target_id, 'status': 'FAILED', 'reason': 'REVIEW_FINGERPRINT_CONFLICT'})
                continue
            previous = row['review'] or {}
            overlay = {'schema_version': 'permitpulse.review-overlay.v1', 'analysis_run_id': analysis['analysis_id'],
                       'document_sha256': analysis['document_sha256'], 'target': {'kind': row['kind'], 'id': target_id},
                       'original_fingerprint': row['original_fingerprint'], 'state': 'APPROVED',
                       'applicability': row['applicability'], 'corrections': {}, 'reviewer': reviewer,
                       'note': previous.get('note', ''), 'reviewed_at': datetime.now(timezone.utc).isoformat()}
            validate_review({k: overlay[k] for k in ('original_fingerprint', 'state', 'applicability', 'corrections', 'reviewer', 'note')}, row['kind'], row['original'])
            store['overlays'][target_id] = overlay
            store['history'].append(deepcopy(overlay))
            results.append({'target_id': target_id, 'status': 'APPROVED', 'reason': None})
        approved = sum(item['status'] == 'APPROVED' for item in results)
        if approved:
            write_store(path, store)
        return {**list_reviews(root, analysis), 'eligible_count': eligible_count, 'approved_count': approved,
                'skipped_count': sum(item['status'] == 'SKIPPED' for item in results),
                'failed_count': sum(item['status'] == 'FAILED' for item in results), 'results': results}


def save_review(root, analysis, target_id, data):
    with LOCK:
        original, path = context(root, analysis)
        target = targets(original).get(target_id)
        if target is None:
            raise ValueError('UNKNOWN_REVIEW_TARGET')
        kind, _, raw = target
        if data.get('original_fingerprint') != fingerprint(raw):
            raise ValueError('REVIEW_FINGERPRINT_CONFLICT')
        if kind == 'spatial_context' and data.get('state') == 'APPROVED' and data.get('applicability') == 'UNASSESSED':
            data = {**data, 'applicability': 'APPLICABLE'}
        validate_review(data, kind, raw)
        store = read_store(path)
        # Validate existing overlays before replacing anything.
        existing = list_reviews(root, analysis)
        if any(row['conflict'] for row in existing['requirements']):
            raise ValueError('REVIEW_CONFLICT')
        overlay = {**deepcopy(data), 'corrections': deepcopy(data.get('corrections', {})), 'note': data.get('note', ''),
                   'schema_version': 'permitpulse.review-overlay.v1', 'analysis_run_id': analysis['analysis_id'],
                   'document_sha256': analysis['document_sha256'], 'target': {'kind': kind, 'id': target_id},
                   'reviewed_at': datetime.now(timezone.utc).isoformat()}
        store['overlays'][target_id] = overlay
        store['history'].append(deepcopy(overlay))
        write_store(path, store)
        return list_reviews(root, analysis)
