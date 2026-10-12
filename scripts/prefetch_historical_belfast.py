"""Prefetch real equivalent April historical subsets for the offline Belfast demo."""
from pathlib import Path
import sys,json
root=Path(__file__).parents[1]; sys.path.insert(0,str(root))
from dotenv import load_dotenv
load_dotenv(root/'.env',override=True)
from src.historical.sources import fetch_marine_history
from src.weather.open_meteo import fetch_history
out=root/'cache'/'historical'/'belfast'
results=[]
for year in (2024,2025,2026):
 for name in ('wave','current','sst'):
  try: results.append(fetch_marine_history(name,54.6,-5.9,f'{year}-04-09T00:00:00Z',f'{year}-04-11T23:00:00Z',out/f'{year}'))
  except Exception as exc: results.append({'year':year,'name':name,'error_type':type(exc).__name__,'error':str(exc)[:500]})
 try: results.append({'name':'weather',**fetch_history(54.6,-5.9,f'{year}-04-09',f'{year}-04-11',out/f'{year}')})
 except Exception as exc: results.append({'year':year,'name':'weather','error_type':type(exc).__name__,'error':str(exc)[:500]})
(out/'manifest.json').write_text(json.dumps({'site':'Belfast Harbour','results':results},indent=2),encoding='utf-8')
print(json.dumps([{'name':x['name'],'status':'FAILED' if 'error' in x else 'SUCCESS','observations':len(x.get('observations',[])),'grid':x.get('grid'),'error':x.get('error')} for x in results],indent=2))
