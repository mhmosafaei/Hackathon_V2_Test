"""Reuse exact downloaded periods across server restarts without retimestamping evidence."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import shutil

def prepare_cache(root, analysis_id, *, mock=False):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',analysis_id):
        raise ValueError('Invalid analysis cache identity')
    base=Path(root)/'cache'/'simple_environment'
    target=base/('saved_mock' if mock else 'saved_live')/analysis_id
    target.mkdir(parents=True,exist_ok=True)
    for path in base.glob(f'*/{analysis_id}/*.json'):
        if path.parent==target or path.parent.parent.name in {'saved_live','saved_mock'}:
            continue
        try:
            payload=json.loads(path.read_text(encoding='utf-8'))
            evidence=payload.get('evidence',{})
            if not isinstance(payload.get('retrieval'),dict) or not evidence.get('retrieved_at'):
                continue
            synthetic=str(evidence.get('dataset_id','')).upper().startswith('SYNTHETIC')
            if synthetic!=mock:
                continue
            destination=target/path.name
            if not destination.exists() or path.stat().st_mtime>destination.stat().st_mtime:
                shutil.copy2(path,destination)
        except (ValueError,OSError,TypeError,AttributeError):
            continue
    return target

def instant(value):
    date=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if date.utcoffset() is None:
        raise ValueError('UTC offset required')
    return date.astimezone(timezone.utc).isoformat()

def normalized(retrieval):
    values=dict(retrieval)
    for key in ('provider_query_start','provider_query_end'):
        if values.get(key): values[key]=instant(values[key])
    return values

def verified_entries(cache_dir, analysis_id, config_version):
    for path in Path(cache_dir).glob('*.json'):
        try:
            cached=json.loads(path.read_text(encoding='utf-8'))
            raw=cached['retrieval']
            expected=sha256(json.dumps({'version':2,'analysis_id':analysis_id,'retrieval':raw,'provider_configuration':config_version},sort_keys=True).encode()).hexdigest()
            if path.stem==expected and isinstance(cached.get('evidence'),dict):
                yield cached
        except (ValueError,KeyError,OSError,TypeError):
            continue

def period_available(entries, inputs):
    if inputs.start_time is None or inputs.end_time is None: return False
    for cached in entries:
        request=cached.get('request',{})
        try:
            if (request.get('coordinates')==[inputs.latitude,inputs.longitude]
                    and instant(request['start_time'])==instant(inputs.start_time)
                    and instant(request['end_time'])==instant(inputs.end_time)):
                return True
        except (ValueError,KeyError,TypeError):
            continue
    return False
