"""Build generic source records; rows retain geometry rather than legal inference."""
from src.models.source_record import SourceRecord,SourceRecordType
from .pdf_parser import PdfPage
from .structure import inspect_permit_structure, NUMBERED_CLAUSE
from .table_reconstruction import reconstruct_tables


def _page_prefix_after_header(text: str) -> str:
 """Return a possible continuation prefix without treating page furniture as text."""
 lines=[line.strip() for line in text.splitlines()]
 while lines and (not lines[0] or lines[0].casefold().startswith('permit number') or lines[0].isdigit() or 'epr/' in lines[0].casefold()):
  lines.pop(0)
 return '\n'.join(lines).strip()


def _continuation_for(clause: dict, pages: list[PdfPage]) -> tuple[str|None,int|None]:
 """Link only explicit list-continuations; all other page endings stay visible as partial."""
 if not clause.get('is_page_terminal', False): return None,None
 page_index=clause['page']
 if page_index >= len(pages): return None,None
 prefix=_page_prefix_after_header(pages[page_index].text)
 next_clause=NUMBERED_CLAUSE.search(prefix)
 prefix=prefix[:next_clause.start()].strip() if next_clause else prefix
 source=clause['source_text'].rstrip()
 # A following alphabetic sub-list can continue a condition across pages.
 # Parenthesised numerals are often a new legal note, so never pull them into
 # a preceding permit condition merely because of physical adjacency.
 if prefix.startswith((';', 'and ', 'or ', 'but ')) or __import__('re').match(r'^(?:\(?[a-z]\)?\.|\([a-z]\))', prefix):
  return prefix,page_index+1
 return None,None


def _table_metadata(row: list[dict]) -> dict:
 """Expose values physically in labelled cells; blank context stays null."""
 values={}
 for cell in row:
  header=(cell.get('header') or '').casefold()
  text=cell.get('text') or None
  if not text: continue
  if 'parameter' in header: values['parameter']=text
  elif 'limit' in header and 'range' not in header: values['limit_text']=text
  elif 'reference period' in header: values['reference_period']=text
  elif 'monitoring frequency' in header: values['monitoring_frequency']=text
  elif 'compliance statistic' in header: values['compliance_statistic']=text
  elif any(label in header for label in ('effluent', 'discharge activity', 'activity reference', 'operating mode')): values['applicability']=text
 return values

def _particular_records(document_id:str,pages:list[PdfPage])->list[SourceRecord]:
 """Inventory Part 1 facts as source context, never as inferred obligations."""
 import re
 records=[]; in_particulars=False
 for page in pages:
  text=page.text
  if re.search(r'(?i)\bpart\s*1\s*[-–]?\s*particulars\b',text): in_particulars=True
  if not in_particulars: continue
  end_match=re.search(r'(?i)\bpart\s*2\s*[-–]?\s*conditions\b',text)
  segment=text[:end_match.start()] if end_match else text
  matches=list(re.finditer(r'(?m)^\s*(\d{1,3})\.\s+(?=[A-Z])',segment))
  for index,match in enumerate(matches):
   end=matches[index+1].start() if index+1<len(matches) else len(segment)
   source=segment[match.start():end].strip()
   ambiguity=['EXTERNAL_DOCUMENT_REQUIRED'] if re.search(r'(?i)licence documentation|application|\bmap\b|\bhra\b|sediment analysis',source) else []
   records.append(SourceRecord(source_record_id=f'particular-p{page.page_number}-{match.group(1)}',document_id=document_id,record_type=SourceRecordType.CONTEXT,source_text=source,pages=[page.page_number],section_reference=f'Part 1.{match.group(1)}',extraction_method='deterministic_particulars_structure',verification_status='SOURCE_VERIFIED',ambiguity=ambiguity))
  if end_match: in_particulars=False
 return records


def _context_records(document_id:str,pages:list[PdfPage])->list[SourceRecord]:
 """Keep maps, legal notes and external references visible without treating them as conditions."""
 import re
 records=[]
 for page in pages:
  for index,line in enumerate(page.text.splitlines()):
   source=line.strip()
   if not source: continue
   folded=source.casefold()
   if ('appendix' in folded and 'map' in folded):
    records.append(SourceRecord(source_record_id=f'map-p{page.page_number}-{index}',document_id=document_id,record_type=SourceRecordType.CONTEXT,source_text=source,pages=[page.page_number],section_reference='Appendix map',extraction_method='deterministic_context_heading',verification_status='SOURCE_VERIFIED',ambiguity=['GEOGRAPHIC_EVIDENCE_ONLY']))
   elif source.upper().startswith('NOTE:') or source.casefold().startswith('further information:'):
    records.append(SourceRecord(source_record_id=f'note-p{page.page_number}-{index}',document_id=document_id,record_type=SourceRecordType.CONTEXT,source_text=source,pages=[page.page_number],extraction_method='deterministic_context_heading',verification_status='SOURCE_VERIFIED',ambiguity=['NON_OPERATIVE_CONTEXT_REQUIRES_REVIEW']))
   elif ('http://' in folded or 'https://' in folded):
    records.append(SourceRecord(source_record_id=f'external-reference-p{page.page_number}-{index}',document_id=document_id,record_type=SourceRecordType.REFERENCE,source_text=source,pages=[page.page_number],extraction_method='deterministic_external_reference_url',verification_status='SOURCE_VERIFIED',ambiguity=['EXTERNAL_DOCUMENT_REQUIRED']))
 return records


def build_source_inventory(document_id:str,pages:list[PdfPage],pdf_path=None)->list[SourceRecord]:
 structure=inspect_permit_structure(pages); records=[]
 for clause in structure.get('numbered_clauses',structure['hierarchical_clauses']):
  continuation,continuation_page=_continuation_for(clause,pages)
  records.append(SourceRecord(source_record_id=f"clause-p{clause['page']}-{clause['id']}",document_id=document_id,record_type=SourceRecordType.CLAUSE,source_text=clause['source_text']+(f'\n{continuation}' if continuation else ''),pages=[clause['page']]+([continuation_page] if continuation_page else []),section_reference=clause['id'],extraction_method='deterministic_pdf_structure',verification_status='SOURCE_VERIFIED',ambiguity=[] if continuation or clause['source_text'].rstrip().endswith(('.', ';', ':')) else ['possible cross-page continuation not structurally linked']))
 for table in structure['tables']:
  records.append(SourceRecord(source_record_id=f"table-p{table['page']}-{table['id'].replace(' ','-')}",document_id=document_id,record_type=SourceRecordType.TABLE,source_text=f"{table['id']} {table['title']}",pages=[table['page']],table_reference=table['id'],extraction_method='deterministic_pdf_structure',verification_status='SOURCE_VERIFIED',ambiguity=['table rows require layout/semantic interpretation']))
 for schedule in structure['schedules']:
  records.append(SourceRecord(source_record_id=f"schedule-p{schedule['page']}-{schedule['id'].replace(' ','-')}",document_id=document_id,record_type=SourceRecordType.SCHEDULE,source_text=f"{schedule['id']} {schedule['title']}",pages=[schedule['page']],section_reference=schedule['id'],extraction_method='deterministic_pdf_structure',verification_status='SOURCE_VERIFIED'))
 if pdf_path:
  for table in reconstruct_tables(pdf_path):
   for row in table['rows']:
    values=[cell['text'] for cell in row if cell['text']]
    if not values: continue
    metadata=_table_metadata(row)
    records.append(SourceRecord(source_record_id=f"{table['id']}-r{row[0]['row']}",document_id=document_id,record_type=SourceRecordType.TABLE_ROW,source_text=' | '.join(values),pages=[table['page']],table_reference=table['id'],row_reference=str(row[0]['row']),column_labels=[cell['header'] or '' for cell in row],layout_provenance={'table_bbox':table['bbox'],'cells':[{'column':c['column'],'bbox':c['bbox'],'text':c['text']} for c in row]},extraction_method='pymupdf_table_geometry',verification_status='SOURCE_VERIFIED' if table['status']=='VERIFIED_STRUCTURE' else 'PARTIAL_STRUCTURE',ambiguity=list(table.get('ambiguities',[]))+(['unresolved blank/merged cells'] if any(not c['text'] for c in row) else []),**metadata))
 records.extend(_particular_records(document_id,pages))
 records.extend(_context_records(document_id,pages))
 # Definitions and external references are source context, not inferred obligations.
 for page in pages:
  for index,line in enumerate(page.text.splitlines()):
   if ' is defined as ' in line.casefold() or ' means ' in line.casefold():
    records.append(SourceRecord(source_record_id=f'definition-p{page.page_number}-{index}',document_id=document_id,record_type=SourceRecordType.DEFINITION,source_text=line.strip(),pages=[page.page_number],extraction_method='deterministic_definition_phrase',verification_status='SOURCE_VERIFIED'))
  for index,line in enumerate(page.text.splitlines()):
   normalized=line.casefold()
   if ('in accordance with' in normalized or 'as approved by' in normalized) and not any(word in normalized for word in ('table s', 'schedule ')):
    records.append(SourceRecord(source_record_id=f'reference-p{page.page_number}-{index}',document_id=document_id,record_type=SourceRecordType.REFERENCE,source_text=line.strip(),pages=[page.page_number],extraction_method='deterministic_external_reference_phrase',verification_status='SOURCE_VERIFIED',ambiguity=['EXTERNAL_DOCUMENT_REQUIRED when referenced document is not present']))
 # Cross-reference links are explicit strings only; absence of a target remains visible.
 by_label={}
 for record in records:
  for label in (record.section_reference,record.table_reference):
   if label: by_label.setdefault(label.casefold(),[]).append(record.source_record_id)
 for record in records:
  references=[]
  for label, ids in by_label.items():
   if label and label in record.source_text.casefold() and record.source_record_id not in ids: references.extend(ids)
  record.related_record_ids=sorted(set(references))
 return records

def link_candidates(candidates:list[dict],records:list[SourceRecord])->list[dict]:
 for c in candidates:
  quote=c['source_quotation'].casefold()
  c['source_record_ids']=[r.source_record_id for r in records if c['page_number'] in r.pages and (quote[:60] in r.source_text.casefold() or r.source_text[:60] in quote)][:5]
 return candidates
