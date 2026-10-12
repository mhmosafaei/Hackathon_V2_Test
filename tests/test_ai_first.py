import shutil
from pathlib import Path
from uuid import uuid4

from src.documents.ai_first import assign_register_ids, build_batches, document_identity, materialize_candidate_drafts, run_document_pipeline, verify_candidates
from src.documents.pdf_parser import PdfPage
def test_unfamiliar_candidate_survives_and_is_review_gated():
 raw=[{'candidate_id':'x','document_id':'d','document_type':'CONTRACT','source_quotation':'The supplier shall notify the client.','page_number':1,'obligation':'notify'}]
 c=verify_candidates(raw,[PdfPage(1,'The supplier shall notify the client.')])[0]
 assert c.state=='SOURCE_VERIFIED' and c.human_review_required
def test_missing_source_stays_visible_not_rule_ready():
 raw=[{'candidate_id':'x','document_id':'d','document_type':'PERMIT','source_quotation':'Missing clause','page_number':1}]
 assert verify_candidates(raw,[PdfPage(1,'Other')])[0].state=='SOURCE_NOT_FOUND'


def test_compact_model_draft_is_enriched_locally_without_changing_source_quote():
 raw=[{'source_quotation':'1. The operator shall retain the log.','page_number':1,'section':'1','obligation_type':'Reporting obligation','linked_references':[],'ambiguity':[]}]
 candidate=materialize_candidate_drafts(raw,'doc')[0]
 assert candidate['document_id']=='doc' and candidate['human_review_required'] is True
 assert candidate['source_quotation']==raw[0]['source_quotation']
 assert candidate['candidate_id'].startswith('candidate-p1-')

def test_duplicate_model_candidate_ids_receive_register_only_keys():
 candidates=assign_register_ids([_candidate('same',1,'First shall apply.'),_candidate('same',2,'Second shall apply.')])
 assert [candidate['candidate_id'] for candidate in candidates]==['same','same']
 assert [candidate['register_id'] for candidate in candidates]==['same@p1-1','same@p2-2']


def test_explicit_analysis_run_id_creates_a_fresh_namespace_without_changing_normal_cache_identity():
 content=b'same source bytes'
 assert document_identity(content,'model') == document_identity(content,'model')
 assert document_identity(content,'model','acceptance-one') != document_identity(content,'model','acceptance-two')
 assert document_identity(content,'model') != document_identity(content,'model','acceptance-one')


def _candidate(identifier, page, quote):
 return {'candidate_id':identifier,'document_id':'fixture','document_type':'CONTRACT','source_quotation':quote,'page_number':page,'obligation':'perform the stated action'}

def _run_folder():
 path=Path.cwd()/'cache'/'test-ai-first'/uuid4().hex
 path.mkdir(parents=True); return path


def test_document_wide_pipeline_keeps_unfamiliar_clauses_and_page_coverage():
 tmp_path=_run_folder()
 pages=[PdfPage(1,'Title and definitions.'),PdfPage(2,'The supplier shall notify the client before mobilisation.'),PdfPage(3,'Schedule A\nThe supplier must not operate outside Zone Red.')]
 calls=[]
 def mocked(packet):
  calls.append(packet['primary_pages'])
  if 2 in packet['primary_pages']:
   return {'candidates':[_candidate('notice',2,'The supplier shall notify the client before mobilisation.')]}
  if 3 in packet['primary_pages']:
   return {'candidates':[_candidate('zone',3,'The supplier must not operate outside Zone Red.')]}
  return {'candidates':[]}
 try:
  result=run_document_pipeline(tmp_path,'fixture',pages,mocked,model='mock',max_chars=45)
  assert len(calls)==3
  assert result['coverage']['processing_complete'] is True
  assert result['coverage']['semantic_coverage_complete'] is False
  assert [x['semantic_status'] for x in result['coverage']['pages']]==['PROCESSED_SOURCE_ONLY','PROCESSED_WITH_OBLIGATIONS','PROCESSED_WITH_OBLIGATIONS']
  assert {x['state'] for x in result['aggregate']['candidates']}=={'SOURCE_VERIFIED'}
  assert (tmp_path/'candidate_aggregate.json').exists()
  run_document_pipeline(tmp_path,'fixture',pages,lambda _: (_ for _ in ()).throw(AssertionError('no repeat')),model='mock',max_chars=45)
 finally: shutil.rmtree(tmp_path,ignore_errors=True)


def test_failed_batch_is_visible_and_successful_batch_is_not_lost():
 tmp_path=_run_folder()
 pages=[PdfPage(1,'Alpha shall apply.'),PdfPage(2,'Beta shall report.')]
 def failing(packet):
  if packet['primary_pages']==[2]: raise TimeoutError('mock timeout')
  return {'candidates':[_candidate('alpha',1,'Alpha shall apply.')]}
 try:
  result=run_document_pipeline(tmp_path,'fixture',pages,failing,model='mock',max_chars=20)
  assert result['coverage']['summary']['failed_pages']==1
  assert len(result['aggregate']['candidates'])==1
  calls=[]
  def resume(packet):
   calls.append(packet['primary_pages']); return {'candidates':[_candidate('beta',2,'Beta shall report.')]}
  result=run_document_pipeline(tmp_path,'fixture',pages,resume,model='mock',max_chars=20)
  assert calls==[[2]] and result['coverage']['processing_complete']
 finally: shutil.rmtree(tmp_path,ignore_errors=True)


def test_invalid_candidate_is_preserved_in_rejected_queue():
 tmp_path=_run_folder()
 pages=[PdfPage(1,'The contractor shall retain records.')]
 try:
  result=run_document_pipeline(tmp_path,'fixture',pages,lambda _: {'candidates':[{'candidate_id':'bad'}]},model='mock')
  assert len(result['aggregate']['rejected'])==1
  assert result['coverage']['pages'][0]['semantic_status']=='PROCESSED_SOURCE_ONLY'
 finally: shutil.rmtree(tmp_path,ignore_errors=True)
