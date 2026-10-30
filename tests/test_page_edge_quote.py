from copy import deepcopy
from types import SimpleNamespace
from src.permit.simple_analysis import apply_source_verification

HEADER = 'PermitPulse - Synthetic marine work permit for software testing only'
TEXT = 'Mean wave direction shall be recorded in degrees. Wave direction is informational only.'
def payload(quote):
    return {'conditions':[{'number':'5','source_spans':[{'page':1,'quotation':TEXT}]}],
        'environmental_requirements':[{'condition_id':'5','source_page':1,'source_spans':[{'page':1,'quotation':quote}]}]}
def test_observed_next_page_header_is_removed_without_changing_original_quote():
    pages=[SimpleNamespace(page_number=1,text=f'{HEADER}\nPage 1\n{TEXT}'),SimpleNamespace(page_number=2,text=f'{HEADER}\nPage 2\nWind data')]
    quote=f'{TEXT}\n\n{HEADER}\nPage 2'; data=payload(quote)
    apply_source_verification(data,pages);row=data['environmental_requirements'][0]
    assert row['source_verified'] is True
    assert row['source_spans'][0]['quotation']==quote
    assert row['verified_source_spans']==[{'page':1,'quotation':TEXT}]
    before=deepcopy(data);apply_source_verification(data,pages);assert before==data

def test_unobserved_trailing_text_remains_unverified():
    pages=[SimpleNamespace(page_number=1,text=TEXT)]
    data=payload(TEXT+'\nInvented extra requirement');apply_source_verification(data,pages)
    assert not data['environmental_requirements'][0]['source_verified']

def test_duplicate_cleaned_quote_remains_unverified():
    pages=[SimpleNamespace(page_number=n,text=f'{HEADER}\nPage {n}\n{TEXT}') for n in (1,2)]
    data=payload(f'{TEXT}\n{HEADER}\nPage 2');apply_source_verification(data,pages)
    assert not data['environmental_requirements'][0]['source_verified']
