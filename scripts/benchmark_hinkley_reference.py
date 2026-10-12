"""Evaluation-only comparison; reference rows never enter production extraction."""
import csv,json,re,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from src.documents.quote_verifier import normalise
from src.documents.benchmarking import classify_reference_rows
RUN=ROOT/'cache/document_runs/2a23b1d45e13b328b78f376315cc799f863eee93315fbc0282c63d3e733b9d31/HINKLEY_AI_FIRST_LIVE_EVAL_01'
REF=Path(r'C:\Users\nedan\Downloads\Hinkley_Permit_Extracted_Register.csv')
data=json.loads((RUN/'recovered_comprehensive_analysis.json').read_text()); candidates=data['candidates']
def match(row):
 text=normalise(row['Exact source text']); page=str(row['PDF page']).strip()
 hits=[c for c in candidates if str(c['page_number'])==page and (text in normalise(c['source_quotation']) or normalise(c['source_quotation']) in text)]
 if hits:return 'FULLY_MATCHED',hits
 tokens=set(re.findall(r'[a-z]{5,}',text)); near=[c for c in candidates if str(c['page_number'])==page and len(tokens & set(re.findall(r'[a-z]{5,}',normalise(c['source_quotation']))))>=6]
 return ('PARTIALLY_MATCHED' if near else 'MISSING_FROM_PERMITPULSE'),near
rows=[]
with REF.open(encoding='utf-8-sig',newline='') as f:
 for row in csv.DictReader(f):
  status,hits=match(row); rows.append({'reference_id':row['ID'],'group':row['Group'],'reference':row['Reference'],'page':row['PDF page'],'status':status,'candidate_ids':[x['candidate_id'] for x in hits],'notes':'automatic matching; disputed/missing table context requires PDF review'})
summary=Counter(x['status'] for x in rows); groups=defaultdict(Counter)
for x in rows:groups[x['group']][x['status']]+=1
out={'reference_rows':len(rows),'summary':dict(summary),'by_group':{k:dict(v) for k,v in groups.items()},'rows':rows,'method':'page plus normalized source-span containment; token overlap is partial only'}
(out['audit_rows'], out['audit_category_summary'])=classify_reference_rows(list(csv.DictReader(REF.open(encoding='utf-8-sig',newline=''))), candidates, data.get('source_inventory',[]))
(out['audit_by_group'])={}
for item in out['audit_rows']:
 out['audit_by_group'].setdefault(item['group'],Counter())[item['category']]+=1
out['audit_by_group']={key:dict(value) for key,value in out['audit_by_group'].items()}
# Keep the legacy narrow matcher intact for reproducibility, then explicitly
# account for precisely the rows it called missing.  This prevents a broader
# source-inventory match from being misreported as a recovered GPT obligation.
legacy_missing={row['reference_id'] for row in rows if row['status']=='MISSING_FROM_PERMITPULSE'}
out['legacy_missing_audit_rows']=[row for row in out['audit_rows'] if row['reference_id'] in legacy_missing]
out['legacy_missing_audit_summary']=dict(Counter(row['category'] for row in out['legacy_missing_audit_rows']))
(RUN/'independent_benchmark.json').write_text(json.dumps(out,indent=2));print(json.dumps({'reference_rows':len(rows),'summary':dict(summary)}))
