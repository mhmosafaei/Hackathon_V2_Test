"""Small authenticated Belfast subsets with JSON provenance cache."""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import numpy as np
import copernicusmarine
sys.path.insert(0,str(Path(__file__).parents[1]))
from src.copernicus.grid_selection import nearest_valid
root=Path(__file__).parents[1]; load_dotenv(root/'.env',override=True); out=root/'cache/copernicus'; out.mkdir(parents=True,exist_ok=True)
items=[('waves','cmems_mod_nws_wav_anfc_1.5km_PT1H-i',['VHM0','VTM02','VMDR','VTPK'],'2026-10-08T00:00:00Z','2026-10-09T00:00:00Z'),('currents','cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT15M-i',['uo','vo'],'2026-10-08T00:00:00Z','2026-10-09T00:00:00Z'),('spm','cmems_obs_oc_nws_bgc_tur-spm-chl_nrt_l3-hr-mosaic_P1D-m',['SPM','TUR'],'2026-10-07T00:00:00Z','2026-10-07T00:00:00Z'),('oxygen','cmems_mod_nws_bgc-o2_anfc_7km-3D_P1D-m',['o2'],'2026-10-08T00:00:00Z','2026-10-09T00:00:00Z'),('sst','cmems_mod_nws_phy-sst_anfc_1.5km-2D_PT1H-i',['thetao'],'2026-10-08T00:00:00Z','2026-10-09T00:00:00Z')]
results=[]
def utc_timestamp(value):
 text=str(value).replace(' ', 'T')
 return text if text.endswith('Z') else text+'Z'
for name,dataset,variables,start,end in items:
 try:
  ds=copernicusmarine.open_dataset(dataset_id=dataset,username=os.environ['COPERNICUSMARINE_SERVICE_USERNAME'],password=os.environ['COPERNICUSMARINE_SERVICE_PASSWORD'],variables=variables,minimum_longitude=-5.98,maximum_longitude=-5.85,minimum_latitude=54.55,maximum_latitude=54.65,start_datetime=start,end_datetime=end,chunk_size_limit=10000000)
  lat=np.asarray(ds.latitude.values); lon=np.asarray(ds.longitude.values)
  field=ds[variables[0]].isel(time=0)
  if 'depth' in field.dims: field=field.isel(depth=0)
  v=np.reshape(np.asarray(field.values),(len(lat),len(lon)))
  cells=[(float(a),float(b),None if np.isnan(v[i,j]) else float(v[i,j])) for i,a in enumerate(lat) for j,b in enumerate(lon)]
  grid=nearest_valid(54.6,-5.9,cells)
  selected=ds.sel(latitude=grid.selected_lat,longitude=grid.selected_lon,method='nearest')
  observations=[]
  for variable in variables:
   series=selected[variable].to_series().dropna()
   for index,value in series.iloc[:250].items():
    if isinstance(index,tuple): index={str(selected[variable].dims[i]):utc_timestamp(part) if str(selected[variable].dims[i])=='time' else str(part) for i,part in enumerate(index)}
    else: index={'time':utc_timestamp(index)}
    observations.append({'variable':variable,'coordinates':index,'value':float(value),'unit':ds[variable].attrs.get('units')})
  if name=='currents' and grid.selected_lat is not None:
   u=selected['uo'].to_series(); v=selected['vo'].to_series()
   for timestamp,value in (u.pow(2).add(v.pow(2)).pow(.5).dropna().iloc[:250].items()):
    observations.append({'variable':'current_speed','coordinates':{'time':utc_timestamp(timestamp)},'value':float(value),'unit':'m s-1','derived_from':['uo','vo']})
  payload={'dataset_id':dataset,'variables':{x:ds[x].attrs.get('units') for x in variables},'sizes':dict(ds.sizes),'product':ds.attrs.get('product'),'version':ds.attrs.get('creation_date'),'retrieved_at':datetime.now(timezone.utc).isoformat(),'requested_coordinates':[54.6,-5.9],'grid':grid.__dict__,'start':start,'end':end,'source_type':'COPERNICUS','role':'SUPPORTIVE' if name in ('spm','oxygen','sst') else 'PREDICTIVE','observations':observations}
  (out/f'{name}.json').write_text(json.dumps(payload,indent=2)); results.append({'name':name,'status':'SUCCESS',**payload})
 except Exception as e: results.append({'name':name,'status':'FAILED','error':f'{type(e).__name__}: {str(e)[:500]}'})
(out/'manifest.json').write_text(json.dumps({'retrieved_at':datetime.now(timezone.utc).isoformat(),'results':results},indent=2)); print(json.dumps([{'name':x['name'],'status':x['status'],'dataset_id':x.get('dataset_id'),'grid':x.get('grid'),'observation_count':len(x.get('observations',[])),'error':x.get('error')} for x in results],indent=2))
