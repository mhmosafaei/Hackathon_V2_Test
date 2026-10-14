"""No AI here. Mapping is local; only explicit Fetch invokes provider transports."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
from .models import EnvironmentalRequest, EvaluationInput
from .router import route
from .catalog import canonical
from .units import convert, canonical_unit
from .errors import ProviderError, diagnostic
from .sampling import MARINE_STEPS, timestep_bounds, source_depth, weather_spatial_limit

CURRENT_VARIABLES = {'eastward_current', 'northward_current', 'surface_current_speed', 'surface_current_direction'}


def precipitation_accumulation_semantics(requirement):
    """Return explicit comparison semantics for accumulated precipitation.

    ``mm per hour`` is retained as source wording, but is not a physical unit
    accepted by the generic converter.  It means a quantity in millimetres
    accumulated over a one-hour interval only when the source says so.
    """
    if canonical(requirement.get('canonical_variable')) != 'precipitation':
        return None
    original_unit = str(requirement.get('unit') or requirement.get('threshold_unit') or '').strip().lower()
    source_text = ' '.join([
        str(requirement.get('requirement_text') or ''),
        str(requirement.get('temporal_requirement') or ''),
        ' '.join(str(span.get('quotation') or '') for span in requirement.get('source_spans', [])),
    ]).lower()
    explicit_hourly = bool(re.search(r'\bmm\s*(?:per|/)\s*(?:one[- ]?)?hour\b', original_unit))
    explicit_hourly = explicit_hourly or bool(
        re.search(r'\bhourly\b.*\baccumulat|\baccumulat\w*\b.*\bone[- ]hour\b', source_text))
    if not explicit_hourly:
        return None
    return {
        'comparison_unit': 'mm',
        'required_accumulation_interval_seconds': 3600,
        'temporal_semantics': 'ACCUMULATED_OVER_INTERVAL',
    }


def provider_status():
    configured = bool(os.getenv('COPERNICUSMARINE_SERVICE_USERNAME') and os.getenv('COPERNICUSMARINE_SERVICE_PASSWORD'))
    return {'COPERNICUS_MARINE': 'Credentials configured · connection not tested' if configured else 'Credentials required',
            'ECMWF_FORECAST': 'Public endpoint configured · connection not tested',
            'ERA5': 'Open-Meteo historical adapter configured · connection not tested',
            'CDS': 'Direct CDS retrieval not implemented', 'CAMS': 'Live retrieval not implemented'}


def derived_sst_checks(requirement):
    """Narrow verified SST/2 m air-temperature recovery, never raw AI mutation."""
    if (not requirement.get('source_verified') or canonical(requirement.get('canonical_variable')) not in {'sea_surface_temperature','air_temperature'}
            or requirement.get('threshold') is not None or requirement.get('operator') is not None):
        return [requirement]
    source = ' '.join(s['quotation'] for s in requirement.get('source_spans', []))
    pattern = r'\bValues below (-?\d+(?:\.\d+)?) (deg C|°C|degrees_C|degree_C|degrees C) or above (-?\d+(?:\.\d+)?) (deg C|°C|degrees_C|degree_C|degrees C) shall be flagged for review\b'
    matches = list(re.finditer(pattern, source, re.I))
    if len(matches) != 1:
        return [requirement]
    match = matches[0]
    low, high = float(match[1]), float(match[3])
    if not math.isfinite(low) or not math.isfinite(high) or low >= high:
        return [requirement]
    return [{**requirement, 'operator':op, 'threshold':value, 'unit':unit,
             'derivation':{'method':'DERIVED_FROM_VERIFIED_SOURCE_TEXT', 'source_expression':match[0],
                           'original_operator':None, 'original_threshold':None}}
            for op,value,unit in [('<',low,match[2]),('>',high,match[4])]]


def map_requirements(analysis):
    rows = []
    # The deterministic source audit is authoritative for whether a model
    # environmental record is eligible for routing.  Keep the original model
    # records untouched in ``analysis`` for audit/provenance; only the derived
    # mapping is constrained.  Older fixtures without an audit retain the
    # historical mapping behavior.
    environmental_extraction = analysis.get('environmental_extraction') or {}
    candidate_conditions = environmental_extraction.get('candidate_conditions')
    allowed_conditions = ({str(condition_id) for condition_id in candidate_conditions}
                          if isinstance(candidate_conditions, list) else None)
    expanded = [(index, item) for index, original in enumerate(analysis.get('environmental_requirements', []))
                for item in derived_sst_checks(original)]
    for index, requirement in expanded:
        if allowed_conditions is not None and str(requirement.get('condition_id')) not in allowed_conditions:
            continue
        evidence_type = requirement['evidence_type'].strip().lower().replace('-', '_')
        quotations = ' '.join(s['quotation'] for s in requirement.get('source_spans', []))
        # PDF/model line wrapping is presentation noise for this classifier;
        # retain ``quotations`` unchanged in the mapped record for provenance.
        classification_text = re.sub(r'\s+', ' ', quotations).strip()
        # A non-equivalence warning is not an instruction to use local sensors.
        # Remove only this explicit negative phrase, leaving actual obligations intact.
        evidence_text = re.sub(r'not\s+equivalent\s+to(?:\s+required)?\s+in[ -]situ\s+monitoring', '', classification_text, flags=re.I)
        if re.search(r'\bin[ -]situ\b|\blocal sensors?\b|\blaboratory\b|\bmonitoring stations?\b', evidence_text, re.I):
            evidence_type = 'local_sensor'
        routing = route(requirement['canonical_variable'], evidence_type)
        precipitation_metadata = precipitation_accumulation_semantics(requirement)
        rows.append({**requirement,
                     **(precipitation_metadata or {}),
                     **({'original_canonical_variable':requirement['canonical_variable']}
                        if routing['canonical_variable'] != requirement['canonical_variable'] else {}),
                     'canonical_variable': routing['canonical_variable'],
                     'requirement_index': index, 'routing': routing,
                     **({'original_threshold':{'operator':requirement.get('operator'),'value':requirement.get('threshold'),'unit':requirement.get('unit')},
                         'provider_evidence_unit':'FNU', 'comparison_status':'MANUAL_FNU_REQUIRED' if (requirement.get('unit') or '').upper()=='NTU' else 'DIRECTLY_COMPARABLE' if (requirement.get('unit') or '').upper()=='FNU' else 'UNIT_INCOMPATIBLE'}
                        if routing['canonical_variable']=='turbidity' and routing['preferred_provider']=='COPERNICUS_MARINE' else {}),
                     'status': 'INFORMATIONAL' if routing['preferred_provider'] == 'NOT_APPLICABLE' else 'EXTERNAL_EVIDENCE_REQUIRED' if routing['preferred_provider'] == 'EXTERNAL' else 'INSUFFICIENT_DATA',
                     'notes_for_evaluation': routing['notes']})
    return rows


def utc(value):
    time = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if time.utcoffset() is None:
        raise ValueError('Timestamp requires UTC offset')
    return time.astimezone(timezone.utc)


def compatible_points(requirement, request, evidence, *, now=None):
    """Evaluate every returned point, never claim whole-period coverage from one value."""
    now = now or datetime.now(timezone.utc)
    # All request and provider timestamps are required to be timezone-aware.  Keep
    # the comparison in UTC so a local-naive clock cannot turn a current/future
    # request into a historical one (or vice versa).
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Evaluation clock must be timezone-aware')
    now = now.astimezone(timezone.utc)
    precipitation_metadata = precipitation_accumulation_semantics(requirement)
    failures = []
    if not requirement.get('source_verified'):
        failures.append('Source quotation/condition link requires verification')
    if evidence.get('provider') != request.provider or not evidence.get('dataset_id'):
        failures.append('Provider/dataset provenance mismatch')
    if evidence.get('canonical_variable') != request.canonical_variable:
        failures.append('Physical variable identity mismatch')
    if evidence.get('quality_status') not in {'SUITABLE', 'COASTAL_REVIEW_REQUIRED'}:
        failures.append('Spatial/temporal representativeness is not verified')
    if evidence.get('requested_coordinates') != list(request.coordinates):
        failures.append('Requested location mismatch')
    allowed_distance = (weather_spatial_limit(evidence.get('dataset_id'), request.coordinates[0])
        if request.provider in {'ECMWF_FORECAST', 'ERA5'} else 5)
    # Injected synthetic evidence has no model grid; never affects live adapters.
    if str(evidence.get('dataset_id', '')).startswith('SYNTHETIC'):
        allowed_distance = 5
    if allowed_distance is None or evidence.get('distance_km') is None or evidence['distance_km'] > allowed_distance:
        failures.append('Selected cell exceeds known model/grid representativeness or metadata is unavailable')
    if request.depth is not None:
        selected_depth = evidence.get('selected_depth_m', evidence.get('depth'))
        if selected_depth is None:
            failures.append('Selected provider depth unavailable')
        elif abs(float(selected_depth) - request.depth) > .5:
            failures.append('Depth tolerance exceeded')
    if request.evidence_mode in {'forecast', 'current'} and evidence.get('data_type') != 'MODEL_FORECAST':
        failures.append('Forecast/observation evidence mode mismatch')
    if request.evidence_mode == 'unspecified' and evidence.get('data_type') not in {'MODEL_FORECAST','SATELLITE_OBSERVATION','OBSERVATION'}:
        failures.append('Evidence type unavailable or incompatible with unspecified current evidence')
    if request.evidence_mode == 'observation' and evidence.get('data_type') not in {'SATELLITE_OBSERVATION', 'OBSERVATION'}:
        failures.append('Observation required, not model forecast')
    # Historical/reanalysis evidence is required only for a request whose whole
    # requested interval had already ended when the evidence was retrieved.
    # Using retrieval time (rather than a later UI evaluation clock) keeps a
    # current/future marine forecast from becoming historical on rerender while
    # preserving the safeguard for genuinely historical requests.
    historical_mode = request.evidence_mode in {'historical', 'reanalysis', 'seasonal'}
    evidence_reference = now
    try:
        evidence_reference = utc(evidence['retrieved_at'])
    except (KeyError, ValueError, TypeError):
        pass
    historical_target = historical_mode and utc(request.end_time) < evidence_reference
    if historical_target and evidence.get('data_type') != 'REANALYSIS':
        failures.append('Historical evidence required')
    try:
        age = (now-utc(evidence['retrieved_at'])).total_seconds()/3600
        if age < 0 or age > 6 and evidence.get('data_type') != 'REANALYSIS':
            failures.append('Stale or future retrieval timestamp')
        if evidence.get('forecast_initialization') and (now-utc(evidence['forecast_initialization'])).total_seconds()/3600 > 24:
            failures.append('Stale forecast initialization')
    except (KeyError, ValueError, TypeError):
        failures.append('Retrieval timestamp unavailable')
    # Source presence is not proof of interpretation. Numeric literal must at least exist.
    threshold = requirement.get('threshold')
    if threshold is not None:
        source_text = ' '.join(s['quotation'] for s in requirement.get('source_spans', []))
        numbers = re.findall(r'(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])', source_text)
        if not any(float(n) == threshold for n in numbers):
            failures.append('Numeric threshold not supported by cited text')
        unit = requirement.get('unit')
        literal_unit_supported = bool(unit and re.search(r'(?<!\w)' + re.escape(unit) + r'(?!\w)', source_text, re.I))
        # For an explicitly hourly accumulated precipitation requirement, the
        # source may state "5 mm in a one-hour interval" rather than the
        # derived display phrase "mm per hour".  The semantic interval is
        # source-backed by precipitation_accumulation_semantics().
        if not literal_unit_supported and not precipitation_metadata:
            failures.append('Threshold unit not supported literally by cited text; review required')
    manual = requirement.get('manual_comparison_threshold')
    target_unit = (precipitation_metadata or {}).get('comparison_unit') or requirement.get('unit')
    if manual and request.canonical_variable == 'turbidity' and (target_unit or '').upper() == 'NTU':
        threshold = manual['value']; target_unit = 'FNU'
    points = []
    for raw in evidence.get('points', [])[:200]:
        notes = list(failures); value = None
        try:
            moment = utc(raw['data_time'])
            if not utc(request.provider_query_start or request.start_time) <= moment <= utc(request.provider_query_end or request.end_time):
                continue
            raw_unit = raw.get('unit')
            if precipitation_metadata:
                # Accumulation is a semantic constraint, not a unit conversion.
                # Compare only directly returned hourly quantities.
                if canonical_unit(raw_unit).lower() != precipitation_metadata['comparison_unit']:
                    raise ValueError('Precipitation quantity unit incompatible')
                if raw.get('accumulation_interval_seconds') != precipitation_metadata['required_accumulation_interval_seconds']:
                    raise ValueError('Precipitation accumulation interval incompatible')
                provider_semantics = str(raw.get('temporal_semantics') or '').upper()
                if 'ACCUMULATED' not in provider_semantics or 'RATE' in provider_semantics:
                    raise ValueError('Precipitation evidence is not accumulated over the required interval')
                value = float(raw['raw_value'])
            else:
                value = convert(raw['raw_value'], raw_unit, target_unit or raw_unit, variable=request.canonical_variable)
        except (KeyError, ValueError, TypeError) as exc:
            message = str(exc).lower()
            if ('units' in message or 'unit' in message or
                    'precipitation accumulation' in message or 'precipitation evidence' in message):
                notes.append('Provider precipitation quantity/accumulation semantics incompatible with permit requirement'
                             if precipitation_metadata else 'Provider unit incompatible with permit requirement')
            else:
                notes.append('Missing required value or invalid timestamp')
        state = 'INSUFFICIENT_DATA'
        comparison = None
        if not notes:
            if threshold is None:
                if request.canonical_variable in {'sea_surface_temperature','air_temperature'} and re.search(r'\bbelow\b|\babove\b', ' '.join(s['quotation'] for s in requirement.get('source_spans', [])), re.I):
                    notes.append('Threshold interpretation requires review')
                else:
                    state = 'INFORMATIONAL'
            elif not requirement.get('explicit_requirement') or not requirement.get('unit') or not request.operator:
                notes.append('Explicit source threshold, unit and operator required')
            else:
                comparisons = {'<': lambda: value < threshold, '<=': lambda: value <= threshold,
                    '>': lambda: value > threshold, '>=': lambda: value >= threshold,
                    '==': lambda: value == threshold, '!=': lambda: value != threshold}
                if request.operator in comparisons:
                    comparison = comparisons[request.operator]()
                    state = 'WITHIN_THRESHOLD' if comparison else 'THRESHOLD_EXCEEDED'
                else:
                    notes.append('Unsupported comparison')
        conversion_method = ('IDENTITY' if precipitation_metadata else
                             'IDENTITY' if (target_unit or raw.get('unit')) == raw.get('unit') else
                             'OXYGEN_MMOL_M3_TO_MG_L' if request.canonical_variable == 'dissolved_oxygen' else 'UNIT_CONVERSION')
        points.append({**raw, 'raw_unit': raw.get('unit'), 'normalized_value': value, 'normalized_unit': canonical_unit(target_unit or raw.get('unit')),
                       'conversion_method': conversion_method,
                       'threshold': threshold, 'comparison': comparison, 'status': state, 'validation_notes': notes})
    # Arbitrary durations, statistics and aggregation must not be silently interpreted.
    if threshold is not None and any(re.search(pattern, requirement.get('temporal_requirement') or '', re.I)
            for pattern in [r'percentile', r'mean', r'average', r'consecutive', r'duration', r'\d+\s*(hours?|minutes?)']):
        for point in points:
            point.update(status='INSUFFICIENT_DATA', comparison=None)
            point['validation_notes'].append('Source statistic/duration requires a dedicated evaluator')
    statuses = {p['status'] for p in points}
    status = ('INSUFFICIENT_DATA' if not points or 'INSUFFICIENT_DATA' in statuses else
              'THRESHOLD_EXCEEDED' if 'THRESHOLD_EXCEEDED' in statuses else
              'INFORMATIONAL' if threshold is None else 'WITHIN_THRESHOLD')
    # Full-period summaries require a regular hourly-or-finer series, endpoints and no gaps.
    temporal_status = 'INCOMPLETE'
    if points:
        times = sorted(set(utc(p['data_time']) for p in points))
        # Daily evidence is still daily: bracketing does not prove subdaily extremes.
        step = request.timestep_seconds or 3600
        gaps = any((b-a).total_seconds() > step for a,b in zip(times, times[1:]))
        if times[0] > utc(request.start_time) or times[-1] < utc(request.end_time) or gaps:
            status = 'INSUFFICIENT_DATA'; failures.append('Requested period not fully covered; point results only')
        else:
            temporal_status = 'COVERED'
    all_notes = list(dict.fromkeys(failures + [note for point in points for note in point['validation_notes']]))
    if not points:
        all_notes.append('Missing required values in requested provider period')
    for point in points:
        point['threshold_evaluation'] = ('NOT_DETERMINED' if point['status'] == 'INSUFFICIENT_DATA' or temporal_status != 'COVERED'
            else 'TRIGGERED' if point['comparison'] is True else 'NOT_TRIGGERED' if point['comparison'] is False else 'NOT_APPLICABLE')
    trigger = ('NOT_DETERMINED' if status == 'INSUFFICIENT_DATA' else 'NOT_APPLICABLE' if threshold is None
               else 'TRIGGERED' if any(p['comparison'] is True for p in points) else 'NOT_TRIGGERED')
    coverage = {'requested_start':request.start_time, 'requested_end':request.end_time,
        'provider_query_start':request.provider_query_start or request.start_time,
        'provider_query_end':request.provider_query_end or request.end_time,
        'temporal_resolution_seconds':request.timestep_seconds,
        'actual_start':times[0].isoformat() if points else None,
        'actual_end':times[-1].isoformat() if points else None, 'points':len(points)}
    return {**evidence, 'points': points, 'status': status, 'validation_notes': all_notes, 'coverage':coverage,
            'retrieval_status':'SUCCESS', 'temporal_coverage_status':temporal_status,
            'spatial_distance_status':'WITHIN_CONFIGURED_DISTANCE' if allowed_distance is not None and evidence.get('distance_km') is not None and evidence['distance_km'] <= allowed_distance else 'OUTSIDE_OR_UNKNOWN_DISTANCE',
            'applicability_status':evidence.get('quality_status'), 'threshold_evaluation':trigger,
            'threshold_evaluation_scope':'Any returned point triggers; not an aggregated regulatory statistic',
            'qualification':'Coastal applicability requires human review. Not a compliance conclusion or operational authorization.' if evidence.get('quality_status') == 'COASTAL_REVIEW_REQUIRED' else 'Not a compliance conclusion or operational authorization.',
            'max_representative_distance_km':allowed_distance,
            'comparison_scope': 'Point comparisons only; never operational authorization'}


def evaluate(analysis, inputs: EvaluationInput, cache_dir: Path, *, transports=None,
             condition_ids=None):
    # Keep provider imports lazy.  A caller that supplies an explicit transport
    # map (for example the Condition-40-only acceptance path) must not import
    # unrelated connectors and their optional dependencies.
    copernicus = None
    if transports is None:
        from . import ecmwf, era5, copernicus
        transports = {'ECMWF_FORECAST': ecmwf.retrieve,
            'ERA5': era5.retrieve, 'COPERNICUS_MARINE': copernicus.retrieve}
    rows = map_requirements(analysis)
    if condition_ids is not None:
        scoped_ids = {str(condition_id) for condition_id in condition_ids}
        if not scoped_ids:
            raise ValueError('Explicit environmental requirement scope cannot be empty')
        rows = [row for row in rows if str(row.get('condition_id')) in scoped_ids]
    dispatched = 0
    fetched = {}  # Per-click retrieval inputs only; thresholds evaluated independently.
    for row in rows:
        routing = row['routing']; provider = routing['preferred_provider']
        if provider == 'NOT_APPLICABLE':
            row['retrieval_status'] = 'NOT_APPLICABLE'
            continue
        if provider == 'EXTERNAL':
            continue
        reasons = []
        if not routing['implemented']:
            reasons.append(routing['notes'])
        if not row.get('source_verified'):
            reasons.append('Source verification required before fetching')
        if routing['canonical_variable'] == 'turbidity':
            if row['comparison_status']=='MANUAL_FNU_REQUIRED':
                manual = inputs.manual_fnu_thresholds.get(row['requirement_index'])
                if manual is None:
                    reasons.append('Provider unit FNU is not comparable with permit requirement NTU; no conversion is supported. MANUAL_FNU_REQUIRED: enter a manually verified FNU threshold.')
                elif row.get('threshold') is None or row.get('operator') not in {'<','<=','>','>=','==','!='}:
                    reasons.append('Original NTU threshold/operator interpretation requires source review before manual screening')
                else:
                    row['manual_comparison_threshold']={'value':manual,'unit':'FNU','source':'USER_SUPPLIED',
                        'entered_at':datetime.now(timezone.utc).isoformat()}
                    row['comparison_status']='READY_WITH_MANUAL_FNU'
            elif row['comparison_status']=='UNIT_INCOMPATIBLE':
                reasons.append('Unsupported turbidity unit; source interpretation requires review')
        if row['evidence_type'] not in {'forecast', 'unspecified', 'historical', 'reanalysis', 'seasonal', 'observation', 'current'}:
            reasons.append('Evidence mode requires review')
        if re.search(r'\bafter\b|\bincident\b|\bseason\b|\b(?:19|20)\d{2}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b', row.get('temporal_requirement') or '', re.I):
            reasons.append('Source calendar/event scope requires explicit interpretation; selected times alone are insufficient')
        if inputs.latitude is None:
            reasons.append('Additional location is required')
        if not inputs.start_time:
            reasons.append('Operational period required before environmental evaluation')
        complex_scope = any(g['type'] in {'route', 'corridor', 'polygon', 'restricted_segment', 'exclusion_zone', 'other'}
                            for g in analysis.get('geofences', []))
        if complex_scope and not inputs.point_scope_confirmed:
            reasons.append('Spatial sampling strategy required; a point cannot represent the whole geofence')
        depth, depth_error = source_depth(row)
        if depth_error:
            reasons.append(depth_error)
        if depth is not None and inputs.depth is not None and inputs.depth != depth:
            reasons.append('Selected depth conflicts with source depth')
        if depth is None:
            depth = inputs.depth  # Explicit user selection, never an inferred default.
        if routing['canonical_variable'] == 'dissolved_oxygen' and depth is None:
            reasons.append('Explicit depth required for 3-D dissolved oxygen evidence')
        if reasons:
            row['notes_for_evaluation'] = '; '.join(reasons)
            continue
        request = EnvironmentalRequest(condition_id=row['condition_id'], requirement_text=row['requirement_text'],
            canonical_variable=routing['canonical_variable'], operator=row['operator'], threshold=row['threshold'],
            threshold_unit=row.get('comparison_unit') or row['unit'], geographic_scope=row['geographic_scope'],
            coordinates=(inputs.latitude, inputs.longitude), start_time=inputs.start_time.astimezone(timezone.utc).isoformat(),
            end_time=inputs.end_time.astimezone(timezone.utc).isoformat(),
            depth=depth,
            evidence_mode=row['evidence_type'].strip().lower().replace('-', '_'), provider=provider,
            requested_unit='FNU' if row.get('manual_comparison_threshold') else row.get('comparison_unit') or row['unit'],
            comparison_unit=row.get('comparison_unit'),
            required_accumulation_interval_seconds=row.get('required_accumulation_interval_seconds'),
            temporal_semantics=row.get('temporal_semantics'))
        if provider == 'COPERNICUS_MARINE':
            if copernicus is None:
                from . import copernicus
            from .router import MARINE
            group, variable = MARINE[routing['canonical_variable']]
            product = copernicus.products()[group]
            request.dataset_id = product['dataset']
            request.dataset_variable = variable
            request.timestep_seconds = MARINE_STEPS[group]
        else:
            from .router import WEATHER
            request.dataset_id = 'ecmwf_ifs' if provider == 'ECMWF_FORECAST' else 'era5'
            request.dataset_variable = WEATHER.get(routing['canonical_variable'])
            request.timestep_seconds = 3600
        request.provider_query_start, request.provider_query_end = timestep_bounds(
            request.start_time, request.end_time, request.timestep_seconds)
        request_data = request.model_dump(mode='json')
        row['request'] = request_data
        # Dataset configuration changes invalidate local provider evidence, not AI results.
        config_path = Path(__file__).resolve().parents[2]/'config/environmental_data_sources.json'
        config_version = sha256(config_path.read_bytes()).hexdigest()
        retrieval_inputs = {key:request_data[key] for key in ('provider','dataset_id','dataset_variable',
            'canonical_variable','coordinates','depth','provider_query_start','provider_query_end','evidence_mode')}
        if provider == 'COPERNICUS_MARINE' and routing['canonical_variable'] in CURRENT_VARIABLES:
            # One uo/vo request is sufficient for all four current projections.
            retrieval_inputs['canonical_variable'] = 'current_vector_bundle'
            retrieval_inputs['dataset_variable'] = 'uo,vo'
        if provider in {'ECMWF_FORECAST', 'ERA5'}:
            retrieval_inputs['cell_selection'] = 'nearest'
        identity = sha256(json.dumps({'version': 2, 'analysis_id': analysis['analysis_id'],
            'retrieval': retrieval_inputs, 'provider_configuration': config_version}, sort_keys=True).encode()).hexdigest()
        row['evidence_request_key'] = identity
        path = cache_dir / f'{identity}.json'
        try:
            if identity in fetched:
                shared = fetched[identity]
                if isinstance(shared, Exception):
                    raise shared
                evidence = shared
                row['cache_state'] = 'REUSED'
            else:
                evidence = None
            cached = json.loads(path.read_text()) if path.exists() else None
            fresh = cached and cached.get('retrieval') == retrieval_inputs and (
                datetime.now(timezone.utc)-utc(cached['evidence']['retrieved_at'])).total_seconds() <= 21600
            if evidence is not None:
                pass
            elif fresh:
                evidence = cached['evidence']; row['cache_state'] = 'CACHED'
            else:
                if dispatched >= 12:
                    row['notes_for_evaluation'] = 'Per-click provider request limit (12) reached; remaining requirements not fetched.'
                    continue
                if provider not in transports:
                    raise ProviderError('TRANSPORT_UNAVAILABLE', 'Mapped provider transport is not enabled in this server configuration.')
                dispatched += 1
                evidence = transports[provider](request)
                # Persist successful retrieval before evaluation, no credential-bearing SDK errors.
                cache_dir.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({'retrieval':retrieval_inputs, 'request': request_data, 'evidence': evidence}, allow_nan=False, indent=2))
                row['cache_state'] = 'FETCHED'
            if provider == 'COPERNICUS_MARINE' and routing['canonical_variable'] in CURRENT_VARIABLES:
                evidence = copernicus.project_current_or_wave_evidence(evidence, routing['canonical_variable'], variable)
            fetched[identity] = evidence
            row['evidence'] = compatible_points(row, request, evidence)
            row['retrieval_status'] = row['cache_state']
            row['status'] = row['evidence']['status']
            if row.get('comparison_status'):
                actual_units = {p.get('unit') for p in evidence.get('points', [])}
                if len(actual_units)==1:
                    row['provider_evidence_unit']=next(iter(actual_units))
            if row.get('comparison_status') and any('unit incompatible' in note.lower() for note in row['evidence']['validation_notes']):
                row['comparison_status']='UNIT_INCOMPATIBLE'
            row['notes_for_evaluation'] = '; '.join(row['evidence']['validation_notes']) or evidence.get('notes', '')
            if row.get('manual_comparison_threshold'):
                audit = {'analysis_id':analysis['analysis_id'], 'requirement_index':row['requirement_index'],
                         'condition_id':row['condition_id'], 'original_threshold':row['original_threshold'],
                         'manual_comparison_threshold':row['manual_comparison_threshold'],
                         'request':request_data, 'evidence':row['evidence'],
                         'review_state':'UNREVIEWED', 'executable':False}
                audit_id = sha256(json.dumps(audit, sort_keys=True).encode()).hexdigest()
                (cache_dir/'manual_comparisons').mkdir(parents=True, exist_ok=True)
                (cache_dir/'manual_comparisons'/f'{audit_id}.json').write_text(json.dumps(audit, indent=2, allow_nan=False))
        except Exception as exc:
            fetched[identity] = exc  # Identical failed evidence is not dispatched twice.
            row['status'] = 'INSUFFICIENT_DATA'
            category, message = diagnostic(exc)
            details = {'provider_error_type':type(exc).__name__, 'provider_error_category':category,
                'provider_error_message':message, 'provider':provider,
                'dataset_id':request.dataset_id, 'variable':request.canonical_variable,
                'request_start':request.start_time, 'request_end':request.end_time}
            if provider == 'COPERNICUS_MARINE':
                if copernicus is None:
                    from . import copernicus
                from .router import MARINE
                group, variable = MARINE.get(request.canonical_variable, (None,None))
                details['dataset_id'] = copernicus.products().get(group, {}).get('dataset')
                details['variable'] = variable
            elif provider in {'ECMWF_FORECAST','ERA5'}:
                from .router import WEATHER
                details['dataset_id'] = request.dataset_id
                details['variable'] = WEATHER.get(request.canonical_variable)
            details['recorded_at'] = datetime.now(timezone.utc).isoformat()
            row['provider_diagnostic'] = details
            row['retrieval_status'] = 'FAILED'
            row['notes_for_evaluation'] = message
            cache_dir.joinpath('errors').mkdir(parents=True, exist_ok=True)
            (cache_dir/'errors'/f'{identity}.json').write_text(json.dumps(details, indent=2))
    states = provider_status()
    for row in rows:
        evidence = row.get('evidence')
        if evidence and evidence.get('points'):
            states[row['routing']['preferred_provider']] = ('Mock transport only · not authenticated' if
                str(evidence.get('dataset_id', '')).startswith('SYNTHETIC') else 'Connected · retrieval completed; evidence suitability still checked separately')
    groups = {}
    for row in rows:
        if not row.get('evidence'):
            continue
        key = row['evidence_request_key']
        group = groups.setdefault(key, {**row, 'checks':[]})
        group['checks'].append({k:row.get(k) for k in ('condition_id','operator','threshold','unit','status','evidence','derivation','manual_comparison_threshold','original_threshold')})
        if row['status'] == 'INSUFFICIENT_DATA':
            group['status'] = 'INSUFFICIENT_DATA'
    return {'requirements': rows, 'evidence_groups':list(groups.values()), 'provider_status': states, 'executable_rules': 0,
            'notes': 'Environmental evidence only. Human review and deciding evidence remain required.'}
