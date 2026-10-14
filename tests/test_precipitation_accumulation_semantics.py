"""Offline regressions for precipitation accumulation semantics."""
from datetime import datetime, timezone

import pytest

from src.environmental.models import EnvironmentalRequest
from src.environmental.service import compatible_points, map_requirements
from src.environmental.units import convert


def _request():
    return EnvironmentalRequest(
        condition_id='34', requirement_text='Hourly accumulated precipitation greater than 5 mm in a one-hour interval',
        canonical_variable='precipitation', operator='>', threshold=5.0, threshold_unit='mm', requested_unit='mm',
        coordinates=(54.023, -5.9275), start_time='2026-10-13T00:00:00+00:00',
        end_time='2026-10-13T01:00:00+00:00', evidence_mode='forecast', provider='ECMWF_FORECAST',
        dataset_id='ecmwf_ifs', dataset_variable='precipitation', timestep_seconds=3600)


def _requirement():
    return {
        'condition_id': '34', 'canonical_variable': 'precipitation',
        'requirement_text': 'Hourly accumulated precipitation greater than 5 mm in a one-hour interval',
        'operator': '>', 'threshold': 5.0, 'unit': 'mm per hour', 'explicit_requirement': True,
        'source_verified': True,
        'source_spans': [{'page': 5, 'quotation':
            'Hourly accumulated precipitation greater than 5 mm in a one-hour interval.'}],
    }


def _evidence(value, *, interval=3600, semantics='ACCUMULATED_OVER_PRECEDING_HOUR', unit='mm'):
    return {
        'provider': 'ECMWF_FORECAST', 'dataset_id': 'ecmwf_ifs', 'canonical_variable': 'precipitation',
        'quality_status': 'SUITABLE', 'requested_coordinates': [54.023, -5.9275], 'distance_km': 0,
        'data_type': 'MODEL_FORECAST', 'retrieved_at': '2026-10-13T08:00:00+00:00',
        'points': [
            {'data_time': '2026-10-13T00:00:00+00:00', 'raw_value': value, 'unit': unit,
             'accumulation_interval_seconds': interval, 'temporal_semantics': semantics},
            {'data_time': '2026-10-13T01:00:00+00:00', 'raw_value': value, 'unit': unit,
             'accumulation_interval_seconds': interval, 'temporal_semantics': semantics},
        ],
    }


def _evaluate(evidence):
    return compatible_points(_requirement(), _request(), evidence,
        now=datetime(2026, 10, 13, 12, tzinfo=timezone.utc))


def test_hourly_accumulation_below_threshold_is_not_triggered():
    result = _evaluate(_evidence(2.4))
    assert result['status'] == 'WITHIN_THRESHOLD'
    assert result['threshold_evaluation'] == 'NOT_TRIGGERED'
    assert result['points'][0]['normalized_unit'] == 'mm'


def test_hourly_accumulation_above_threshold_is_triggered():
    result = _evaluate(_evidence(5.1))
    assert result['status'] == 'THRESHOLD_EXCEEDED'
    assert result['threshold_evaluation'] == 'TRIGGERED'


@pytest.mark.parametrize('kwargs', [
    {'interval': None},
    {'semantics': 'INSTANTANEOUS'},
    {'semantics': 'RATE'},
    {'interval': 1800},
    {'interval': 86400},
])
def test_non_hourly_or_non_accumulated_evidence_is_not_determined(kwargs):
    result = _evaluate(_evidence(5.1, **kwargs))
    assert result['status'] == 'INSUFFICIENT_DATA'
    assert result['threshold_evaluation'] == 'NOT_DETERMINED'
    assert any('accumulation semantics incompatible' in note for note in result['validation_notes'])


def test_original_source_wording_is_preserved_while_mapping_comparison_semantics():
    analysis = {'environmental_requirements': [_requirement()],
                'environmental_extraction': {'candidate_conditions': ['34']}}
    row = map_requirements(analysis)[0]
    assert row['unit'] == 'mm per hour'
    assert row['comparison_unit'] == 'mm'
    assert row['required_accumulation_interval_seconds'] == 3600
    assert row['temporal_semantics'] == 'ACCUMULATED_OVER_INTERVAL'


def test_generic_unit_conversion_does_not_alias_rate_to_quantity():
    with pytest.raises(ValueError, match='Incompatible or unsupported units'):
        convert(2.4, 'mm', 'mm per hour')
