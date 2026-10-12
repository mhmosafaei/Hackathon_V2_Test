import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.documents.extractor import CandidateResponseError, candidate_response_schema, parse_candidate_response
from src.documents.live_budget import AcceptanceDispatchLedger


def _response(content, *, finish_reason="stop", refusal=None):
    return SimpleNamespace(
        id="chatcmpl-test",
        _request_id="req-test",
        usage=SimpleNamespace(prompt_tokens=120, completion_tokens=24),
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, refusal=refusal), finish_reason=finish_reason)],
    )


def test_candidate_schema_is_strict_and_valid_completed_json_preserves_metadata():
    assert candidate_response_schema()["strict"] is True
    payload = parse_candidate_response(_response('{"candidates": []}'), "gpt-4.1-mini")
    assert payload["candidates"] == []
    assert payload["_response_metadata"]["finish_reason"] == "stop"
    assert payload["_response_metadata"]["response_content_length"] == len('{"candidates": []}')
    assert payload["_response_metadata"]["request_id"] == "req-test"


def test_candidate_schema_is_compact_and_keeps_only_source_bearing_fields():
    fields = candidate_response_schema()["schema"]["properties"]["candidates"]["items"]["properties"]
    assert set(fields) == {"source_quotation", "page_number", "section", "obligation_type", "linked_references", "ambiguity"}
    assert "candidate_id" not in fields


def test_completed_compact_candidate_json_validates_before_local_enrichment():
    content = ('{"candidates":[{"source_quotation":"1. The operator shall retain the log.",'
               '"page_number":1,"section":"1","obligation_type":"Reporting obligation",'
               '"linked_references":[],"ambiguity":[]}]}')
    payload = parse_candidate_response(_response(content), "gpt-4.1-mini")
    assert payload["candidates"][0]["source_quotation"] == "1. The operator shall retain the log."


def test_candidate_response_joins_supported_content_parts_before_parsing():
    payload = parse_candidate_response(_response([{"text": '{"candidates": '}, {"text": "[]}"}]), "gpt-4.1-mini")
    assert payload["candidates"] == []


@pytest.mark.parametrize(
    ("response", "category"),
    [
        (_response('{"candidates": [', finish_reason="length"), "INCOMPLETE_OUTPUT"),
        (_response(None), "EMPTY_RESPONSE"),
        (_response('{"candidates": []}', refusal="Policy refusal"), "REFUSED_OUTPUT"),
        (_response('{"candidates": ['), "INVALID_JSON"),
        (_response('{"candidates": [{}]}'), "SCHEMA_VIOLATION"),
    ],
)
def test_candidate_response_rejects_incomplete_refused_and_invalid_outputs(response, category):
    with pytest.raises(CandidateResponseError) as exc:
        parse_candidate_response(response, "gpt-4.1-mini")
    assert exc.value.category == category
    assert exc.value.response_received is True
    assert exc.value.response_metadata["request_id"] == "req-test"


def test_completed_invalid_response_is_persisted_and_halts_later_dispatches():
    path = Path("tmp") / f"candidate-response-ledger-{uuid4().hex}.json"
    ledger = AcceptanceDispatchLedger(path, run_id="candidate-response-test", model="gpt-4.1-mini")
    with pytest.raises(CandidateResponseError):
        ledger.call(
            dispatch_id="candidate-batch-1", stage="CANDIDATE_EXTRACTION", input_text="source",
            input_token_ceiling=100, output_token_ceiling=25,
            invoke=lambda: parse_candidate_response(_response('{"candidates": ['), "gpt-4.1-mini"),
        )
    event = json.loads(path.read_text())["dispatches"][0]
    assert event["status"] == "COMPLETED_INVALID_RESPONSE"
    assert event["error_category"] == "INVALID_JSON"
    assert event["response_metadata"]["response_content_length"] == len('{"candidates": [')
    with pytest.raises(RuntimeError, match="COMPLETED_INVALID_RESPONSE"):
        ledger.call(
            dispatch_id="candidate-batch-2", stage="CANDIDATE_EXTRACTION", input_text="source",
            input_token_ceiling=100, output_token_ceiling=25,
            invoke=lambda: pytest.fail("later dispatch must not run"),
        )
