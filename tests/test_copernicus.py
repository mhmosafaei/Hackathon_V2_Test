from pathlib import Path
from src.copernicus.adapter import current_speed,knots,oxygen_mg_l,cache_key,load_cached_product
from src.copernicus.grid_selection import nearest_valid
import pytest
def test_derivations_and_missing():
 assert current_speed(3,4)==5 and knots(1)==pytest.approx(1.943844) and current_speed(None,1) is None
def test_oxygen_unit_guard():
 assert oxygen_mg_l(100,'mmol/m3')==pytest.approx(3.2)
 with pytest.raises(ValueError): oxygen_mg_l(1,'mystery')
def test_masked_grid_selects_nearest_valid():
 x=nearest_valid(54.6,-5.9,[(54.6,-5.9,None),(54.61,-5.9,1)])
 assert x.selected_lat==54.61 and x.distance_km is not None
def test_cache_identity(): assert cache_key('a',['x'],1,2,'s','e')==cache_key('a',['x'],1,2,'s','e')
def test_cached_belfast_result_loads_offline(monkeypatch):
 cache=Path('cache/copernicus')
 if not (cache/'currents.json').exists(): pytest.skip('live cache not present')
 monkeypatch.delenv('COPERNICUSMARINE_SERVICE_USERNAME',raising=False)
 monkeypatch.delenv('COPERNICUSMARINE_SERVICE_PASSWORD',raising=False)
 payload=load_cached_product('currents',cache,max_age_hours=24*365*10)
 assert payload['cache_fresh'] and payload['observations'] and payload['dataset_id'].startswith('cmems_')
