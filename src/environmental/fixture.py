"""Synthetic transport, reachable only through explicit --mock or test injection."""
from datetime import datetime, timezone, timedelta


def mock_evidence(request):
    start = datetime.fromisoformat(request.start_time)
    end = datetime.fromisoformat(request.end_time)
    points = []
    while start <= end:
        points.append({'data_time': start.isoformat(), 'raw_value': 1.2, 'unit': request.requested_unit or 'm'})
        start += timedelta(hours=1)
    return {'canonical_variable': request.canonical_variable, 'provider': request.provider, 'dataset_id': 'SYNTHETIC-OFFLINE-FIXTURE',
        'dataset_name': 'Synthetic provider test data — not environmental observations',
        'dataset_variable': request.canonical_variable, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
        'data_type': 'MODEL_FORECAST', 'forecast_initialization': None,
        'latitude': request.coordinates[0], 'longitude': request.coordinates[1],
        'requested_coordinates': list(request.coordinates), 'distance_km': 0, 'depth': request.depth,
        'quality_status': 'SUITABLE', 'spatial_resolution': 'Synthetic only', 'temporal_resolution': 'hourly',
        'points': points, 'notes': 'Mocked evidence for UI testing; never an operational authorization.'}
