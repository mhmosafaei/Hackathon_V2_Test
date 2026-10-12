"""Location-isolated environmental retrieval orchestration (advisory data only)."""
import hashlib, json
from pathlib import Path
from src.weather.open_meteo import fetch_forecast
from src.copernicus.live import fetch_product

def location_key(latitude: float, longitude: float, model: str='ecmwf_ifs025') -> str:
    return hashlib.sha256(json.dumps([round(latitude,5),round(longitude,5),model]).encode()).hexdigest()[:16]

def retrieve_location(root: Path, latitude:float, longitude:float, forecast_days:int=3) -> dict:
    if not(-90<=latitude<=90 and -180<=longitude<=180): raise ValueError('latitude/longitude outside valid geographic range')
    key=location_key(latitude,longitude); out=root/'cache'/'environment_locations'/key
    weather=fetch_forecast(latitude,longitude,out/'weather',forecast_days=forecast_days)
    start=weather['hourly']['time'][0]+':00Z'; end=weather['hourly']['time'][-1]+':00Z'
    marine={}
    for name in ('waves','currents','sst'):
        try: marine[name]=fetch_product(name,latitude,longitude,start,end,out/'copernicus')
        except Exception as exc: marine[name]={'error_type':type(exc).__name__,'error':str(exc)[:500]}
    result={'location_key':key,'latitude':latitude,'longitude':longitude,'weather':{'model':weather['model'],'forecast_hours':weather['forecast_hours'],'cache_directory':str(out/'weather')},'marine':marine}
    out.mkdir(parents=True,exist_ok=True); (out/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
