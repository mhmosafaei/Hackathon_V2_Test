"""Revalidate an already-persisted AI-first response without contacting any API."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.documents.pdf_parser import parse_pdf
from src.documents.ai_first import validate_and_verify_candidates

folder=Path(sys.argv[1]); output=folder/'candidate_batch_001.json'
record=json.loads(output.read_text()); pages=parse_pdf(folder/'source.pdf').pages
candidates,rejected=validate_and_verify_candidates(record['raw']['candidates'],pages)
record['candidates']=[x.model_dump(mode='json') for x in candidates]; record['rejected']=rejected
output.write_text(json.dumps(record,indent=2)); print(f'valid={len(candidates)} rejected={len(rejected)}')
