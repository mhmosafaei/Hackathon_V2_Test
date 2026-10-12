from src.documents.benchmarking import classify_reference_row


def test_reference_row_can_be_source_only_with_unresolved_table_context():
    result = classify_reference_row(
        {"PDF page": "9", "Reference": "S3.1-r4", "Exact source text": "Parameter flow limit 15 minute continuous N/A"},
        [],
        [{"source_record_id": "row-4", "pages": [9], "source_text": "flow limit 15 minute continuous N/A", "ambiguity": ["merged cell"], "verification_status": "PARTIAL_STRUCTURE"}],
    )
    assert result["category"] == "C_UNRESOLVED_CONTEXT"


def test_reference_row_does_not_create_a_candidate():
    candidate = {"candidate_id": "c-1", "page_number": 2, "section": "1.1.1", "source_quotation": "The operator shall keep records for six years."}
    result = classify_reference_row({"PDF page": "2", "Reference": "1.1.1", "Exact source text": candidate["source_quotation"]}, [candidate], [])
    assert result["category"] == "A_PRESENT_CANDIDATE"
