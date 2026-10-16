"""Read-only direction evidence linkage. Never a decision/gating evaluator."""
from copy import deepcopy
from datetime import datetime
import math
from src.environmental.catalog import canonical
from src.environmental.units import convert

DIRECTIONS = {'mean_wave_direction','surface_current_direction','wind_direction_10m'}


def moment(value):
    value = datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.utcoffset() is None:
        raise ValueError('UTC offset required')
    return value


def attach_direction_audit(result, row, environment, start, end):
    variable = canonical(result['effective_rule'].get('canonical_variable'))
    if result['gating'] or row['kind'] != 'environmental_requirement' or variable not in DIRECTIONS or result['effective_rule'].get('threshold') is not None:
        return
    audit = {'status':'UNAVAILABLE','non_gating':True,'points':[],
             'qualification':'Native informational evidence for audit only; no threshold or continuous interval validity is inferred.'}
    result['informational_evidence'] = audit
    if not result['source_verified']:
        audit['reason'] = 'Source verification unresolved'
        return
    index = None
    # Use the same requirement identity/index as normal environmental linkage.
    import re
    identity = re.fullmatch(r'environmental_requirement-(\d+)-.+', row['target_id'])
    if identity:
        index = int(identity[1])
    mappings = [m for m in row.get('mapping',[]) if canonical(m.get('canonical_variable')) == variable
                and (index is None or m.get('requirement_index') == index)]
    if len(mappings) != 1:
        return
    mapped = mappings[0]
    matches = [r for r in (environment or {}).get('requirements',[])
               if r.get('requirement_index') == mapped.get('requirement_index')
               and str(r.get('condition_id')) == str(row['condition_id'])
               and canonical(r.get('canonical_variable')) == variable]
    if len(matches) != 1:
        return
    candidate = matches[0]
    evidence = candidate.get('evidence') or {}
    if (evidence.get('provider') != mapped['routing']['preferred_provider'] or not evidence.get('dataset_id')
            or canonical(evidence.get('canonical_variable')) != variable):
        return
    points = []
    for p in evidence.get('points',[]):
        try:
            time = moment(p['data_time'])
            if p.get('status') != 'INFORMATIONAL' or p.get('validation_notes') or isinstance(p.get('raw_value'),bool):
                continue
            value = convert(p['raw_value'],p['unit'],'degrees',variable=variable)
            if not math.isfinite(value) or time >= end:
                continue
            points.append({'valid_time':p['data_time'],'value':value,'unit':'degrees',
                'raw_value':p['raw_value'],'raw_unit':p['unit'],
                'derivation':deepcopy(p.get('derivation')),'component_values':deepcopy(p.get('component_values')),
                'derived_from':deepcopy(p.get('derived_from') or [])})
        except (KeyError,TypeError,ValueError):
            continue
    inside = [p for p in points if moment(p['valid_time']) >= start]
    selected = inside or ([max(points,key=lambda p:moment(p['valid_time']))] if points else [])
    if not selected:
        return
    audit.update(status='INFORMATIONAL',points=selected,reference_only=not bool(inside),
        direction_convention=evidence.get('direction_convention'),direction_metadata=deepcopy(evidence.get('direction_metadata')),
        derived=variable=='surface_current_direction')
    reference = {key:deepcopy(evidence.get(key)) for key in ('provider','dataset_id','dataset_name','dataset_variable',
        'retrieved_at','latitude','longitude','distance_km','requested_coordinates','requested_depth','selected_depth_m',
        'temporal_resolution','coverage','data_type','direction_convention','direction_metadata')}
    reference['evidence_id'] = candidate.get('evidence_request_key')
    audit['provenance'] = reference
    result['evidence_references'].append(reference)
