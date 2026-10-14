"""Offline regressions for the v1.5.1 environmental naming patch."""
import json
from pathlib import Path

import pytest

from src.environmental.catalog import canonical
from src.environmental.capabilities import capability_for
from src.environmental.router import route
from src.environmental.service import map_requirements


ALIASES = {
    'mean_wave_direction_degrees': 'mean_wave_direction',
    'eastward_current_component': 'eastward_current',
    'eastward_current_component_u': 'eastward_current',
    'northward_current_component': 'northward_current',
    'northward_current_component_v': 'northward_current',
    'current_direction_towards_degrees': 'surface_current_direction',
    'current_direction_towards': 'surface_current_direction',
    'wind_direction_10m_degrees': 'wind_direction_10m',
    'precipitation_accumulated_hourly': 'precipitation',
    'hourly_accumulated_precipitation': 'precipitation',
    'precipitation_hourly_accumulated': 'precipitation',
    'hourly_precipitation': 'precipitation',
    'precipitation_hourly': 'precipitation',
    'turbidity_fnu': 'turbidity',
    'dissolved_oxygen_1m_below_surface': 'dissolved_oxygen',
}


def test_extraction_aliases_reach_existing_router_capabilities():
    for alias, expected in ALIASES.items():
        assert canonical(alias) == expected
        routed = route(alias)
        assert routed['canonical_variable'] == expected
        assert routed['implemented'] is True
        # Routing is authoritative for supported environmental variables.
        # The static capability catalogue is intentionally narrower and does
        # not expose every marine route (notably dissolved oxygen).
        capability = capability_for(alias)
        if capability is not None:
            assert capability['canonical_variable'] == expected


def test_current_components_remain_independent_but_share_provider_variables():
    assert route('eastward_current_component')['potential_source_variables'] == []
    assert route('northward_current_component')['potential_source_variables'] == []
    assert route('eastward_current_component')['implemented']
    assert route('northward_current_component')['implemented']
    assert capability_for('surface_current_speed')['canonical_variable'] == 'surface_current_speed'
    assert capability_for('surface_current_direction')['canonical_variable'] == 'surface_current_direction'


def test_turbidity_is_fnu_supportive_only():
    capability = capability_for('turbidity_fnu')
    assert capability['unit'] == 'FNU'
    assert 'No NTU' in capability['notes']
    assert route('turbidity_fnu')['potential_source_variables'] == []


@pytest.mark.parametrize('raw, expected', [
    ('10m_wind_speed', 'wind_speed_10m'),
    ('10m_wind_direction', 'wind_direction_10m'),
    ('10m_wind_gust', 'wind_gust'),
    ('hourly_precipitation_accumulated', 'precipitation'),
    ('precipitation_hourly_accumulated', 'precipitation'),
    ('hourly_precipitation', 'precipitation'),
    ('hourly_precipitation_mm', 'precipitation'),
    ('precipitation_hourly', 'precipitation'),
    ('2m_air_temperature', 'air_temperature'),
    ('air_temperature_2m_celsius', 'air_temperature'),
    ('visibility_m', 'visibility'),
])
def test_fresh_weather_aliases_use_authoritative_canonical_names(raw, expected):
    assert canonical(raw) == expected
    routed = route(raw, 'forecast')
    assert routed['canonical_variable'] == expected
    assert routed['preferred_provider'] == 'ECMWF_FORECAST'
    assert routed['implemented'] is True


@pytest.mark.parametrize('raw, expected', [
    ('sea_surface_temperature_celsius', 'sea_surface_temperature'),
    ('sea_surface_height_m', 'sea_surface_height'),
    ('dissolved_oxygen_mg_per_l', 'dissolved_oxygen'),
])
def test_fresh_marine_aliases_use_authoritative_canonical_names(raw, expected):
    assert canonical(raw) == expected
    routed = route(raw, 'observation')
    assert routed['canonical_variable'] == expected
    assert routed['preferred_provider'] == 'COPERNICUS_MARINE'
    if expected == 'sea_surface_height':
        assert routed['preferred_provider'] == 'COPERNICUS_MARINE'
        assert routed['implemented'] is False
    else:
        assert routed['implemented'] is True


def test_hourly_precipitation_alias_preserves_accumulation_semantics():
    row = {
        'condition_id': '34', 'canonical_variable': 'hourly_precipitation',
        'evidence_type': 'forecast', 'requirement_text':
            'Hourly accumulated precipitation greater than 5 mm in a one-hour interval.',
        'operator': '>', 'threshold': 5.0, 'unit': 'mm per hour',
        'source_verified': True,
        'source_spans': [{'page': 5, 'quotation':
            'Hourly accumulated precipitation greater than 5 mm in a one-hour interval.'}],
    }
    mapped = map_requirements({'environmental_requirements': [row]})[0]
    assert mapped['canonical_variable'] == 'precipitation'
    assert mapped['routing']['preferred_provider'] == 'ECMWF_FORECAST'
    assert mapped['routing']['implemented'] is True
    assert mapped['unit'] == 'mm per hour'
    assert mapped['comparison_unit'] == 'mm'
    assert mapped['required_accumulation_interval_seconds'] == 3600
    assert mapped['temporal_semantics'] == 'ACCUMULATED_OVER_INTERVAL'


def test_persisted_condition_32_source_gate_stays_independent():
    path = Path('cache/simple_analysis/0a665f53ba058e48da31f094723f6e3af679699d5a1cea3658a66f4b8d96b585/c1136faddcaa4146a7f6fde5c5902d4c/analysis.json')
    analysis = json.loads(path.read_text(encoding='utf-8'))
    row = next(x for x in analysis['environmental_requirements'] if x['condition_id'] == '32')
    assert row['source_verified'] is False
    mapped = next(x for x in map_requirements({'environmental_requirements': [row]}) if x['condition_id'] == '32')
    assert mapped['routing']['canonical_variable'] == 'wind_direction_10m'
    assert mapped['routing']['implemented'] is True
    assert mapped['source_verified'] is False


def test_unknown_variable_remains_unavailable():
    routed = route('unknown_unverified_environment_variable')
    assert routed['implemented'] is False
    assert routed['preferred_provider'] == 'UNAVAILABLE'
