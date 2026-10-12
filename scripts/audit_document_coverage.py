"""Build a deterministic numbered-condition inventory from a PDF and recovered cache."""
import json,re,sys
from pathlib import Path
root=Path(__file__).parents[1];sys.path.insert(0,str(root))
from src.documents.pdf_parser import parse_pdf
from src.documents.quote_verifier import normalise
pdf,folder=Path(sys.argv[1]),Path(sys.argv[2]); pages=parse_pdf(pdf).pages
start=next(p.page_number for p in pages if re.search(r'(?i)part\s*2\s*[-–]?\s*conditions',p.text)); end=next((p.page_number for p in pages if p.page_number>start and re.search(r'(?im)^\s*notes\s*$',p.text)),len(pages)+1)
selected=[p for p in pages if start<=p.page_number<end]; joined='\n'.join(p.text for p in selected)
matches=list(re.finditer(r'(?m)^\s*(\d{1,2})\.\s+',joined)); recovered=json.loads((folder/'recovery_aggregate.json').read_text())['conditions']; inventory=[]
for i,m in enumerate(matches):
 number=int(m.group(1)); span=joined[m.start():matches[i+1].start() if i+1<len(matches) else len(joined)]; records=[r for r in recovered if re.match(rf'^{number}(?:\D|$)',r['condition_id'])]
 verified=[r for r in records if r['quote_verified']]; inventory.append({'condition_number':number,'source_text':span,'pages':[p.page_number for p in selected if normalise(p.text)[:20] in normalise(span)],'records':[r['condition_id'] for r in records],'status':'CAPTURED' if verified else 'REVIEW_REQUIRED' if records else 'MISSING','reason':'at least one quote-verified recovered record' if verified else 'records require source review' if records else 'no recovered record'})
result={'document':pdf.name,'physical_pages':len(pages),'conditions_section_pages':[p.page_number for p in selected],'source_conditions_inventoried':len(inventory),'summary':{s:sum(x['status']==s for x in inventory) for s in ('CAPTURED','REVIEW_REQUIRED','MISSING')},'conditions':inventory}; (folder/'coverage_audit.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result['summary']))
