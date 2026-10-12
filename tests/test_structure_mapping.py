from src.documents.pdf_parser import PdfPage
from src.documents.structure_mapping import map_structure

def test_generic_mapping_preserves_table_continuation_references_and_external_docs():
 pages=[PdfPage(1,'Conditions\n1.1.1 The operator shall monitor discharge in accordance with Schedule 3, Table S3.1.\nSchedule 3 - Monitoring\nTable S3.1 Limits\nFlow | 95 percentile | m3/d\nA1 | 4 | m3/d'),PdfPage(2,'Table S3.1 Limits\nA2 | 5 | m3/d\nPO1 The operator must submit an approved monitoring plan.')]
 result=map_structure(pages)
 assert any(x.identifier=='1.1.1' for x in result['nodes'])
 assert any(x.continuation_of=='TABLE S3.1' for x in result['nodes'] if x.kind=='table')
 assert any('Schedule 3, Table S3.1' in x.linked_references for x in result['candidates'])
 assert result['unresolved_references'][0]['state']=='EXTERNAL_DOCUMENT_REQUIRED'

def test_unstructured_text_is_not_promoted_to_obligation():
 assert map_structure([PdfPage(1,'This introductory text describes permit history.')])['candidates']==[]
