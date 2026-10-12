"""OpenAI structured-output adapter with a mockable transport and per-page errors."""
import json
import os
import base64
import re
from hashlib import sha256
from typing import Any
from jsonschema import Draft202012Validator
from dotenv import load_dotenv
from dataclasses import dataclass
from collections.abc import Callable
from .pdf_parser import PdfPage
from .openai_transport import direct_openai_client


RESPONSE_PARSER_VERSION = "candidate-response-parser-v2"
CANDIDATE_RESPONSE_CONTRACT_VERSION = "candidate-obligations-compact-v1"


def candidate_response_capabilities() -> dict[str, bool]:
    """Declared and testable guarantees of the loaded response parser."""
    return {
        "finish_reason_before_json": True,
        "response_metadata": True,
        "schema_validation": True,
    }


class CandidateResponseError(RuntimeError):
    """A completed provider response that cannot safely become candidates.

    ``response_received`` lets the capped-run ledger distinguish a known bad
    completion from a transport outcome that might have reached the provider.
    Only safe metadata is retained; source text and credentials are never put
    in exception messages or the dispatch ledger.
    """
    response_received = True

    def __init__(self, category: str, message: str, metadata: dict[str, Any]):
        super().__init__(message)
        self.category = category
        self.response_metadata = metadata


def candidate_response_schema() -> dict[str, Any]:
    """Compact strict contract for source-backed candidate discovery.

    Identity, state and verification are application facts.  They stay local
    rather than being repeated by the model for every source quotation.
    """
    return {
        "name": "candidate_obligations_compact",
        "schema": {"type": "object", "additionalProperties": False,
                   "properties": {"candidates": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                       "properties": {"source_quotation": {"type": "string"}, "page_number": {"type": "integer"},
                           "section": {"type": ["string", "null"]}, "obligation_type": {"type": ["string", "null"]},
                           "linked_references": {"type": "array", "items": {"type": "string"}}, "ambiguity": {"type": "array", "items": {"type": "string"}}},
                       "required": ["source_quotation", "page_number", "section", "obligation_type", "linked_references", "ambiguity"]}}},
                   "required": ["candidates"]}, "strict": True}


def _content_text(content: Any) -> str | None:
    """Return every text block supplied by an SDK response, without guessing."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            value = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
            if isinstance(value, str):
                parts.append(value)
            else:
                return None
        return "".join(parts)
    return None


def _safe_metadata(response: Any, model: str, choice: Any | None = None, content: str | None = None) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    metadata = {
        "model": model,
        "request_id": getattr(response, "_request_id", None),
        "response_id": getattr(response, "id", None),
        "finish_reason": getattr(choice, "finish_reason", None),
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
    }
    if content is not None:
        metadata.update({"response_content_length": len(content),
                         "response_content_sha256": sha256(content.encode("utf-8")).hexdigest()})
    return metadata


def parse_candidate_response(response: Any, model: str) -> dict:
    """Classify completion before parsing and locally validate strict output."""
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise CandidateResponseError("EMPTY_RESPONSE", "candidate response has no choices", _safe_metadata(response, model))
    choice = choices[0]
    message = getattr(choice, "message", None)
    content = _content_text(getattr(message, "content", None))
    metadata = _safe_metadata(response, model, choice, content)
    refusal = getattr(message, "refusal", None)
    if refusal:
        raise CandidateResponseError("REFUSED_OUTPUT", "candidate response was refused", metadata)
    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason != "stop":
        category = "INCOMPLETE_OUTPUT" if finish_reason in {"length", "content_filter", None} else "FAILED_OUTPUT"
        raise CandidateResponseError(category, f"candidate response did not complete normally: {finish_reason or 'unknown'}", metadata)
    if not content or not content.strip():
        raise CandidateResponseError("EMPTY_RESPONSE", "candidate response content is empty", metadata)
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise CandidateResponseError("INVALID_JSON", f"candidate response is not valid JSON: {exc.msg}", metadata) from exc
    errors = list(Draft202012Validator(candidate_response_schema()["schema"]).iter_errors(payload))
    if errors:
        first = errors[0]
        location = ".".join(map(str, first.absolute_path)) or "$"
        raise CandidateResponseError("SCHEMA_VIOLATION", f"candidate response fails schema at {location}: {first.message}", metadata)
    payload["_response_metadata"] = metadata
    return payload


def openai_candidate_request(batch: dict) -> dict:
    """Live adapter for the universal candidate contract.

    It is intentionally not called by tests.  The caller provides a bounded
    batch assembled from the document-wide pipeline; no credentials or request
    payload are written to disk by this adapter.
    """
    load_dotenv()
    model = os.environ["OPENAI_MODEL"]
    schema = candidate_response_schema()
    content = [{"type": "text", "text": batch["prompt"]}]
    # Table pages get visual context in addition to text. This is deliberately
    # bounded and happens only in an explicitly authorized live request.
    table_pages = [p['page_number'] for p in batch['pages'] if re.search(r'(?im)^\s*table\s+S?\d+\.\d+|emission limits|monitoring points', p['text'])]
    if table_pages:
        import pymupdf
        with pymupdf.open(batch['source_pdf']) as pdf:
            for number in table_pages[:3]:
                pix = pdf[number - 1].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                encoded = base64.b64encode(pix.tobytes('png')).decode('ascii')
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}", "detail": "high"}})
    request_kwargs = {"model": model, "messages": [{"role": "system", "content": "Extract complete source-backed obligation candidates only. Do not emit fragments. Copy the complete source quotation verbatim; do not duplicate it in another field. Preserve unresolved context in ambiguity. Do not decide compliance or approve anything."}, {"role": "user", "content": content}],
                      "response_format": {"type": "json_schema", "json_schema": schema}}
    if batch.get("max_output_tokens") is not None:
        request_kwargs["max_completion_tokens"] = batch["max_output_tokens"]
    client = direct_openai_client(timeout=90.0, max_retries=0)
    try:
        response = client.chat.completions.create(**request_kwargs)
    finally:
        client.close()
    return parse_candidate_response(response, model)

@dataclass(frozen=True)
class ExtractionRun:
    conditions: list[dict]
    errors: list[str]

def extract_pages(pages: list[PdfPage], request: Callable[[str], str]) -> ExtractionRun:
    conditions, errors = [], []
    for page in pages:
        try:
            response = json.loads(request(page.text))
            conditions.extend(response["conditions"])
        except Exception as exc:
            errors.append(f"page {page.page_number}: {exc}")
    return ExtractionRun(conditions, errors)

def openai_request(page_text: str, document_id: str = "ML2025054") -> str:
    """Return a structured extraction response without exposing credentials."""
    load_dotenv()
    model = os.environ["OPENAI_MODEL"]
    prompt = ("Extract ALL operational, environmental, monitoring, approval, reporting, temporal, geographic, equipment, method, stop/resume, notification, and evidence-related conditions from this marine licence page. A condition need not contain a numeric threshold. Return JSON only with "
              "a conditions array. Each condition must include condition_id, document_type=PERMIT, "
              f"document_id={document_id}, source_text copied verbatim, page_number, condition_type, "
              "variable, operator, threshold, threshold_upper, unit, duration_hours, "
              "evidence_requirements (array of strings), required_action (one of NONE, REPORT, NOTIFY, REQUEST_APPROVAL, MANUAL_CONFIRMATION, PROVIDE_EXTERNAL_EVIDENCE), confidence and review_required. condition_id must be a string. condition_type must be one of INSTANT_THRESHOLD, DURATION_THRESHOLD, STATE_TRANSITION, RANGE, ROLLING_LIMIT, CALENDAR_RESTRICTION, TIME_WINDOW, GEOFENCE, EQUIPMENT_STATE, DOCUMENT_APPROVAL, REPORTING_DEADLINE, EVENT_TRIGGER, OPERATING_METHOD, MONITORING_OBLIGATION, WEATHER_DOWNTIME, WORKABILITY_WINDOW, WEATHER_RISK_ALLOCATION, OTHER. "
              "Use null/LOW/review_required=true when unclear. Do not decide compliance, name datasets, "
              "assign automation status, or claim quote verification.\nPAGE:\n" + page_text)
    client = direct_openai_client(timeout=75.0, max_retries=2)
    try:
        response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": "You extract explicit licence conditions accurately. Output valid JSON only."},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        )
    finally:
        client.close()
    return response.choices[0].message.content or '{"conditions": []}'
