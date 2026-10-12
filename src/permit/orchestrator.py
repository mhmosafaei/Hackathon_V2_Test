"""Resumable document-level extraction orchestration with isolated page checkpoints."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path
import json
from src.documents.pdf_parser import parse_pdf
from src.documents.page_filter import select_pages_with_numbered_conditions
from src.documents.validator import validate_conditions

PROMPT_VERSION='permit-v2'
def identity(pdf: bytes, model: str) -> str: return sha256(pdf+model.encode()+PROMPT_VERSION.encode()).hexdigest()
def analyze(pdf_path: Path, cache_root: Path, model: str, request, workers: int=2) -> dict:
    parsed=parse_pdf(pdf_path); key=identity(pdf_path.read_bytes(),model); folder=cache_root/key; folder.mkdir(parents=True,exist_ok=True)
    manifest_path=folder/'manifest.json'; manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'identity':key,'model':model,'prompt_version':PROMPT_VERSION,'pages':{}}
    pages=select_pages_with_numbered_conditions(parsed.pages)
    def one(page):
        entry=manifest['pages'].get(str(page.page_number),{})
        if entry.get('status')=='COMPLETE': return page.page_number,entry
        try:
            raw=request(page.text)
            if isinstance(raw,str): raw=json.loads(raw)
            if not isinstance(raw,dict): raise ValueError('extraction response must be a JSON object')
            conditions,errors=validate_conditions(raw.get('conditions',[]),parsed.pages)
            out=folder/f'page_{page.page_number:02}.json'; out.write_text(json.dumps({'raw':raw,'conditions':[c.model_dump(mode='json') for c in conditions],'errors':errors},indent=2))
            return page.page_number,{'status':'COMPLETE','output_file':out.name,'conditions':len(conditions),'errors':len(errors)}
        except Exception as exc: return page.page_number,{'status':'FAILED','error':f'{type(exc).__name__}: {str(exc)[:300]}'}
    with ThreadPoolExecutor(max_workers=min(3,max(1,workers))) as pool:
        futures=[pool.submit(one,p) for p in pages]
        for future in as_completed(futures):
            number,entry=future.result(); manifest['pages'][str(number)]=entry; manifest_path.write_text(json.dumps(manifest,indent=2))
    manifest['coverage_complete']=all(v['status']=='COMPLETE' for v in manifest['pages'].values())
    manifest_path.write_text(json.dumps(manifest,indent=2)); return manifest
