"""Small live Copernicus subset retrieval with coordinate/time/source identity."""
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import copernicusmarine
from .grid_selection import nearest_valid

PRODUCTS={
 'waves':('cmems_mod_nws_wav_anfc_1.5km_PT1H-i',['VHM0','VTM02','VMDR','VTPK'],'PREDICTIVE'),
 'currents':('cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT15M-i',['uo','vo'],'PREDICTIVE'),
 'sst':('cmems_mod_nws_phy-sst_anfc_1.5km-2D_PT1H-i',['thetao'],'SUPPORTIVE'),
}
def _utc(value):
    value=str(value).replace(' ','T'); return value if value.endswith('Z') else value+'Z'
def cache_identity(dataset, latitude, longitude, start, end, version='live'):
    return hashlib.sha256(json.dumps([dataset,round(latitude,5),round(longitude,5),start,end,version]).encode()).hexdigest()[:16]
def fetch_product(name:str, latitude:float, longitude:float, start:str, end:str, cache_dir:Path, radius:float=.07)->dict:
    if name not in PRODUCTS: raise ValueError(f'unsupported marine product: {name}')
    if not(-90<=latitude<=90 and -180<=longitude<=180): raise ValueError('invalid latitude/longitude')
    username=os.getenv('COPERNICUSMARINE_SERVICE_USERNAME'); password=os.getenv('COPERNICUSMARINE_SERVICE_PASSWORD')
    if not(username and password): raise RuntimeError('Copernicus credentials unavailable')
    dataset,variables,role=PRODUCTS[name]
    ds=copernicusmarine.open_dataset(dataset_id=dataset,username=username,password=password,variables=variables,
      minimum_longitude=longitude-radius,maximum_longitude=longitude+radius,minimum_latitude=latitude-radius,maximum_latitude=latitude+radius,
      start_datetime=start,end_datetime=end,chunk_size_limit=20_000_000)
    lat=np.asarray(ds.latitude.values); lon=np.asarray(ds.longitude.values); field=ds[variables[0]].isel(time=0)
    if 'depth' in field.dims: field=field.isel(depth=0)
    values=np.reshape(np.asarray(field.values),(len(lat),len(lon)))
    grid=nearest_valid(latitude,longitude,[(float(a),float(b),None if np.isnan(values[i,j]) else float(values[i,j])) for i,a in enumerate(lat) for j,b in enumerate(lon)])
    observations=[]
    if grid.selected_lat is not None:
      selected=ds.sel(latitude=grid.selected_lat,longitude=grid.selected_lon,method='nearest')
      for variable in variables:
       for index,value in selected[variable].to_series().dropna().iloc[:1000].items():
        coordinates={'time':_utc(index)} if not isinstance(index,tuple) else {dim:_utc(part) if dim=='time' else str(part) for dim,part in zip(selected[variable].dims,index)}
        observations.append({'variable':variable,'coordinates':coordinates,'value':float(value),'unit':ds[variable].attrs.get('units'),'raw':True})
      if name=='currents':
       for timestamp,value in (selected['uo'].to_series().pow(2).add(selected['vo'].to_series().pow(2)).pow(.5).dropna().iloc[:1000].items()):
        observations.append({'variable':'current_speed','coordinates':{'time':_utc(timestamp)},'value':float(value),'unit':'m s-1','derived_from':['uo','vo'],'raw':False,'alignment_method':'hourly_max'})
    result={'name':name,'dataset_id':dataset,'product':ds.attrs.get('product'),'source_creation_time':ds.attrs.get('creation_date'),
            'forecast_issue_time':None,'retrieved_at':datetime.now(timezone.utc).isoformat(),'requested_coordinates':[latitude,longitude],
            'requested_start':start,'requested_end':end,'grid':grid.__dict__,'variables':{x:ds[x].attrs.get('units') for x in variables},
            'role':role,'observations':observations,'cache_identity':cache_identity(dataset,latitude,longitude,start,end,ds.attrs.get('creation_date') or 'unknown')}
    cache_dir.mkdir(parents=True,exist_ok=True); path=cache_dir/f'{name}_{result["cache_identity"]}.json'; path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
