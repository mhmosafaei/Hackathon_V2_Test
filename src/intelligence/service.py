"""Resumable three-stage PermitPulse intelligence orchestration.

The service consumes the existing AI-first aggregate instead of replacing its
extraction, source inventory, quote verifier or checkpoint manifest.  Stage
transports are injected so offline tests can exercise the same stage ledger
without network access.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
from pathlib import Path
from time import monotonic
from typing import Any, Callable

from .contracts import (
    Audit, CanonicalAnalysis, ConstraintProposal, Coverage, DataFeasibility,
    DataNeed, Definition, DocumentRecord, OperationalAssessment, PageCoverage,
    Requirement, ReviewFlag, SourceRecord, Stage1Response, Stage2Response,
    Stage3Response, StageRun, WorkWindowStatus,
)
from .prompts import (
    STAGE1_DEVELOPER_PROMPT, STAGE1_PROMPT_VERSION,
    STAGE2_DEVELOPER_PROMPT, STAGE2_PROMPT_VERSION,
    STAGE3_DEVELOPER_PROMPT, STAGE3_PROMPT_VERSION,
)
from src.documents.openai_transport import direct_openai_client


INTELLIGENCE_TRANSPORT_VERSION = "intelligence-transport-v1"


def intelligence_transport_capabilities() -> dict[str, bool]:
    return {"structured_json": True, "response_metadata": True, "checkpointed_stages": True}

INTELLIGENCE_VERSION = "permitpulse.intelligence.v1"
StageTransport = Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any]]


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _kind(record: dict[str, Any]) -> str:
    return {
        "CLAUSE": "OPERATIVE_INSTRUMENT", "TABLE": "TABLE", "TABLE_ROW": "TABLE",
        "SCHEDULE": "SCHEDULE", "DEFINITION": "DEFINITION", "REFERENCE": "INCORPORATED_DOCUMENT",
        "CONTEXT": "OTHER",
    }.get(record.get("record_type"), "OTHER")


def _source(record: dict[str, Any]) -> SourceRecord:
    text = record.get("source_text", "")
    pages = record.get("pages") or [1]
    return SourceRecord(
        source_id=record["source_record_id"], parent_source_id=None,
        section_id=record.get("section_reference"), source_kind=_kind(record),
        page_start=min(pages), page_end=max(pages), exact_text=text,
        source_hash=sha256(text.encode("utf-8")).hexdigest(), authority_actor=None,
    )


def _modality(quote: str) -> str:
    value = quote.lower()
    if "must not" in value or "shall not" in value or "may not" in value:
        return "MUST_NOT"
    if "must" in value or "shall" in value or "required" in value:
        return "MUST"
    if "should" in value:
        return "SHOULD"
    if " may " in f" {value} ":
        return "MAY"
    return "UNKNOWN"


def _lifecycle(candidate: dict[str, Any]) -> list[str]:
    text = " ".join(str(candidate.get(k) or "") for k in ("deadline", "trigger", "source_quotation")).lower()
    if "before" in text or "prior" in text or "commence" in text:
        return ["PRE_WORK"]
    if "after" in text or "completion" in text:
        return ["POST_WORK"]
    if "during" in text:
        return ["DURING_WORK"]
    return ["UNKNOWN"]


def _requirement(candidate: dict[str, Any], source_ids: list[str]) -> Requirement:
    quote = candidate["source_quotation"]
    state = candidate.get("state", "EXTRACTED_UNVERIFIED")
    verification = "SOURCE_VERIFIED" if state == "SOURCE_VERIFIED" else "CONTEXT_UNRESOLVED" if state == "CONTEXT_UNRESOLVED" else "SOURCE_NOT_FOUND"
    authority = "CONTEXT_ONLY" if candidate.get("document_type") == "CONTEXT" else "UNRESOLVED"
    return Requirement(
        requirement_id=candidate.get("register_id") or candidate["candidate_id"],
        parent_condition_id=candidate.get("section"), source_ids=source_ids,
        page_start=candidate["page_number"], page_end=candidate["page_number"],
        section_id=candidate.get("section"), exact_quote=quote,
        summary=candidate.get("obligation") or quote,
        actor=(candidate.get("parties") or [None])[0], action=candidate.get("action"),
        object=candidate.get("subject"), modality=_modality(quote), authority_status=authority,
        authority_basis_source_ids=source_ids, source_verification=verification,
        atomic_completeness="UNRESOLVED" if candidate.get("ambiguity") else "COMPLETE",
        temporal_expressions=[candidate["deadline"]] if candidate.get("deadline") else [],
        numeric_expressions=[f"{candidate['threshold']} {candidate.get('unit') or ''}".strip()] if candidate.get("threshold") is not None else [],
        exception_texts=[candidate["exception"]] if candidate.get("exception") else [],
        cross_reference_ids=candidate.get("linked_references") or [], lifecycle_phases=_lifecycle(candidate),
        ambiguity_flags=candidate.get("ambiguity") or [], human_review="UNREVIEWED",
    )


def _mock_stage1(aggregate: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    sources = [_source(item).model_dump(mode="json") for item in aggregate.get("source_inventory", [])]
    # The strict Stage 1 provider contract deliberately permits only PENDING
    # evidence verification.  Quote verification is a local post-processing
    # fact and is applied while assembling the canonical document artifact.
    source_kinds = {item["source_id"]: item["source_kind"] for item in sources}
    requirements = []
    for item in aggregate.get("candidates", []):
        requirement = _requirement(item, item.get("source_record_ids") or []).model_dump(mode="json")
        requirement["source_verification"] = "PENDING"
        if any(source_kinds.get(source_id) == "OPERATIVE_INSTRUMENT" for source_id in requirement["source_ids"]):
            requirement["authority_status"] = "OPERATIVE"
            requirement["authority_basis_source_ids"] = requirement["source_ids"]
        requirements.append(requirement)
    return {"document_id": packet["document_id"], "batch_id": packet["batch_id"], "page_start": 1,
            "page_end": packet["physical_pages"], "sources": sources, "definitions": [],
            "requirements": requirements, "unresolved_source_ids": [], "issues": []}


def _role(requirement: Requirement) -> str:
    text = " ".join([requirement.action or "", requirement.exact_quote]).lower()
    if any(word in text for word in ("report", "submit report")):
        return "REPORTING_OR_ADMINISTRATION"
    if any(word in text for word in ("notify", "approval", "approve", "agree")):
        return "NOTIFICATION_OR_APPROVAL"
    if any(word in text for word in ("monitor", "sample", "measure")):
        return "MONITORING_REQUIREMENT"
    if requirement.modality == "MUST_NOT":
        return "DIRECT_WORK_GATE"
    return "UNRESOLVED"


def _mock_stage2(requirements: list[Requirement], packet: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for requirement in requirements:
        role = _role(requirement)
        rows.append(OperationalAssessment(
            requirement_id=requirement.requirement_id, primary_role=role,
            operational_activities=[], lifecycle_phases=requirement.lifecycle_phases,
            is_direct_work_gate=role == "DIRECT_WORK_GATE", could_block_work=role in {"DIRECT_WORK_GATE", "NOTIFICATION_OR_APPROVAL"},
            dependency_requirement_ids=[], evidence_categories=[],
            rationale="Mock classification for offline workflow validation; human review required.",
            uncertainty_reasons=["No live Stage 2 inference was dispatched."],
        ).model_dump(mode="json"))
    return {"document_id": packet["document_id"], "batch_id": packet["batch_id"],
            "operational_assessments": rows, "unclassified_requirement_ids": [], "issues": []}


def _domain(requirement: Requirement) -> tuple[str, str, str]:
    text = requirement.exact_quote.lower()
    if "wave" in text:
        return "WAVES", "significant_wave_height", "Significant wave height"
    if "wind" in text:
        return "WEATHER", "wind", "Wind"
    if "current" in text:
        return "CURRENTS", "current", "Current"
    if any(word in text for word in ("oxygen", "turbidity", "sediment", "water quality")):
        return "WATER_QUALITY", "water_quality", "Water quality"
    if any(word in text for word in ("coordinate", "location", "area", "appendix")):
        return "GEOLOCATION", "permit_geography", "Permit geography"
    if any(word in text for word in ("day", "date", "month", "season", "hours")):
        return "CALENDAR", "permit_calendar", "Permit calendar"
    return "OTHER", "manual_evidence", "Manual evidence"


def _mock_stage3(requirements: list[Requirement], packet: dict[str, Any]) -> dict[str, Any]:
    constraints: list[dict[str, Any]] = []
    needs: list[dict[str, Any]] = []
    for requirement in requirements:
        domain, key, label = _domain(requirement)
        if domain == "OTHER":
            continue
        need_id = f"data-{requirement.requirement_id}"
        needs.append(DataNeed(
            data_need_id=need_id, requirement_ids=[requirement.requirement_id], constraint_ids=[],
            parameter_key=key, parameter_label=label, domain=domain,
            evidence_kind="CALENDAR" if domain == "CALENDAR" else "STATIC_GIS" if domain == "GEOLOCATION" else "UNKNOWN",
            needed_unit=None, needed_depth=None, needed_time_resolution=None, needed_spatial_resolution=None,
            needed_forecast_horizon=None, needed_location=None, provider_hints=[], provider_verified=False,
            suitability_status="NOT_CHECKED", relevance_reason="Mock evidence mapping; suitability requires deterministic adapter verification.",
        ).model_dump(mode="json"))
    return {"document_id": packet["document_id"], "batch_id": packet["batch_id"],
            "constraint_proposals": constraints, "data_needs": needs,
            "unmapped_requirement_ids": [r.requirement_id for r in requirements if _domain(r)[0] == "OTHER"], "issues": []}


def mock_stage_transport(stage: str, packet: dict[str, Any], _schema: dict[str, Any]) -> dict[str, Any]:
    """Local deterministic transport used only by offline tests/UI mock mode."""
    if stage == "stage1":
        return _mock_stage1(packet["aggregate"], packet)
    if stage == "stage2":
        return _mock_stage2([Requirement.model_validate(row) for row in packet["requirements"]], packet)
    if stage == "stage3":
        return _mock_stage3([Requirement.model_validate(row) for row in packet["requirements"]], packet)
    raise ValueError(f"unknown intelligence stage: {stage}")


def _strict_schema(model: type) -> dict[str, Any]:
    """Produce the strict JSON-schema subset required by Responses API."""
    schema = model.model_json_schema()
    def visit(node: Any) -> None:
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                node["additionalProperties"] = False
                node["required"] = list(props)
            for value in node.values(): visit(value)
        elif isinstance(node, list):
            for value in node: visit(value)
    visit(schema)
    return schema


def openai_stage_transport(stage: str, packet: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Live Responses API edge. Never invoked by imports or offline tests."""
    model = os.environ.get("OPENAI_MODEL")
    if not model:
        raise RuntimeError("OPENAI_MODEL is required for live intelligence analysis")
    prompts = {"stage1": (STAGE1_DEVELOPER_PROMPT, STAGE1_PROMPT_VERSION),
               "stage2": (STAGE2_DEVELOPER_PROMPT, STAGE2_PROMPT_VERSION),
               "stage3": (STAGE3_DEVELOPER_PROMPT, STAGE3_PROMPT_VERSION)}
    developer, version = prompts[stage]
    request_kwargs = {"model": model,
        "input": [{"role": "developer", "content": developer},
                  {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}],
        "text": {"format": {"type": "json_schema", "name": f"permitpulse_{stage}_{version}", "strict": True, "schema": schema}}}
    if packet.get("max_output_tokens") is not None:
        request_kwargs["max_output_tokens"] = packet["max_output_tokens"]
    client = direct_openai_client(timeout=90.0, max_retries=0)
    try:
        response = client.responses.create(**request_kwargs)
    finally:
        client.close()
    if getattr(response, "status", None) != "completed":
        raise RuntimeError(f"{stage} did not complete: {getattr(response, 'status', None)}")
    result = json.loads(response.output_text)
    result["_response_metadata"] = {"model": model, "request_id": getattr(response, "_request_id", None),
                                    "input_tokens": getattr(getattr(response, "usage", None), "input_tokens", None),
                                    "output_tokens": getattr(getattr(response, "usage", None), "output_tokens", None)}
    return result


def _checkpoint(folder: Path, name: str, model: type, stage: str, packet: dict[str, Any], transport: StageTransport) -> tuple[dict[str, Any], bool]:
    path = folder / f"intelligence_{name}.json"
    if path.exists():
        return _json(path), True
    schema = _strict_schema(model)
    started = monotonic()
    payload = transport(stage, packet, schema)
    metadata = payload.pop("_response_metadata", {})
    validated = model.model_validate(payload).model_dump(mode="json")
    stored = {"response": validated, "response_metadata": metadata, "elapsed_seconds": round(monotonic() - started, 3)}
    _write(path, stored)
    return stored, False


def _coverage(aggregate: dict[str, Any], requirements: list[Requirement]) -> Coverage:
    source_ids = {source.source_id for source in [_source(row) for row in aggregate.get("source_inventory", [])]}
    linked = {item for requirement in requirements for item in requirement.source_ids}
    page_rows = []
    coverage = aggregate.get("coverage", {})
    for row in coverage.get("pages", []):
        processing = row.get("processing")
        semantic = row.get("semantic_status")
        status = "FAILED" if processing == "FAILED" else "NOT_PROCESSED" if processing != "PROCESSED" else "PROCESSED_WITH_REQUIREMENTS" if row.get("candidate_ids") else "PROCESSED_SOURCE_ONLY"
        page_rows.append(PageCoverage(page_number=row["page"], status=status, source_count=0,
                                     requirement_count=len(row.get("candidate_ids") or []), errors=[]))
    if not page_rows:
        physical = int(coverage.get("physical_pages", 0))
        page_rows = [PageCoverage(page_number=i, status="NOT_PROCESSED", source_count=0, requirement_count=0, errors=[]) for i in range(1, physical + 1)]
    for page in page_rows:
        page.source_count = sum(page.page_number in item.get("pages", []) for item in aggregate.get("source_inventory", []))
    structural = coverage.get("structure", {})
    numbered = [str(item.get("id")) for item in structural.get("numbered_clauses", []) if item.get("id")]
    processed = sum(x.status in {"PROCESSED_WITH_REQUIREMENTS", "PROCESSED_SOURCE_ONLY"} for x in page_rows)
    failures = sum(x.status == "FAILED" for x in page_rows)
    unreadable = sum(x.status == "UNREADABLE" for x in page_rows)
    return Coverage(physical_pages=len(page_rows), processed_pages=processed,
                    source_only_pages=sum(x.status == "PROCESSED_SOURCE_ONLY" for x in page_rows),
                    failed_pages=failures, unreadable_pages=unreadable, page_results=page_rows,
                    numbered_conditions=numbered,
                    unlinked_condition_ids=sorted(source_ids - linked),
                    completeness="COMPLETE_WITH_REVIEW" if processed == len(page_rows) and not failures else "PARTIAL")


def stage1_condition_accountability(aggregate: dict[str, Any], stage1: dict[str, Any]) -> dict[str, Any]:
    """Produce a deterministic numbered-condition audit beside the Stage 1 response.

    It never creates a requirement for omitted text.  Instead, every numbered
    source span remains visible as unresolved until Stage 1 links a supported
    atomic requirement (or explicitly reports it unresolved).
    """
    response = Stage1Response.model_validate(stage1["response"])
    requirements = response.requirements
    records = aggregate.get("source_inventory", [])
    rows = []
    for record in records:
        if record.get("record_type") != "CLAUSE":
            continue
        condition_id = str(record.get("section_reference") or "")
        if not re.match(r"^\d+(?:[.\-]\d+)*$", condition_id):
            continue
        source_id = record["source_record_id"]
        linked = [item for item in requirements if source_id in item.source_ids]
        statuses = {item.authority_status for item in linked}
        authority = "OPERATIVE" if "OPERATIVE" in statuses else "CONTEXT_ONLY" if statuses == {"CONTEXT_ONLY"} else "UNRESOLVED"
        if not linked:
            disposition = "UNRESOLVED"
        elif any(item.atomic_completeness != "COMPLETE" for item in linked) or source_id in response.unresolved_source_ids:
            disposition = "PARTIALLY_INTERPRETED"
        else:
            disposition = "FULLY_INTERPRETED"
        rows.append({"condition_id": condition_id, "page": min(record.get("pages") or [0]),
                     "source_record_id": source_id, "authority_status": authority,
                     "authority_evidence": [item.authority_basis_source_ids for item in linked],
                     "linked_requirement_ids": [item.requirement_id for item in linked],
                     "interpretation_status": disposition,
                     "review_items": [{"exceptions": item.exception_texts,
                                        "dependencies": item.cross_reference_ids,
                                        "thresholds": item.numeric_expressions,
                                        "deadlines": item.temporal_expressions,
                                        "ambiguities": item.ambiguity_flags} for item in linked],
                     "source_quote": record.get("source_text", "")})
    rows.sort(key=lambda item: (item["page"], item["condition_id"]))
    return {"schema_version": "stage1-condition-accountability-v1",
            "numbered_conditions": rows,
            "unresolved_source_ids": response.unresolved_source_ids,
            "issues": response.issues,
            "summary": {"total": len(rows),
                        "fully_interpreted": sum(row["interpretation_status"] == "FULLY_INTERPRETED" for row in rows),
                        "partially_interpreted": sum(row["interpretation_status"] == "PARTIALLY_INTERPRETED" for row in rows),
                        "unresolved": sum(row["interpretation_status"] == "UNRESOLVED" for row in rows)}}


def build_intelligence_analysis(folder: Path, aggregate: dict[str, Any], stage1: dict[str, Any], stage2: dict[str, Any], stage3: dict[str, Any], *, filename: str, document_sha256: str, processor: str) -> CanonicalAnalysis:
    s1 = Stage1Response.model_validate(stage1["response"])
    s2 = Stage2Response.model_validate(stage2["response"])
    s3 = Stage3Response.model_validate(stage3["response"])
    original_candidates = {item.get("register_id") or item.get("candidate_id"): item for item in aggregate.get("candidates", [])}
    requirements = []
    for item in s1.requirements:
        candidate = original_candidates.get(item.requirement_id)
        if candidate is None:
            requirements.append(item)
            continue
        verified = _requirement(candidate, item.source_ids)
        # Keep semantic extraction fields from the exact Stage 1 response;
        # only evidence verification is deterministic local evidence.
        requirements.append(item.model_copy(update={"source_verification": verified.source_verification}))
    coverage = _coverage(aggregate, requirements)
    stage_specs = [
        ("DOCUMENT_EXTRACTION", s1, stage1, STAGE1_PROMPT_VERSION),
        ("OPERATIONAL_RELEVANCE", s2, stage2, STAGE2_PROMPT_VERSION),
        ("ENVIRONMENTAL_MAPPING", s3, stage3, STAGE3_PROMPT_VERSION),
    ]
    stage_runs = []
    for stage, response, saved, version in stage_specs:
        meta = saved.get("response_metadata", {})
        stage_runs.append(StageRun(stage=stage, status="COMPLETED", processor=processor,
            model=meta.get("model"), prompt_version=version, batches_total=1, batches_completed=1,
            response_ids=[meta["request_id"]] if meta.get("request_id") else [], input_tokens=meta.get("input_tokens"),
            output_tokens=meta.get("output_tokens"), elapsed_seconds=saved.get("elapsed_seconds"), cost_usd=meta.get("actual_cost_usd"), error_messages=[]))
    feasibility = [DataFeasibility(data_need_id=item.data_need_id,
        status="REQUIRES_LOCAL_MEASUREMENT" if item.evidence_kind == "DIRECT_LOCAL_MEASUREMENT" else "REQUIRES_MANUAL_CONFIRMATION" if item.evidence_kind == "MANUAL_CONFIRMATION" else "NOT_CHECKED",
        fit_reason="No deterministic adapter verification has been performed for this analysis.") for item in s3.data_needs]
    stage_runs.extend([
        StageRun(stage="DATA_FEASIBILITY", status="NOT_APPLICABLE", processor="DETERMINISTIC"),
        StageRun(stage="WORK_WINDOW_EVALUATION", status="NOT_APPLICABLE", processor="NONE"),
    ])
    flags = [ReviewFlag(flag_id=f"review-{req.requirement_id}", related_requirement_ids=[req.requirement_id],
                        related_source_ids=req.source_ids, severity="MEDIUM", category="AUTHORITY",
                        message="Requirement remains unreviewed and cannot become an executable rule.", status="OPEN",
                        recommended_action="Verify operative authority and approve only through the human review workflow.") for req in requirements]
    raw_paths = [str(folder / f"intelligence_{name}.json") for name in ("stage1", "stage2", "stage3")]
    metadata = [x.get("response_metadata", {}) for x in (stage1, stage2, stage3)]
    analysis = CanonicalAnalysis(
        analysis_id=folder.name, document=DocumentRecord(document_id=aggregate["document_id"], filename=filename,
            sha256=document_sha256, title=filename, physical_pages=coverage.physical_pages), coverage=coverage,
        stage_runs=stage_runs, source_inventory=s1.sources, definitions=s1.definitions, requirements=requirements,
        operational_assessments=s2.operational_assessments, constraint_proposals=s3.constraint_proposals,
        data_needs=s3.data_needs, data_feasibility=feasibility, review_flags=flags,
        work_windows=WorkWindowStatus(status="NOT_EVALUATED", evaluation_ready=False,
            blocking_reasons=["Human review, rule approval and deciding-evidence verification are incomplete."], windows=[]),
        audit=Audit(analysis_version=INTELLIGENCE_VERSION, raw_response_paths=raw_paths,
            source_manifest_path=str(folder / "manifest.json"), api_call_count=sum(1 for item in metadata if item.get("request_id")),
            total_input_tokens=sum(item.get("input_tokens") or 0 for item in metadata) or None,
            total_output_tokens=sum(item.get("output_tokens") or 0 for item in metadata) or None,
            total_cost_usd=sum(item.get("actual_cost_usd") or 0 for item in metadata) or None,
            notes=["Canonical analysis is derived from immutable extraction checkpoints.", "No requirement is approved or executable by this analysis.",
                   *[f"{stage}: {saved.get('response_metadata', {}).get('execution', 'LOADED_FROM_CHECKPOINT')}" for stage, _, saved, _ in stage_specs]]),
    )
    return analysis


def _analysis_cache_folder(folder: Path, document_sha256: str, processor: str) -> Path:
    """Return a versioned, document-scoped stage-cache namespace.

    The legacy candidate run folder remains immutable.  This nested namespace
    prevents a change to any intelligence prompt or configured model from
    reusing a previous structured response.  The top-level canonical JSON is
    only a convenient document-scoped pointer for the Streamlit UI.
    """
    model = os.environ.get("OPENAI_MODEL", "mock") if processor == "OPENAI" else "mock"
    identity = "|".join((document_sha256, model, INTELLIGENCE_VERSION,
                         STAGE1_PROMPT_VERSION, STAGE2_PROMPT_VERSION,
                         STAGE3_PROMPT_VERSION))
    target = folder / "intelligence" / sha256(identity.encode("utf-8")).hexdigest()
    target.mkdir(parents=True, exist_ok=True)
    return target


def run_intelligence_pipeline(folder: Path, aggregate: dict[str, Any], *, filename: str, document_sha256: str, transport: StageTransport, processor: str) -> CanonicalAnalysis:
    """Run/resume stages 1–3 then locally assemble stages 4–5 placeholders."""
    document_id = aggregate["document_id"]
    stage_folder = _analysis_cache_folder(folder, document_sha256, processor)
    physical_pages = int(aggregate.get("coverage", {}).get("physical_pages", 0))
    stage1, _ = _checkpoint(stage_folder, "stage1", Stage1Response, "stage1", {
        "document_id": document_id, "batch_id": "stage1-document", "physical_pages": physical_pages,
        "aggregate": aggregate,
    }, transport)
    _write(stage_folder / "stage1_condition_accountability.json", stage1_condition_accountability(aggregate, stage1))
    requirements = stage1["response"]["requirements"]
    stage2, _ = _checkpoint(stage_folder, "stage2", Stage2Response, "stage2", {
        "document_id": document_id, "batch_id": "stage2-requirements", "requirements": requirements,
    }, transport)
    stage3, _ = _checkpoint(stage_folder, "stage3", Stage3Response, "stage3", {
        "document_id": document_id, "batch_id": "stage3-evidence", "requirements": requirements,
        "operational_assessments": stage2["response"]["operational_assessments"],
    }, transport)
    analysis = build_intelligence_analysis(stage_folder, aggregate, stage1, stage2, stage3,
        filename=filename, document_sha256=document_sha256, processor=processor)
    # Point to the source run's manifest rather than requiring a duplicate.
    analysis = analysis.model_copy(update={"audit": analysis.audit.model_copy(update={
        "source_manifest_path": str(folder / "manifest.json"),
    })})
    _write(stage_folder / "intelligence_analysis_v1.json", analysis.model_dump(mode="json"))
    _write(folder / "intelligence_analysis_v1.json", analysis.model_dump(mode="json"))
    return analysis
