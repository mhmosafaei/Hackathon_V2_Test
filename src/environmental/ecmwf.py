"""Small ECMWF IFS requests through the existing Open-Meteo provider, no retries."""
import json
from datetime import datetime, timezone
from urllib.parse import urlencode
import httpx
from .router import WEATHER
from .errors import ProviderError
from .sampling import weather_spatial_limit, WEATHER_MODELS


def retrieve(request, *, client=None, historical=False, model=None):
    variable = WEATHER.get(request.canonical_variable)
    if not variable:
        raise ValueError('Variable not implemented by this connector')
    start = datetime.fromisoformat(request.provider_query_start or request.start_time)
    end = datetime.fromisoformat(request.provider_query_end or request.end_time)
    endpoint = ('https://archive-api.open-meteo.com/v1/archive' if historical else
                'https://api.open-meteo.com/v1/forecast')
    model = 'era5' if historical else model or 'ecmwf_ifs'
    if model not in WEATHER_MODELS:
        raise ValueError('Unsupported weather model')
    lat, lon = request.coordinates
    query = {'latitude': lat, 'longitude': lon, 'hourly': variable, 'timezone': 'UTC',
             'start_date': start.date().isoformat(), 'end_date': end.date().isoformat(),
             'models': model, 'wind_speed_unit': 'ms', 'temperature_unit': 'celsius',
             'precipitation_unit': 'mm', 'cell_selection': 'nearest'}
    owned = client is None
    client = client or httpx.Client(timeout=25, trust_env=False, follow_redirects=False)
    try:
        response = client.get(endpoint, params=query)
        # Only an explicit model-unavailability 400 permits the documented coarse
        # alternative. No retry/fallback for network, authentication or server errors.
        fallback_reason = None
        if response.status_code == 400 and model == 'ecmwf_ifs':
            try:
                reason = str(response.json().get('reason','')).lower()
            except ValueError:
                reason = ''
            if 'model' in reason and ('unavailable' in reason or 'not available' in reason or 'invalid' in reason):
                fallback_reason = 'Preferred ECMWF IFS HRES model unavailable; explicit coarse 0.25 degree fallback.'
                model = 'ecmwf_ifs025'; query['models'] = model
                response = client.get(endpoint, params=query)
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError('Response exceeds size limit')
        payload = response.json()
    finally:
        if owned:
            client.close()
    # Archive results without a returned location cannot pass spatial validation.
    selected_lat, selected_lon = payload.get('latitude'), payload.get('longitude')
    from src.copernicus.grid_selection import haversine_km
    distance = (haversine_km(lat, lon, selected_lat, selected_lon)
                if selected_lat is not None and selected_lon is not None else None)
    hourly = payload.get('hourly', {})
    unit = payload.get('hourly_units', {}).get(variable)
    if not isinstance(hourly, dict) or not isinstance(hourly.get('time'), list) or not isinstance(hourly.get(variable), list):
        raise ProviderError('MISSING_FIELD', 'Provider response is missing hourly time or requested variable: ' + variable)
    if not unit:
        raise ProviderError('MISSING_FIELD', 'Provider response is missing source units for ' + variable)
    if variable == 'visibility' and unit.lower() not in {'m', 'metre', 'metres', 'meter', 'meters'}:
        raise ProviderError('UNIT_INCOMPATIBLE', 'Open-Meteo visibility did not return metres; no visibility conversion is assumed.')
    if len(hourly['time']) != len(hourly[variable]):
        raise ProviderError('MALFORMED_RESPONSE', 'Provider timestamps and variable values have different lengths.')
    values = hourly.get(variable, [])
    points = []
    for i, time in enumerate(hourly.get('time', [])):
        moment = datetime.fromisoformat(time).replace(tzinfo=timezone.utc)
        if start <= moment <= end:
            point = {'data_time': moment.isoformat(), 'raw_value': values[i] if i < len(values) else None,
                     'unit': unit}
            if variable == 'precipitation':
                point.update({'accumulation_interval_seconds': 3600,
                              'temporal_semantics': 'ACCUMULATED_OVER_PRECEDING_HOUR'})
            points.append(point)
    allowed_distance = weather_spatial_limit(model, lat)
    return {'canonical_variable': request.canonical_variable, 'provider': request.provider, 'dataset_id': model, 'dataset_name':
            'ERA5 via Open-Meteo archive' if historical else 'ECMWF IFS via Open-Meteo',
            'dataset_variable': variable, 'data_type': 'REANALYSIS' if historical else 'MODEL_FORECAST',
            'retrieved_at': datetime.now(timezone.utc).isoformat(), 'forecast_initialization': None,
            'latitude': selected_lat, 'longitude': selected_lon, 'requested_coordinates': [lat, lon],
            'depth': None, 'distance_km': distance, 'spatial_resolution': '9 km HRES O1280 model grid' if model == 'ecmwf_ifs' else '0.25° model grid',
            'grid_resolution_km':9 if model == 'ecmwf_ifs' else None,
            'grid_resolution_degrees':None if model == 'ecmwf_ifs' else .25,
            'max_representative_distance_km':allowed_distance, 'fallback_reason':fallback_reason,
            'cell_selection':'nearest',
            'spatial_check_basis':'Approximate nominal-grid representativeness check; not exact O1280 geometry or local point truth',
            'temporal_resolution': 'hourly', 'quality_status': 'SUITABLE' if distance is not None and distance <= allowed_distance else 'SPATIAL_REVIEW_REQUIRED', 'points': points,
            'notes': 'Model evidence via Open-Meteo, not local point truth; initialization time not supplied. '
                'Provider hourly output may interpolate coarser native forecast timesteps; PermitPulse does not interpolate. '
                + ('Precipitation values are accumulated over the preceding provider hour; no rate conversion is applied. ' if variable == 'precipitation' else '')
                + (fallback_reason or 'Preferred HRES 9 km source.'),
            'endpoint': endpoint, 'request_parameters': query}
