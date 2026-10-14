"""Offline checks for exact persisted analysis restoration."""
import json
from pathlib import Path

import pytest

from src.permit.persisted_analysis import load_persisted_analysis


HASH = 'a' * 64
RUN = 'b' * 32


def write_run(root: Path, *, run_id=RUN, document_hash=HASH, complete=True):
    folder = root / 'cache' / 'simple_analysis' / document_hash / run_id
    folder.mkdir(parents=True)
    (folder / 'manifest.json').write_text(json.dumps({
        'run_id': run_id, 'document_sha256': document_hash, 'status': 'COMPLETE'}))
    requirements = [{'condition_id': str(i), 'requirement_text': f'Requirement {i}',
                     'variable': 'visibility', 'canonical_variable': 'visibility',
                     'evidence_type': 'forecast', 'source_spans': [],
                     'source_verified': True} for i in range(20)]
    (folder / 'analysis.json').write_text(json.dumps({
        'analysis_id': run_id,
        'environmental_requirements': requirements,
        'environmental_extraction': {'complete': complete, 'missing_count': 0 if complete else 3,
                                     'candidate_conditions': [str(i) for i in range(20)]},
        'environmental_mapping': [{'condition_id': 'stale', 'routing': {'preferred_provider': 'UNAVAILABLE'}}]}),
        encoding='utf-8')
    return folder


def test_exact_restore_loads_all_records_without_writing(tmp_path):
    folder = write_run(tmp_path)
    original = (folder / 'analysis.json').read_bytes()
    restored = load_persisted_analysis(tmp_path, HASH, RUN)
    assert len(restored['environmental_requirements']) == 20
    assert restored['restored_from_persistence'] is True
    assert (folder / 'analysis.json').read_bytes() == original


def test_missing_or_mismatched_references_fail_explicitly(tmp_path):
    write_run(tmp_path)
    with pytest.raises(FileNotFoundError, match='PERSISTED_ANALYSIS_NOT_FOUND'):
        load_persisted_analysis(tmp_path, HASH, 'c' * 32)
    wrong_folder = tmp_path / 'cache' / 'simple_analysis' / ('c' * 64) / RUN
    wrong_folder.mkdir(parents=True)
    (wrong_folder / 'manifest.json').write_text(json.dumps({'run_id': RUN, 'document_sha256': HASH}))
    (wrong_folder / 'analysis.json').write_text(json.dumps({'analysis_id': RUN}))
    with pytest.raises(ValueError, match='DOCUMENT_HASH_MISMATCH'):
        load_persisted_analysis(tmp_path, 'c' * 64, RUN)


def test_incomplete_run_is_explicitly_marked(tmp_path):
    write_run(tmp_path, complete=False)
    restored = load_persisted_analysis(tmp_path, HASH, RUN)
    assert restored['restoration_status'] == 'INCOMPLETE'
    assert restored['missing_count'] == 3


def test_malformed_artifact_fails_explicitly(tmp_path):
    folder = write_run(tmp_path)
    (folder / 'analysis.json').write_text('[]')
    with pytest.raises(ValueError, match='MALFORMED_PERSISTED_ANALYSIS'):
        load_persisted_analysis(tmp_path, HASH, RUN)


def test_multiple_runs_require_exact_run_id(tmp_path):
    write_run(tmp_path)
    other = write_run(tmp_path, run_id='c' * 32)
    payload = json.loads((other / 'analysis.json').read_text())
    payload['environmental_requirements'] = [{
        'condition_id': 'only-other', 'requirement_text': 'Other requirement',
        'variable': 'visibility', 'canonical_variable': 'visibility',
        'evidence_type': 'forecast', 'source_spans': [], 'source_verified': True}]
    (other / 'analysis.json').write_text(json.dumps(payload))
    assert len(load_persisted_analysis(tmp_path, HASH, RUN)['environmental_requirements']) == 20
    assert load_persisted_analysis(tmp_path, HASH, 'c' * 32)['environmental_requirements'][0]['condition_id'] == 'only-other'


def test_restore_rebuilds_mapping_without_mutating_artifact(tmp_path):
    folder = write_run(tmp_path)
    original = (folder / 'analysis.json').read_bytes()
    restored = load_persisted_analysis(tmp_path, HASH, RUN)
    assert {row['condition_id'] for row in restored['environmental_mapping']} == {str(i) for i in range(20)}
    assert (folder / 'analysis.json').read_bytes() == original


def test_restore_preserves_raw_extra_but_excludes_it_from_mapping(tmp_path):
    folder = write_run(tmp_path)
    payload = json.loads((folder / 'analysis.json').read_text(encoding='utf-8'))
    payload['environmental_requirements'].append({
        'condition_id': '23', 'requirement_text': 'Select a point and period',
        'variable': 'fetch point', 'canonical_variable': 'environmental_fetch_point_operational_period',
        'evidence_type': 'manual', 'source_spans': [], 'source_verified': True})
    (folder / 'analysis.json').write_text(json.dumps(payload), encoding='utf-8')
    restored = load_persisted_analysis(tmp_path, HASH, RUN)
    assert any(row['condition_id'] == '23' for row in restored['environmental_requirements'])
    assert '23' not in {row['condition_id'] for row in restored['environmental_mapping']}


def _write_reconciliation_run(root: Path, *, source_text='--- PAGE 1 ---\nOther text\n--- PAGE 4 ---\nExact obligation text\n'):
    folder = write_run(root)
    payload = {
        'analysis_id': RUN,
        'environmental_extraction': {'complete': True, 'missing_count': 0,
                                     'candidate_conditions': ['31']},
        'conditions': [{'number': '31', 'source_page': 5,
                        'source_spans': [{'page': 5, 'quotation': 'Exact obligation text'}]}],
        'environmental_requirements': [{
            'condition_id': '31', 'requirement_text': 'Wind speed',
            'variable': 'wind_speed_10m', 'canonical_variable': 'wind_speed_10m',
            'evidence_type': 'forecast', 'source_page': 5,
            'source_spans': [{'page': 5, 'quotation': 'Exact obligation text'}],
            'source_verified': False, 'operator': '>', 'threshold': 12,
            'unit': 'm/s', 'temporal_requirement': None,
            'depth_requirement': None, 'geographic_scope': None,
            'explicit_requirement': True}],
    }
    (folder / 'analysis.json').write_text(json.dumps(payload), encoding='utf-8')
    (folder / 'input.txt').write_text(source_text, encoding='utf-8')
    return folder


def test_restore_reconciles_unique_quote_in_memory_and_preserves_artifact(tmp_path):
    folder = _write_reconciliation_run(tmp_path)
    original = (folder / 'analysis.json').read_bytes()
    restored = load_persisted_analysis(tmp_path, HASH, RUN)
    condition = restored['conditions'][0]
    requirement = restored['environmental_requirements'][0]
    assert condition['source_page'] == 4
    assert condition['model_declared_source_page'] == 5
    assert requirement['source_page'] == 4
    assert requirement['source_verified'] is True
    assert restored['environmental_mapping'][0]['source_verified'] is True
    assert (folder / 'analysis.json').read_bytes() == original


def test_restore_reconciliation_is_idempotent(tmp_path):
    _write_reconciliation_run(tmp_path)
    first = load_persisted_analysis(tmp_path, HASH, RUN)
    second = load_persisted_analysis(tmp_path, HASH, RUN)
    assert first['environmental_requirements'] == second['environmental_requirements']
    assert first['conditions'] == second['conditions']


def test_restore_missing_input_fails_closed(tmp_path):
    folder = _write_reconciliation_run(tmp_path)
    (folder / 'input.txt').unlink()
    restored = load_persisted_analysis(tmp_path, HASH, RUN)
    assert restored['restoration_source_verification'] == 'SOURCE_TEXT_UNAVAILABLE'
    assert restored['environmental_requirements'][0]['source_verified'] is False


def test_restore_duplicate_quote_remains_unverified(tmp_path):
    _write_reconciliation_run(tmp_path,
        source_text='--- PAGE 1 ---\nExact obligation text\n--- PAGE 4 ---\nExact obligation text\n')
    restored = load_persisted_analysis(tmp_path, HASH, RUN)
    assert restored['environmental_requirements'][0]['source_verified'] is False
    assert restored['environmental_requirements'][0]['source_reconciliation']['status'] == 'UNRESOLVED_NO_UNIQUE_MATCH'


def test_restore_absent_quote_remains_unverified(tmp_path):
    _write_reconciliation_run(tmp_path, source_text='--- PAGE 4 ---\nDifferent source text\n')
    restored = load_persisted_analysis(tmp_path, HASH, RUN)
    requirement = restored['environmental_requirements'][0]
    assert requirement['source_verified'] is False
    assert requirement['source_reconciliation']['status'] == 'UNRESOLVED_NO_UNIQUE_MATCH'


def test_restore_correct_page_is_unchanged(tmp_path):
    folder = _write_reconciliation_run(tmp_path, source_text='--- PAGE 5 ---\nExact obligation text\n')
    restored = load_persisted_analysis(tmp_path, HASH, RUN)
    requirement = restored['environmental_requirements'][0]
    assert requirement['source_page'] == 5
    assert requirement['source_spans'] == [{'page': 5, 'quotation': 'Exact obligation text'}]
    assert requirement['source_verified'] is True
    assert requirement.get('source_reconciliation') is None
