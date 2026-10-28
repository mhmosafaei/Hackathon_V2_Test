"""Source sampling metadata and outward UTC query bounds, never interpolation."""
from datetime import datetime, timezone
import math
import re

MARINE_STEPS = {'waves': 3600, 'currents': 900, 'sst': 3600,
                'oxygen': 86400, 'spm': 86400, 'turbidity': 86400}
DEPTH_TOLERANCE_M = 0.5  # Existing conservative model-level matching limit.
WEATHER_MODELS = {'ecmwf_ifs': {'grid_km': 9, 'step_seconds': 3600},
                  'ecmwf_ifs025': {'grid_degrees': .25, 'step_seconds': 3600},
                  'era5': {'grid_degrees': .25, 'step_seconds': 3600}}


def timestep_bounds(start, end, seconds):
    """UTC epoch-aligned boundaries. A boundary already on-grid is unchanged."""
    def stamp(value):
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.utcoffset() is None:
            raise ValueError('UTC offset required')
        return dt.timestamp()
    if seconds <= 0:
        raise ValueError('Positive timestep required')
    return (datetime.fromtimestamp(math.floor(stamp(start)/seconds)*seconds, timezone.utc).isoformat(),
            datetime.fromtimestamp(math.ceil(stamp(end)/seconds)*seconds, timezone.utc).isoformat())


def source_depth(requirement):
    """Accept only a literal source-backed metric depth, not guessed surface levels."""
    text = requirement.get('depth_requirement')
    if text is None:
        return None, None
    quotes = ' '.join(s['quotation'] for s in requirement.get('source_spans', []))
    if requirement['routing']['preferred_provider'] in {'ECMWF_FORECAST', 'ERA5'} and text in {'surface','10m','10 m','2m','2 m'}:
        return None, None
    if requirement['routing']['preferred_provider'] in {'ECMWF_FORECAST', 'ERA5'}:
        from .catalog import canonical
        variable = canonical(requirement['routing'].get('canonical_variable') or requirement.get('canonical_variable'))
        height = {'wind_speed_10m':10, 'wind_direction_10m':10, 'wind_gust':10, 'air_temperature':2}.get(variable)
        if height is not None:
            atmospheric_height = re.fullmatch(
                rf'{height}\s*(?:m|metres?|meters?)\s+(?:height|above\s+(?:the\s+)?(?:ground|sea\s+surface))',
                text.strip(), re.I)
            legacy_atmospheric_height = re.fullmatch(
                rf'{height}\s*(?:m|metres?|meters?)\s+(?:height|above\s+(?:the\s+)?ground)',
                text.strip(), re.I)
            source_supports_height = re.search(
                r'\b(?:10\s*m\s+wind|wind\s+gust|wind\s+direction)\b', quotes, re.I)
            if atmospheric_height and (legacy_atmospheric_height or source_supports_height):
                return None, None  # Atmospheric measurement height, not ocean depth.
    model_level = re.fullmatch(r'sea[- ]surface\s+model\s+level\s*\((.+)\)', text.strip(), re.I)
    if model_level and re.sub(r'\s+', ' ', text.strip()).casefold() in re.sub(r'\s+', ' ', quotes).casefold():
        text = model_level[1]  # Same source-backed literal depth; preserve original attribution.
    # An explicit model-level annotation does not make the preceding metric
    # depth absent. Retain the original source/structured text for provenance.
    annotation = re.search(r'\s*\((sea[- ]surface\s+model\s+level)\)\s*$', text, re.I)
    if annotation and re.search(re.escape(annotation[1]).replace(r'\ ',r'\s+'), quotes, re.I):
        text = text[:annotation.start()].strip()
    if text == 'surface':
        return 0., None  # Existing explicit structured surface selector, not a default.
    # Fixed-height atmospheric fields are not ocean depth selectors.
    pattern = r'(?<![\d.])(?:(?:approximately|about|around)\s+)?(\d+(?:\.\d+)?)\s*(?:m\b|metres?\b|meters?\b)\s*(?:below (?:the )?sea surface|below (?:the )?surface)'
    stated = re.fullmatch(pattern, text.strip(), re.I)
    supported = list(re.finditer(pattern, quotes, re.I))
    if stated and any(float(m[1]) == float(stated[1]) for m in supported):
        return float(stated[1]), None
    # A numeric-only structured depth is accepted only with the full quoted context.
    short = re.fullmatch(r'(?:(?:approximately|about|around)\s+)?(\d+(?:\.\d+)?)\s*(?:m|metres?|meters?)', text.strip(), re.I)
    if short and any(float(m[1]) == float(short[1]) for m in supported):
        return float(short[1]), None
    return None, 'Source depth interpretation requires review; arbitrary depth override is not accepted'


def depth_metadata(requirement):
    depth, error = source_depth(requirement)
    if depth is None or error:
        return {}
    text = str(requirement.get('depth_requirement') or '')
    quotes = ' '.join(s.get('quotation') or '' for s in requirement.get('source_spans', []))
    approximate = re.search(r'\b(?:approximately|about|around)\s+' + re.escape(f'{depth:g}') + r'(?![\d.])\s*(?:m\b|metres?\b|meters?\b)', text+' '+quotes, re.I)
    return {'requested_depth_mode': 'APPROXIMATE' if approximate else 'EXPLICIT',
            'depth_tolerance_m': DEPTH_TOLERANCE_M}


def weather_spatial_limit(model, latitude):
    """Half nominal cell diagonal: bounds nearest-cell geometry, not local truth.

    Coarse angular grids use latitude-dependent east-west spacing. Marine coastal
    checks retain their independent 5 km limit and coastal-review gate.
    """
    metadata = WEATHER_MODELS.get(model)
    if not metadata:
        return None
    if 'grid_km' in metadata:
        return metadata['grid_km']/math.sqrt(2)
    north = 111.32 * metadata['grid_degrees']
    east = north * math.cos(math.radians(latitude))
    return math.hypot(north, east)/2
