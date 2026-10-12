"""Small verified historical retrievals, cached per source/year/period."""
import json, os
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import copernicusmarine
from src.copernicus.grid_selection import nearest_valid

SOURCES={'wave':('MetO-NWS-WAV-RAN',['VHM0'],'NWSHELF_REANALYSIS_WAV_004_015','202007'),
         'current':('cmems_mod_nws_phy-uv_my_7km-2D_PT1H-i',['uo','vo'],'NWSHELF_MULTIYEAR_PHY_004_009','202112'),
         'sst':('cmems_mod_nws_phy-sst_my_7km-2D_PT1H-i',['thetao'],'NWSHELF_MULTIYEAR_PHY_004_009','202112')}
def _time(x):
 x=str(x).replace(' ','T'); return x if x.endswith('Z') else x+'Z'
def fetch_marine_history(name,latitude,longitude,start,end,cache_dir:Path):
 if name not in SOURCES: raise ValueError('unsupported historical marine variable')
 user,password=os.getenv('COPERNICUSMARINE_SERVICE_USERNAME'),os.getenv('COPERNICUSMARINE_SERVICE_PASSWORD')
 if not(user and password): raise RuntimeError('Copernicus credentials unavailable')
 dataset,variables,product,version=SOURCES[name]
 ds=copernicusmarine.open_dataset(dataset_id=dataset,username=user,password=password,variables=variables,minimum_longitude=longitude-.07,maximum_longitude=longitude+.07,minimum_latitude=latitude-.07,maximum_latitude=latitude+.07,start_datetime=start,end_datetime=end,chunk_size_limit=20_000_000)
 lat=np.asarray(ds.latitude.values); lon=np.asarray(ds.longitude.values); raw=np.reshape(np.asarray(ds[variables[0]].isel(time=0).values),(len(lat),len(lon)))
 grid=nearest_valid(latitude,longitude,[(float(a),float(b),None if np.isnan(raw[i,j]) else float(raw[i,j])) for i,a in enumerate(lat) for j,b in enumerate(lon)])
 observations=[]
 if grid.selected_lat is not None:
  picked=ds.sel(latitude=grid.selected_lat,longitude=grid.selected_lon,method='nearest')
  for variable in variables:
   for moment,value in picked[variable].to_series().dropna().items(): observations.append({'time':_time(moment),'variable':variable,'value':float(value),'unit':ds[variable].attrs.get('units'),'raw':True})
  if name=='current':
   for moment,value in (picked['uo'].to_series().pow(2).add(picked['vo'].to_series().pow(2)).pow(.5).dropna().items()): observations.append({'time':_time(moment),'variable':'current_speed','value':float(value),'unit':'m s-1','raw':False,'derived_from':['uo','vo']})
 result={'name':name,'dataset_id':dataset,'product_id':product,'version':version,'retrieved_at':datetime.now(timezone.utc).isoformat(),'requested_coordinates':[latitude,longitude],'start':start,'end':end,'grid':grid.__dict__,'observations':observations}
 cache_dir.mkdir(parents=True,exist_ok=True); (cache_dir/f'{name}_{start[:10]}.json').write_text(json.dumps(result,indent=2),encoding='utf-8'); return result
