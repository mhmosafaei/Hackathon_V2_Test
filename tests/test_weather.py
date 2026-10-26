import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from src.weather import open_meteo
from src.environment.analytics import summary, rainfall_total, advisory_windows, exceedance_hours

class Response:
 def __init__(self,payload): self.payload=payload
 def __enter__(self): return self
 def __exit__(self,*args): return False
 def read(self): return json.dumps(self.payload).encode()

def test_ecmwf_request_is_bounded_cached_and_utc(monkeypatch,tmp_path):
 payload={'latitude':54.6,'longitude':-5.9,'utc_offset_seconds':0,
          'hourly_units':{'time':'iso8601','wind_speed_10m':'km/h'},
          'hourly':{'time':['2026-10-09T00:00','2026-10-09T01:00'],'wind_speed_10m':[1,2]}}
 captured=[]
 def fake(url,timeout): captured.extend([url,timeout]); return Response(payload)
 monkeypatch.setattr(open_meteo,'urlopen',fake)
 cache=tmp_path/'weather_runtime'
 result=open_meteo.fetch_forecast(54.6,-5.9,cache,forecast_days=3,timeout_seconds=9)
 assert result['model']=='ecmwf_ifs025' and result['provenance_label']=='ECMWF IFS via Open-Meteo'
 assert 'models=ecmwf_ifs025' in captured[0] and captured[1]==9
 assert open_meteo.load_cached_forecast(cache,max_age_hours=1)['cache_fresh']

def test_weather_bounds_and_missing_data():
 with pytest.raises(ValueError): open_meteo.fetch_forecast(1,2,Path('.'),forecast_days=0)
 assert summary([1,None,3])['mean']==2
 assert rainfall_total([1,None,2])==3
 assert exceedance_hours([1,None,3],2)==1
 assert advisory_windows(['a','b'],{'wind':[1,None]},{'wind':2})[0]['samples']==1
 assert advisory_windows(['a','b'],{'wind':[1,1]},{'wind':2})[0]['samples']==2
