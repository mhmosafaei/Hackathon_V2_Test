"""One-request-only authorized S3.1 page-21 evaluation; never retries."""
import base64, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import pymupdf
from openai import OpenAI
sys.path.insert(0,str(Path(__file__).parents[1]))
from src.documents.hybrid_table import validate_proposal

ROOT=Path(__file__).parents[1]; NS=ROOT/'cache/document_runs/2a23b1d45e13b328b78f376315cc799f863eee93315fbc0282c63d3e733b9d31'; PDF=NS/'source.pdf'; EXPECTED='a9dec163f30956e1e4b99208df4b482a54df1d5db666598ef9f93fee2a1d19da'
def main():
 load_dotenv(ROOT/'.env'); model=os.getenv('OPENAI_MODEL'); key=os.getenv('OPENAI_API_KEY')
 if not key or not model or hashlib.sha256(PDF.read_bytes()).hexdigest()!=EXPECTED: raise RuntimeError('preflight failed')
 tables=json.loads((NS/'table_layout_audit.json').read_text()); table=next(x for x in tables if x['id']=='p21-t1'); box=table['bbox']; doc=pymupdf.open(PDF); page=doc[20]
 if not page.rect.contains(pymupdf.Rect(box)): raise RuntimeError('crop outside authorized page')
 pix=page.get_pixmap(clip=pymupdf.Rect(box),matrix=pymupdf.Matrix(2,2),alpha=False); image=pix.tobytes('png'); cells=[{'id':f"r{c['row']}c{c['column']}",'text':c['text'],'bbox':c['bbox'],'header':c['header'],'ambiguous':c['ambiguous']} for row in table['rows'] for c in row]
 out=NS/'controlled_s31_evaluation'; out.mkdir(exist_ok=True)
 if (out/'raw_model_response.json').exists(): raise RuntimeError('successful response already exists; refusing redispatch')
 ledger=out/'dispatch_ledger.json'; ledger.write_text(json.dumps({'authorized_dispatches':1,'attempted_at':datetime.now(timezone.utc).isoformat(),'outcome':'UNKNOWN','model':model}))
 (out/'page21_s31.png').write_bytes(image)
 manifest={'source_sha256':EXPECTED,'page_index':20,'physical_page':21,'crop':box,'image_dimensions':[pix.width,pix.height],'model':model,'timestamp':datetime.now(timezone.utc).isoformat(),'request_count':1,'cells':cells,'headers':table['headers']}; (out/'preflight.json').write_text(json.dumps(manifest,indent=2))
 prompt='Return JSON only: {"confidence":number,"relationships":[{"cells":[[row,column]],"values":[strings],"kind":string,"evidence":string}],"unresolved":[string]}. Cite only supplied cells/values. Describe structural header/row relationships only; do not interpret legal obligations or invent values.'
 client=OpenAI(api_key=key,max_retries=0,timeout=90)
 response=client.responses.create(model=model,input=[{'role':'user','content':[{'type':'input_text','text':prompt+'\nHeaders:'+json.dumps(table['headers'])+'\nCells:'+json.dumps(cells)},{'type':'input_image','image_url':'data:image/png;base64,'+base64.b64encode(image).decode()}]}])
 raw=response.output_text; (out/'raw_model_response.json').write_text(raw); ledger.write_text(json.dumps({'authorized_dispatches':1,'attempted_at':datetime.now(timezone.utc).isoformat(),'outcome':'RESPONSE_RECEIVED','model':model,'request_id':getattr(response,'_request_id',None)}))
 try: proposal=json.loads(raw); validation=validate_proposal(table,proposal)
 except Exception as exc: validation={'state':'STRUCTURE_REVIEW_REQUIRED','errors':[{'reason':type(exc).__name__}],'review_required':True}
 usage=getattr(response,'usage',None); (out/'validation.json').write_text(json.dumps({'validation':validation,'usage':usage.model_dump() if usage else None},indent=2,default=str))
 print(json.dumps({'model':model,'validation':validation,'usage':usage.model_dump() if usage else None}))
if __name__=='__main__': main()
