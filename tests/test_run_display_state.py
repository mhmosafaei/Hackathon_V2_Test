import json

from streamlit.testing.v1 import AppTest

from src.permit.document_store import analysis_result_notice, available_documents, load_document


def test_failed_diagnostic_is_an_error_in_streamlit():
    app = AppTest.from_string('''
import streamlit as st
from src.permit.document_store import analysis_result_notice
result = {'pages': 6, 'conditions': 0, 'state': 'DIAGNOSTIC_FAILED',
          'diagnostic': {'batch': {'error': 'prior OUTCOME_UNKNOWN dispatch'}}}
kind, message = analysis_result_notice(result)
getattr(st, kind)(message)
''').run()
    assert not app.exception
    assert not app.success
    assert 'prior OUTCOME_UNKNOWN' in app.error[0].value


def test_diagnostic_success_does_not_claim_full_analysis():
    kind, message = analysis_result_notice({'pages': 6, 'conditions': 3, 'state': 'DIAGNOSTIC_COMPLETE'})
    assert kind == 'warning'
    assert 'were not run' in message


def test_same_document_runs_have_distinct_labels_and_isolated_records(tmp_path):
    for name, state, candidates in [('old-run', 'REVIEW_REQUIRED', [{'candidate_id': 'a'}]), ('failed-run', 'FAILED', [])]:
        folder = tmp_path / 'cache/document_runs' / name
        folder.mkdir(parents=True)
        (folder / 'candidate_aggregate.json').write_text(json.dumps({
            'document_id': 'same-source', 'candidates': candidates,
            'coverage': {'physical_pages': 6, 'processing_complete': state != 'FAILED'},
        }))
        (folder / 'manifest.json').write_text(json.dumps({
            'analysis_run_id': name, 'document_state': state,
            'batches': {'1': {'error': 'prior OUTCOME_UNKNOWN'}} if state == 'FAILED' else {},
        }))
        if state == 'FAILED':
            (folder / 'live_acceptance_dispatch_ledger.json').write_text(json.dumps({
                'dispatches': [{'status': 'OUTCOME_UNKNOWN', 'reserved_cost_usd': .01}]
            }))
    before = {p: p.read_bytes() for p in tmp_path.rglob('*.json')}
    docs = available_documents(tmp_path)
    assert docs['old-run']['title'] != docs['failed-run']['title']
    assert 'FAILED' in docs['failed-run']['title']
    spec, records, coverage = load_document(tmp_path, 'failed-run')
    assert records == [] and not coverage['processing_complete']
    assert spec['outcome_unknown'] and spec['dispatch_count'] == 1
    assert load_document(tmp_path, 'old-run')[1] == [{'candidate_id': 'a'}]
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*.json')}
