"""Offline-only comparison of a source-oriented reference register.

The reference register is evidence for evaluation, never an extraction input.  In
particular, this module must not create candidates or amend a document register.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from .quote_verifier import normalise


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", normalise(value)))


def _overlap(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def _same_page(item: dict, page: int) -> bool:
    return int(item.get("page_number", -1)) == page or page in item.get("pages", [])


def classify_reference_row(row: dict, candidates: Iterable[dict], records: Iterable[dict]) -> dict:
    """Classify one independent source row without treating row matching as legal proof.

    Categories follow the acceptance audit: A is a candidate present but missed by
    a narrow matcher; B is retained source-only material; C has unresolved layout
    context; D has no trustworthy representation; E is an evident duplicate or
    administrative reference; F needs human review.
    """
    source = row.get("Exact source text", "")
    page = int(str(row.get("PDF page", "0") or 0))
    reference = (row.get("Reference") or "").casefold()
    candidate_hits = []
    for candidate in candidates:
        quote = candidate.get("source_quotation", "")
        score = _overlap(source, quote)
        same_identifier = reference and reference in (candidate.get("section") or "").casefold()
        if score >= 0.78 or (same_identifier and score >= 0.50):
            candidate_hits.append((score, candidate))
    if candidate_hits:
        candidate_hits.sort(key=lambda item: item[0], reverse=True)
        return {"category": "A_PRESENT_CANDIDATE", "status": "FULLY_MATCHED",
                "candidate_ids": [item[1]["candidate_id"] for item in candidate_hits[:3]],
                "source_record_ids": [], "confidence": candidate_hits[0][0]}

    record_hits = []
    for record in records:
        if not _same_page(record, page):
            continue
        score = _overlap(source, record.get("source_text", ""))
        # A reference record names table fields; layout extraction stores the
        # source values only.  Seven shared content tokens is meaningful enough
        # to show source retention, but not to assert applicability.
        if score >= 0.65 or len(_tokens(source) & _tokens(record.get("source_text", ""))) >= 7:
            record_hits.append((score, record))
    if record_hits:
        record_hits.sort(key=lambda item: item[0], reverse=True)
        top = record_hits[0][1]
        unresolved = bool(top.get("ambiguity")) or top.get("verification_status") != "SOURCE_VERIFIED"
        return {"category": "C_UNRESOLVED_CONTEXT" if unresolved else "B_SOURCE_ONLY",
                "status": "UNRESOLVED_CONTEXT" if unresolved else "SOURCE_CAPTURED_NO_CANDIDATE",
                "candidate_ids": [], "source_record_ids": [item[1]["source_record_id"] for item in record_hits[:3]],
                "confidence": record_hits[0][0]}

    kind = (row.get("Type") or "").casefold()
    if "administrative" in kind or not _tokens(source):
        return {"category": "E_REFERENCE_NONOPERATIVE_OR_DEFECT", "status": "REFERENCE_RECORD_DEFECT",
                "candidate_ids": [], "source_record_ids": [], "confidence": 0.0}
    return {"category": "D_GENUINELY_ABSENT_OR_F_REVIEW", "status": "MISSING_OR_REVIEW",
            "candidate_ids": [], "source_record_ids": [], "confidence": 0.0}


def classify_reference_rows(rows: Iterable[dict], candidates: list[dict], records: list[dict]) -> tuple[list[dict], dict]:
    results = []
    for row in rows:
        result = classify_reference_row(row, candidates, records)
        results.append({"reference_id": row.get("ID"), "group": row.get("Group"),
                        "reference": row.get("Reference"), "page": row.get("PDF page"), **result})
    return results, dict(Counter(item["category"] for item in results))
