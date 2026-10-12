"""Document-hash scoped review storage; never falls back to another permit."""
import json
from pathlib import Path
from datetime import datetime, timezone

BELFAST_KEY='belfast-ml2025054'
NEW_KEY='07203-20-0'
NEW_RUN='26030226cec91f0d7f7fc9bfde20989bf360e99fc818261d2f8297b5239e0163'

def resolve_active_permit(documents: dict, selected: str | None, analysis_run_id: str | None) -> str:
    """Preserve explicit selection; restore a run URL after worker restart."""
    if selected in documents:
        return selected
    matched = next((key for key, spec in documents.items() if analysis_run_id and spec.get('analysis_run_id') == analysis_run_id), None)
    return matched or next(iter(documents))

def run_display_metadata(folder: Path) -> dict:
    """Read saved run state without invoking extraction or changing artifacts."""
    manifest_path = folder / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    ledger_path = folder / 'live_acceptance_dispatch_ledger.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    dispatches = ledger.get('dispatches', [])
    return {
        'analysis_run_id': manifest.get('analysis_run_id'),
        'extraction_status': manifest.get('document_state', 'UNKNOWN'),
        'batch_errors': [entry.get('error') for entry in manifest.get('batches', {}).values() if entry.get('error')],
        'dispatch_count': len(dispatches),
        'outcome_unknown': any(entry.get('status') == 'OUTCOME_UNKNOWN' for entry in dispatches),
    }

def analysis_result_notice(result: dict) -> tuple[str, str]:
    """A failed diagnostic must never be presented as completed analysis."""
    state = result.get('state', 'UNKNOWN')
    counts = f"{result['pages']} pages; {result['conditions']} reviewable records"
    if state in {'FAILED', 'DIAGNOSTIC_FAILED'}:
        error = result.get('diagnostic', {}).get('batch', {}).get('error') or 'See the selected run status below.'
        return 'error', f'Analysis failed: {counts}. {error}'
    if state == 'DIAGNOSTIC_COMPLETE':
        return 'warning', f'Diagnostic only: {counts}. Remaining extraction and intelligence stages were not run.'
    return 'success', f'{counts}. Results are selected below.'

def available_documents(root:Path)->dict:
    items={BELFAST_KEY:{'title':'Belfast Harbour ML2025054','pages':14,'aggregate':root/'cache/extractions/ml2025054/aggregate.json','coverage':root/'cache/extractions/ml2025054/coverage_audit.json','version':'stage1-recovery'}}
    run=root/'cache/document_runs'/NEW_RUN
    if (run/'recovery_aggregate.json').exists(): items[NEW_KEY]={'title':'Marine Licence 07203/20/0','pages':10,'aggregate':run/'recovery_aggregate.json','coverage':run/'coverage_audit.json','version':'recovery-v1','hash':NEW_RUN}
    for candidate in (root/'cache'/'document_runs').glob('*'):
        aggregate=candidate/'recovery_aggregate.json'
        if aggregate.exists() and candidate.name not in {NEW_RUN}:
            payload=json.loads(aggregate.read_text()); key=candidate.name
            items[key]={'title':f"Uploaded permit {payload.get('document_id',key)[:16]}",'pages':None,'aggregate':aggregate,'coverage':candidate/'coverage_audit.json','version':payload.get('processing_schema_version','recovery-v1'),'hash':key}
        ai_first=candidate/'candidate_aggregate.json'
        if ai_first.exists():
            derived = candidate/'deterministic-permit-v1'/'candidate_aggregate.json'
            if derived.exists():
                ai_first = derived
            payload=json.loads(ai_first.read_text()); key=candidate.name
            metadata = run_display_metadata(candidate)
            run_label = metadata['analysis_run_id'] or f'cached-{key[:12]}'
            items[key]={'title':f"Uploaded document {payload.get('document_id',key)[:16]} · {run_label} · {metadata['extraction_status']}",'pages':payload.get('coverage',{}).get('physical_pages'),'aggregate':ai_first,'coverage':ai_first.parent/'coverage_audit.json','version':payload.get('processing_schema_version','ai-first-candidates-v1'),'hash':key,'candidate_mode':True, **metadata}
    hinkley=root/'cache/document_runs'/'2a23b1d45e13b328b78f376315cc799f863eee93315fbc0282c63d3e733b9d31'/'HINKLEY_AI_FIRST_LIVE_EVAL_01'/'recovered_comprehensive_analysis.json'
    if hinkley.exists():
        items['hinkley-live-eval-01']={'title':'Hinkley Point C — live AI evaluation','pages':46,'aggregate':hinkley,'coverage':hinkley,'version':'offline-state-normalization-v1','hash':'a9dec163f30956e1','candidate_mode':True,'live_mode':True}
    return items
def load_document(root:Path,key:str)->tuple[dict,list[dict],dict]:
    spec=available_documents(root)[key]; aggregate=json.loads(spec['aggregate'].read_text()); coverage=json.loads(spec['coverage'].read_text()) if spec['coverage'].exists() else {}
    return spec, aggregate.get('candidates', aggregate.get('conditions', [])), aggregate.get('coverage', coverage)

def namespace(root:Path, document_hash:str, version:str='recovery-v1')->Path:
    return root/'cache'/'document_reviews'/document_hash/version
def decisions_path(root:Path, document_hash:str, version:str='recovery-v1')->Path:
    return namespace(root,document_hash,version)/'review_decisions.json'
def load_decisions(root:Path, document_hash:str, version:str='recovery-v1')->dict:
    p=decisions_path(root,document_hash,version); return json.loads(p.read_text()) if p.exists() else {}
def save_decision(root:Path, document_hash:str, condition:dict, decision:str, reviewer:str, version:str='recovery-v1')->dict:
    quote_verified = condition.get('quote_verified') or condition.get('state') == 'SOURCE_VERIFIED'
    if decision=='CONFIRMED' and not quote_verified: raise ValueError('unverified quotations cannot be confirmed')
    p=decisions_path(root,document_hash,version); p.parent.mkdir(parents=True,exist_ok=True); data=load_decisions(root,document_hash,version)
    record_id=condition.get('register_id') or condition.get('condition_id') or condition.get('candidate_id')
    if not record_id: raise ValueError('review record requires a stable condition or candidate identifier')
    data[record_id]={'decision':decision,'reviewer':reviewer,'at':datetime.now(timezone.utc).isoformat()}; p.write_text(json.dumps(data,indent=2)); return data[record_id]
