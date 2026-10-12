import base64,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
from dotenv import load_dotenv
import pymupdf
sys.path.insert(0,str(Path(__file__).parents[1]))
from openai import OpenAI
from src.documents.evidence_contract_v2 import inventory,validate,VERSION
R=Path(__file__).parents[1];N=R/'cache/document_runs/2a23b1d45e13b328b78f376315cc799f863eee93315fbc0282c63d3e733b9d31';O=N/'controlled_s31_evaluation'/'v2_preflight';H='a9dec163f30956e1e4b99208df4b482a54df1d5db666598ef9f93fee2a1d19da'
def main():
 load_dotenv(R/'.env'); model=os.getenv('OPENAI_MODEL'); ledger=O/'dispatch_ledger_v2.json'; state=json.loads(ledger.read_text())
 if state.get('status')!='PENDING_AUTHORIZATION' or hashlib.sha256((N/'source.pdf').read_bytes()).hexdigest()!=H: raise RuntimeError('v2 preflight or ledger failed')
 audit=json.loads((N/'table_layout_audit.json').read_text());t=next(x for x in audit if x['id']=='p21-t1');i=inventory(t)
 if len(i['cells'])!=77: raise RuntimeError('cell count')
 attempt='v2-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); ledger.write_text(json.dumps({'contract_version':VERSION,'status':'DISPATCH_STARTED','attempt_id':attempt,'max_dispatches':1,'retries':0,'model':model},indent=2))
 d=N/'controlled_s31_evaluation'/attempt;d.mkdir(); img=(N/'controlled_s31_evaluation'/'page21_s31.png').read_bytes()
 schema={'type':'object','additionalProperties':False,'properties':{'contract_version':{'type':'string'},'relationships':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{'relationship_id':{'type':'string'},'relationship_type':{'type':'string'},'value':{'type':'string'},'value_cells':{'type':'array','items':{'type':'string'}},'context_cells':{'type':'array','items':{'type':'string'}},'header_cells':{'type':'array','items':{'type':'string'}},'geometry_basis':{'type':'array','items':{'type':'string'}},'confidence':{'type':'number'},'unresolved_dependencies':{'type':'array','items':{'type':'string'}}},'required':['relationship_id','relationship_type','value','value_cells','context_cells','header_cells','geometry_basis','confidence','unresolved_dependencies']} }},'required':['contract_version','relationships']}
 prompt='Return only v2 source-backed table structure. Cite exact supplied IDs. Do not guess unresolved context.'
 c=OpenAI(api_key=os.getenv('OPENAI_API_KEY'),max_retries=0,timeout=90);resp=c.responses.create(model=model,input=[{'role':'user','content':[{'type':'input_text','text':prompt+'\n'+json.dumps(i)},{'type':'input_image','image_url':'data:image/png;base64,'+base64.b64encode(img).decode()}]}],text={'format':{'type':'json_schema','name':'v2','strict':True,'schema':schema}})
 raw=resp.output_text; (d/'raw_response.json').write_text(raw);p=json.loads(raw);v=validate(t,{'contract_version':p['contract_version'],'claims':[{'value':x['value'],'value_cells':x['value_cells'],'context_cells':x['context_cells'],'header_cells':x['header_cells'],'geometry_basis':x['geometry_basis']} for x in p['relationships']]});(d/'validation.json').write_text(json.dumps(v,indent=2));ledger.write_text(json.dumps({'contract_version':VERSION,'status':'SUCCEEDED','attempt_id':attempt,'max_dispatches':1,'request_id':getattr(resp,'_request_id',None),'usage':resp.usage.model_dump() if resp.usage else None},indent=2));print(json.dumps({'attempt':attempt,'relationships':len(p['relationships']),'validation':v,'request_id':getattr(resp,'_request_id',None),'usage':resp.usage.model_dump() if resp.usage else None},default=str))
if __name__=='__main__':main()
