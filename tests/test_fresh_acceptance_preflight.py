"""Offline checks of the production capped upload path; never call OpenAI."""
import json

import pymupdf

from src.documents import ai_first
from src.documents.ai_first import document_identity
from src.permit import upload_flow
from src.intelligence.contracts import CanonicalAnalysis
from src.intelligence.service import mock_stage_transport


def test_fresh_full_upload_dispatches_only_candidates_and_normalizes_locally(monkeypatch, tmp_path):
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-test-only')
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-4.1-mini')
    pdf = pymupdf.open()
    for number in range(1, 7):
        heading = 'Part 2 - Conditions\n' if number == 1 else ''
        pdf.new_page().insert_text((72, 72), heading + f'{number}. The operator shall retain notification records.')
    content = pdf.tobytes()
    pdf.close()
    calls = []

    def batches(pages, max_chars=12000):
        return [{'batch': number, 'primary_pages': [p.page_number for p in group],
                 'context_pages': [], 'pages': [{'page_number': p.page_number, 'text': p.text} for p in group]}
                for number, group in enumerate([pages[:4], pages[4:]], 1)]

    def candidates(packet):
        calls.append(('candidate', packet['batch']))
        assert packet['max_output_tokens'] == 8000
        return {'candidates': [{'source_quotation': next(line for line in p['text'].splitlines() if 'operator' in line), 'page_number': p['page_number'],
                                'section': str(p['page_number']), 'obligation_type': 'Reporting obligation',
                                'linked_references': [], 'ambiguity': []} for p in packet['pages']],
                '_response_metadata': {'input_tokens': 100, 'output_tokens': 100}}

    def stages(stage, packet, schema):
        calls.append((stage, None))
        assert packet['max_output_tokens'] == 6000
        if stage == 'stage1':
            assert len(packet['aggregate']['candidates']) == 6
            assert packet['aggregate']['source_inventory']
        elif stage == 'stage2':
            assert len(packet['requirements']) == 6
            assert all(r['source_ids'] for r in packet['requirements'])
        else:
            assert len(packet['requirements']) == 6
            assert len(packet['operational_assessments']) == 6
        response = mock_stage_transport(stage, packet, schema)
        response['_response_metadata'] = {'input_tokens': 100, 'output_tokens': 100}
        return response

    monkeypatch.setattr(ai_first, 'build_batches', batches)
    monkeypatch.setattr(upload_flow, 'build_batches', batches)
    monkeypatch.setattr(upload_flow, 'openai_candidate_request', candidates)
    monkeypatch.setattr(upload_flow, 'openai_stage_transport', stages)
    monkeypatch.setattr(upload_flow, 'pre_dispatch_runtime_check', lambda: {'ready': True})
    # A failed older namespace exists, but no part of it may be read or changed.
    old_id = 'acceptance-offline-historical'
    old = tmp_path / 'cache/document_runs' / document_identity(content, 'gpt-4.1-mini', old_id)
    old.mkdir(parents=True)
    old_ledger = old / 'live_acceptance_dispatch_ledger.json'
    old_ledger.write_text(json.dumps({'run_id': old_id, 'dispatches': [{'status': 'OUTCOME_UNKNOWN'}]}))
    historical = old_ledger.read_bytes()

    result = upload_flow.analyze_ai_first_upload(tmp_path, 'fixture.pdf', content,
        request=candidates, analysis_run_id='acceptance-offline-fresh', live_acceptance=True,
        diagnostic_candidate_batch_only=False)
    assert calls == [('candidate', 1), ('candidate', 2)]
    assert result['run_identity'] != old.name
    assert old_ledger.read_bytes() == historical
    ledger = json.loads((tmp_path / 'cache/document_runs' / result['run_identity'] / 'live_acceptance_dispatch_ledger.json').read_text())
    assert ledger['request_cap'] == 5 and ledger['budget_cap_usd'] == .15
    assert len(ledger['dispatches']) == 2
    analysis = CanonicalAnalysis.model_validate_json(__import__('pathlib').Path(result['intelligence_analysis']).read_text())
    assert len(analysis.requirements) == 6
    assert all(r.human_review == 'UNREVIEWED' for r in analysis.requirements)
    assert all(r.source_ids for r in analysis.requirements)
    assert analysis.work_windows.status == 'NOT_EVALUATED'
    # Rerenders/resume reuse only this run's checkpoints, with no new transport calls.
    resumed = upload_flow.analyze_ai_first_upload(tmp_path, 'fixture.pdf', content,
        request=candidates, analysis_run_id='acceptance-offline-fresh', live_acceptance=True)
    assert resumed['run_identity'] == result['run_identity']
    assert len(calls) == 2
