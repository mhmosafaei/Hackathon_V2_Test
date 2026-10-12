"""Resumable one-request-per-page Stage 1 extraction runner."""
import argparse, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).parents[1]; sys.path.insert(0, str(ROOT)); load_dotenv(ROOT / '.env', override=True)
from src.documents.pdf_parser import parse_pdf
from src.documents.page_filter import select_relevant_pages, select_pages_with_numbered_conditions
from src.documents.extractor import openai_request
from src.documents.validator import validate_conditions
from src.permit.classification import classify
def stamp(): return datetime.now(timezone.utc).isoformat()
def save(path, data): path.write_text(json.dumps(data, indent=2), encoding='utf-8')
def main():
    cli=argparse.ArgumentParser(); cli.add_argument('--page',type=int); cli.add_argument('--force',action='store_true'); args=cli.parse_args()
    pdf=ROOT/'data/permits/ML2025054.pdf'; parsed=parse_pdf(pdf); import yaml
    prioritized=select_relevant_pages(parsed.pages,yaml.safe_load((ROOT/'config/keywords.yaml').read_text())['permit'])
    pages={x.page_number:x for x in prioritized}
    pages.update({x.page_number:x for x in select_pages_with_numbered_conditions(parsed.pages)})
    by_number=dict(sorted(pages.items()))
    folder=ROOT/'cache/extractions/ml2025054'; folder.mkdir(parents=True,exist_ok=True); manifest_path=folder/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'document':'ML2025054.pdf','pages':{}}
    targets=[args.page] if args.page else list(by_number)
    for number in targets:
        if number not in by_number: continue
        entry=manifest['pages'].setdefault(str(number),{'page':number,'status':'PENDING','attempts':0})
        if entry['status']=='COMPLETE' and not args.force: continue
        input_file=folder/f'page_{number:02}_input.txt'; input_file.write_text(by_number[number].text,encoding='utf-8')
        entry.update(status='PENDING',attempts=entry['attempts']+1,model=os.environ['OPENAI_MODEL'],start_timestamp=stamp(),input_file=input_file.name); save(manifest_path,manifest)
        try:
            print(f'STARTING PAGE {number}', flush=True); print('CALLING OPENAI', flush=True)
            raw=json.loads(openai_request(by_number[number].text)); conditions, errors=validate_conditions(raw.get('conditions',[]),parsed.pages)
            print('RESPONSE RECEIVED', flush=True); print('VALIDATING', flush=True); print('QUOTE VERIFYING', flush=True)
            out=folder/f'page_{number:02}.json'; save(out,{'page':number,'raw':raw,'conditions':[x.model_dump(mode='json') for x in conditions],'validation_errors':errors})
            rejected=len(errors); duplicates=max(0,len(raw.get('conditions',[]))-len(conditions)-rejected)
            save(folder/f'page_{number:02}_reconciliation.json',{'raw_total':len(raw.get('conditions',[])),'valid':len(conditions),'rejected':rejected,'duplicates_removed':duplicates,'other_explicitly_accounted_categories':0,'quote_verified_true':sum(x.quote_verified for x in conditions),'quote_verified_false':sum(not x.quote_verified for x in conditions),'validation_errors':errors})
            print('SAVING RESULT', flush=True); entry.update(status='COMPLETE',conditions_extracted=len(conditions),quote_verified=sum(x.quote_verified for x in conditions),quote_failed=sum(not x.quote_verified for x in conditions),error=None,output_file=out.name,end_timestamp=stamp()); print(f'PAGE {number} COMPLETE', flush=True)
        except Exception as exc: entry.update(status='FAILED',error_type=type(exc).__name__,error=f'{str(exc)[:500]}',end_timestamp=stamp())
        save(manifest_path,manifest)
    if all(manifest['pages'].get(str(n),{}).get('status')=='COMPLETE' for n in by_number):
        raw=[]
        for n in by_number: raw += json.loads((folder/manifest['pages'][str(n)]['output_file']).read_text())['conditions']
        reconciliations=[json.loads((folder/f'page_{n:02}_reconciliation.json').read_text()) for n in by_number]
        raw_total=sum(item['raw_total'] for item in reconciliations)
        rejected_total=sum(item['rejected'] for item in reconciliations)
        within_page_duplicates=sum(item['duplicates_removed'] for item in reconciliations)
        seen=set(); final=[]
        for c in raw:
            key=(' '.join(c['source_text'].casefold().split()),c.get('clause') or '')
            if key not in seen: seen.add(key); final.append(c)
        statuses={}
        for c in final:
            _,status=classify(c.get('variable'),c['condition_type'],c.get('evidence_requirements',[])); statuses[status.value]=statuses.get(status.value,0)+1
        save(folder/'aggregate.json',{'document_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'model':os.environ['OPENAI_MODEL'],'selected_pages':list(by_number),'successful_pages':list(by_number),'failed_pages':[],'total_raw_conditions':raw_total,'validation_rejected_items':rejected_total,'within_page_duplicates_removed':within_page_duplicates,'cross_page_duplicates_removed':len(raw)-len(final),'final_condition_count':len(final),'quote_verified_true':sum(c['quote_verified'] for c in final),'quote_verified_false':sum(not c['quote_verified'] for c in final),'review_required':sum(c['review_required'] for c in final),'automation_status_counts':statuses,'extraction_timestamp':stamp(),'conditions':final})
    print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
