import json
import pytest
from pathlib import Path
from src.documents.page_filter import select_pages_with_numbered_conditions
from src.documents.pdf_parser import PdfPage
from src.permit.coverage import coverage_gate

@pytest.mark.source_backed
def test_coverage_audit_detects_keyword_filter_omission():
    audit=json.loads(Path('cache/extractions/ml2025054/coverage_audit.json').read_text())
    assert audit['page_filter_omissions'][0]['page']==3
    assert 9 in audit['page_filter_omissions'][0]['conditions']
    assert any(x['id']==9 and x['status']=='REJECTED_RECOVERY' for x in audit['conditions'])

def test_numbered_condition_pages_override_keyword_omission_and_gate_blocks_gaps():
    pages=[PdfPage(3,'\n1. Binding condition'),PdfPage(4,'continuation')]
    assert [p.page_number for p in select_pages_with_numbered_conditions(pages)] == [3,4]
    complete,gaps=coverage_gate([{'status':'CAPTURED'},{'status':'NOT_EXTRACTED','id':1}])
    assert not complete and gaps[0]['id']==1
