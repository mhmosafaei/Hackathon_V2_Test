"""Offline final acceptance audit; never contacts an AI provider or alters reviews."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT=Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from src.documents.pdf_parser import parse_pdf
from src.documents.quote_verifier import normalise

RUN=ROOT/'cache/document_runs/2a23b1d45e13b328b78f376315cc799f863eee93315fbc0282c63d3e733b9d31/HINKLEY_AI_FIRST_LIVE_EVAL_01'
SOURCE=RUN/'source.pdf'
REFERENCE=Path(r'C:\Users\nedan\Downloads\Hinkley_Permit_Extracted_Register.csv')
EXPECTED='a9dec163f30956e1e4b99208df4b482a54df1d5db666598ef9f93fee2a1d19da'

def page_contains(page_text: str, span: str) -> bool:
    """Use a 12-token source sequence: robust to PDF line wrapping, not fuzzy semantics."""
    page=normalise(page_text); tokens=normalise(span).split()
    if not tokens: return False
    chunks=[' '.join(tokens[index:index+12]) for index in range(0,max(1,len(tokens)-11),12)]
    return any(chunk in page for chunk in chunks if len(chunk.split()) >= 4)

def main() -> None:
    checksum=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if checksum != EXPECTED: raise SystemExit('source checksum mismatch')
    analysis=json.loads((RUN/'recovered_comprehensive_analysis.json').read_text())
    benchmark=json.loads((RUN/'independent_benchmark.json').read_text())
    pages={page.page_number:page.text for page in parse_pdf(SOURCE).pages}
    with REFERENCE.open(encoding='utf-8-sig',newline='') as handle: rows=list(csv.DictReader(handle))
    # two representative source records per group plus high-risk numeric/table rows.
    samples=[]; seen=Counter()
    for row in rows:
        group=row['Group']
        high_risk=group in {'Emission limits / monitoring','Discharge and monitoring points'}
        if seen[group] < 2 or (high_risk and len([x for x in samples if x['group']==group]) < 4):
            page=int(row['PDF page']); linear=page_contains(pages[page],row['Exact source text'])
            samples.append({'reference_id':row['ID'],'group':group,'reference':row['Reference'],'page':page,'source_span_present_on_page':linear}); seen[group]+=1
    audit_lookup={row['reference_id']:row for row in benchmark['audit_rows']}
    for sample in samples:
        result=audit_lookup[sample['reference_id']]
        sample.update(category=result['category'],candidate_ids=result['candidate_ids'],source_record_ids=result['source_record_ids'])
        if not sample['source_span_present_on_page'] and sample['reference'].upper().startswith('S') and sample['source_record_ids']:
            sample['source_span_check']='LAYOUT_SERIALIZATION_NONLINEAR'
        else:
            sample['source_span_check']='LINEAR_MATCH' if sample['source_span_present_on_page'] else 'REVIEW_REQUIRED'
    out={'source_sha256':checksum,'pages':len(pages),'candidate_count':len(analysis['candidates']),
         'source_record_count':len(analysis['source_inventory']),'representative_material_records_reviewed':len(samples),
         'linear_source_span_matches':sum(item['source_span_check']=='LINEAR_MATCH' for item in samples),
         'layout_serialization_non_linear':sum(item['source_span_check']=='LAYOUT_SERIALIZATION_NONLINEAR' for item in samples),
         'source_span_review_required':sum(item['source_span_check']=='REVIEW_REQUIRED' for item in samples),
         'sample_category_summary':dict(Counter(item['category'] for item in samples)),
         'samples':samples,
         'note':'This is a direct source-span audit of a stratified sample, not an exhaustive legal-semantic validation.'}
    (RUN/'final_acceptance_sample_audit.json').write_text(json.dumps(out,indent=2))
    print(json.dumps({key:out[key] for key in out if key!='samples'}))

if __name__=='__main__': main()
