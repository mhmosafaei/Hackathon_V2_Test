"""Mocked end-to-end coverage tests; no document content leaves the test process."""
import json
import shutil
from pathlib import Path
import pytest

import fitz

from src.permit.orchestrator import identity
from src.permit.upload_flow import analyze_upload, analyze_ai_first_upload, local_mock_candidate_request
from src.documents.ai_first import document_identity


def _fixture_pdf() -> bytes:
    document = fitz.open()
    for text in (
        "Part 1 - Particulars\nTest marine works permit",
        "Part 2 - Conditions\n1. Notify the Authority before works commence.\n2. Operations must remain within the marked boundary.",
        "Continuation of condition 2 applies at all times.\n3. Wave height must not exceed 2 m.",
        "NOTES\nEnd of licence.",
    ):
        page = document.new_page()
        page.insert_text((72, 72), text)
    return document.tobytes()


def _condition(condition_id: str, source_text: str) -> dict:
    return {
        "condition_id": condition_id,
        "document_type": "PERMIT",
        "document_id": "mock-permit",
        "source_text": source_text,
        "page_number": 999,  # recovery must replace this with trusted page provenance
        "condition_type": "REPORTING_DEADLINE" if condition_id == "1" else "GEOFENCE" if condition_id == "2" else "INSTANT_THRESHOLD",
        "variable": "wave_height" if condition_id == "3" else None,
        "operator": "<=" if condition_id == "3" else None,
        "threshold": 2.0 if condition_id == "3" else None,
        "unit": "m" if condition_id == "3" else None,
        "evidence_requirements": ["AUTHORITY_APPROVAL"] if condition_id == "1" else ["GIS"] if condition_id == "2" else ["LOCAL_SENSOR"],
        "required_action": "NOTIFY" if condition_id == "1" else "NONE",
        "confidence": "HIGH",
        "review_required": True,
        "automation_status": "MANUAL_INPUT_REQUIRED" if condition_id == "1" else "NOT_EVALUABLE",
    }


def test_mocked_upload_runs_to_coverage_and_resumes_without_repeat_requests(monkeypatch):
    """The upload service checkpoints pages and retries the coverage stage offline."""
    content = _fixture_pdf()
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-secret")
    monkeypatch.setenv("OPENAI_MODEL", "mock-model")
    calls = []

    def response(page_text: str, _document_id: str):
        calls.append(page_text)
        if "Notify the Authority" in page_text:
            return {"conditions": [
                _condition("1", "1. Notify the Authority before works commence."),
                _condition("2", "2. Operations must remain within the marked boundary."),
            ]}
        return {"conditions": [_condition("3", "3. Wave height must not exceed 2 m.")]}

    # The project cache is already writable in the desktop sandbox; isolate this
    # deterministic fixture under its own model/document identity and remove it.
    root = Path.cwd()
    folder = root / "cache" / "document_runs" / identity(content, "mock-model")
    try:
        result = analyze_upload(root, "sanitized-fixture.pdf", content, request=response)
        assert result["state"] == "COVERAGE_COMPLETE"
        assert result["condition_pages"] == [2, 3]
        assert result["coverage"]["summary"]["CAPTURED"] == 3
        assert len(calls) == 2

        manifest = json.loads((folder / "manifest.json").read_text())
        assert {entry["status"] for entry in manifest["pages"].values()} == {"COMPLETE"}
        assert (folder / "coverage_audit.json").exists()
        assert (folder / "recovery_aggregate.json").exists()

        # A restart uses the independent page checkpoints: it must not make any model call.
        def must_not_call(*_args):
            raise AssertionError("completed page was sent to the model again")

        resumed = analyze_upload(root, "sanitized-fixture.pdf", content, request=must_not_call)
        assert resumed["state"] == "COVERAGE_COMPLETE"
        assert resumed["conditions"] == 3
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_interrupted_upload_preserves_complete_page_and_retries_only_failure(monkeypatch):
    content = _fixture_pdf(); monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-secret"); monkeypatch.setenv("OPENAI_MODEL", "mock-model")
    root = Path.cwd(); folder = root / "cache" / "document_runs" / identity(content, "mock-model")
    def first_attempt(text, _document_id):
        if "Wave height" in text: raise TimeoutError("mock timeout")
        return {"conditions":[_condition("1", "1. Notify the Authority before works commence."), _condition("2", "2. Operations must remain within the marked boundary.")]}
    try:
        interrupted=analyze_upload(root, "sanitized-fixture.pdf", content, request=first_attempt)
        assert interrupted["state"] == "COVERAGE_INCOMPLETE"
        manifest=json.loads((folder / "manifest.json").read_text())
        assert manifest["pages"]["2"]["status"] == "COMPLETE"
        assert manifest["pages"]["3"]["status"] == "FAILED"
        calls=[]
        def resume(text, _document_id):
            calls.append(text)
            return {"conditions":[_condition("3", "3. Wave height must not exceed 2 m.")]}
        completed=analyze_upload(root, "sanitized-fixture.pdf", content, request=resume)
        assert completed["state"] == "COVERAGE_COMPLETE"
        assert len(calls) == 1 and "Wave height" in calls[0]
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_new_upload_defaults_to_full_document_ai_first_candidate_workflow(monkeypatch):
    content = _fixture_pdf()
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-secret")
    monkeypatch.setenv("OPENAI_MODEL", "mock-model")
    root = Path.cwd(); folder = root / "cache" / "document_runs" / document_identity(content, "mock-model")
    try:
        result = analyze_ai_first_upload(root, "unfamiliar-contract.pdf", content, request=local_mock_candidate_request)
        assert result['pages'] == 4
        assert result['condition_pages'] == [1, 2, 3, 4]
        assert result['conditions'] == 3
        assert result['coverage']['processing_complete'] is True
        assert result['coverage']['semantic_coverage_complete'] is False
        payload=json.loads((folder/'candidate_aggregate.json').read_text())
        assert {c['state'] for c in payload['candidates']} == {'SOURCE_VERIFIED'}
        assert payload['source_inventory']
        assert all('source_record_ids' in c for c in payload['candidates'])
        assert not (folder/'recovery_aggregate.json').exists()
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_fresh_run_ids_keep_mocked_document_runs_isolated(monkeypatch):
    content = _fixture_pdf(); monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-secret"); monkeypatch.setenv("OPENAI_MODEL", "mock-model")
    root = Path.cwd()
    folders = [root / 'cache' / 'document_runs' / document_identity(content, 'mock-model', run_id) for run_id in ('fresh-run-one', 'fresh-run-two')]
    try:
        one = analyze_ai_first_upload(root, 'fixture.pdf', content, request=local_mock_candidate_request, analysis_run_id='fresh-run-one')
        two = analyze_ai_first_upload(root, 'fixture.pdf', content, request=local_mock_candidate_request, analysis_run_id='fresh-run-two')
        assert one['run_identity'] != two['run_identity']
        assert all((folder / 'candidate_aggregate.json').exists() for folder in folders)
    finally:
        for folder in folders: shutil.rmtree(folder, ignore_errors=True)


def test_live_acceptance_profile_refuses_wrong_candidate_batch_plan_without_api(monkeypatch):
    content = _fixture_pdf(); monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-secret"); monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    root = Path.cwd(); run_id = 'acceptance-refusal-test'
    folder = root / 'cache' / 'document_runs' / document_identity(content, 'gpt-4.1-mini', run_id)
    try:
        # This fixture is one candidate batch; the live-acceptance profile
        # requires exactly two and aborts before a request transport exists.
        with pytest.raises(RuntimeError, match='exactly two candidate batches'):
            analyze_ai_first_upload(root, 'fixture.pdf', content, analysis_run_id=run_id, live_acceptance=True)
        assert not (folder / 'live_acceptance_dispatch_ledger.json').exists()
    finally:
        shutil.rmtree(folder, ignore_errors=True)
