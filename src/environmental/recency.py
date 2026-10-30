"""Explicit MVP reference-evidence policies, not continuous validity spans."""
from datetime import datetime, timezone
import math

TURBIDITY_MAX_AGE_HOURS = 72
TURBIDITY_REFERENCE_LOOKBACK_HOURS = 30 * 24
OXYGEN_MAX_AGE_HOURS = 24
WAVE_HEIGHT_MAX_AGE_MINUTES = 90


def utc(value):
    result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.utcoffset() is None:
        raise ValueError('Timezone required')
    return result.astimezone(timezone.utc)


def policy(variable, depth=None, *, wave_height=False):
    # Wave acceptance is F09-only: do not alter provider queries/screening.
    if wave_height and variable == 'significant_wave_height':
        return WAVE_HEIGHT_MAX_AGE_MINUTES / 60, 'STALE_WAVE_EVIDENCE', 'NO_WAVE_EVIDENCE'
    if variable == 'turbidity':
        return TURBIDITY_MAX_AGE_HOURS, 'STALE_TURBIDITY_EVIDENCE', 'NO_COMPATIBLE_ACCESSIBLE_SOURCE'
    if variable == 'dissolved_oxygen' and depth == 0:
        return OXYGEN_MAX_AGE_HOURS, 'STALE_OXYGEN_EVIDENCE', 'NO_COMPATIBLE_OXYGEN_SOURCE'
    return None


def select(points, reference, variable, depth=None, *, wave_height=False):
    """Newest compatible past point. Never select a future or invalid value."""
    from .units import convert
    rule = policy(variable, depth, wave_height=wave_height)
    reference = utc(reference)
    eligible = []
    for point in points:
        try:
            time = utc(point['data_time'])
            if time > reference or point.get('validation_notes') or point.get('status') == 'INSUFFICIENT_DATA':
                continue
            if isinstance(point['raw_value'], bool):
                continue
            target_unit = 'm' if variable == 'significant_wave_height' else 'FNU' if variable == 'turbidity' else 'mg/L'
            value = convert(point['raw_value'], point['unit'], target_unit, variable=variable)
            if math.isfinite(value):
                eligible.append((time, point))
        except (KeyError, ValueError, TypeError):
            continue
    if not rule:
        raise ValueError('No reference-evidence policy')
    if not eligible:
        return None, {'reason_code': rule[2], 'max_age_hours': rule[0]}
    time, point = max(eligible, key=lambda pair: pair[0])
    age = (reference-time).total_seconds()/3600
    metadata = {'source_timestamp': point['data_time'], 'assessed_time': reference.isoformat(),
                'age_hours': age, 'max_age_hours': rule[0],
                'temporal_semantics': 'HISTORICAL_REFERENCE_UNDER_RECENCY_POLICY',
                'reason_code': rule[1] if age > rule[0] else None}
    if wave_height and variable == 'significant_wave_height':
        metadata.update(age_minutes=age*60, max_age_minutes=WAVE_HEIGHT_MAX_AGE_MINUTES,
                        policy_authority='PERMITPULSE_MVP_NOT_PROVIDER_VALIDITY')
    return (None if age > rule[0] else point), metadata
