from types import SimpleNamespace
from pathlib import Path

from src.permit.simple_analysis import (
    PROMPT,
    assess_environmental_extraction_completeness,
    candidate_manifest_prompt,
    identify_environmental_source_candidates,
)


def _pages():
    fixture = Path(__file__).parent / 'fixtures' / 'full_p0_environment_source.txt'
    pages = []
    for block in fixture.read_text(encoding='utf-8').split('--- PAGE ')[1:]:
        page, text = block.split(' ---\n', 1)
        pages.append(SimpleNamespace(page_number=int(page), text=text.strip()))
    return pages


def _requirements(ids):
    return [{'condition_id': str(identifier)} for identifier in ids]


def test_candidate_manifest_is_explicit_and_source_grounded():
    candidates = [{'condition_id': 'A', 'source_record_id': 'environmental-A',
                   'source_page': 3, 'source_text': 'A. Wave evidence shall be reviewed.'}]
    prompt = candidate_manifest_prompt(candidates)
    assert 'AUTHORITATIVE ENVIRONMENTAL CANDIDATES' in prompt
    assert 'Do not silently omit a listed candidate' in prompt
    assert '"condition_id":"A"' in prompt
    assert 'Wave evidence shall be reviewed.' in prompt


def test_prompt_requires_external_manual_survey_obligations_independently():
    required_phrases = [
        'seabed surveys', 'benthos photography/video', 'grab samples',
        'before-work environmental surveys', 'after-work environmental surveys',
        'local/manual monitoring', 'external evidence or reporting requirements',
        'appearing in conditions does not satisfy environmental extraction completeness',
        'do not merge before-work and after-work obligations',
    ]
    assert all(phrase in PROMPT for phrase in required_phrases)


def test_full_p0_fixture_discovers_all_18_environmental_conditions():
    candidates = identify_environmental_source_candidates(_pages())
    assert [c['condition_id'] for c in candidates] == [str(i) for i in range(24, 42)]
    result = assess_environmental_extraction_completeness(candidates, _requirements(range(24, 42)))
    assert result['candidate_count'] == 18
    assert result['extracted_count'] == 18
    assert result['missing_count'] == 0
    assert result['complete'] is True
    assert result['incomplete_records'] == []


def test_full_p0_excludes_controls_and_processing_rules():
    source = SimpleNamespace(page_number=3, text="\n".join([
        "11. AIS must remain operational during all operations.",
        "12. If positioning fails, work must stop until repaired.",
        "23. Select the forecast location and confirmed UTC period before a fetch.",
        "42. Wave and current evidence may be shared and reused to avoid redundant requests.",
    ]))
    assert identify_environmental_source_candidates([source]) == []


def test_general_condition_copy_does_not_satisfy_environmental_completeness():
    source = SimpleNamespace(page_number=2, text=(
        "7. Survey the seabed before disposal, photograph/video the benthos, "
        "collect grab samples and report the results."
    ))
    candidates = identify_environmental_source_candidates([source])
    # The general conditions array is intentionally not passed as environmental
    # requirements; a same-numbered ordinary condition cannot satisfy this gate.
    result = assess_environmental_extraction_completeness(candidates, [
        {'number': '7', 'requirement': 'same source-backed survey'}
    ])
    assert result['candidate_conditions'] == ['7']
    assert result['missing_conditions'] == ['7']
    assert result['complete'] is False


def test_shared_provider_requests_are_process_only_but_source_requests_are_measurements():
    process_only = SimpleNamespace(page_number=5, text=(
        "42. Shared evidence and deterministic derivations: Where multiple requirements use the same "
        "provider product, location, depth and period, PermitPulse may reuse the same retrieved evidence "
        "rather than issuing redundant provider requests. Wave variables may share a wave retrieval; "
        "U, V, current speed and current direction may share current-component evidence; multiple "
        "thresholds on one variable shall remain separate checks."
    ))
    source_request = SimpleNamespace(page_number=5, text=(
        "37. Sea-surface height shall be requested as informational water-level context if a verified "
        "provider dataset and variable mapping exist."
    ))
    assert identify_environmental_source_candidates([process_only]) == []
    assert [c['condition_id'] for c in identify_environmental_source_candidates([source_request])] == ['37']


def test_full_p0_expected_candidate_set_is_stable():
    source = SimpleNamespace(page_number=5, text="\n".join([
        "7. Survey the seabed, photograph/video the benthos, collect grab samples and report the results.",
        "20. Survey the seabed and reference site after disposal; report the grab samples.",
        "24. Significant wave height evidence shall be reviewed.",
        "25. Mean wave period shall be retrieved.",
        "26. Mean wave direction shall be recorded as informational evidence.",
        "27. Eastward current component shall be retrieved.",
        "28. Northward current component shall be retrieved.",
        "29. Current speed shall be reviewed.",
        "30. Current direction derived from U/V shall be recorded.",
        "31. Wind speed shall be recorded.",
        "32. Wind direction shall be recorded.",
        "33. Wind gust shall be recorded.",
        "34. Precipitation evidence shall be reviewed.",
        "35. Visibility shall be measured.",
        "36. Air temperature shall be recorded.",
        "37. Sea-surface height shall be requested as informational water-level context.",
        "38. Sea-surface temperature shall be recorded.",
        "39. Dissolved oxygen shall be monitored.",
        "40. Turbidity FNU requires manual evidence.",
        "41. Turbidity NTU requires manual comparison evidence.",
        "42. Shared evidence may be reused to avoid redundant provider requests.",
    ]))
    assert [c['condition_id'] for c in identify_environmental_source_candidates([source])] == [
        '7', '20', *[str(i) for i in range(24, 42)]
    ]


def test_thresholdless_and_derived_environmental_evidence_remains_candidate():
    source = SimpleNamespace(page_number=1, text="\n".join([
        "1. Record mean wave direction as informational evidence.",
        "2. Record current direction derived from U/V components.",
        "3. Record wind direction as informational evidence.",
        "4. Retrieve sea-surface height if verified mapping exists.",
        "5. Manual FNU comparison required for NTU threshold.",
    ]))
    assert [c['condition_id'] for c in identify_environmental_source_candidates([source])] == [
        '1', '2', '3', '4', '5'
    ]


def test_processing_context_does_not_hide_a_real_measurement_requirement():
    source = SimpleNamespace(page_number=1, text=(
        "1. Sea-surface temperature shall be recorded as informational evidence. "
        "Both checks shall share one environmental retrieval and one evidence card."
    ))
    assert [c['condition_id'] for c in identify_environmental_source_candidates([source])] == ['1']


def test_environmental_provider_words_without_measurement_semantics_are_not_candidates():
    source = SimpleNamespace(page_number=1, text="1. Copernicus forecast provider and selected location.")
    assert identify_environmental_source_candidates([source]) == []


def test_environmental_sampling_and_survey_are_supported():
    source = SimpleNamespace(page_number=1, text=(
        "1. Sediment shall be sampled and laboratory results recorded.\n"
        "2. A seabed benthos survey shall be completed and reported."
    ))
    assert [c['condition_id'] for c in identify_environmental_source_candidates([source])] == ['1', '2']


def test_missing_direction_vector_is_incomplete_without_fabrication():
    candidates = identify_environmental_source_candidates(_pages())
    result = assess_environmental_extraction_completeness(candidates, _requirements(i for i in range(24, 42) if i != 26))
    assert result['complete'] is False
    assert result['missing_conditions'] == ['26']
    diagnostic = result['incomplete_records'][0]
    assert diagnostic['status'] == 'EXTRACTION_INCOMPLETE'
    assert diagnostic['source_page'] == 4
    assert 'Wave direction' in diagnostic['source_text']
    assert 'variable' not in diagnostic and 'threshold' not in diagnostic and 'provider' not in diagnostic


def test_extra_non_candidate_does_not_satisfy_authoritative_candidate():
    candidates = [{'condition_id': '24', 'source_record_id': 'src-24', 'source_page': 1,
                   'source_location': 'p1', 'source_text': '24. Wave evidence.', 'source_spans': []}]
    result = assess_environmental_extraction_completeness(candidates, _requirements(['99']))
    assert result['candidate_conditions'] == ['24']
    assert result['missing_conditions'] == ['24']
    assert result['complete'] is False


def test_duplicate_model_records_do_not_hide_a_missing_candidate():
    candidates = [
        {'condition_id': '24', 'source_record_id': 'src-24', 'source_page': 1,
         'source_location': 'p1', 'source_text': '24. Wave evidence.', 'source_spans': []},
        {'condition_id': '25', 'source_record_id': 'src-25', 'source_page': 1,
         'source_location': 'p1', 'source_text': '25. Wave period.', 'source_spans': []},
    ]
    result = assess_environmental_extraction_completeness(candidates, _requirements(['24', '24']))
    assert result['returned_record_count'] == 2
    assert result['extracted_conditions'] == ['24']
    assert result['missing_conditions'] == ['25']
    assert result['complete'] is False


def test_missing_unsupported_and_manual_conditions_are_reported():
    candidates = identify_environmental_source_candidates(_pages())
    returned = [i for i in range(24, 42) if i not in {37, 40, 41}]
    result = assess_environmental_extraction_completeness(candidates, _requirements(returned))
    assert result['missing_conditions'] == ['37', '40', '41']
    assert result['missing_count'] == 3
    assert all(item['status'] == 'EXTRACTION_INCOMPLETE' for item in result['incomplete_records'])


def test_duplicate_model_records_count_once_and_wrong_page_is_not_omission():
    candidates = identify_environmental_source_candidates(_pages())
    requirements = _requirements(range(24, 42))
    requirements.extend([{'condition_id': '31'}, {'condition_id': '31', 'source_page': 5}])
    result = assess_environmental_extraction_completeness(candidates, requirements)
    assert result['returned_record_count'] == 20
    assert result['extracted_count'] == 18
    assert result['complete'] is True
    # Page/quotation correctness remains the separate source-verification gate;
    # this completeness audit must not silently mark a wrong-page record valid.
