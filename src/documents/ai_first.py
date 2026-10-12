"""Document-wide, AI-first candidate discovery with deterministic verification.

The module accepts an injected transport rather than creating an OpenAI client.
That makes checkpointing and safety behaviour testable offline; inference stays
an explicit action at the edge of the application.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Callable
from collections import Counter

from src.models.candidate_obligation import CandidateObligation, CandidateState
from .pdf_parser import PdfPage
from .quote_verifier import verify_quote
from .structure import inspect_permit_structure
from .source_inventory import build_source_inventory, link_candidates

PROMPT_VERSION = "ai-first-candidates-v1"
ORCHESTRATION_VERSION = "candidate-pipeline-v2"


def orchestration_capabilities() -> dict[str, bool]:
    return {"failed_candidate_halts_later_batches": True, "checkpoint_resume": True}


def document_identity(content: bytes, model: str, analysis_run_id: str | None = None) -> str:
    """Cache identity includes source bytes, model, prompt contract and optional fresh run.

    With no run id, historical resumable behaviour stays exactly deterministic.
    A caller requesting an acceptance run supplies a stable explicit id, which
    creates a separate namespace without disturbing previous checkpoints.
    """
    fresh = (analysis_run_id or "").encode("utf-8")
    return sha256(content + model.encode("utf-8") + PROMPT_VERSION.encode("utf-8") + fresh).hexdigest()


def build_batches(pages: list[PdfPage], max_chars: int = 12_000) -> list[dict]:
    """Create bounded primary batches with adjacent continuation context."""
    batches: list[dict] = []
    current: list[PdfPage] = []
    size = 0
    for page in pages:
        if current and size + len(page.text) > max_chars:
            batches.append(_batch(len(batches) + 1, pages, current))
            current, size = [], 0
        current.append(page)
        size += len(page.text)
    if current:
        batches.append(_batch(len(batches) + 1, pages, current))
    return batches


def _batch(number: int, all_pages: list[PdfPage], primary: list[PdfPage]) -> dict:
    first, last = primary[0].page_number, primary[-1].page_number
    context = [p for p in all_pages if p.page_number in {first - 1, last + 1}]
    included = sorted({p.page_number: p for p in [*context, *primary]}.values(), key=lambda p: p.page_number)
    return {"batch": number, "primary_pages": [p.page_number for p in primary],
            "context_pages": [p.page_number for p in context],
            "pages": [{"page_number": p.page_number, "text": p.text} for p in included]}


def candidate_prompt(batch: dict, document_id: str) -> str:
    """Prompt for discovery only; it cannot authorize or decide compliance."""
    page_text = "\n\n".join(f"[PDF page {p['page_number']}]\n{p['text']}" for p in batch["pages"])
    return (
        "Discover explicit obligation candidates in this permit or contract. Include numbered and "
        "unnumbered clauses, restrictions, approvals, deadlines, exceptions, schedules and tables. "
        "Return only source-backed candidates; use null for unknown structured fields. Copy each "
        "source_quotation verbatim and cite its physical PDF page. Do not determine legal compliance, "
        "create rules, infer missing values, or approve anything. Document id: " + document_id + "\n\n" + page_text
    )


def verify_candidates(raw: list[dict], pages: list[PdfPage]) -> list[CandidateObligation]:
    """Compatibility entry point: malformed candidates do not drop neighbours."""
    verified, _ = validate_and_verify_candidates(raw, pages)
    return verified


def _candidate_id(item: dict, index: int) -> str:
    """Create a stable local ID; it is not a model assertion."""
    basis = f"{item.get('page_number')}|{item.get('section')}|{item.get('source_quotation')}"
    return f"candidate-p{item.get('page_number', 'unknown')}-{index + 1}-{sha256(basis.encode('utf-8')).hexdigest()[:10]}"


def materialize_candidate_drafts(raw: list[dict], document_id: str | None = None) -> list[dict]:
    """Add local-only identity and review fields omitted by the compact contract.

    Raw provider output remains stored unchanged.  This enrichment performs no
    legal interpretation and retains every source quotation verbatim.
    """
    materialized = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            materialized.append(item)
            continue
        materialized.append({
            **item,
            "candidate_id": item.get("candidate_id") or _candidate_id(item, index),
            "document_id": item.get("document_id") or document_id or "UNKNOWN",
            "document_type": item.get("document_type") or "UNKNOWN",
            "obligation": item.get("obligation") or item.get("source_quotation"),
            "state": CandidateState.EXTRACTED_UNVERIFIED,
            "human_review_required": True,
        })
    return materialized


def validate_and_verify_candidates(raw: list[dict], pages: list[PdfPage], document_id: str | None = None) -> tuple[list[CandidateObligation], list[dict]]:
    verified: list[CandidateObligation] = []
    rejected: list[dict] = []
    for index, item in enumerate(materialize_candidate_drafts(raw, document_id)):
        try:
            # Verification state is deterministic application output, never a
            # model assertion. Preserve raw item separately, but prevent an
            # arbitrary model label (for example "active") rejecting an
            # otherwise useful candidate.
            normalized = {**item, "state": CandidateState.EXTRACTED_UNVERIFIED, "human_review_required": True}
            candidate = CandidateObligation.model_validate(normalized)
            match = verify_quote(candidate.source_quotation, pages, candidate.page_number)
            state = (CandidateState.SOURCE_VERIFIED if match.verified and not candidate.ambiguity
                     else CandidateState.CONTEXT_UNRESOLVED if match.verified else CandidateState.SOURCE_NOT_FOUND)
            verified.append(candidate.model_copy(update={"state": state, "human_review_required": True}))
        except Exception as exc:
            rejected.append({"index": index, "raw": item, "error": f"{type(exc).__name__}: {str(exc)[:500]}"})
    return verified, rejected


def assign_register_ids(candidates: list[dict]) -> list[dict]:
    """Give the persisted register a deterministic unique key.

    Model-supplied ``candidate_id`` remains untouched in the raw response and
    aggregate.  Some providers restart a local sequence in each checkpoint;
    ``register_id`` prevents those otherwise distinct records colliding in the
    review UI or its document-scoped decision store.
    """
    totals = Counter(candidate["candidate_id"] for candidate in candidates)
    occurrences: Counter[str] = Counter()
    for candidate in candidates:
        base = candidate["candidate_id"]
        occurrences[base] += 1
        candidate["register_id"] = (base if totals[base] == 1
                                    else f"{base}@p{candidate['page_number']}-{occurrences[base]}")
    return candidates


def run_document_pipeline(folder: Path, document_id: str, pages: list[PdfPage], request: Callable[[dict], dict | str], *, model: str, max_chars: int = 12_000, analysis_run_id: str | None = None, halt_on_failed_batch: bool = False, runtime: dict | None = None, batch_limit: int | None = None) -> dict:
    """Persist independent batches and a document-wide, non-authorizing coverage view."""
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {
        "processing_schema_version": PROMPT_VERSION, "document_id": document_id, "model": model,
        "analysis_run_id": analysis_run_id, "runtime": runtime, "batches": {}}
    batches = build_batches(pages, max_chars)
    if batch_limit is not None:
        if batch_limit < 1:
            raise ValueError("batch_limit must be positive")
        batches_to_run = batches[:batch_limit]
        manifest["diagnostic_batch_limit"] = batch_limit
        manifest["planned_batch_count"] = len(batches)
    else:
        batches_to_run = batches
    for batch in batches_to_run:
        key = str(batch["batch"])
        old = manifest["batches"].get(key, {})
        if old.get("status") == "COMPLETE":
            continue
        manifest["batches"][key] = {**old, "status": "PENDING", "primary_pages": batch["primary_pages"], "context_pages": batch["context_pages"]}
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        try:
            response = request({**batch, "document_id": document_id, "prompt": candidate_prompt(batch, document_id), "source_pdf": str(folder / 'source.pdf')})
            if isinstance(response, str):
                response = json.loads(response)
            if not isinstance(response, dict):
                raise ValueError("candidate extraction response must be a JSON object")
            raw = response.get("candidates", [])
            if not isinstance(raw, list):
                raise ValueError("candidate extraction response requires a candidates array")
            candidates, rejected = validate_and_verify_candidates(raw, pages, document_id)
            output_file = f"candidate_batch_{batch['batch']:03}.json"
            output = {"batch": batch["batch"], "primary_pages": batch["primary_pages"], "context_pages": batch["context_pages"], "response_metadata": response.get("_response_metadata", {}),
                      "raw": response, "candidates": [c.model_dump(mode="json") for c in candidates], "rejected": rejected}
            (folder / output_file).write_text(json.dumps(output, indent=2), encoding="utf-8")
            manifest["batches"][key] = {"status": "COMPLETE", "primary_pages": batch["primary_pages"], "context_pages": batch["context_pages"],
                                          "output_file": output_file, "raw_candidates": len(raw), "valid_candidates": len(candidates), "rejected_candidates": len(rejected), "response_metadata": response.get("_response_metadata", {})}
        except Exception as exc:
            failure = {**manifest["batches"][key], "status": "FAILED",
                       "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
            # Known invalid/incomplete provider output has a different audit
            # meaning from a transport outcome.  Preserve only metadata, never
            # credentials or raw prompt/response text, in the manifest.
            category = getattr(exc, "category", None)
            metadata = getattr(exc, "response_metadata", None)
            if category:
                failure["error_category"] = category
            if isinstance(metadata, dict):
                failure["response_metadata"] = metadata
            manifest["batches"][key] = failure
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        # Acceptance runs are intentionally fail-closed at the orchestration
        # boundary as well as inside the dispatch ledger.  A failed network
        # call may have reached the provider, so later batches must never be
        # scheduled while its outcome is uncertain.
        if halt_on_failed_batch and manifest["batches"][key]["status"] == "FAILED":
            break

    candidates: list[dict] = []
    rejected: list[dict] = []
    for entry in manifest["batches"].values():
        if entry.get("status") == "COMPLETE":
            record = json.loads((folder / entry["output_file"]).read_text(encoding="utf-8"))
            candidates.extend(record["candidates"]); rejected.extend(record["rejected"])
    unique, duplicates, seen = [], [], set()
    for candidate in candidates:
        identity = (candidate["document_id"], candidate["page_number"], candidate["source_quotation"])
        if identity in seen: duplicates.append(candidate)
        else: seen.add(identity); unique.append(candidate)
    # Inventory construction and linking are a mandatory, local stage.  It is
    # intentionally after checkpoint aggregation, so an offline rerun can
    # repair inventory/linking without re-dispatching any completed batch.
    unique = assign_register_ids(unique)
    source_pdf = folder / "source.pdf"
    source_inventory = build_source_inventory(document_id, pages, source_pdf if source_pdf.exists() else None)
    unique = link_candidates(unique, source_inventory)
    structure = inspect_permit_structure(pages)
    processed = {page for entry in manifest["batches"].values() if entry.get("status") == "COMPLETE" for page in entry.get("primary_pages", [])}
    failed = {page for entry in manifest["batches"].values() if entry.get("status") == "FAILED" for page in entry.get("primary_pages", [])}
    page_coverage = []
    for page in pages:
        processing = "PROCESSED" if page.page_number in processed else "FAILED" if page.page_number in failed else "PENDING"
        ids = [c["candidate_id"] for c in unique if c["page_number"] == page.page_number]
        records_on_page = [r for r in source_inventory if page.page_number in r.pages]
        has_operational_source = any(r.record_type.value in {"CLAUSE", "TABLE_ROW"} for r in records_on_page)
        semantic = ("FAILED" if processing == "FAILED" else
                    "PROCESSED_WITH_OBLIGATIONS" if ids else
                    "PROCESSED_REVIEW_REQUIRED" if processing == "PROCESSED" and has_operational_source else
                    "PROCESSED_SOURCE_ONLY" if processing == "PROCESSED" and records_on_page else
                    "NOT_PROCESSED" if processing != "PROCESSED" else "PROCESSED_SOURCE_ONLY")
        page_coverage.append({"page": page.page_number, "processing": processing, "candidate_ids": ids, "semantic_status": semantic})
    coverage = {"schema_version": "ai-first-coverage-v1", "physical_pages": len(pages), "pages": page_coverage,
                "structure": structure, "unresolved_references": [], "processing_complete": len(processed) == len(pages),
                "semantic_coverage_complete": False,
                "summary": {"processed_pages": len(processed), "failed_pages": len(failed), "pages_without_candidates": sum(not x["candidate_ids"] for x in page_coverage), "source_only_pages": sum(x["semantic_status"] == "PROCESSED_SOURCE_ONLY" for x in page_coverage), "review_required_pages": sum(x["semantic_status"] == "PROCESSED_REVIEW_REQUIRED" for x in page_coverage)}}
    aggregate = {"document_id": document_id, "processing_schema_version": PROMPT_VERSION, "model": model,
                 "candidates": unique, "rejected": rejected, "duplicates": duplicates,
                 "source_inventory": [record.model_dump(mode="json") for record in source_inventory], "coverage": coverage}
    (folder / "candidate_aggregate.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    (folder / "coverage_audit.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    manifest["document_state"] = "REVIEW_REQUIRED" if coverage["processing_complete"] else "FAILED"
    manifest["coverage_summary"] = coverage["summary"]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"manifest": manifest, "aggregate": aggregate, "coverage": coverage}
