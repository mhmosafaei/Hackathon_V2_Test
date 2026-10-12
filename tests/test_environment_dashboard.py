from pathlib import Path
import ast
from src.environment.dashboard import load_belfast, evidence_readiness, marine_series, weather_series
from src.environment.analytics import advisory_windows

ROOT=Path('.')

def test_belfast_cached_environment_loads_without_network():
 data=load_belfast(ROOT)
 assert data['weather']['model']=='ecmwf_ifs025'
 assert data['marine']['waves']['dataset_id'].startswith('cmems_')
 times,values,unit=marine_series(data['marine']['currents'],'current_speed')
 assert times and values and unit=='m s-1'
 wt,wv,wu=weather_series(data['weather'],'wind_speed_10m')
 assert len(wt)==len(wv) and wu=='km/h'

def test_missing_evidence_cannot_form_advisory_window_and_external_sources_stay_external():
 assert advisory_windows(['a','b'],{'wind':[1,None],'wave':[1,1]},{'wind':2,'wave':2})[0]['samples']==1
 rows=evidence_readiness(ROOT)
 assert rows and all('DECIDING' not in row['environmental_role'] or 'EXTERNAL' in row['environmental_role'] for row in rows)

def test_app_keeps_analytics_summary_callable_and_gates_non_belfast_environment():
 source=Path('app.py').read_text()
 tree=ast.parse(source)
 assigned={node.id for node in ast.walk(tree) if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Store)}
 assert 'summary' not in assigned  # regression: coverage summary must not shadow analytics.summary()
 assert "Belfast data are not applied to it." in source
 assert "no site-matched data are available" in source
 assert "Extract conditions from selected pages" not in source
 assert "Diagnostics (audit metadata)" in source
