"""Official Toolbox in a timeout-bounded worker. Never returns credentials."""
import json
import math
import re
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from .router import MARINE
from .errors import ProviderError, diagnostic
from .sampling import DEPTH_TOLERANCE_M

ROOT = Path(__file__).resolve().parents[2]
WORKER_TIMEOUT_SECONDS = 60


def select_oxygen_depth(ds, requested):
    """Select a native positive-down metre level, never substitute another axis."""
    if requested is None or not math.isfinite(requested) or requested < 0:
        raise ProviderError('MISSING_DEPTH', 'A finite non-negative explicit nominal oxygen depth is required.')
    if 'depth' not in ds.coords:
        raise ProviderError('DEPTH_AXIS_MISSING', 'Dissolved oxygen dataset has no explicit depth axis.')
    axis = ds.depth
    if axis.dims != ('depth',) or str(axis.attrs.get('units', '')).lower() not in {'m','metre','metres','meter','meters'} or axis.attrs.get('positive') != 'down':
        raise ProviderError('DEPTH_METADATA_INVALID', 'Provider depth axis must be one-dimensional metres positive down.')
    try:
        depths = [float(v) for v in axis.values]
        if not depths or any(not math.isfinite(v) or v < 0 for v in depths):
            raise ValueError()
    except (ValueError, TypeError):
        raise ProviderError('DEPTH_METADATA_INVALID', 'Provider depth levels are empty or invalid.') from None
    index = min(range(len(depths)), key=lambda i: abs(depths[i]-requested))
    if abs(depths[index]-requested) > DEPTH_TOLERANCE_M:
        raise ProviderError('DEPTH_TOLERANCE_EXCEEDED', 'Nearest provider vertical level is outside the conservative 0.5 m depth tolerance.',
            {'returned_depth_levels_m':depths,'selected_depth_m':depths[index],
             'depth_difference_m':abs(depths[index]-requested)})
    return index, depths[index], depths


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
    try:
        completed = subprocess.run([sys.executable, '-m', 'src.environmental.copernicus'],
            input=request.model_dump_json(), text=True, capture_output=True, cwd=ROOT, timeout=WORKER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise ProviderError('TIMEOUT', 'Copernicus worker exceeded the bounded 60-second retrieval timeout; no complete evidence bundle returned. Worker phase is unknown; no automatic retry.', {
            'failure_stage': 'UNKNOWN_WORKER_PHASE',
            'dataset_id': request.dataset_id,
            'dataset_variable': request.dataset_variable,
            'timeout_seconds': WORKER_TIMEOUT_SECONDS,
        }) from None
    # Toolbox output may include sensitive server diagnostics. Never forward stdout/stderr.
    marker = 'PERMITPULSE_RESULT='
    lines = [line[len(marker):] for line in completed.stdout.splitlines() if line.startswith(marker)]
    if completed.returncode or not lines:
        raise ProviderError('WORKER_RUNTIME', 'Copernicus worker exited without a usable structured response.', {
            'failure_stage': 'WORKER_STARTUP_OR_EXIT',
            'worker_exit_code': completed.returncode,
            'dataset_id': request.dataset_id,
            'dataset_variable': request.dataset_variable,
        })
    try:
        result = json.loads(lines[-1])
    except (TypeError, ValueError):
        raise ProviderError('WORKER_PROTOCOL', 'Copernicus worker returned an invalid structured response.', {
            'failure_stage': 'WORKER_RESPONSE_PARSE',
            'worker_exit_code': completed.returncode,
            'dataset_id': request.dataset_id,
            'dataset_variable': request.dataset_variable,
        }) from None
    if 'error_type' in result:
        raise ProviderError(result.get('error_category','PROVIDER_RUNTIME'),
            result.get('error_message','Copernicus retrieval failed; no usable evidence returned.'), result.get('error_metadata'))
    return result


def worker(request):
    np, copernicusmarine = _load_worker_dependencies()
    from src.copernicus.grid_selection import nearest_valid
    group, variable = MARINE[request.canonical_variable]
    product = products()[group]
    if group == 'turbidity':
        text=re.sub(r'\s+',' ',request.requirement_text or '')
        requires_model=re.search(r'\b(?:using|requires?|shall\s+use)\s+(?:compatible\s+)?(?:Copernicus\s+Marine\s+)?(?:modelled|modeled)\s+turbidity\s+evidence\b',text,re.I)
        if requires_model and product.get('mode')!='FORECAST':
            raise ProviderError('NO_COMPATIBLE_CONFIGURED_SOURCE',
                'No verified modelled FNU turbidity source is configured. The configured TUR source is satellite observation evidence, not modelled evidence; no substitution or NTU/FNU conversion was attempted.')
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
    variables = (['uo', 'vo'] if group == 'currents' else
                 ['VHM0', 'VTM02', 'VMDR'] if group == 'waves' else [variable])
    kwargs = dict(dataset_id=product['dataset'], variables=variables,
        minimum_latitude=lat-.05, maximum_latitude=lat+.05,
        minimum_longitude=lon-.05, maximum_longitude=lon+.05,
        start_datetime=request.provider_query_start or request.start_time,
        end_datetime=request.provider_query_end or request.end_time, chunk_size_limit=2_000_000)
    # Pass deployment credentials explicitly to the isolated SDK call.  The
    # Toolbox also discovers these names implicitly, but explicit propagation
    # avoids losing the Render worker environment across the process boundary.
    if user:
        kwargs['username'] = user
    if password:
        kwargs['password'] = password
    if request.depth is not None:
        kwargs.update(minimum_depth=request.depth, maximum_depth=request.depth)
    if group == 'oxygen':
        # Include bracketing native levels, then enforce the unchanged tolerance.
        kwargs.update(minimum_depth=max(0, request.depth-DEPTH_TOLERANCE_M),
                      maximum_depth=request.depth+DEPTH_TOLERANCE_M,
                      coordinates_selection_method='outside')
    try:
        ds = _stage('dataset_open', lambda: copernicusmarine.open_dataset(**kwargs))
    except ProviderError as exc:
        if (group == 'turbidity' and exc.__cause__ is not None
                and type(exc.__cause__).__name__ == 'CoordinatesOutOfDatasetBounds'
                and 'for the time dimension' in str(exc.__cause__).lower()):
            # SDK catalogue-bound validation precedes usable evidence. Inspect
            # only for classification; never forward arbitrary SDK diagnostics.
            raise ProviderError('NO_COMPATIBLE_ACCESSIBLE_SOURCE',
                'Configured FNU TUR observation source does not cover the requested UTC period. No compatible accessible evidence was returned for that period; no fallback, time substitution, or NTU/FNU conversion was attempted.',
                {'failure_stage': 'TEMPORAL_SELECTION', 'dataset_id': product['dataset'],
                 'dataset_variable': variable, 'evidence_mode': product['mode']}) from None
        if group=='turbidity' and exc.__cause__ is not None and diagnostic(exc.__cause__)[0]=='DATASET_LOOKUP':
            raise ProviderError('CONFIGURED_DATASET_UNAVAILABLE', 'Configured Copernicus turbidity dataset is unavailable or invalid; no fallback dataset or variable was substituted.') from None
        raise
    try:
        # Metadata/coverage checks before selecting or loading numerical values.
        if any(v not in ds for v in variables) or 'time' not in ds.coords:
            raise ProviderError('VARIABLE_LOOKUP', 'Selected dataset is missing the requested variable or time coordinate.')
        if group=='turbidity' and str(ds[variable].attrs.get('units') or '').strip().upper()!='FNU':
            raise ProviderError('UNIT_INCOMPATIBLE', 'Configured TUR evidence does not declare native FNU units. No reviewed compatible normalization or automatic NTU/FNU conversion is available.')
        if not ds.time.size:
            raise ProviderError('TEMPORAL_COVERAGE', 'Selected dataset has no timestamps in the requested period.')
        if sum(ds[v].size*8 for v in variables) > 5_000_000:
            raise ProviderError('SIZE_LIMIT', 'Requested subset exceeds the bounded download size.')
        if any(ds[v].dims not in [('time', 'latitude', 'longitude'), ('time', 'depth', 'latitude', 'longitude')]
               for v in variables):
            raise ProviderError('SOURCE_LAYOUT', 'Dataset dimensions are not supported by this connector.')
        depth_index = None
        available_depths = None
        if group == 'oxygen':
            try:
                depth_index, selected_depth, available_depths = select_oxygen_depth(ds, request.depth)
            except ProviderError as exc:
                exc.metadata.update(provider='COPERNICUS_MARINE',dataset_id=product['dataset'],dataset_name=product['product'],
                    dataset_variable=variable,requested_depth_m=request.depth,
                    requested_depth_mode=request.requested_depth_mode or 'EXPLICIT',depth_tolerance_m=DEPTH_TOLERANCE_M,
                    requested_coordinates=[lat,lon],data_type='MODEL_FORECAST',screening_status='DEPTH_UNSATISFIED')
                exc.metadata['native_unit'] = str(ds[variable].attrs.get('units') or '')[:80]
                from .units import convert
                try:
                    convert(1, exc.metadata['native_unit'], 'mg/L', variable='dissolved_oxygen')
                    exc.metadata['normalized_unit'] = 'mg/L'  # Unit compatibility only; no screened value.
                except ValueError:
                    pass
                if 'depth' in ds.coords:
                    exc.metadata['depth_axis_unit'] = str(ds.depth.attrs.get('units') or '')[:40]
                    exc.metadata['depth_axis_positive'] = str(ds.depth.attrs.get('positive') or '')[:40]
                exc.metadata['returned_time_start'] = str(ds.time.values[0])
                exc.metadata['returned_time_end'] = str(ds.time.values[-1])
                raise
        elif 'depth' in ds.coords:
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
        field = ds[variables[0]].isel(time=-1 if group == 'turbidity' else 0)
        if 'depth' in field.dims:
            field = field.isel(depth=depth_index)
        field = field.transpose('latitude', 'longitude')
        if group == 'currents':
            # Load the small native first-time grid once for both components;
            # choose a valid cell for U AND V, not U alone.
            component_units = {name: ds[name].attrs.get('units') for name in variables}
            if any(unit not in {'m/s', 'm s-1', 'ms-1'} for unit in component_units.values()):
                raise ProviderError('UNIT_INCOMPATIBLE', 'Current components require verified native metre-per-second units before vector derivation.')
            first_grid = _stage('spatial_selection', lambda: ds[variables].isel(time=0, **({'depth': depth_index} if 'depth' in ds.dims else {})).load())
            u_grid = np.asarray(first_grid['uo'].values)
            v_grid = np.asarray(first_grid['vo'].values)
            raw = np.where(np.isfinite(u_grid) & np.isfinite(v_grid), u_grid, np.nan)
        else:
            raw = np.asarray(field.values)
        grid = _stage('spatial_selection', lambda: nearest_valid(lat, lon, [(float(a), float(b), float(raw[i,j]) if np.isfinite(raw[i,j]) else None)
            for i,a in enumerate(ds.latitude.values) for j,b in enumerate(ds.longitude.values)]))
        if group == 'turbidity':
            from .recency import utc, TURBIDITY_MAX_AGE_HOURS
            # Cloud/masked newest images must not hide an older compatible
            # observation. Search native grids newest first, within policy only.
            reference = utc(request.start_time)
            candidates = sorted(((utc(str(t).split('.')[0]+'+00:00'), i)
                                 for i,t in enumerate(ds.time.values)), reverse=True)
            grid = None
            for moment, index in candidates:
                age = (reference-moment).total_seconds()/3600
                if not 0 <= age <= TURBIDITY_MAX_AGE_HOURS:
                    continue
                raw = np.asarray(ds[variable].isel(time=index).transpose('latitude','longitude').values)
                candidate = _stage('spatial_selection', lambda: nearest_valid(lat, lon,
                    [(float(a),float(b),float(raw[i,j]) if np.isfinite(raw[i,j]) else None)
                     for i,a in enumerate(ds.latitude.values) for j,b in enumerate(ds.longitude.values)]))
                if candidate.selected_lat is not None and candidate.distance_km <= 5:
                    grid = candidate
                    break
            if grid is None:
                if candidates and all((reference-moment).total_seconds()/3600 > TURBIDITY_MAX_AGE_HOURS for moment,_ in candidates):
                    raise ProviderError('STALE_TURBIDITY_EVIDENCE', 'Returned native turbidity observations exceed the configured 72-hour maximum age; no stale observation was accepted.')
                raise ProviderError('NO_COMPATIBLE_ACCESSIBLE_SOURCE', 'No compatible unmasked native FNU observation within the configured recency and spatial limits; no time substitution or NTU/FNU conversion.')
        if grid.selected_lat is None or grid.distance_km > 5:
            raise ProviderError('SPATIAL_COVERAGE', 'No valid ocean grid cell within the 5 km representativeness limit; coastal cells may be masked.')
        selected = _stage('spatial_selection', lambda: ds.sel(latitude=grid.selected_lat, longitude=grid.selected_lon))
        if 'depth' in selected.dims:
            selected = selected.isel(depth=depth_index)
        if group in {'currents', 'oxygen', 'turbidity'}:
            # Materialize only the selected point/time/level, once. Reading a
            # lazy scalar per timestamp previously caused repeated remote reads.
            selected = _stage('temporal_selection', lambda: selected[variables].load())
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
                **({'component_units': component_units} if group == 'currents' else {}),
                'source_values': {name: (value if math.isfinite(value) else None) for name, value in source_values.items()} if group == 'waves' else None})
        return {'canonical_variable': request.canonical_variable, 'provider': 'COPERNICUS_MARINE', 'dataset_id': product['dataset'],
            'dataset_name': product['product'], 'dataset_variable': variable, 'source_version': ds.attrs.get('dataset_version'),
            'data_type': 'SATELLITE_OBSERVATION' if product['mode'] == 'OBSERVATION' else 'MODEL_FORECAST',
            'retrieved_at': datetime.now(timezone.utc).isoformat(), 'forecast_initialization': None,
            'latitude': grid.selected_lat, 'longitude': grid.selected_lon, 'distance_km': grid.distance_km,
            'requested_coordinates': [lat, lon], 'depth': selected_depth, 'requested_depth':request.depth,
            'requested_depth_m': request.depth, 'selected_depth_m': selected_depth,
            'depth_difference_m': (abs(selected_depth-request.depth) if selected_depth is not None and request.depth is not None else None),
            **({'requested_depth_mode': request.requested_depth_mode or 'EXPLICIT',
                'depth_tolerance_m': DEPTH_TOLERANCE_M, 'returned_depth_levels_m': available_depths,
                'depth_coordinate_convention': 'METRES_POSITIVE_DOWN'} if group == 'oxygen' else {}),
            'quality_status': 'COASTAL_REVIEW_REQUIRED',
            'spatial_resolution': ds.attrs.get('spatial_resolution'), 'temporal_resolution': request.timestep_seconds,
            'points': points, 'notes': 'Nearest valid cell; coastal/local representativeness requires review. '
                'Current direction is towards, clockwise from north. Wave direction convention is provider-defined and is not converted between from/towards. No tide or local sensor equivalence. '
                'Modelled oxygen is supportive and not equivalent to required in-situ monitoring. '
                'Daily products cannot resolve subdaily excursions.',
            'direction_convention': ('TOWARDS_CLOCKWISE_FROM_NORTH' if request.canonical_variable == 'surface_current_direction' else
                                     'PROVIDER_DEFINED_NOT_NORMALIZED' if request.canonical_variable == 'mean_wave_direction' else None),
            **({'direction_metadata': {key: ds[variable].attrs.get(key) for key in ('long_name','standard_name','units')}}
               if request.canonical_variable == 'mean_wave_direction' else {}),
            'catalogue_reference_verified_at': product.get('live_verified')}
    finally:
        ds.close()


if __name__ == '__main__':
    from .models import EnvironmentalRequest
    try:
        result = worker(EnvironmentalRequest.model_validate_json(sys.stdin.read()))
    except Exception as exc:
        category, message = diagnostic(exc)
        result = {'error_type': type(exc).__name__, 'error_category':category, 'error_message':message,
                  'error_metadata': exc.metadata if isinstance(exc, ProviderError) else {}}
    print('PERMITPULSE_RESULT='+json.dumps(result, allow_nan=False))


def project_current_or_wave_evidence(evidence, canonical_variable, dataset_variable):
    """Project one shared source bundle into a requested physical variable."""
    import copy
    result = copy.deepcopy(evidence)
    result['canonical_variable'] = canonical_variable
    result['dataset_variable'] = dataset_variable
    if canonical_variable in {'significant_wave_height', 'mean_wave_period', 'mean_wave_direction'}:
        for point in result.get('points', []):
            source_values = point.get('source_values') or {}
            if dataset_variable in source_values:
                point['raw_value'] = source_values[dataset_variable]
                point['unit'] = {'VHM0': 'm', 'VTM02': 's', 'VMDR': 'degrees'}.get(dataset_variable, point.get('unit'))
        return result
    if canonical_variable in {'eastward_current', 'northward_current', 'surface_current_speed', 'surface_current_direction'}:
        result['direction_convention'] = 'TOWARDS_CLOCKWISE_FROM_NORTH' if canonical_variable == 'surface_current_direction' else None
    for point in result.get('points', []):
        if canonical_variable in {'eastward_current', 'northward_current', 'surface_current_speed', 'surface_current_direction'}:
            components = point.get('component_values') or {}
            u, v = components.get('uo'), components.get('vo')
            valid = all(isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) for value in (u,v))
            if valid:
                if canonical_variable == 'eastward_current': point.update(raw_value=u, unit='m/s')
                elif canonical_variable == 'northward_current': point.update(raw_value=v, unit='m/s')
                elif canonical_variable == 'surface_current_speed': point.update(raw_value=math.hypot(u, v), unit='m/s')
                else: point.update(raw_value=math.degrees(math.atan2(u, v)) % 360, unit='degrees')
            if canonical_variable == 'surface_current_direction':
                point['unit']='degrees'
                point['derivation']={'method':'ATAN2_U_V_TOWARDS_CLOCKWISE_FROM_NORTH','source_variables':['uo','vo']}
                if not valid:
                    point['raw_value']=None
            point['derived_from'] = ['uo', 'vo']
        elif canonical_variable in {'significant_wave_height', 'mean_wave_period', 'mean_wave_direction'}:
            source = point.get('source_values') or {}
            if dataset_variable in source:
                point['raw_value'] = source[dataset_variable]
                point['unit'] = {'VHM0':'m','VTM02':'s','VMDR':'degrees'}.get(dataset_variable, point.get('unit'))
    return result
