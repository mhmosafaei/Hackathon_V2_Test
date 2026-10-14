"""Dimension-safe conversions. No calibrated NTU/SPM equivalence is assumed."""
import math

GROUPS = {
    'm/s': ('speed', 1, 0), 'ms-1': ('speed', 1, 0), 'm s-1': ('speed', 1, 0),
    'knots': ('speed', 0.5144444444, 0), 'knot': ('speed', 0.5144444444, 0),
    'km/h': ('speed', 1/3.6, 0), '°c': ('temperature', 1, 273.15),
    'degrees_celsius': ('temperature', 1, 273.15), 'c': ('temperature', 1, 273.15), 'k': ('temperature', 1, 0),
    'pa': ('pressure', 1, 0), 'hpa': ('pressure', 100, 0),
    'm': ('length', 1, 0), 'cm': ('length', .01, 0), 'mm': ('length', .001, 0),
    'hours': ('time', 3600, 0), 'minutes': ('time', 60, 0), 's': ('time', 1, 0),
    'mg/l': ('mass_concentration', 1, 0), 'g/m3': ('mass_concentration', 1, 0),
    'degrees': ('angle', 1, 0), '°': ('angle', 1, 0), 'ntu': ('turbidity_ntu', 1, 0),
    'fnu': ('turbidity_fnu', 1, 0), 'psu': ('salinity', 1, 0),
}


def canonical_unit(unit):
    text = str(unit or '').strip()
    lowered = text.lower()
    if lowered in {'deg c', '°c', 'degrees_c', 'degree_c', 'degrees c', 'degrees_celsius', 'c'}:
        return '°C'
    if lowered in {'degree', 'degrees', 'deg'}:
        return 'degrees'
    return text


def convert(value, source, target, *, variable=None):
    if value is None or not math.isfinite(float(value)):
        raise ValueError('Missing or nonfinite value')
    a, b = canonical_unit(source).lower(), canonical_unit(target).lower()
    if a == b and a:
        return float(value)
    if variable == 'dissolved_oxygen' and a in {'mmol/m3', 'mmol m-3'} and b == 'mg/l':
        return float(value) * .031998
    if a not in GROUPS or b not in GROUPS or GROUPS[a][0] != GROUPS[b][0]:
        raise ValueError('Incompatible or unsupported units')
    _, scale, offset = GROUPS[a]; _, target_scale, target_offset = GROUPS[b]
    return (float(value)*scale + offset - target_offset)/target_scale
