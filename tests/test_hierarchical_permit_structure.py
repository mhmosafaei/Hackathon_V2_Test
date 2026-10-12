from src.documents.page_filter import select_pages_with_numbered_conditions
from src.documents.pdf_parser import PdfPage
from src.documents.structure import inspect_permit_structure

def test_standalone_conditions_heading_selects_hierarchical_clauses_and_schedules():
    pages=[
        PdfPage(1,'Permit\nParticulars'),
        PdfPage(2,'Conditions\n1\nManagement\n1.1 General\n1.1.1\nThe operator shall comply.'),
        PdfPage(3,'2.1.1\nThe activity shall be monitored.\n4.3.6\nThe operator shall notify.'),
        PdfPage(4,'Schedule 1 - Operations\nTable S1.1 Activities\nIC1\nThe operator shall report.'),
        PdfPage(5,'Schedule 5 - Notification\nTable S4.1 Reporting'),
        PdfPage(6,'Schedule 6 - Interpretation'),
    ]
    assert [p.page_number for p in select_pages_with_numbered_conditions(pages)] == [2,3,4,5]
    result=inspect_permit_structure(pages)
    assert result['conditions_start_page']==2
    assert {x['id'] for x in result['hierarchical_clauses']} == {'1.1','1.1.1','2.1.1','4.3.6'}
    assert result['schedule_obligation_ids']==[{'id':'IC1','page':4}]
    assert [x['id'] for x in result['tables']] == ['TABLE S1.1','TABLE S4.1']

def test_structure_requires_heading_and_hierarchical_clause_signal():
    pages=[PdfPage(1,'Introductory note: conditions may be varied.'),PdfPage(2,'Conditions\nNo clause numbering here.')]
    assert select_pages_with_numbered_conditions(pages)==[]
    assert inspect_permit_structure(pages)['structure_review_required'] is True
