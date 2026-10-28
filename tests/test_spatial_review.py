"""Offline spatial-source verification and explicit point-review gates."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from src.permit.simple_analysis import apply_source_verification
from src.permit.review_overlays import approved_spatial_points, list_reviews, save_review


QUOTE = 'Latitude 54.025000 N, Longitude 5.925000 W, coordinate reference system WGS84.'


def location(**changes):
    return {**{'location_name': 'Test position', 'coordinates_original': '54.025000 N, 5.925000 W',
        'coordinate_system': 'WGS84', 'latitude': 54.025, 'longitude': -5.925,
        'easting': None, 'northing': None, 'geometry_type': 'point', 'source_page': 1,
        'source_spans': [{'page': 1, 'quotation': QUOTE}]}, **changes}


def analysis(root, digest='a' * 64, run='b' * 32, **changes):
    value = {**{'analysis_id': run, 'document_sha256': digest, 'conditions': [], 'environmental_requirements': [],
        'geofences': [], 'spatial_context': [location()]}, **changes}
    folder = root / 'cache' / 'simple_analysis' / digest / run
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'analysis.json').write_text(json.dumps(value), encoding='utf-8')
    (folder / 'manifest.json').write_text(json.dumps({'run_id': run, 'document_sha256': digest}), encoding='utf-8')
    return value


def verify(value):
    apply_source_verification(value, [SimpleNamespace(page_number=1, text=QUOTE)])
    return value['spatial_context'][0]


def test_explicit_wgs84_quote_verifies_source_but_requires_human_point_approval(tmp_path):
    spatial = verify(analysis(tmp_path))
    assert spatial['source_verified'] is True
    assert spatial['point_verified'] is False
    assert spatial['longitude'] == -5.925


@pytest.mark.parametrize('change', [
    {'latitude': 54.026}, {'longitude': 5.925},
    {'source_spans': [{'page': 1, 'quotation': 'Latitude 54.025000, Longitude 5.925000 W, WGS84.'}]},
    {'coordinate_system': 'Unknown CRS'},
])
def test_invalid_or_ambiguous_source_coordinates_fail_closed(tmp_path, change):
    value = analysis(tmp_path, spatial_context=[location(**change)])
    spatial = verify(value)
    assert spatial['source_verified'] is False
    assert spatial['point_verified'] is False


def test_explicit_spatial_review_is_bound_to_analysis_and_enables_only_that_point(tmp_path):
    value = analysis(tmp_path); verify(value)
    row = next(item for item in list_reviews(tmp_path, value)['requirements'] if item['kind'] == 'spatial_context')
    assert row['bulk_blocker'] == 'SPATIAL_REVIEW_REQUIRES_EXPLICIT_ACTION'
    saved = save_review(tmp_path, value, row['target_id'], {
        'original_fingerprint': row['original_fingerprint'], 'state': 'APPROVED', 'applicability': 'APPLICABLE',
        'corrections': {}, 'reviewer': 'Reviewer', 'note': 'Point checked against page 1 quotation.'})
    context = saved['decision_context']['spatial_context'][0]
    assert context['point_verified'] is True
    assert approved_spatial_points(saved) == {(54.025, -5.925)}
    assert saved['analysis_run_id'] == value['analysis_id']
    assert saved['document_sha256'] == value['document_sha256']


def test_rejected_spatial_review_keeps_point_blocked(tmp_path):
    value = analysis(tmp_path); verify(value)
    row = next(item for item in list_reviews(tmp_path, value)['requirements'] if item['kind'] == 'spatial_context')
    saved = save_review(tmp_path, value, row['target_id'], {
        'original_fingerprint': row['original_fingerprint'], 'state': 'REJECTED', 'applicability': 'UNASSESSED',
        'corrections': {}, 'reviewer': 'Reviewer', 'note': 'Coordinate source needs clarification.'})
    assert saved['decision_context']['spatial_context'][0]['point_verified'] is False


def test_changed_source_coordinates_invalidate_prior_spatial_approval(tmp_path):
    value = analysis(tmp_path); verify(value)
    row = next(item for item in list_reviews(tmp_path, value)['requirements'] if item['kind'] == 'spatial_context')
    save_review(tmp_path, value, row['target_id'], {
        'original_fingerprint': row['original_fingerprint'], 'state': 'APPROVED', 'applicability': 'APPLICABLE',
        'corrections': {}, 'reviewer': 'Reviewer', 'note': 'Checked.'})
    changed = deepcopy(value)
    changed['spatial_context'][0]['longitude'] = -5.924
    changed['spatial_context'][0]['coordinates_original'] = '54.025000 N, 5.924000 W'
    folder = tmp_path / 'cache' / 'simple_analysis' / value['document_sha256'] / value['analysis_id']
    (folder / 'analysis.json').write_text(json.dumps(changed), encoding='utf-8')
    with pytest.raises(ValueError, match='REVIEW_TARGET_CONFLICT'):
        list_reviews(tmp_path, changed)
