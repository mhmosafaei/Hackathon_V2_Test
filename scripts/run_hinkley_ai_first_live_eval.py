"""One authorized, capped Hinkley AI-first evaluation. Never retry a dispatch."""
from __future__ import annotations
import hashlib, json, os, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
SOURCE=ROOT/'cache/document_runs/2a23b1d45e13b328b78f376315cc799f863eee93315fbc0282c63d3e733b9d31/source.pdf'
RUN=SOURCE.parent/'HINKLEY_AI_FIRST_LIVE_EVAL_01'
SHA='a9dec163f30956e1e4b99208df4b482a54df1d5db666598ef9f93fee2a1d19da'
MODEL='gpt-4.1-mini'; CAP=9; BUDGET=1.00; INPUT_RATE=.40/1_000_000; OUTPUT_RATE=1.60/1_000_000

def fail(message):
 print(f'PREFLIGHT_FAILED: {message}'); raise SystemExit(2)
def cost_bound(packet):
 # Conservative text 1 token/2 chars, 3 full-page high-detail images <=10k each, and 6k output.
 text=sum(len(p['text']) for p in packet['pages']); images=sum(bool(__import__('re').search(r'(?im)^\s*table\s+S?\d+\.\d+|emission limits|monitoring points',p['text'])) for p in packet['pages'])
 return (text/2 + min(images,3)*10_000)*INPUT_RATE + 6_000*OUTPUT_RATE
def main():
 if not SOURCE.exists(): fail('authorized cached source is missing')
 if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SHA: fail('source checksum mismatch')
 from src.documents.pdf_parser import parse_pdf
 from src.documents.ai_first import PROMPT_VERSION, build_batches, run_document_pipeline
 from src.documents.extractor import openai_candidate_request
 parsed=parse_pdf(SOURCE)
 if len(parsed.pages)!=46 or parsed.needs_ocr: fail('page count/text-layer preflight failed')
 if os.environ.get('OPENAI_MODEL')!=MODEL: fail('OPENAI_MODEL is not gpt-4.1-mini')
 if not os.environ.get('OPENAI_API_KEY'): fail('OPENAI_API_KEY unavailable')
 if any(os.environ.get(name) for name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')): fail('proxy variables must be removed in the child process')
 if any(os.environ.get(name) not in (None,'https://api.openai.com/v1') for name in ('OPENAI_BASE_URL','OPENAI_API_BASE')): fail('non-standard OpenAI endpoint configured')
 batches=build_batches(parsed.pages)
 if len(batches)!=9 or sorted(p for b in batches for p in b['primary_pages'])!=list(range(1,47)): fail('nine-batch primary-page plan failed')
 RUN.mkdir(parents=True,exist_ok=True)
 local=RUN/'source.pdf'
 if not local.exists(): shutil.copy2(SOURCE,local)
 ledger_path=RUN/'dispatch_ledger.json'
 ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {'run_id':'HINKLEY_AI_FIRST_LIVE_EVAL_01','execution_mode':'LIVE','source_sha256':SHA,'model':MODEL,'pipeline_version':PROMPT_VERSION,'authorized_request_cap':CAP,'budget_cap_usd':BUDGET,'dispatches':[]}
 done={x['batch'] for x in ledger['dispatches'] if x['status'] in {'SUCCEEDED','FAILED','OUTCOME_UNKNOWN'}}
 def request(packet):
  batch=packet['batch']
  if batch in done: raise RuntimeError('previously attempted batch may not be redispatched')
  if len(ledger['dispatches'])>=CAP: raise RuntimeError('authorized request cap exhausted')
  bound=cost_bound(packet); reserved=sum(x['estimated_upper_cost_usd'] for x in ledger['dispatches'])
  if reserved+bound>BUDGET: raise RuntimeError(f'conservative budget cap would be exceeded: {reserved+bound:.4f}')
  event={'batch':batch,'status':'DISPATCH_STARTED','started_at':datetime.now(timezone.utc).isoformat(),'estimated_upper_cost_usd':bound,'primary_pages':packet['primary_pages']}
  ledger['dispatches'].append(event); ledger_path.write_text(json.dumps(ledger,indent=2))
  try:
   result=openai_candidate_request(packet)
   event.update({'status':'SUCCEEDED','ended_at':datetime.now(timezone.utc).isoformat(),'request_id':result.get('_response_metadata',{}).get('request_id'),'input_tokens':result.get('_response_metadata',{}).get('input_tokens'),'output_tokens':result.get('_response_metadata',{}).get('output_tokens')})
   ledger_path.write_text(json.dumps(ledger,indent=2)); return result
  except Exception as exc:
   event.update({'status':'FAILED','ended_at':datetime.now(timezone.utc).isoformat(),'error':f'{type(exc).__name__}: {str(exc)[:500]}'})
   ledger_path.write_text(json.dumps(ledger,indent=2)); raise
 result=run_document_pipeline(RUN,SHA[:16],parsed.pages,request,model=MODEL)
 print(json.dumps({'run':str(RUN),'state':result['manifest']['document_state'],'dispatches':len(ledger['dispatches']),'candidates':len(result['aggregate']['candidates'])},indent=2))
if __name__=='__main__': main()
