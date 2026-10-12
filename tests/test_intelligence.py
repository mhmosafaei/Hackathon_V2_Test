import json
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.intelligence.contracts import CanonicalAnalysis, Stage1Response
from src.intelligence.service import mock_stage_transport, run_intelligence_pipeline


def aggregate_fixture():
    quote = "Marine operations shall stop when significant wave height exceeds 1.5 m."
    return {
        "document_id": "fixture-doc",
        "candidates": [{
            "candidate_id": "candidate-1", "register_id": "candidate-1", "document_id": "fixture-doc",
            "document_type": "PERMIT", "source_quotation": quote, "page_number": 1,
            "section": "4.1", "obligation": "Stop operations above the stated wave height.",
            "obligation_type": "Operational restriction", "parties": ["Licensee"], "action": "stop",
            "subject": "marine operations", "trigger": None, "deadline": None, "threshold": 1.5,
            "operator": "GT", "unit": "m", "operating_mode": None, "scope": None, "exception": None,
            "evidence": [], "linked_references": [], "ambiguity": [], "confidence": 0.9,
            "state": "SOURCE_VERIFIED", "human_review_required": True, "source_record_ids": ["src-4.1"],
        }],
        "rejected": [], "duplicates": [],
        "source_inventory": [{
            "source_record_id": "src-4.1", "document_id": "fixture-doc", "record_type": "CLAUSE",
            "source_text": quote, "pages": [1], "section_reference": "4.1", "table_reference": None,
            "row_reference": None, "column_labels": [], "applicability": None, "parameter": None,
            "limit_text": None, "reference_period": None, "monitoring_frequency": None,
            "compliance_statistic": None, "operating_mode": None, "layout_provenance": None,
            "related_record_ids": [], "extraction_method": "fixture", "verification_status": "VERIFIED", "ambiguity": [],
        }],
        "coverage": {"physical_pages": 1, "pages": [{"page": 1, "processing": "PROCESSED", "candidate_ids": ["candidate-1"], "semantic_status": "PROCESSED_WITH_OBLIGATIONS"}], "structure": {"numbered_clauses": [{"id": "4.1"}]}},
    }


def _run_dir() -> Path:
    path = Path("tmp") / f"intelligence-test-{uuid4().hex}"
    path.mkdir(parents=True)
    return path


def test_offline_intelligence_pipeline_is_checkpointed_and_non_authorizing():
    tmp_path = _run_dir()
    aggregate = aggregate_fixture()
    analysis = run_intelligence_pipeline(tmp_path, aggregate, filename="fixture.pdf", document_sha256="a" * 64,
                                         transport=mock_stage_transport, processor="MOCK")
    assert analysis.schema_version == "permitpulse.intelligence.v1"
    assert analysis.audit.api_call_count == 0
    assert len(analysis.requirements) == 1
    assert analysis.requirements[0].source_verification == "SOURCE_VERIFIED"
    assert analysis.requirements[0].human_review == "UNREVIEWED"
    assert analysis.work_windows.status == "NOT_EVALUATED"
    assert all(item.approval_status == "PROPOSED" for item in analysis.constraint_proposals)
    stage_folder = next((tmp_path / "intelligence").iterdir())
    assert (stage_folder / "intelligence_stage1.json").exists()
    assert (stage_folder / "intelligence_stage2.json").exists()
    assert (stage_folder / "intelligence_stage3.json").exists()
    first = (stage_folder / "intelligence_stage1.json").read_text(encoding="utf-8")
    second = run_intelligence_pipeline(tmp_path, aggregate, filename="fixture.pdf", document_sha256="a" * 64,
                                       transport=lambda *_: pytest.fail("checkpoint should prevent redispatch"), processor="MOCK")
    assert second.analysis_id == analysis.analysis_id
    assert (stage_folder / "intelligence_stage1.json").read_text(encoding="utf-8") == first


def test_canonical_contract_is_strict_and_schema_valid():
    tmp_path = _run_dir()
    Draft202012Validator.check_schema(CanonicalAnalysis.model_json_schema())
    analysis = run_intelligence_pipeline(tmp_path, aggregate_fixture(), filename="fixture.pdf", document_sha256="b" * 64,
                                         transport=mock_stage_transport, processor="MOCK")
    payload = analysis.model_dump(mode="json")
    Draft202012Validator(CanonicalAnalysis.model_json_schema()).validate(payload)
    stage_folder = next((tmp_path / "intelligence").iterdir())
    stage = json.loads((stage_folder / "intelligence_stage1.json").read_text())["response"]
    assert Stage1Response.model_validate(stage).requirements[0].requirement_id == "candidate-1"
    stage["unexpected"] = True
    with pytest.raises(ValidationError):
        Stage1Response.model_validate(stage)


def test_stage_cache_is_isolated_by_document_and_model(monkeypatch):
    root = _run_dir()
    monkeypatch.setenv("OPENAI_MODEL", "model-a")
    run_intelligence_pipeline(root, aggregate_fixture(), filename="fixture.pdf", document_sha256="d" * 64,
                              transport=mock_stage_transport, processor="OPENAI")
    monkeypatch.setenv("OPENAI_MODEL", "model-b")
    run_intelligence_pipeline(root, aggregate_fixture(), filename="fixture.pdf", document_sha256="d" * 64,
                              transport=mock_stage_transport, processor="OPENAI")
    run_intelligence_pipeline(root, aggregate_fixture(), filename="fixture.pdf", document_sha256="e" * 64,
                              transport=mock_stage_transport, processor="MOCK")
    # The immutable stage responses cannot be reused across either model or
    # source-document identity.  No transport in this test reaches a network.
    assert len(list((root / "intelligence").iterdir())) == 3


def test_stage1_accountability_preserves_each_numbered_source_condition():
    root = _run_dir()
    run_intelligence_pipeline(root, aggregate_fixture(), filename="fixture.pdf", document_sha256="f" * 64,
                              transport=mock_stage_transport, processor="MOCK")
    stage_folder = next((root / "intelligence").iterdir())
    report = json.loads((stage_folder / "stage1_condition_accountability.json").read_text())
    assert report["summary"] == {"total": 1, "fully_interpreted": 1, "partially_interpreted": 0, "unresolved": 0}
    row = report["numbered_conditions"][0]
    assert row["condition_id"] == "4.1"
    assert row["authority_status"] == "OPERATIVE"
    assert row["linked_requirement_ids"] == ["candidate-1"]
