from datetime import date
from src.documents.page_filter import select_relevant_pages, select_pages_with_numbered_conditions
from src.documents.pdf_parser import PdfPage
from src.documents.quote_verifier import verify_quote
from src.documents.validator import validate_conditions
from src.permit.classification import classify
from src.permit.rule_factory import make_rule
from src.models.common import AutomationStatus, ConditionType, Confidence, ReviewState, SourceType
from src.models.extracted_condition import ExtractedCondition

PAGES = [PdfPage(1, "No dredging shall take place during the hours of darkness between 1 April and 31 May."), PdfPage(2, "Suspended solids shall not exceed 300 mg/l for more than six hours.")]

def raw(**extra):
    value = dict(condition_id="x", document_type="PERMIT", document_id="ML", source_text=PAGES[0].text,
                 page_number=1, condition_type=ConditionType.CALENDAR_RESTRICTION, variable="darkness", confidence=Confidence.HIGH)
    value.update(extra); return value

def test_page_filter_keeps_neighbours():
    assert [p.page_number for p in select_relevant_pages(PAGES, ["suspended"])] == [1, 2]

def test_numbered_condition_filter_uses_part_two_not_numbered_particulars():
    pages=[PdfPage(1,'Part 1 - Particulars\n1. Location'),PdfPage(2,'Part 2 - Conditions\n1. Notify authority'),PdfPage(3,'2. Continue condition'),PdfPage(4,'NOTES\n1. Other authorisations')]
    assert [p.page_number for p in select_pages_with_numbered_conditions(pages)]==[2,3]

def test_quote_normalizes_bullets_curly_quotes_hyphenation_and_whitespace():
    page = PdfPage(1, chr(0x2022) + " The " + chr(0x2018) + "well-\nbeing" + chr(0x2019) + "  condition applies")
    assert verify_quote("The 'wellbeing' condition applies", [page], 1).verified

def test_quote_preserves_line_break_hyphen_when_it_is_semantic():
    page = PdfPage(1, "Submit to MLComplianceandEnforcement@daera-\nni.gov.uk")
    assert verify_quote("Submit to MLComplianceandEnforcement@daera-ni.gov.uk", [page], 1).verified

def test_fabricated_quote_is_rejected_and_null_threshold_requires_review():
    records, errors = validate_conditions([raw(source_text="fabricated wording", threshold=None)], PAGES)
    assert not errors and not records[0].quote_verified and records[0].review_required

def test_exact_duplicates_are_removed():
    records, _ = validate_conditions([raw(), raw()], PAGES)
    assert len(records) == 1

def test_malformed_record_does_not_crash_batch():
    records, errors = validate_conditions([raw(), {"bad": True}], PAGES)
    assert len(records) == 1 and errors

def test_unconfirmed_condition_cannot_create_rule():
    condition = ExtractedCondition.model_validate(raw())
    binding, status = classify(condition.variable, condition.condition_type.value, [])
    condition = condition.model_copy(update={"automation_status": status})
    assert make_rule(condition, binding, "tester") is None

def test_confirmed_condition_creates_rule_and_calendar_is_automatic():
    condition = ExtractedCondition.model_validate(raw(review_state=ReviewState.CONFIRMED, quote_verified=True, start_date=date(2026,4,1)))
    binding, status = classify(condition.variable, condition.condition_type.value, [])
    condition = condition.model_copy(update={"automation_status": status})
    assert status is AutomationStatus.AUTOMATIC and make_rule(condition, binding, "tester") is not None

def test_external_and_manual_and_unsupported_statuses():
    assert classify("dissolved_oxygen", "INSTANT_THRESHOLD", [])[1] is AutomationStatus.EXTERNAL_DATA_REQUIRED
    assert classify(None, "DOCUMENT_APPROVAL", ["written approval"])[1] is AutomationStatus.MANUAL_INPUT_REQUIRED
    assert classify(None, "OTHER", [])[1] is AutomationStatus.NOT_EVALUABLE
