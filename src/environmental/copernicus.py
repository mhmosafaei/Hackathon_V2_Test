"""Official Toolbox in a timeout-bounded worker. Never returns credentials."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from .router import MARINE
from .errors import ProviderError, diagnostic

ROOT = Path(__file__).resolve().parents[2]


def _load_worker_dependencies():
    """Load worker-only dependencies with a safe, stable diagnostic."""
    try:
        import numpy as np
        import copernicusmarine
    except (ImportError, ModuleNotFoundError) as exc:
        raise ProviderError(
            'WORKER_DEPENDENCY',
            'Copernicus worker dependency is unavailable; retrieval was not attempted.',
        ) from exc
    return np, copernicusmarine


def _stage(stage, operation):
    """Run a provider operation while preserving a safe diagnostic stage."""
    try:
        return operation()
    except ProviderError:
        raise
    except Exception as exc:
        category = {
            'dataset_open': 'DATASET_OPEN',
            'variable_lookup': 'VARIABLE_LOOKUP',
            'temporal_selection': 'TEMPORAL_COVERAGE',
            'spatial_selection': 'SPATIAL_COVERAGE',
            'layout_validation': 'SOURCE_LAYOUT',
        }.get(stage, 'PROVIDER_RUNTIME')
        raise ProviderError(category, 'Copernicus %s failed; no usable evidence returned.' % stage.replace('_', ' ')) from exc


def products():
    """Reuse locally verified product references; never substitute a guessed dataset."""
    config = json.loads((ROOT/'config/environmental_data_sources.json').read_text())['capabilities']
    lookup = {'waves': 'significant_wave_height', 'currents': 'current_speed',
              'sst': 'sea_surface_temperature', 'oxygen': 'dissolved_oxygen',
              'spm': 'suspended_particulate_matter', 'turbidity': 'suspended_particulate_matter'}
    return {key: config[name]['adapters'][0] for key, name in lookup.items() if config[name]['adapters']}


def retrieve(request):
    # Bounded wall time includes authentication/catalogue/DAP; no detached worker.
    completed = subprocess.run([sys.executable, '-m', 'src.environmental.copernicus'],
        input=request.model_dump_json(), text=True, capture_output=True, cwd=ROOT, timeout=60)
    # Toolbox output may include sensitive server diagnostics. Never forward stdout/stderr.
    marker = 'PERMITPULSE_RESULT='
    lines = [line[len(marker):] for line in completed.stdout.splitlines() if line.startswith(marker)]
    if completed.returncode or not lines:
        raise ProviderError('WORKER_RUNTIME', 'Copernicus worker exited without a usable structured response.')
    result = json.loads(lines[-1])
    if 'error_type' in result:
        raise ProviderError(result.get('error_category','PROVIDER_RUNTIME'),
            result.get('error_message','Copernicus retrieval failed; no usable evidence returned.'))
    return result


def worker(request):
    np, copernicusmarine = _load_worker_dependencies()
    from src.copernicus.grid_selection import nearest_valid
    group, variable = MARINE[request.canonical_variable]
    product = products()[group]
    # The locally verified TUR source is FNU. No FNU/SPM-to-NTU equivalence.
    if group == 'turbidity' and (request.requested_unit or '').upper() == 'NTU':
        raise ProviderError('UNIT_INCOMPATIBLE', 'Mapped Copernicus TUR product provides FNU, not required NTU turbidity. No supported conversion; local NTU evidence is required.')
    if group == 'oxygen' and request.depth is None:
        raise ProviderError('MISSING_DEPTH', 'Dissolved oxygen is a 3-D daily model product. Select an explicit compatible depth; it is not hourly in-situ regulatory evidence.')
    user = os.environ.get('COPERNICUSMARINE_SERVICE_USERNAME')
    password = os.environ.get('COPERNICUSMARINE_SERVICE_PASSWORD')
    lat, lon = request.coordinates
    # The vector current product supplies uo/vo together. Other products retain
    # their established one-variable request contract.
    variables = ['uo', 'vo'] if group == 'currents' else [variable]
    kwargs = dict(dataset_id=product['dataset'], variables=variables,
        minimum_latitude=lat-.05, maximum_latitude=lat+.05,
        minimum_longitude=lon-.05, maximum_longitude=lon+.05,
        start_datetime=request.provider_query_start or request.start_time,
        end_datetime=request.provider_query_end or request.end_time, chunk_size_limit=2_000_000)
    if request.depth is not None:
        kwargs.update(minimum_depth=request.depth, maximum_depth=request.depth)
    ds = _stage('dataset_open', lambda: copernicusmarine.open_dataset(**kwargs))
    try:
        # Metadata/coverage checks before selecting or loading numerical values.
        if any(v not in ds for v in variables) or 'time' not in ds.coords:
            raise ProviderError('VARIABLE_LOOKUP', 'Selected dataset is missing the requested variable or time coordinate.')
        if not ds.time.size:
            raise ProviderError('TEMPORAL_COVERAGE', 'Selected dataset has no timestamps in the requested period.')
        if sum(ds[v].size*8 for v in variables) > 5_000_000:
            raise ProviderError('SIZE_LIMIT', 'Requested subset exceeds the bounded download size.')
        if any(ds[v].dims not in [('time', 'latitude', 'longitude'), ('time', 'depth', 'latitude', 'longitude')]
               for v in variables):
            raise ProviderError('SOURCE_LAYOUT', 'Dataset dimensions are not supported by this connector.')
        depth_index = None
        if 'depth' in ds.coords:
            if request.depth is None:
                raise ProviderError('MISSING_DEPTH', 'Explicit compatible depth required; surface is not a safe default.')
            depths = [float(value) for value in ds.depth.values]
            depth_index = min(range(len(depths)), key=lambda index: abs(depths[index] - request.depth)) if depths else None
            if depth_index is None:
                raise ProviderError('DEPTH_LEVEL_UNAVAILABLE', 'No provider vertical level was returned for the requested depth.')
            selected_depth = depths[depth_index]
            if abs(selected_depth - request.depth) > .5:
                raise ProviderError('DEPTH_TOLERANCE_EXCEEDED', 'Nearest provider vertical level is outside the conservative 0.5 m depth tolerance.')
        else:
            selected_depth = request.depth
        field = ds[variables[0]].isel(time=0)
        if 'depth' in field.dims:
            field = field.isel(depth=depth_index)
        field = field.transpose('latitude', 'longitude')
        raw = np.asarray(field.values)
        grid = _stage('spatial_selection', lambda: nearest_valid(lat, lon, [(float(a), float(b), float(raw[i,j]) if np.isfinite(raw[i,j]) else None)
            for i,a in enumerate(ds.latitude.values) for j,b in enumerate(ds.longitude.values)]))
        if grid.selected_lat is None or grid.distance_km > 5:
            raise ProviderError('SPATIAL_COVERAGE', 'No valid ocean grid cell within the 5 km representativeness limit; coastal cells may be masked.')
        selected = _stage('spatial_selection', lambda: ds.sel(latitude=grid.selected_lat, longitude=grid.selected_lon))
        if 'depth' in selected.dims:
            selected = selected.isel(depth=depth_index)
        points = []
        for i, moment in enumerate(selected.time.values):
            source_values = {name: float(selected[name].isel(time=i).values) for name in variables}
            first = source_values[variables[0]]
            value = first
            unit = selected[variables[0]].attrs.get('units')
            if group == 'currents':
                second = source_values['vo']
                if request.canonical_variable == 'eastward_current':
                    value, unit = source_values['uo'], 'm/s'
                elif request.canonical_variable == 'northward_current':
                    value, unit = source_values['vo'], 'm/s'
                elif request.canonical_variable == 'surface_current_direction':
                    value = math.degrees(math.atan2(first, second)) % 360; unit = 'degrees'
                else:
                    value = math.hypot(first, second); unit = 'm/s'
            elif group == 'waves':
                value = source_values[variable]
                unit = selected[variable].attrs.get('units')
            points.append({'data_time': str(moment).split('.')[0]+'+00:00',
                'raw_value': value if math.isfinite(value) else None, 'unit': unit,
                'derived_from': variables if group == 'currents' else [],
                'component_values': {'uo': first if math.isfinite(first) else None,
                                     'vo': second if math.isfinite(second) else None} if group == 'currents' else None,
                'source_values': {name: (value if math.isfinite(value) else None) for name, value in source_values.items()} if group == 'waves' else None})
        return {'canonical_variable': request.canonical_variable, 'provider': 'COPERNICUS_MARINE', 'dataset_id': product['dataset'],
            'dataset_name': product['product'], 'dataset_variable': variable, 'source_version': ds.attrs.get('dataset_version'),
            'data_type': 'SATELLITE_OBSERVATION' if product['mode'] == 'OBSERVATION' else 'MODEL_FORECAST',
            'retrieved_at': datetime.now(timezone.utc).isoformat(), 'forecast_initialization': None,
            'latitude': grid.selected_lat, 'longitude': grid.selected_lon, 'distance_km': grid.distance_km,
            'requested_coordinates': [lat, lon], 'depth': selected_depth, 'requested_depth':request.depth,
            'requested_depth_m': request.depth, 'selected_depth_m': selected_depth,
            'depth_difference_m': (abs(selected_depth-request.depth) if selected_depth is not None and request.depth is not None else None),
            'quality_status': 'COASTAL_REVIEW_REQUIRED',
            'spatial_resolution': ds.attrs.get('spatial_resolution'), 'temporal_resolution': request.timestep_seconds,
            'points': points, 'notes': 'Nearest valid cell; coastal/local representativeness requires review. '
                'Current direction is towards, clockwise from north. Wave direction convention is provider-defined and is not converted between from/towards. No tide or local sensor equivalence. '
                'Modelled oxygen is supportive and not equivalent to required in-situ monitoring. '
                'Daily products cannot resolve subdaily excursions.',
            'direction_convention': ('TOWARDS_CLOCKWISE_FROM_NORTH' if request.canonical_variable == 'surface_current_direction' else
                                     'PROVIDER_DEFINED_NOT_NORMALIZED' if request.canonical_variable == 'mean_wave_direction' else None),
            'catalogue_reference_verified_at': product.get('live_verified')}
    finally:
        ds.close()


if __name__ == '__main__':
    from .models import EnvironmentalRequest
    try:
        result = worker(EnvironmentalRequest.model_validate_json(sys.stdin.read()))
    except Exception as exc:
        category, message = diagnostic(exc)
        result = {'error_type': type(exc).__name__, 'error_category':category, 'error_message':message}
    print('PERMITPULSE_RESULT='+json.dumps(result, allow_nan=False))


def project_current_or_wave_evidence(evidence, canonical_variable, dataset_variable):
    """Project one shared source bundle into a requested physical variable."""
    import copy
    result = copy.deepcopy(evidence)
    result['canonical_variable'] = canonical_variable
    result['dataset_variable'] = dataset_variable
    for point in result.get('points', []):
        if canonical_variable in {'eastward_current', 'northward_current', 'surface_current_speed', 'surface_current_direction'}:
            components = point.get('component_values') or {}
            u, v = components.get('uo'), components.get('vo')
            if u is not None and v is not None:
                if canonical_variable == 'eastward_current': point.update(raw_value=u, unit='m/s')
                elif canonical_variable == 'northward_current': point.update(raw_value=v, unit='m/s')
                elif canonical_variable == 'surface_current_speed': point.update(raw_value=math.hypot(u, v), unit='m/s')
                else: point.update(raw_value=math.degrees(math.atan2(u, v)) % 360, unit='degrees')
            point['derived_from'] = ['uo', 'vo']
        elif canonical_variable in {'significant_wave_height', 'mean_wave_period', 'mean_wave_direction'}:
            source = point.get('source_values') or {}
            if dataset_variable in source:
                point['raw_value'] = source[dataset_variable]
                point['unit'] = {'VHM0':'m','VTM02':'s','VMDR':'degrees'}.get(dataset_variable, point.get('unit'))
    return result
