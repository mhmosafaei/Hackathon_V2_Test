"""Explicit zero depth is source-backed, never a missing-value sentinel."""
from copy import deepcopy
import json
import pytest
from src.environmental.sampling import source_depth
from src.environmental.models import EvaluationInput
from src.environmental.service import evaluate
from src.environmental.copernicus import worker
from tests.test_simple_environment import requirement,analysis,inputs
from tests.test_copernicus_current_oxygen_patch import oxygen_dataset,mock_client


def zero_requirement():
    return requirement('dissolved_oxygen',operator='<',threshold=6,unit='mg/L',
        depth_requirement='0 m below sea surface (sea-surface model level)',
        source_spans=[{'page':1,'quotation':'Oxygen at the sea-surface model level (0 m below sea surface). STOP condition: oxygen below 6 mg/L.'}])


def test_zero_survives_api_and_worker_persistence(tmp_path,monkeypatch):
    raw=zero_requirement();before=deepcopy(raw)
    calls=mock_client(monkeypatch,oxygen_dataset((0.,)))
    parsed=EvaluationInput.model_validate_json(inputs(depth=0).model_dump_json())
    result=evaluate(analysis(raw),parsed,tmp_path,transports={'COPERNICUS_MARINE':worker})
    row=result['requirements'][0]
    assert source_depth({**row,'routing':row['routing']})==(0.,None)
    assert len(calls)==1 and calls[0]['minimum_depth']==0
    assert row['request']['depth']==0 and row['evidence']['requested_depth_m']==0
    assert row['evidence']['selected_depth_m']==0
    saved=next(p for p in tmp_path.glob('*.json'))
    assert json.loads(saved.read_text())['request']['depth']==0
    assert raw==before


def test_absent_source_and_blank_input_still_block(tmp_path):
    r=zero_requirement();r['depth_requirement']=None
    result=evaluate(analysis(r),inputs(depth=None),tmp_path,transports={})
    assert 'Explicit depth required' in result['requirements'][0]['notes_for_evaluation']


def test_annotation_requires_source_support():
    r=zero_requirement();r['routing']={'preferred_provider':'COPERNICUS_MARINE'}
    r['source_spans']=[{'page':1,'quotation':'0 m below sea surface.'}]
    assert source_depth(r)[0] is None
