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
    return {'geofences': geofences, 'summary': {'permit_number': 'DEMO-2026', 'licensee': 'Example Harbour Ltd (synthetic)',
        'authority': 'Example Marine Authority', 'activity': 'Synthetic marine works', 'valid_from': None,
        'valid_until': None, 'source_spans': span},
        'conditions': [{'number': str(i), 'phase': PHASES[(i - 1) % 4],
            'requirement': f'Synthetic condition {i}: retain the required work and notification records.',
            'important_limit': None, 'timing': 'Within 24 hours' if i % 3 == 0 else None,
            'category': CATEGORIES[(i - 1) % len(CATEGORIES)], 'source_spans': by_number.get(str(i), span)} for i in range(1, 23)],
        'key_limits': [{'label': 'Example reporting deadline', 'value': 'Within 24 hours',
            'condition_numbers': ['3'], 'source_spans': by_number.get('3', span)}]}
