"""Offline recovery of a document-run cache; never calls an external API."""
import json,sys
from pathlib import Path
root=Path(__file__).parents[1]; sys.path.insert(0,str(root))
from src.documents.pdf_parser import parse_pdf
from src.documents.validator import recover_conditions
pdf=Path(sys.argv[1]); folder=Path(sys.argv[2]); pages=parse_pdf(pdf).pages
totals={'raw':0,'recovered':0,'rejected':0,'duplicates':0,'quote_verified':0,'quote_failed':0}; all_conditions=[]
for file in sorted(folder.glob('page_*.json')):
 page=int(file.stem.split('_')[1]); original=json.loads(file.read_text()); records,audit,errors=recover_conditions(original['raw']['conditions'],pages,page)
 payload={'processing_schema_version':'recovery-v1','original_file':file.name,'trusted_page':page,'conditions':[x.model_dump(mode='json') for x in records],'audit':audit,'errors':errors}; (folder/f'{file.stem}_recovered.json').write_text(json.dumps(payload,indent=2))
 totals['raw']+=len(original['raw']['conditions']); totals['recovered']+=len(records); totals['rejected']+=len(errors); totals['duplicates']+=sum(x['disposition']=='EXACT_DUPLICATE_REMOVED' for x in audit); totals['quote_verified']+=sum(x.quote_verified for x in records); totals['quote_failed']+=sum(not x.quote_verified for x in records); all_conditions.extend(payload['conditions'])
(folder/'recovery_aggregate.json').write_text(json.dumps({'processing_schema_version':'recovery-v1','totals':totals,'conditions':all_conditions},indent=2)); print(json.dumps(totals,indent=2))
