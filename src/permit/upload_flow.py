"""One-click upload orchestration; document content is data, never instructions."""
import hashlib,json,os,re
from pathlib import Path
from src.documents.pdf_parser import parse_pdf
from src.documents.page_filter import select_pages_with_numbered_conditions
from src.documents.extractor import openai_request, openai_candidate_request
from src.permit.orchestrator import analyze,identity
from src.documents.validator import recover_conditions
from src.documents.quote_verifier import normalise
from src.documents.ai_first import build_batches, document_identity, run_document_pipeline
from src.documents.live_budget import AcceptanceDispatchLedger
from src.intelligence.service import (
    mock_stage_transport, openai_stage_transport, run_intelligence_pipeline,
)
from src.runtime import pre_dispatch_runtime_check
from src.intelligence.deterministic import persist_projection


# The one-request diagnostic intentionally holds the original 3k ceiling so a
# truncation is observable.  The full capped profile needs a little more room
# for a four-page structured candidate batch; the five-request worst-case
# reservation remains below its $0.15 cap.
DIAGNOSTIC_CANDIDATE_OUTPUT_TOKENS = 3_000
LIVE_CANDIDATE_OUTPUT_TOKENS = 8_000


def local_mock_candidate_request(packet: dict) -> dict:
    """Explicit UI-test transport for sanitized fixtures; never a legal extractor.

    It is deliberately opt-in in Streamlit and derives only modal-containing
    source lines, so browser testing exercises the same persistence and review
    services without transmitting uploaded text.
    """
    candidates = []
    for page in packet['pages']:
        for line_number, line in enumerate(page['text'].splitlines(), 1):
            source = line.strip()
            if re.search(r'\b(?:shall|must|may not|shall not|required to|notify)\b', source, re.I):
                candidates.append({'candidate_id': f"mock-p{page['page_number']}-l{line_number}", 'document_id': packet['document_id'],
                                   'document_type': 'UNKNOWN', 'source_quotation': source, 'page_number': page['page_number'],
                                   'obligation': source, 'obligation_type': None, 'state': 'EXTRACTED_UNVERIFIED', 'human_review_required': True})
    return {'candidates': candidates}

def coverage_audit(pdf:Path, folder:Path, conditions:list[dict])->dict:
    """Deterministic numbered-source inventory; separate from extraction/review state."""
    pages=parse_pdf(pdf).pages; start=next(p.page_number for p in pages if re.search(r'(?i)part\s*2\s*[-–]?\s*conditions',p.text)); end=next((p.page_number for p in pages if p.page_number>start and re.search(r'(?im)^\s*notes\s*$',p.text)),len(pages)+1)
    selected=[p for p in pages if start<=p.page_number<end]; text='\n'.join(p.text for p in selected); matches=list(re.finditer(r'(?m)^\s*(\d{1,2})\.\s+',text)); inventory=[]
    for i,match in enumerate(matches):
        number=int(match.group(1)); source=text[match.start():matches[i+1].start() if i+1<len(matches) else len(text)]; records=[x for x in conditions if re.match(rf'^{number}(?:\D|$)',x['condition_id'])]
        verified=[x for x in records if x.get('quote_verified')]
        status='CAPTURED' if verified else 'REVIEW_REQUIRED' if records else 'MISSING'
        inventory.append({'condition_number':number,'source_text':source,'records':[x['condition_id'] for x in records],'status':status,'evidence':'quote-verified recovered record' if verified else 'recovered record needs review' if records else 'no recovered record'})
    summary={s:sum(x['status']==s for x in inventory) for s in ('CAPTURED','PARTIALLY_CAPTURED','RECOVERY_REQUIRED','MISSING','REVIEW_REQUIRED')}
    result={'schema_version':'coverage-v1','source_conditions_inventoried':len(inventory),'conditions':inventory,'summary':summary,'coverage_complete':not(summary['MISSING'] or summary['PARTIALLY_CAPTURED'] or summary['RECOVERY_REQUIRED'])}
    (folder/'coverage_audit.json').write_text(json.dumps(result,indent=2)); return result

def _analyze_legacy_upload(root:Path, filename:str, content:bytes, request)->dict:
    if not filename.lower().endswith('.pdf'): raise ValueError('Upload a PDF file')
    if len(content)>25_000_000: raise ValueError('PDF exceeds 25 MB limit')
    model=os.environ.get('OPENAI_MODEL')
    if not model or not os.environ.get('OPENAI_API_KEY'): raise RuntimeError('OpenAI configuration is unavailable')
    digest=hashlib.sha256(content).hexdigest(); folder=root/'cache'/'document_runs'/identity(content,model); folder.mkdir(parents=True,exist_ok=True); pdf=folder/'source.pdf'; pdf.write_bytes(content)
    parsed=parse_pdf(pdf)
    if parsed.needs_ocr: raise ValueError('PDF text layer is unsuitable; OCR review is required before extraction')
    selected=select_pages_with_numbered_conditions(parsed.pages)
    if not selected: raise ValueError('No numbered conditions section was found')
    manifest=analyze(pdf,root/'cache'/'document_runs',model,lambda text:request(text,digest[:16]),workers=2)
    all_conditions=[]; audit=[]
    for page in selected:
        page_state=manifest.get('pages',{}).get(str(page.page_number),{})
        if page_state.get('status') != 'COMPLETE':
            # A failed page is a coverage/review gap, not a reason to discard
            # successful neighbouring checkpoints or repeat their API calls.
            audit.append({'page':page.page_number,'disposition':'PAGE_NOT_RECOVERED','status':page_state.get('status','PENDING'),'error':page_state.get('error')})
            continue
        record=json.loads((folder/f'page_{page.page_number:02}.json').read_text()); recovered,events,_=recover_conditions(record['raw']['conditions'],parsed.pages,page.page_number); all_conditions.extend(x.model_dump(mode='json') for x in recovered); audit.extend(events)
    (folder/'recovery_aggregate.json').write_text(json.dumps({'document_id':digest[:16],'processing_schema_version':'recovery-v1','conditions':all_conditions,'audit':audit},indent=2))
    try:
        coverage=coverage_audit(pdf,folder,all_conditions); state='COVERAGE_COMPLETE' if coverage['coverage_complete'] else 'COVERAGE_INCOMPLETE'
    except Exception as exc:
        coverage={'error':f'{type(exc).__name__}: {exc}'}; state='EXTRACTION_COMPLETE'
    manifest['document_state']=state; manifest['coverage_summary']=coverage.get('summary'); (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return {'document_hash':digest,'pages':len(parsed.pages),'condition_pages':[p.page_number for p in selected],'conditions':len(all_conditions),'coverage':coverage,'state':state,'ready_for_review':state == 'COVERAGE_COMPLETE'}


def analyze_ai_first_upload(root: Path, filename: str, content: bytes, request=openai_candidate_request,
                            intelligence_transport=None, *, analysis_run_id: str | None = None,
                            live_acceptance: bool = False,
                            diagnostic_candidate_batch_only: bool = False,
                            experimental_intelligence: bool = False) -> dict:
    """Default new-document path: process every readable physical page.

    Structural detection is retained as evidence in the coverage artifact, but
    unfamiliar headings never prevent a valid PDF reaching human review.
    """
    if not filename.lower().endswith('.pdf'):
        raise ValueError('Upload a PDF file')
    if len(content) > 25_000_000:
        raise ValueError('PDF exceeds 25 MB limit')
    model = os.environ.get('OPENAI_MODEL')
    if not model or not os.environ.get('OPENAI_API_KEY'):
        raise RuntimeError('OpenAI configuration is unavailable')
    digest = hashlib.sha256(content).hexdigest()
    if analysis_run_id and not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', analysis_run_id):
        raise ValueError('analysis run ID must contain 8–80 letters, digits, underscores or hyphens')
    if diagnostic_candidate_batch_only and not live_acceptance:
        raise RuntimeError('a one-request candidate diagnostic requires the live acceptance profile')
    if live_acceptance and (not analysis_run_id or request is not openai_candidate_request):
        raise RuntimeError('a fresh live acceptance run requires an explicit run ID and the production OpenAI transport')
    folder = root / 'cache' / 'document_runs' / document_identity(content, model, analysis_run_id)
    folder.mkdir(parents=True, exist_ok=True)
    pdf = folder / 'source.pdf'
    if not pdf.exists():
        pdf.write_bytes(content)
    parsed = parse_pdf(pdf)
    if parsed.needs_ocr:
        raise ValueError('PDF text layer is unsuitable; OCR review is required before extraction')

    dispatch_ledger = None
    runtime = None
    if live_acceptance:
        # This is intentionally performed in the Streamlit worker immediately
        # before it can create a dispatch ledger or issue a request.
        runtime = pre_dispatch_runtime_check()
        planned = build_batches(parsed.pages)
        if len(planned) != 2:
            raise RuntimeError(f'live acceptance profile requires exactly two candidate batches; planned {len(planned)}')
        dispatch_ledger = AcceptanceDispatchLedger(folder / 'live_acceptance_dispatch_ledger.json',
                                                   run_id=analysis_run_id, model=model,
                                                   request_cap=1 if diagnostic_candidate_batch_only else 5,
                                                   budget_cap_usd=.15)

    def transport(packet: dict):
        if dispatch_ledger is None:
            return request(packet)
        output_ceiling = (DIAGNOSTIC_CANDIDATE_OUTPUT_TOKENS if diagnostic_candidate_batch_only
                          else LIVE_CANDIDATE_OUTPUT_TOKENS)
        bounded_packet = {**packet, 'max_output_tokens': output_ceiling}
        return dispatch_ledger.call(
            dispatch_id=f"candidate-batch-{packet['batch']}", stage='CANDIDATE_EXTRACTION',
            input_text=packet['prompt'], input_token_ceiling=16_000, output_token_ceiling=output_ceiling,
            invoke=lambda: request(bounded_packet),
        )

    result = run_document_pipeline(folder, digest[:16], parsed.pages, transport, model=model,
                                   analysis_run_id=analysis_run_id,
                                   halt_on_failed_batch=live_acceptance, runtime=runtime,
                                   batch_limit=1 if diagnostic_candidate_batch_only else None)
    aggregate = result['aggregate']; coverage = result['coverage']
    if diagnostic_candidate_batch_only:
        batch = result['manifest'].get('batches', {}).get('1', {})
        diagnostic = {
            'schema_version': 'candidate-diagnostic-v1',
            'analysis_run_id': analysis_run_id,
            'mode': 'CANDIDATE_BATCH_1_ONLY',
            'model': model,
            'runtime': runtime,
            'batch': batch,
            'dispatch_ledger': str(folder / 'live_acceptance_dispatch_ledger.json'),
            'downstream_stages_dispatched': False,
        }
        (folder / 'candidate_batch_1_diagnostic.json').write_text(json.dumps(diagnostic, indent=2), encoding='utf-8')
        return {
            'document_hash': digest, 'run_identity': folder.name, 'analysis_run_id': analysis_run_id,
            'pages': len(parsed.pages), 'condition_pages': list(range(1, len(parsed.pages) + 1)),
            'conditions': len(aggregate['candidates']), 'candidates': len(aggregate['candidates']),
            'rejected': len(aggregate['rejected']), 'coverage': coverage,
            'state': 'DIAGNOSTIC_COMPLETE' if batch.get('status') == 'COMPLETE' else 'DIAGNOSTIC_FAILED',
            'diagnostic': diagnostic, 'dispatch_ledger': diagnostic['dispatch_ledger'],
            'ready_for_review': False,
        }
    if live_acceptance and not coverage.get('processing_complete'):
        raise RuntimeError('candidate extraction is incomplete; refusing downstream intelligence dispatch')
    if not experimental_intelligence:
        intelligence_path = persist_projection(folder, filename=filename, document_sha256=digest)
        return {
            'document_hash': digest, 'run_identity': folder.name, 'analysis_run_id': analysis_run_id,
            'pages': len(parsed.pages), 'condition_pages': list(range(1, len(parsed.pages) + 1)),
            'conditions': len(aggregate['candidates']), 'candidates': len(aggregate['candidates']),
            'rejected': len(aggregate['rejected']), 'coverage': coverage,
            'state': result['manifest']['document_state'], 'intelligence_analysis': str(intelligence_path),
            'intelligence_status': 'DETERMINISTIC_REVIEW_READY', 'ready_for_review': True,
            'dispatch_ledger': str(dispatch_ledger.path) if dispatch_ledger else None,
        }
    # The existing candidate checkpoints remain the immutable Stage 1 source.
    # A caller that supplies a non-production candidate transport (tests/UI
    # mock mode) automatically receives the local mock stage transport, so
    # an offline test can never fall through to a live Stage 2/3 request.
    if live_acceptance:
        stage_limits = {'stage1': (60_000, 6_000), 'stage2': (50_000, 6_000), 'stage3': (60_000, 6_000)}
        def intelligence_transport(stage: str, packet: dict, schema: dict) -> dict:
            input_ceiling, output_ceiling = stage_limits[stage]
            bounded_packet = {**packet, 'max_output_tokens': output_ceiling}
            return dispatch_ledger.call(
                dispatch_id=stage, stage=stage.upper(), input_text=json.dumps(bounded_packet, ensure_ascii=False),
                input_token_ceiling=input_ceiling, output_token_ceiling=output_ceiling,
                invoke=lambda: openai_stage_transport(stage, bounded_packet, schema),
            )
        processor = 'OPENAI'
    else:
        if intelligence_transport is None:
            intelligence_transport = openai_stage_transport if request is openai_candidate_request else mock_stage_transport
        processor = 'OPENAI' if intelligence_transport is openai_stage_transport else 'MOCK'
    intelligence = run_intelligence_pipeline(
        folder, aggregate, filename=filename, document_sha256=digest,
        transport=intelligence_transport, processor=processor,
    )
    return {
        'document_hash': digest, 'run_identity': folder.name, 'analysis_run_id': analysis_run_id, 'pages': len(parsed.pages),
        'condition_pages': list(range(1, len(parsed.pages) + 1)), 'conditions': len(aggregate['candidates']),
        'candidates': len(aggregate['candidates']), 'rejected': len(aggregate['rejected']),
        'coverage': coverage, 'state': result['manifest']['document_state'],
        'intelligence_analysis': str(folder / 'intelligence_analysis_v1.json'),
        'intelligence_status': intelligence.stage_runs[2].status,
        'dispatch_ledger': str(folder / 'live_acceptance_dispatch_ledger.json') if dispatch_ledger else None,
        'ready_for_review': True,  # human review is mandatory, not an approval signal
    }


def analyze_upload(root: Path, filename: str, content: bytes, request=None) -> dict:
    """Analyze a new upload with AI-first processing by default.

    The optional legacy callback is retained only for historical fixture and
    migration callers that return the established ``conditions`` payload.
    """
    if request is None:
        return analyze_ai_first_upload(root, filename, content)
    return _analyze_legacy_upload(root, filename, content, request)
