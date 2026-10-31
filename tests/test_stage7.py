from pathlib import Path
import pytest
from src.historical.audit import audit_belfast_history
from src.permit.coverage import coverage_gate
import json

@pytest.mark.source_backed
def test_cached_historical_source_slices_have_integrity_metadata():
    report=audit_belfast_history(Path('.'))
    assert report['all_wave_slices_valid'] and report['all_era5_slices_valid']
    assert all(x['masked_coastal_sources']=={'current':True,'sst':True} for x in report['years'])

@pytest.mark.source_backed
def test_reconciled_condition_20_is_covered_but_not_operationally_approved():
    inventory=json.loads(Path('cache/extractions/ml2025054/coverage_audit.json').read_text())['conditions']
    complete,gaps=coverage_gate(inventory)
    item=next(x for x in inventory if x['id']==20)
    assert complete and not gaps and item['status']=='CAPTURED'
