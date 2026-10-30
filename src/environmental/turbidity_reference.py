"""Display-only latest observation, kept separate from decision-qualified evidence."""
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
from .models import EnvironmentalRequest
from .recency import utc,TURBIDITY_REFERENCE_LOOKBACK_HOURS

def attach_reference(result, inputs, cache_dir, *, allow_download=False, transport=None):
    targets=[row for row in result.get('requirements',[]) if row.get('canonical_variable')=='turbidity' and row.get('status')=='INSUFFICIENT_DATA']
    if not targets or inputs.latitude is None or inputs.start_time is None:
        return result
    from .copernicus import products,retrieve
    product=products()['turbidity']
    key=sha256(json.dumps({'dataset':product['dataset'],'coordinates':[inputs.latitude,inputs.longitude]},sort_keys=True).encode()).hexdigest()
    path=Path(cache_dir)/'references'/f'{key}.json'
    bundle=None
    try:
        if path.exists(): bundle=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):pass
    def sample_from(data):
        if not isinstance(data,dict) or data.get('provider')!='COPERNICUS_MARINE' or data.get('dataset_id')!=product['dataset'] or data.get('data_type') not in {'SATELLITE_OBSERVATION','OBSERVATION'} or data.get('requested_coordinates')!=[inputs.latitude,inputs.longitude]:return None
        distance=data.get('distance_km')
        if not isinstance(distance,(int,float)) or not math.isfinite(distance) or not 0<=distance<=5:return None
        eligible=[]
        for point in data.get('points',[]):
            try:
                value=point.get('raw_value')
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or str(point.get('unit','')).upper()!='FNU' or point.get('validation_notes'):continue
                moment=utc(point['data_time'])
                if moment<=utc(inputs.start_time) and moment<=datetime.now(timezone.utc):eligible.append((moment,point))
            except (ValueError,KeyError,TypeError):continue
        return max(eligible,key=lambda pair:pair[0])[1] if eligible else None
    sample=sample_from(bundle)
    if sample is None and allow_download:
        request=EnvironmentalRequest(condition_id=str(targets[0]['condition_id']),requirement_text=targets[0].get('requirement_text',''),canonical_variable='turbidity',coordinates=(inputs.latitude,inputs.longitude),start_time=utc(inputs.start_time).isoformat(),end_time=utc(inputs.end_time).isoformat(),provider_query_start=(utc(inputs.start_time)-timedelta(hours=TURBIDITY_REFERENCE_LOOKBACK_HOURS)).isoformat(),provider_query_end=min(utc(inputs.start_time),datetime.now(timezone.utc)).isoformat(),evidence_mode='historical_reference_only',provider='COPERNICUS_MARINE',dataset_id=product['dataset'],dataset_variable='TUR',requested_unit='FNU',timestep_seconds=86400)
        try:
            bundle=(transport or retrieve)(request)
            sample=sample_from(bundle)
            if sample is not None:
                path.parent.mkdir(parents=True,exist_ok=True)
                temporary=path.with_suffix('.tmp')
                temporary.write_text(json.dumps(bundle,allow_nan=False),encoding='utf-8')
                temporary.replace(path)
        except Exception:
            return result
    if sample is None:return result
    reference={key:bundle.get(key) for key in ['provider','dataset_id','dataset_name','data_type','retrieved_at','latitude','longitude','distance_km']}
    reference.update(raw_value=sample['raw_value'],unit='FNU',data_time=sample['data_time'],age_hours=(utc(inputs.start_time)-utc(sample['data_time'])).total_seconds()/3600,reference_only=True,qualifies_for_decision=False,note='Latest saved observation in the searched region. Historical context only; not a forecast or evidence that future turbidity meets the permit limit.')
    for row in targets:row['historical_reference']=dict(reference)
    return result
