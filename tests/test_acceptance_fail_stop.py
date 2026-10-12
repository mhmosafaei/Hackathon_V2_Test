from pathlib import Path
from uuid import uuid4

import pymupdf
import pytest

from src.documents import ai_first
from src.documents.ai_first import run_document_pipeline
from src.documents.live_budget import AcceptanceDispatchLedger
from src.documents.pdf_parser import PdfPage
from src.permit import upload_flow


def test_first_unknown_candidate_prevents_second_candidate_dispatch():
    tmp_path = Path('tmp') / f'acceptance-fail-stop-{uuid4().hex}'
    tmp_path.mkdir(parents=True)
    pages = [
        PdfPage(page_number=1, text="A" * 12_000),
        PdfPage(page_number=2, text="B" * 12_000),
    ]
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "1. Fixture source")
    document.save(tmp_path / "source.pdf")
    document.close()
    ledger = AcceptanceDispatchLedger(tmp_path / "live_acceptance_dispatch_ledger.json", run_id="acceptance-test-0002", model="gpt-4.1-mini")
    calls: list[int] = []

    def transport(packet: dict):
        return ledger.call(
            dispatch_id=f"candidate-{packet['batch']}", stage="CANDIDATE_EXTRACTION",
            input_text=packet["prompt"], input_token_ceiling=30_000, output_token_ceiling=100,
            invoke=lambda: _fail(packet["batch"], calls),
        )

    run_document_pipeline(tmp_path, "fixture", pages, transport, model="gpt-4.1-mini", max_chars=12_000)
    assert calls == [1]
    assert len(ledger.dispatches) == 1
    assert ledger.dispatches[0]["status"] == "OUTCOME_UNKNOWN"


def test_second_unknown_candidate_blocks_intelligence_after_restart():
    root = Path('tmp') / f'acceptance-second-failure-{uuid4().hex}'
    root.mkdir(parents=True)
    ledger = AcceptanceDispatchLedger(root / 'live_acceptance_dispatch_ledger.json', run_id='acceptance-test-0003', model='gpt-4.1-mini')
    ledger.call(dispatch_id='candidate-1', stage='CANDIDATE_EXTRACTION', input_text='evidence', input_token_ceiling=100, output_token_ceiling=25,
                invoke=lambda: {'_response_metadata': {'input_tokens': 1, 'output_tokens': 1}})
    try:
        ledger.call(dispatch_id='candidate-2', stage='CANDIDATE_EXTRACTION', input_text='evidence', input_token_ceiling=100, output_token_ceiling=25,
                    invoke=lambda: (_ for _ in ()).throw(ConnectionError('controlled batch two failure')))
    except ConnectionError:
        pass
    restarted = AcceptanceDispatchLedger(ledger.path, run_id='acceptance-test-0003', model='gpt-4.1-mini')
    try:
        restarted.call(dispatch_id='stage1', stage='STAGE1', input_text='evidence', input_token_ceiling=100, output_token_ceiling=25,
                       invoke=lambda: (_ for _ in ()).throw(AssertionError('must not invoke after batch two uncertainty')))
    except RuntimeError as exc:
        assert 'halted after prior OUTCOME_UNKNOWN' in str(exc)
    else:
        raise AssertionError('Stage 1 dispatch was not blocked')


def test_live_upload_path_stops_before_second_candidate_dispatch(monkeypatch):
    """Exercise the same upload entry point that Streamlit invokes."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    tmp_path = Path("tmp") / f"acceptance-upload-fail-stop-{uuid4().hex}"
    tmp_path.mkdir(parents=True)
    calls: list[int] = []

    def uncertain(packet: dict):
        calls.append(packet["batch"])
        raise ConnectionError("controlled upload-path connection failure")

    def two_batches(pages, max_chars=12_000):
        def packet(number, primary):
            return {"batch": number, "primary_pages": [p.page_number for p in primary],
                    "context_pages": [], "pages": [{"page_number": p.page_number, "text": p.text} for p in primary]}
        return [packet(1, pages[:1]), packet(2, pages[1:])]

    monkeypatch.setattr(upload_flow, "openai_candidate_request", uncertain)
    monkeypatch.setattr(upload_flow, "build_batches", two_batches)
    monkeypatch.setattr(ai_first, "build_batches", two_batches)
    document = pymupdf.open()
    for number in range(1, 4):
        page = document.new_page()
        page.insert_text((72, 72), f"{number}. " + ("source evidence " * 650))
    pdf = tmp_path / "fixture.pdf"
    document.save(pdf)
    document.close()

    with pytest.raises(RuntimeError, match="candidate extraction is incomplete"):
        upload_flow.analyze_ai_first_upload(
            tmp_path,
            "fixture.pdf",
            pdf.read_bytes(),
            request=uncertain,
            analysis_run_id="acceptance-upload-fail-stop",
            live_acceptance=True,
        )

    ledgers = list((tmp_path / "cache" / "document_runs").rglob("live_acceptance_dispatch_ledger.json"))
    assert calls == [1]
    assert len(ledgers) == 1
    ledger = __import__("json").loads(ledgers[0].read_text(encoding="utf-8"))
    assert [event["status"] for event in ledger["dispatches"]] == ["OUTCOME_UNKNOWN"]


def _fail(batch: int, calls: list[int]) -> dict:
    calls.append(batch)
    raise ConnectionError("controlled network failure")
