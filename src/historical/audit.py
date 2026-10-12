"""Deterministic integrity checks for the genuine, cached Belfast history."""
import hashlib
import json
from datetime import datetime
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hour_steps(times: list[str]) -> bool:
    parsed=[datetime.fromisoformat(x.replace('Z','+00:00')) for x in times]
    return all((later-earlier).total_seconds()==3600 for earlier,later in zip(parsed,parsed[1:]))


def audit_belfast_history(root: Path) -> dict:
    """Audit cached source slices; does not alter observations or contact providers."""
    base=root/'cache'/'historical'/'belfast'; years=[]
    for year in (2024,2025,2026):
        directory=base/str(year); wave_path=next(directory.glob('wave_*.json')); weather_path=next(directory.glob('era5_*.json'))
        wave=json.loads(wave_path.read_text()); weather=json.loads(weather_path.read_text())
        rows=wave['observations']; times=[row['time'] for row in rows]
        grid=wave['grid']; wave_ok=(wave['dataset_id']=='MetO-NWS-WAV-RAN' and all(row['variable']=='VHM0' and row['unit']=='m' and row['value'] >= 0 for row in rows) and len(rows)==24 and grid['representativeness']=='GOOD')
        hourly=weather['hourly']; weather_ok=(weather['data_type']=='HISTORICAL' and weather['model']=='era5' and weather['hourly_units'].get('wind_speed_10m')=='km/h' and len(hourly.get('time',[]))==72 and _hour_steps(hourly['time']))
        masked={name:len(json.loads(next(directory.glob(f'{name}_*.json')).read_text())['observations'])==0 for name in ('current','sst')}
        years.append({'year':year,'wave':{'status':'SOURCE_SLICE_VALIDATED' if wave_ok else 'UNVERIFIED','samples':len(rows),'time_index_3_hourly':all((datetime.fromisoformat(b.replace('Z','+00:00'))-datetime.fromisoformat(a.replace('Z','+00:00'))).total_seconds()==10800 for a,b in zip(times,times[1:])),'grid':grid,'file_sha256':_sha(wave_path)},'weather':{'status':'SOURCE_SLICE_VALIDATED' if weather_ok else 'UNVERIFIED','samples':len(hourly.get('time',[])),'time_index_hourly':_hour_steps(hourly.get('time',[])),'file_sha256':_sha(weather_path)},'masked_coastal_sources':masked})
    result={'scope':'Cached source-slice integrity audit; no remote NetCDF was retained for byte-for-byte reinspection.','years':years,'all_wave_slices_valid':all(x['wave']['status']=='SOURCE_SLICE_VALIDATED' for x in years),'all_era5_slices_valid':all(x['weather']['status']=='SOURCE_SLICE_VALIDATED' for x in years),'limitation':'Three 72-hour April samples are illustrative equivalent-period samples, not comprehensive seasonal climatology.'}
    (base/'quality_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
