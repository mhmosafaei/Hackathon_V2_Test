"""Explicitly synthetic UI fixture, not an extraction of a real licence."""
from .simple_analysis import CATEGORIES, PHASES
import re


def mock_request(packet):
    source = packet['pages'][0].text.strip()
    span = [{'page': 1, 'quotation': source}]
    by_number = {}
    for page in packet['pages']:
        matches = list(re.finditer(r'(?m)^(\d+)\.\s+', page.text))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(page.text)
            by_number[match.group(1)] = [{'page': page.page_number, 'quotation': page.text[match.start():end].strip()}]
    geofences = []
    # Explicit synthetic fixture only, never a production geographic extractor.
    sentence = 'Disposal is permitted only within Test Zone, radius 0.5 NM.'
    for page in packet['pages']:
        if sentence in page.text:
            geofences.append({'name': 'Test Zone', 'description': 'Synthetic disposal area', 'type': 'radius',
                'coordinates_or_boundary': 'radius 0.5 NM', 'restriction': sentence,
                'source_pages': [page.page_number], 'source_spans': [{'page': page.page_number, 'quotation': sentence}]})
    environmental = []
    sentence = 'Significant wave height shall not exceed 2.5 m during works.'
    for page in packet['pages']:
        if sentence in page.text:
            environmental.append({'condition_id': '1', 'source_page': page.page_number,
                'requirement_text': sentence, 'variable': 'significant wave height',
                'canonical_variable': 'significant_wave_height', 'operator': '<=', 'threshold': 2.5,
                'unit': 'm', 'temporal_requirement': 'during works', 'depth_requirement': 'surface',
                'geographic_scope': None, 'evidence_type': 'forecast', 'explicit_requirement': True,
                'notes': None, 'source_spans': [{'page': page.page_number, 'quotation': sentence}]})
    contexts = []
    context_sentence = 'Synthetic work point: WGS84 latitude 54.1 longitude -6.1.'
    for page in packet['pages']:
        if context_sentence in page.text:
            contexts.append(dict(location_name='Synthetic work point',coordinates_original='WGS84 latitude 54.1 longitude -6.1',
                coordinate_system='WGS84',geometry_type='point',latitude=54.1,longitude=-6.1,source_reference=None,
                easting=None,northing=None,source_page=page.page_number,
                source_spans=[{'page':page.page_number,'quotation':context_sentence}]))
    return {'spatial_context': contexts, 'temporal_context': {
        'permit_valid_from': None, 'permit_valid_until': None, 'operation_start': None, 'operation_end': None,
        'operation_time_restrictions': [], 'source_reference': None, 'source_spans': []},
        'environmental_requirements': environmental, 'geofences': geofences, 'summary': {'permit_number': 'DEMO-2026', 'licensee': 'Example Harbour Ltd (synthetic)',
        'authority': 'Example Marine Authority', 'activity': 'Synthetic marine works', 'valid_from': None,
        'valid_until': None, 'source_spans': span},
        'conditions': [{'number': str(i), 'phase': PHASES[(i - 1) % 4],
            'requirement': f'Synthetic condition {i}: retain the required work and notification records.',
            'important_limit': None, 'timing': 'Within 24 hours' if i % 3 == 0 else None,
            'category': CATEGORIES[(i - 1) % len(CATEGORIES)], 'source_spans': by_number.get(str(i), span)} for i in range(1, 23)],
        'key_limits': [{'label': 'Example reporting deadline', 'value': 'Within 24 hours',
            'condition_numbers': ['3'], 'source_spans': by_number.get('3', span)}]}
