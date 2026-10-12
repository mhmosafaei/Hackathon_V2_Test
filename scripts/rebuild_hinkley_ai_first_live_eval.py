"""Offline-only rebuild from immutable raw response artifacts."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).parents[1]; sys.path.insert(0,str(ROOT))
from src.documents.pdf_parser import parse_pdf
from src.documents.ai_first import validate_and_verify_candidates
from src.documents.source_inventory import build_source_inventory,link_candidates
D=ROOT/'cache/document_runs/2a23b1d45e13b328b78f376315cc799f863eee93315fbc0282c63d3e733b9d31/HINKLEY_AI_FIRST_LIVE_EVAL_01'
pages=parse_pdf(D/'source.pdf').pages; candidates=[]; rejected=[]; batch_stats=[]
for path in sorted(D.glob('candidate_batch_*.json')):
 record=json.loads(path.read_text()); valid,invalid=validate_and_verify_candidates(record['raw'].get('candidates',[]),pages)
 # Preserve raw response unchanged; write a separate recovery result.
 candidates.extend(x.model_dump(mode='json') for x in valid); rejected.extend([{**x,'batch':record['batch']} for x in invalid]); batch_stats.append({'batch':record['batch'],'raw':len(record['raw'].get('candidates',[])),'valid':len(valid),'rejected':len(invalid)})
seen=set(); unique=[]; duplicates=[]
for c in candidates:
 key=(c['page_number'],c['source_quotation'])
 (duplicates if key in seen else unique).append(c); seen.add(key)
inventory=build_source_inventory('a9dec163f30956e1',pages,D/'source.pdf'); link_candidates(unique,inventory)
payload={'run_id':'HINKLEY_AI_FIRST_LIVE_EVAL_01','recovery_method':'offline-state-normalization-v1','raw_candidate_count':len(candidates)+len(rejected),'candidates':unique,'rejected':rejected,'duplicates':duplicates,'source_inventory':[x.model_dump(mode='json') for x in inventory],'batch_stats':batch_stats,'coverage':{'physical_pages':46,'processed_pages':list(range(1,47))}}
(D/'recovered_comprehensive_analysis.json').write_text(json.dumps(payload,indent=2)); print(json.dumps({'raw':payload['raw_candidate_count'],'recovered':len(unique),'rejected':len(rejected),'duplicates':len(duplicates),'source_records':len(inventory)}))
