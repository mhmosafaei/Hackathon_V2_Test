"""Offline tests: the simple React route must never reach experimental engines."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient
import pymupdf
import pytest

from src.permit.simple_analysis import (ExtractionIncompleteError, analyze, response_schema, parse_response, PROMPT,
                                        reconcile_source_attribution, source_spans_verified)
from src.permit.simple_api import create_app
from src.permit.simple_fixture import mock_request
from src.documents.extractor import CandidateResponseError


def pdf_bytes(include_environmental=False):
    pdf = pymupdf.open()
    for page in range(6):
        text = 'Part 2 - Conditions\n' if page == 0 else ''
        if page == 0:
            text += 'Synthetic work point: WGS84 latitude 54.1 longitude -6.1.\n'
            if include_environmental:
                text += '1. Significant wave height shall not exceed 2.5 m during works.\n'
        text += '\n'.join(f'{i}. The operator shall keep records. Within 24 hours notify the authority.' for i in range(page*4+1, min(page*4+5, 23)))
        if not text: text = 'Appendix A: synthetic map context and geographic evidence for test only.'
        pdf.new_page().insert_text((50, 60), text)
    data = pdf.tobytes(); pdf.close(); return data


def sdk_response(payload, finish='stop', refusal=None):
    return NS(id='test-response', _request_id='test-request', usage=NS(prompt_tokens=100, completion_tokens=200),
        choices=[NS(finish_reason=finish, message=NS(content=json.dumps(payload), refusal=refusal))])


def test_simple_extraction_one_call_and_history_unchanged(tmp_path, monkeypatch):
    history = tmp_path / 'cache' / 'document_runs' / 'old'; history.mkdir(parents=True)
    (history / 'review.json').write_text('historical decisions')
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-4.1-mini')
    import src.permit.upload_flow as old
    monkeypatch.setattr(old, 'run_intelligence_pipeline', lambda *a, **k: pytest.fail('experimental chain reached'))
    calls = []
    def transport(packet): calls.append(packet); return mock_request(packet)
    result = analyze(pdf_bytes(), 'synthetic.pdf', tmp_path, transport=transport)
    assert len(calls) == 1 and len(calls[0]['pages']) == 6
    assert all(f'--- PAGE {i} ---' in calls[0]['text'] for i in range(1, 7))
    assert 'AUTHORITATIVE ENVIRONMENTAL CANDIDATES' in calls[0]['text']
    assert len(result['conditions']) == 22
    assert result['executable_rules'] == 0
    assert all(c['review_state'] == 'UNREVIEWED' and not c['executable'] for c in result['conditions'])
    assert (history / 'review.json').read_text() == 'historical decisions'
    assert len(list((tmp_path / 'cache/simple_analysis').glob('*/*/analysis.json'))) == 1
    assert all('candidate' not in f.name for f in (tmp_path / 'cache/simple_analysis').rglob('*'))
    manifest = json.loads(next((tmp_path / 'cache/simple_analysis').glob('*/*/manifest.json')).read_text())
    assert manifest['status'] == 'COMPLETE'
    assert manifest['missing_conditions'] == []


def test_parse_strict_schema_and_completion():
    from src.documents.pdf_parser import parse_pdf_bytes
    payload = mock_request({'pages': parse_pdf_bytes(pdf_bytes()).pages})
    parsed = parse_response(sdk_response(payload), 'gpt-4.1-mini')
    assert len(parsed['conditions']) == 22
    assert parsed['_response_metadata']['finish_reason'] == 'stop'
    for finish, refusal, category in [('length', None, 'INCOMPLETE_OUTPUT'), ('stop', 'no', 'REFUSED_OUTPUT')]:
        with pytest.raises(CandidateResponseError) as exc:
            parse_response(sdk_response(payload, finish, refusal), 'gpt-4.1-mini')
        assert exc.value.category == category
    malformed = sdk_response(payload); malformed.choices[0].message.content = '{'
    with pytest.raises(CandidateResponseError, match='INVALID_JSON'): parse_response(malformed, 'gpt-4.1-mini')
    payload['conditions'][0]['phase'] = 'WORK_AUTHORIZED'
    with pytest.raises(CandidateResponseError, match='SCHEMA_VIOLATION'): parse_response(sdk_response(payload), 'gpt-4.1-mini')


def test_api_restart_clean_and_explicit_dispatch(tmp_path):
    calls = []
    def transport(packet): calls.append(1); return mock_request(packet)
    client = TestClient(create_app(tmp_path, transport=transport))
    session = client.get('/api/session').json()
    assert 'analysis' not in session and calls == []
    headers = {'x-session-id': session['boot_id'], 'x-filename': 'synthetic.pdf'}
    response = client.post('/api/analyze', content=pdf_bytes(), headers=headers)
    assert response.status_code == 200 and len(response.json()['conditions']) == 22
    files = {str(p): p.read_bytes() for p in (tmp_path / 'cache').rglob('*') if p.is_file()}
    restarted = TestClient(create_app(tmp_path, transport=transport))
    assert restarted.get('/api/session').json()['boot_id'] != session['boot_id']
    assert restarted.post('/api/analyze', content=pdf_bytes(), headers=headers).status_code == 409
    assert calls == [1]
    assert files == {str(p): p.read_bytes() for p in (tmp_path / 'cache').rglob('*') if p.is_file()}


def test_missing_sources_visible_and_quotes_not_promoted(tmp_path):
    def transport(packet):
        result = mock_request(packet); result['conditions'] = result['conditions'][1:]
        result['conditions'][0]['source_spans'] = [{'page': 99, 'quotation': 'invented'}]
        return result
    result = analyze(pdf_bytes(), 'synthetic.pdf', tmp_path, transport=transport)
    assert not result['conditions'][0]['source_verified']
    assert any('condition 1 ' in w for w in result['warnings'])


def test_environmental_incompleteness_fails_closed_and_preserves_audit(tmp_path, monkeypatch):
    import src.permit.simple_analysis as service
    monkeypatch.setattr(service, 'identify_environmental_source_candidates', lambda pages: [{
        'source_record_id': 'environmental-p1-99', 'condition_id': '99', 'source_page': 1,
        'source_location': 'PDF page 1, condition 99', 'source_text': '99. Wave evidence shall be reviewed.',
        'source_spans': [{'page': 1, 'quotation': '99. Wave evidence shall be reviewed.'}],
    }])
    calls = []
    def transport(packet):
        calls.append(packet)
        return mock_request(packet)
    with pytest.raises(ExtractionIncompleteError):
        analyze(pdf_bytes(), 'synthetic.pdf', tmp_path, transport=transport)
    folder = next((tmp_path / 'cache/simple_analysis').glob('*/*'))
    manifest = json.loads((folder / 'manifest.json').read_text())
    payload = json.loads((folder / 'analysis.json').read_text())
    assert len(calls) == 1
    assert manifest['status'] == 'EXTRACTION_INCOMPLETE'
    assert manifest['environmental_extraction_complete'] is False
    assert payload['environmental_extraction']['missing_conditions'] == ['99']
    assert (folder / 'response.json').exists()


def test_single_pass_rejects_unsafe_input_and_preserves_failures(tmp_path):
    with pytest.raises(ValueError, match='INVALID_PDF'): analyze(b'not a PDF', 'test.pdf', tmp_path, transport=mock_request)
    calls = []
    def fail(packet): calls.append(1); raise RuntimeError('fake failure')
    with pytest.raises(RuntimeError): analyze(pdf_bytes(), 'test.pdf', tmp_path, transport=fail)
    manifest = json.loads(next((tmp_path/'cache/simple_analysis').glob('*/*/manifest.json')).read_text())
    assert manifest['status'] == 'FAILED' and calls == [1] and manifest['executable_rules'] == 0


def test_duplicate_numbers_fail_without_silent_dropping(tmp_path):
    def duplicate(packet):
        result = mock_request(packet); result['conditions'].append(deepcopy(result['conditions'][0])); return result
    with pytest.raises(ValueError, match='DUPLICATE_CONDITION_NUMBER'):
        analyze(pdf_bytes(), 'test.pdf', tmp_path, transport=duplicate)


def test_api_errors_are_generic_and_cross_origin_blocked(tmp_path):
    def fail(packet): raise RuntimeError('private SDK detail must not leak')
    client = TestClient(create_app(tmp_path, transport=fail))
    session = client.get('/api/session').json()
    headers = {'x-session-id': session['boot_id'], 'x-filename': 'test.pdf'}
    response = client.post('/api/analyze', content=pdf_bytes(), headers=headers)
    assert response.status_code == 422 and 'private SDK' not in response.text
    assert client.post('/api/analyze', content=pdf_bytes(), headers={**headers, 'origin': 'https://unrelated.example'}).status_code == 403


def test_live_adapter_mocked_sdk_one_strict_call_and_budget(tmp_path, monkeypatch):
    import src.permit.simple_analysis as service
    from src.documents.pdf_parser import parse_pdf_bytes
    payload = mock_request({'pages': parse_pdf_bytes(pdf_bytes()).pages})
    response = sdk_response(payload)
    response.model_dump_json = lambda: json.dumps({'id': response.id, 'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(payload)}}]})
    calls = []
    class Client:
        def __init__(self): self.chat = NS(completions=NS(create=self.create))
        def create(self, **kwargs): calls.append(kwargs); return response
        def close(self): pass
    def factory(**kwargs):
        assert kwargs == {'timeout': 120.0, 'max_retries': 0}
        return Client()
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-dummy-not-a-secret')
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-4.1-mini')
    monkeypatch.setattr(service, 'direct_openai_client', factory)
    result = analyze(pdf_bytes(), 'test.pdf', tmp_path)
    assert len(calls) == 1 and len(result['conditions']) == 22
    assert calls[0]['response_format']['json_schema']['strict'] is True
    assert calls[0]['max_completion_tokens'] == 16000
    assert 'temperature' not in calls[0]
    assert calls[0]['messages'][0]['content'] == PROMPT
    assert '--- PAGE 6 ---' in calls[0]['messages'][1]['content']
    assert 'AUTHORITATIVE ENVIRONMENTAL CANDIDATES' in calls[0]['messages'][1]['content']
    ledger = json.loads(next((tmp_path/'cache/simple_analysis').glob('*/*/dispatch_ledger.json')).read_text())
    assert ledger['request_cap'] == 5 and ledger['budget_cap_usd'] == .15
    assert len(ledger['dispatches']) == 1 and ledger['dispatches'][0]['status'] == 'SUCCEEDED'
    assert 'offline-dummy-not-a-secret' not in ''.join(p.read_text(errors='ignore') for p in tmp_path.rglob('*.json'))


def test_incomplete_output_raw_response_preserved_no_retry(tmp_path, monkeypatch):
    import src.permit.simple_analysis as service
    response = sdk_response({}, finish='length')
    response.model_dump_json = lambda: '{"id":"test-response","finish_reason":"length"}'
    calls = []
    class Client:
        def __init__(self): self.chat = NS(completions=NS(create=self.create))
        def create(self, **kwargs): calls.append(1); return response
        def close(self): pass
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-dummy')
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-4.1-mini')
    monkeypatch.setattr(service, 'direct_openai_client', lambda **kwargs: Client())
    with pytest.raises(CandidateResponseError, match='INCOMPLETE_OUTPUT'):
        analyze(pdf_bytes(), 'test.pdf', tmp_path)
    ledger = json.loads(next((tmp_path/'cache/simple_analysis').glob('*/*/dispatch_ledger.json')).read_text())
    assert len(calls) == 1
    assert ledger['dispatches'][0]['status'] == 'COMPLETED_INVALID_RESPONSE'
    assert ledger['dispatches'][0]['reserved_cost_usd'] > 0
    assert next((tmp_path/'cache/simple_analysis').glob('*/*/response.json')).exists()
    assert not list((tmp_path/'cache/simple_analysis').glob('*/*/analysis.json'))


def test_large_text_is_not_truncated_or_dispatched(tmp_path, monkeypatch):
    import src.permit.simple_analysis as service
    from src.documents.pdf_parser import PdfPage
    monkeypatch.setattr(service, 'parse_pdf_bytes', lambda content: NS(needs_ocr=False, pages=[PdfPage(1, 'A'*61000)]))
    with pytest.raises(ValueError, match='DOCUMENT_TOO_LARGE_FOR_SINGLE_PASS'):
        analyze(b'%PDF-large', 'test.pdf', tmp_path, transport=lambda packet: pytest.fail('must not dispatch'))
    assert not (tmp_path/'cache').exists()


def test_geofence_schema_and_single_pass_preserve_source_and_review(tmp_path):
    from src.documents.pdf_parser import PdfPage
    sentence = 'Disposal is permitted only within Test Zone, radius 0.5 NM.'
    geofence = mock_request({'pages': [PdfPage(3, sentence)]})['geofences'][0]
    assert geofence['source_pages'] == [3]
    assert geofence['coordinates_or_boundary'] == 'radius 0.5 NM'
    def transport(packet):
        result = mock_request(packet)
        result['geofences'] = [{**geofence, 'source_pages': [2], 'source_spans': [{'page': 2, 'quotation': sentence}]}]
        return result
    pdf = pymupdf.open(stream=pdf_bytes(), filetype='pdf')
    pdf[1].insert_text((50, 400), sentence)
    content = pdf.tobytes(); pdf.close()
    result = analyze(content, 'test.pdf', tmp_path, transport=transport)
    saved = result['geofences'][0]
    assert saved['source_verified'] and saved['review_state'] == 'UNREVIEWED' and not saved['executable']
    assert saved['source_pages'] == [2] and saved['coordinates_or_boundary'] == 'radius 0.5 NM'
    # Verification means source quotation presence, not semantic boundary approval.
    assert result['executable_rules'] == 0


def test_geofence_invalid_type_and_source_page_conflict(tmp_path):
    def transport(packet):
        result = mock_request(packet)
        result['geofences'] = [{'name': 'Example route', 'description': 'Synthetic route restriction',
            'type': 'route', 'coordinates_or_boundary': None, 'restriction': 'Works only on the approved route.',
            'source_pages': [99], 'source_spans': [{'page': 1, 'quotation': packet['pages'][0].text.strip()}]}]
        return result
    result = analyze(pdf_bytes(), 'test.pdf', tmp_path, transport=transport)
    assert not result['geofences'][0]['source_verified']
    payload = transport({'pages': [NS(text='source')]})
    payload['geofences'][0]['type'] = 'inferred_nearby_town'
    with pytest.raises(CandidateResponseError, match='SCHEMA_VIOLATION'):
        parse_response(sdk_response(payload), 'gpt-4.1-mini')


def test_location_only_mock_has_no_geofences_and_prompt_prohibits_inference():
    from src.documents.pdf_parser import PdfPage
    result = mock_request({'pages': [PdfPage(1, 'Works are located near Example Town.')]})
    assert result['geofences'] == []
    assert 'mere location mention' in PROMPT
    assert 'Do not infer coordinates' in PROMPT


def test_unique_source_quote_page_is_reconciled_with_original_attribution_retained():
    record = {'source_page': 5, 'source_spans': [{'page': 5, 'quotation': 'Wind speed greater than 12 m/s.'}]}
    reconcile_source_attribution(record, {4: 'Wind speed greater than 12 m/s.', 5: 'Other page text'})
    assert record['source_page'] == 4
    assert record['model_declared_source_page'] == 5
    assert record['reconciled_source_page'] == 4
    assert record['source_spans'][0]['page'] == 4
    assert record['source_spans'][0]['model_declared_page'] == 5
    assert record['source_spans'][0]['reconciled_physical_page'] == 4
    assert record['source_reconciliation']['status'] == 'UNIQUE_EXACT_MATCH'
    assert source_spans_verified(record['source_spans'], {4: 'wind speed greater than 12 m/s.', 5: 'other page text'})


def test_source_quote_without_unique_page_remains_unresolved():
    absent = {'source_page': 5, 'source_spans': [{'page': 5, 'quotation': 'Absent quote'}]}
    reconcile_source_attribution(absent, {4: 'Different text', 5: 'Other text'})
    assert absent['source_page'] == 5 and absent['source_spans'][0]['page'] == 5
    assert absent['source_reconciliation']['status'] == 'UNRESOLVED_NO_UNIQUE_MATCH'
    duplicate = {'source_page': 5, 'source_spans': [{'page': 5, 'quotation': 'Repeated quote'}]}
    reconcile_source_attribution(duplicate, {4: 'Repeated quote', 5: 'Repeated quote'})
    assert duplicate['source_page'] == 5 and duplicate['source_spans'][0]['page'] == 5
    assert duplicate['source_reconciliation']['status'] == 'UNRESOLVED_NO_UNIQUE_MATCH'


def test_correct_source_page_is_unchanged_without_reconciliation():
    record = {'source_page': 4, 'source_spans': [{'page': 4, 'quotation': 'Correct quote'}]}
    reconcile_source_attribution(record, {4: 'Correct quote', 5: 'Other text'})
    assert record['source_page'] == 4 and record['source_spans'][0] == {'page': 4, 'quotation': 'Correct quote'}
    assert 'source_reconciliation' not in record


def test_correctly_attributed_page_records_remain_unchanged_for_multiple_requirements():
    records = [
        {'source_page': 5, 'source_spans': [{'page': 5, 'quotation': 'Wind direction.'}]},
        {'source_page': 5, 'source_spans': [{'page': 5, 'quotation': 'Wind gust.'}]},
        {'source_page': 5, 'source_spans': [{'page': 5, 'quotation': 'Air temperature.'}]},
    ]
    for record in records:
        original = deepcopy(record)
        reconcile_source_attribution(record, {4: 'Other page', 5: 'Wind direction. Wind gust. Air temperature.'})
        assert record == original


def test_geofence_boundary_not_in_source_remains_unverified(tmp_path):
    def transport(packet):
        result = mock_request(packet)
        result['geofences'] = [{'name': 'Unresolved test boundary', 'description': 'Requires source review',
            'type': 'restricted_segment', 'coordinates_or_boundary': 'KP 12.3 to KP 14.5',
            'restriction': 'Test restriction', 'source_pages': [1],
            'source_spans': [{'page': 1, 'quotation': packet['pages'][0].text.strip()}]}]
        return result
    result = analyze(pdf_bytes(), 'test.pdf', tmp_path, transport=transport)
    assert not result['geofences'][0]['source_verified']
    assert result['geofences'][0]['coordinates_or_boundary'] == 'KP 12.3 to KP 14.5'
    assert result['geofences'][0]['review_state'] == 'UNREVIEWED'
    assert not result['geofences'][0]['executable']
