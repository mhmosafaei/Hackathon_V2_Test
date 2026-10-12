"""Persistent human-review state; confirmation never bypasses quote verification."""
import json
from pathlib import Path
from datetime import datetime, timezone
from src.models.extracted_condition import ExtractedCondition
from src.models.common import ReviewState
from src.documents.quote_verifier import verify_quote
from src.documents.pdf_parser import parse_pdf

def load_conditions(root: Path) -> list[dict]:
    return json.loads((root/'cache/extractions/ml2025054/aggregate.json').read_text())['conditions']

def load_recovery(root: Path) -> list[dict]:
    output=[]
    for page in range(4,11):
        p=root/f'cache/extractions/ml2025054/page_{page:02}.json'
        d=json.loads(p.read_text())
        for raw, error in zip(d['raw'].get('conditions',[]), d['validation_errors']):
            output.append({'page':page,'raw':raw,'validation_error':error})
    return output

def review_path(root: Path) -> Path: return root/'cache/extractions/ml2025054/review_decisions.json'
def load_decisions(root: Path) -> dict:
    p=review_path(root); return json.loads(p.read_text()) if p.exists() else {}
def save_decision(root: Path, condition_id: str, decision: str, reviewer: str, manual_source_verified: bool=False) -> dict:
    conditions={c['condition_id']:c for c in load_conditions(root)}; c=conditions[condition_id]
    if decision=='CONFIRMED' and not c['quote_verified'] and not manual_source_verified:
        raise ValueError('unverified quotations require a separately audited manual source verification')
    d=load_decisions(root); d[condition_id]={'decision':decision,'reviewer':reviewer,'at':datetime.now(timezone.utc).isoformat(),'manual_source_verified':manual_source_verified}
    review_path(root).write_text(json.dumps(d,indent=2),encoding='utf-8'); return d[condition_id]

def recover(root: Path, raw: dict, page: int) -> ExtractedCondition:
    condition=ExtractedCondition.model_validate(raw)
    match=verify_quote(condition.source_text,parse_pdf(root/'data/permits/ML2025054.pdf').pages,page)
    return condition.model_copy(update={'quote_verified':match.verified,'review_required':not match.verified})
