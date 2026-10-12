import json

import pytest

from src.documents.ai_first import run_document_pipeline
from src.documents.pdf_parser import PdfPage
from src import runtime


def test_runtime_preflight_reports_loaded_safety_contract():
    result = runtime.pre_dispatch_runtime_check()
    assert result["ready"] is True
    assert result["response_parser_version"] == "candidate-response-parser-v2"
    assert result["checks"]["candidate_finish_reason_before_parse"] is True
    assert result["checks"]["five_request_budget_cap"] is True
    assert result["checks"]["failure_stops_dispatch"] is True


def test_runtime_preflight_fails_closed_when_loaded_candidate_parser_is_old(monkeypatch):
    from src.documents import extractor

    monkeypatch.setattr(extractor, "RESPONSE_PARSER_VERSION", "old-parser")
    with pytest.raises(RuntimeError, match="STALE_RUNTIME"):
        runtime.pre_dispatch_runtime_check()


def test_manifest_persists_runtime_identity_for_new_run(tmp_path):
    page = PdfPage(1, "1. The operator shall notify the authority.")
    run_document_pipeline(
        tmp_path, "doc", [page],
        lambda packet: {"candidates": []}, model="mock-model",
        analysis_run_id="acceptance-runtime-test",
        runtime={"build_fingerprint": "test-fingerprint", "response_parser_version": "candidate-response-parser-v2"},
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["runtime"]["build_fingerprint"] == "test-fingerprint"
