"""Small controlled Copernicus subset adapter; network use requires credentials."""
import hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
def cache_key(dataset,variables,lat,lon,start,end):return hashlib.sha256(json.dumps([dataset,sorted(variables),lat,lon,start,end]).encode()).hexdigest()
def current_speed(uo,vo): return None if uo is None or vo is None else (uo**2+vo**2)**.5
def knots(value): return None if value is None else value*1.943844
def oxygen_mg_l(value,unit):
    if value is None:return None
    if unit.lower().replace(' ','') in {'mmol/m3','mmolm-3'}:return value*.032
    raise ValueError('unconfirmed oxygen unit')
def retrieve_subset(dataset,variables,lat,lon,start,end,cache_dir:Path):
    key=cache_key(dataset,variables,lat,lon,start,end); path=cache_dir/f'{key}.json'
    if path.exists(): return json.loads(path.read_text()),'CACHED'
    if not(os.getenv('COPERNICUSMARINE_SERVICE_USERNAME') and os.getenv('COPERNICUSMARINE_SERVICE_PASSWORD')): raise RuntimeError('Copernicus credentials unavailable')
    raise RuntimeError('Live retrieval must be run by verified catalogue script before use')
def load_cached_product(name,cache_dir:Path,max_age_hours=None,now=None):
    """Load a provenance-complete live result without contacting Copernicus."""
    payload=json.loads((cache_dir/f'{name}.json').read_text())
    required={'dataset_id','retrieved_at','requested_coordinates','grid','observations'}
    missing=required-payload.keys()
    if missing: raise ValueError(f'incomplete cache metadata: {sorted(missing)}')
    retrieved=datetime.fromisoformat(payload['retrieved_at'].replace('Z','+00:00'))
    current=now or datetime.now(timezone.utc)
    age_hours=(current-retrieved).total_seconds()/3600
    payload['cache_age_hours']=age_hours
    payload['cache_fresh']=max_age_hours is None or age_hours<=max_age_hours
    return payload
