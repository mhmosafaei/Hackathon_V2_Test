"""Offline pre-demo readiness check; makes no network requests and exposes no secrets."""
from pathlib import Path
import json, sys
root=Path(__file__).parents[1]; sys.path.insert(0,str(root))
from src.environment.dashboard import load_belfast
from src.historical.audit import audit_belfast_history
from src.permit.coverage import coverage_gate

checks=[]
def check(name,ok,detail): checks.append({'check':name,'status':'PASS' if ok else 'FAIL','detail':detail})
aggregate=root/'cache/extractions/ml2025054/aggregate.json'; coverage=root/'cache/extractions/ml2025054/coverage_audit.json'
check('permit aggregate',aggregate.exists(),'cached aggregate available')
if coverage.exists():
 data=json.loads(coverage.read_text()); complete,gaps=coverage_gate(data['conditions']); check('source coverage gate',complete,f'{len(gaps)} unresolved source-condition gaps')
else: check('source coverage gate',False,'coverage audit absent')
env=load_belfast(root); check('offline weather cache',not env['weather'].get('missing'),'ECMWF cache loaded without network')
check('offline wave cache',not env['marine']['waves'].get('missing'),'Copernicus cache loaded without network')
audit=audit_belfast_history(root); check('historical source slices',audit['all_wave_slices_valid'] and audit['all_era5_slices_valid'],'wave and ERA5 integrity checks')
check('demonstration contract',(root/'data/contracts/demo_weather_contract.txt').exists(),'labelled local demo contract')
engineering=all(x['status']=='PASS' for x in checks if x['check'] != 'source coverage gate')
coverage_ready=next(x['status']=='PASS' for x in checks if x['check']=='source coverage gate')
readiness={'ENGINEERING_READY':engineering,'DATA_CACHE_READY':all(x['status']=='PASS' for x in checks if 'cache' in x['check'] or 'historical' in x['check']),'SOURCE_COVERAGE_READY':coverage_ready,'DEMO_READY_NON_AUTHORIZING':engineering and coverage_ready,'OPERATIONAL_COMPLIANCE_READY':False}
result={'ready':readiness['DEMO_READY_NON_AUTHORIZING'],'readiness':readiness,'checks':checks,'operational_notice':'False by design: human review, deciding evidence, and accepted rules are outstanding.'}; print(json.dumps(result,indent=2)); raise SystemExit(0 if result['ready'] else 1)
