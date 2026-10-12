import json
from pathlib import Path

import pymupdf

from src.documents import ai_first
from src.permit import upload_flow


def _pdf_bytes() -> bytes:
    document = pymupdf.open()
    for number in range(1, 5):
        page = document.new_page()
        page.insert_text((72, 72), f"{number}. The operator shall retain source evidence. " + ("x" * 6_100))
    data = document.tobytes()
    document.close()
    return data


def test_live_diagnostic_dispatches_only_first_candidate_batch(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    calls = []

    def response(packet):
        calls.append(packet["batch"])
        return {"candidates": [], "_response_metadata": {"input_tokens": 10, "output_tokens": 10}}

    monkeypatch.setattr(upload_flow, "openai_candidate_request", response)
    monkeypatch.setattr(upload_flow, "pre_dispatch_runtime_check", lambda: {"ready": True, "response_parser_version": "candidate-response-parser-v2"})
    def two_batches(pages, max_chars=12_000):
        return [
            {"batch": 1, "primary_pages": [pages[0].page_number], "context_pages": [], "pages": [{"page_number": pages[0].page_number, "text": pages[0].text}]},
            {"batch": 2, "primary_pages": [pages[1].page_number], "context_pages": [], "pages": [{"page_number": pages[1].page_number, "text": pages[1].text}]},
        ]
    monkeypatch.setattr(upload_flow, "build_batches", two_batches)
    monkeypatch.setattr(ai_first, "build_batches", two_batches)
    result = upload_flow.analyze_ai_first_upload(
        tmp_path, "fixture.pdf", _pdf_bytes(), request=response,
        analysis_run_id="diagnostic-test-run", live_acceptance=True,
        diagnostic_candidate_batch_only=True,
    )
    assert calls == [1]
    assert result["state"] == "DIAGNOSTIC_COMPLETE"
    assert result["diagnostic"]["downstream_stages_dispatched"] is False
    ledger = json.loads(Path(result["dispatch_ledger"]).read_text(encoding="utf-8"))
    assert ledger["request_cap"] == 1
    assert [event["dispatch_id"] for event in ledger["dispatches"]] == ["candidate-batch-1"]
    assert ledger["dispatches"][0]["output_token_ceiling"] == 3_000


def test_full_acceptance_reservation_with_five_thousand_candidate_ceiling_stays_under_cap():
    from src.documents.live_budget import reserve

    # Two candidates plus stage 1–3, using the configured conservative
    # character-to-token estimate and no assumptions about actual usage.
    worst_case = (
        reserve(32_000, 0, 8_000) * 2
        + reserve(120_000, 0, 6_000)
        + reserve(100_000, 0, 6_000)
        + reserve(120_000, 0, 6_000)
    )
    assert worst_case < .15
    assert round(worst_case, 4) == .1352
