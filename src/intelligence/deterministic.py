"""Local, non-authorizing permit projection from immutable candidate evidence."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re

from src.documents.exports import csv_bytes, excel_bytes, export_json
from src.documents.quote_verifier import normalise
from src.mapping.capability_registry import derive_automation_status
from src.models.common import SourceType
from src.permit.classification import classify
from .contracts import (Audit, CanonicalAnalysis, DataNeed, DataFeasibility,
                        DocumentRecord, OperationalAssessment, ReviewFlag, StageRun, WorkWindowStatus)
from .service import _source, _requirement, _coverage, _role

VERSION = "deterministic-permit-v1"


def build_projection(aggregate: dict, *, filename: str, document_sha256: str, analysis_id: str,
                     page_texts: dict[int, str] | None = None) -> tuple[CanonicalAnalysis, dict]:
    """Never invent candidates, legal interpretations, thresholds or approvals.

    Page corrections require unique exact-normalized inventory evidence. Original
    attribution and verification states are retained separately in the audit.
    """
    sources = aggregate.get("source_inventory", [])
    projected = deepcopy(aggregate)
    corrections, mapping, requirements, assessments, needs, feasibility = [], [], [], [], [], []
    for candidate in projected.get("candidates", []):
        quote = normalise(candidate["source_quotation"])
        matches = [s for s in sources if quote and quote in normalise(s.get("source_text", ""))]
        # Prefer the smallest containing source span; equal alternatives remain ambiguous.
        matches.sort(key=lambda s: len(normalise(s.get("source_text", ""))))
        certain = matches and (len(matches) == 1 or len(normalise(matches[0]["source_text"])) < len(normalise(matches[1]["source_text"])))
        if certain:
            source = matches[0]
            candidate["source_record_ids"] = [source["source_record_id"]]
            pages = source.get("pages") or []
            if page_texts is not None:
                pages = [number for number, text in page_texts.items() if quote in normalise(text)]
            if len(pages) == 1 and candidate["page_number"] != pages[0]:
                corrections.append({"candidate_id": candidate["candidate_id"], "original_page": candidate["page_number"],
                                    "source_page": pages[0], "source_record_id": source["source_record_id"],
                                    "basis": "Unique exact-normalized quotation within source inventory"})
                candidate["original_page_number"] = candidate["page_number"]
                candidate["page_number"] = pages[0]
            condition = str(source.get("section_reference") or "")
            if source.get("record_type") == "CLAUSE" and re.fullmatch(r"\d+(?:\.\d+)*", condition):
                candidate["original_section"] = candidate.get("section")
                candidate["section"] = condition
        requirement = _requirement(candidate, candidate.get("source_record_ids") or [])
        # Quote matching is not proof of semantic or legal completeness.
        requirement.atomic_completeness = "UNRESOLVED"
        requirements.append(requirement)
        role = _role(requirement)
        binding, automation = classify(None, "OTHER", [candidate["source_quotation"]])
        # Existing manual-source capability is appropriate for an explicit
        # reporting/approval action, but never establishes that evidence exists.
        if binding.source_type == SourceType.UNKNOWN and role in {"REPORTING_OR_ADMINISTRATION", "NOTIFICATION_OR_APPROVAL"}:
            binding = binding.model_copy(update={"source_type": SourceType.MANUAL_INPUT, "deciding": False})
            automation = derive_automation_status(variable=None, required_source=SourceType.MANUAL_INPUT, has_deciding_adapter=False)
        mapping.append({"requirement_id": requirement.requirement_id, "condition_id": requirement.parent_condition_id,
                        "source_ids": requirement.source_ids, "evidence_source": binding.source_type.value,
                        "automation_status": automation.value, "evidence_availability": "DATA_REQUIRED",
                        "mapping_basis": "Existing classify/derive_automation_status; no adapter or evidence acquired",
                        "executable": False})
        assessments.append(OperationalAssessment(requirement_id=requirement.requirement_id, primary_role=role,
            lifecycle_phases=requirement.lifecycle_phases, evidence_categories=[binding.source_type.value, automation.value],
            rationale="Conservative deterministic mapping; legal authority and interpretation require human review.",
            uncertainty_reasons=["No semantic intelligence inference or deciding-evidence verification performed."]))
        source_type = binding.source_type
        domain, kind = ("LOCAL_MEASUREMENT", "DIRECT_LOCAL_MEASUREMENT") if source_type == SourceType.LOCAL_SENSOR else ("EQUIPMENT_OR_MANUAL", "MANUAL_CONFIRMATION") if source_type in {SourceType.MANUAL_INPUT, SourceType.AUTHORITY_APPROVAL} else ("EQUIPMENT_OR_MANUAL", "UNKNOWN") if source_type == SourceType.AIS_GNSS else ("OTHER", "UNKNOWN")
        need_id = "need-" + requirement.requirement_id
        needs.append(DataNeed(data_need_id=need_id, requirement_ids=[requirement.requirement_id],
            parameter_key=source_type.value.lower(), parameter_label=source_type.value, domain=domain, evidence_kind=kind,
            relevance_reason="Source-backed candidate mapped using existing evidence classifier; unknowns remain unresolved."))
        feasibility.append(DataFeasibility(data_need_id=need_id,
            status="REQUIRES_LOCAL_MEASUREMENT" if source_type == SourceType.LOCAL_SENSOR else "REQUIRES_MANUAL_CONFIRMATION" if kind == "MANUAL_CONFIRMATION" else "NOT_CHECKED",
            fit_reason="DATA REQUIRED. No location-matched environmental availability has been verified."))

    groups = []
    for source in sources:
        condition = str(source.get("section_reference") or "")
        if source.get("record_type") != "CLAUSE" or not re.fullmatch(r"\d+(?:\.\d+)*", condition):
            continue
        source_id = source["source_record_id"]
        linked = [c for c in projected["candidates"] if source_id in c.get("source_record_ids", [])]
        # Number prefixes may establish a review lead, not verified evidence.
        leads = [c for c in projected["candidates"] if re.match(rf"^\s*{re.escape(condition)}\.\s", c["source_quotation"])]
        linked = linked or leads
        verified = [c for c in linked if c.get("state") == "SOURCE_VERIFIED"]
        full = any(normalise(source["source_text"]) in normalise(c["source_quotation"]) for c in verified)
        status = "CAPTURED" if full else "PARTIAL" if verified else "REVIEW_REQUIRED" if linked else "NOT_CAPTURED"
        groups.append({"condition_id": condition, "page": min(source.get("pages") or [0]),
                       "source_record_id": source_id, "source_quote": source["source_text"], "status": status,
                       "candidate_ids": [c["candidate_id"] for c in linked],
                       "basis": "Exact normalized source-span coverage, not semantic completeness"})
    summary = {state: sum(g["status"] == state for g in groups) for state in ("CAPTURED", "PARTIAL", "REVIEW_REQUIRED", "NOT_CAPTURED")}
    coverage = _coverage(projected, requirements)
    coverage.numbered_conditions = [g["condition_id"] for g in groups]
    coverage.unlinked_condition_ids = [g["condition_id"] for g in groups if g["status"] != "CAPTURED"]
    coverage.completeness = "PARTIAL" if coverage.unlinked_condition_ids or not aggregate.get("coverage", {}).get("processing_complete", True) else "COMPLETE_WITH_REVIEW"
    # Reconcile physical-page counts after conservative attribution corrections.
    for page in coverage.page_results:
        page.requirement_count = sum(r.page_start <= page.page_number <= r.page_end for r in requirements)
    flags = [ReviewFlag(flag_id="review-" + r.requirement_id, related_requirement_ids=[r.requirement_id], related_source_ids=r.source_ids,
        severity="HIGH" if r.source_verification != "SOURCE_VERIFIED" else "MEDIUM", category="QUOTE" if r.source_verification != "SOURCE_VERIFIED" else "AUTHORITY",
        message=f"{r.source_verification}; human review required; non-executable.", recommended_action="Inspect source, authority and evidence before explicit review.") for r in requirements]
    flags.extend(ReviewFlag(flag_id="gap-" + g["source_record_id"], related_source_ids=[g["source_record_id"]], severity="HIGH", category="COVERAGE",
        message=f"Condition {g['condition_id']}: {g['status']}", recommended_action="Review original source; do not fabricate a missing candidate.") for g in groups if g["status"] != "CAPTURED")
    stages = [StageRun(stage=s, status="COMPLETED", processor="DETERMINISTIC") for s in ("DOCUMENT_EXTRACTION", "OPERATIONAL_RELEVANCE", "ENVIRONMENTAL_MAPPING")]
    stages += [StageRun(stage="DATA_FEASIBILITY", status="BLOCKED", processor="DETERMINISTIC", error_messages=["Deciding evidence not verified."]), StageRun(stage="WORK_WINDOW_EVALUATION", status="NOT_APPLICABLE", processor="NONE")]
    analysis = CanonicalAnalysis(analysis_id=analysis_id, document=DocumentRecord(document_id=aggregate["document_id"], filename=filename, sha256=document_sha256, title=filename, physical_pages=coverage.physical_pages),
        coverage=coverage, stage_runs=stages, source_inventory=[_source(s) for s in sources], definitions=[], requirements=requirements,
        operational_assessments=assessments, constraint_proposals=[], data_needs=needs, data_feasibility=feasibility, review_flags=flags,
        work_windows=WorkWindowStatus(blocking_reasons=["Human review and deciding evidence required; no WORK authorization."]),
        audit=Audit(analysis_version=VERSION, api_call_count=0, notes=["Local projection only; no Stage 1/2/3 OpenAI calls.", "Source verification is preserved; semantic authority is unresolved."]))
    projected["condition_groups"] = groups
    projected["evidence_mapping"] = mapping
    projected["attribution_corrections"] = corrections
    projected["coverage"]["condition_groups"] = groups
    projected["coverage"]["source_conditions_inventoried"] = len(groups)
    projected["coverage"]["condition_summary"] = summary
    projected["coverage"].setdefault('summary', {}).update({
        'CAPTURED': summary['CAPTURED'], 'MISSING': summary['NOT_CAPTURED'],
        'PARTIALLY_CAPTURED': summary['PARTIAL'], 'REVIEW_REQUIRED': summary['REVIEW_REQUIRED'],
    })
    projected["coverage"]["semantic_coverage_complete"] = False
    return analysis, projected


def persist_projection(folder: Path, *, filename: str, document_sha256: str) -> Path:
    """Add derived artifacts only; never overwrite candidate/ledger/review history."""
    raw_path = folder / "candidate_aggregate.json"
    raw_bytes = raw_path.read_bytes()
    aggregate = json.loads(raw_bytes)
    page_texts = None
    if (folder / 'source.pdf').exists():
        from src.documents.pdf_parser import parse_pdf
        source_bytes = (folder / 'source.pdf').read_bytes()
        if sha256(source_bytes).hexdigest() != document_sha256:
            raise ValueError('PDF identity mismatch; refusing normalization')
        page_texts = {p.page_number: p.text for p in parse_pdf(folder / 'source.pdf').pages}
    target = folder / VERSION
    target.mkdir(exist_ok=True)
    analysis, projected = build_projection(aggregate, filename=filename, document_sha256=document_sha256, analysis_id=folder.name, page_texts=page_texts)
    analysis.audit.raw_response_paths = [str(raw_path)]
    analysis.audit.source_manifest_path = str(folder / "manifest.json")
    analysis.audit.notes.append("Parent aggregate SHA256: " + sha256(raw_bytes).hexdigest())
    payload = analysis.model_dump(mode="json")
    (target / "intelligence_analysis_v1.json").write_bytes(export_json(payload))
    (target / "candidate_aggregate.json").write_bytes(export_json(projected))
    (target / "coverage_audit.json").write_bytes(export_json(projected["coverage"]))
    (target / "requirements.csv").write_bytes(csv_bytes([{**r, **next(m for m in projected["evidence_mapping"] if m["requirement_id"] == r["requirement_id"])} for r in payload["requirements"]]))
    workbook = {**payload, "condition_groups": projected["condition_groups"], "evidence_mapping": projected["evidence_mapping"], "attribution_corrections": projected["attribution_corrections"], "duplicates": projected.get("duplicates", [])}
    (target / "intelligence.xlsx").write_bytes(excel_bytes(workbook))
    (target / "normalization_audit.json").write_bytes(export_json({"version": VERSION, "parent_aggregate_sha256": sha256(raw_bytes).hexdigest(), "condition_groups": projected["condition_groups"], "evidence_mapping": projected["evidence_mapping"], "attribution_corrections": projected["attribution_corrections"], "duplicates": projected.get("duplicates", [])}))
    return target / "intelligence_analysis_v1.json"
