"""Refresh only waves, currents and SST for the cached weather forecast interval."""
import json, sys
from pathlib import Path
root=Path(__file__).parents[1]; sys.path.insert(0,str(root))
from dotenv import load_dotenv
load_dotenv(root/'.env',override=True)
from src.weather.open_meteo import load_cached_forecast
from src.copernicus.live import fetch_product

weather=load_cached_forecast(root/'cache'/'weather')
start=weather['hourly']['time'][0]+':00Z'; end=weather['hourly']['time'][-1]+':00Z'
out=root/'cache'/'copernicus'/'synchronized'
out.mkdir(parents=True,exist_ok=True)
results=[]
for name in ('waves','currents','sst'):
 try:
  results.append(fetch_product(name,54.6,-5.9,start,end,out))
 except Exception as exc:
  results.append({'name':name,'error_type':type(exc).__name__,'error':str(exc)[:500]})
(out/'manifest.json').write_text(json.dumps({'site':'Belfast Harbour','latitude':54.6,'longitude':-5.9,'weather_model':weather['model'],'shared_grid':'hourly UTC','start':start,'end':end,'results':results},indent=2),encoding='utf-8')
print(json.dumps([{'name':x['name'],'status':'FAILED' if 'error' in x else 'SUCCESS','observations':len(x.get('observations',[])),'grid':x.get('grid'),'cache_identity':x.get('cache_identity'),'error':x.get('error')} for x in results],indent=2))
