from pathlib import Path
from src.documents.pdf_parser import PdfPage
from src.contracts.service import extract_weather_clauses, save_clauses, load_clauses, save_review, reviews, analyse_confirmed
from src.models.contract_clause import ContractReviewState

TEXT='1. Operations shall not proceed where significant wave height does not exceed 1.5 m. 2. Wind speed not to exceed 30 km/h. 3. Weather standby is contractor risk and requires notice.'
def test_contract_clause_extraction_preserves_quotes_and_ambiguity():
 clauses=extract_weather_clauses('contract-test',[PdfPage(1,TEXT)])
 assert len(clauses)==3 and all(c.quote_verified for c in clauses)
 assert any(c.environmental_variable=='wave' and c.threshold==1.5 and c.unit=='m' for c in clauses)
 assert any(c.consequence=='standby/downtime provision' for c in clauses)

def test_contract_review_persists_and_unconfirmed_clauses_cannot_analyse():
 root=Path('tests/fixtures/contract_runtime'); clauses=extract_weather_clauses('contract-runtime',[PdfPage(1,TEXT)]); save_clauses(root,clauses)
 assert analyse_confirmed(root,clauses,{})['status']=='UNKNOWN'
 save_review(root,'contract-runtime',clauses[0].clause_id,ContractReviewState.CONFIRMED,'test')
 assert reviews(root,'contract-runtime')[clauses[0].clause_id]['state']=='CONFIRMED'

def test_missing_units_remain_review_required_and_do_not_become_thresholds():
 clause=extract_weather_clauses('contract-ambiguous',[PdfPage(1,'Wave height shall be acceptable for operations.')])[0]
 assert clause.threshold is None and clause.review_required and clause.ambiguity

def test_confirmed_contract_fixture_uses_cached_forecast_and_reports_non_legal_windows():
 clauses=extract_weather_clauses('contract-analysis',[PdfPage(1,'Operations shall not proceed where significant wave height does not exceed 1.5 m.')])
 result=analyse_confirmed(Path('.'),clauses,{clauses[0].clause_id:{'state':'CONFIRMED'}})
 assert result['status']=='FORECAST_ANALYSIS_ONLY' and result['forecast_hours']==72
 assert all(item['advisory'] for item in result['windows']) and 'NOT LEGAL ADVICE' in result['legal_notice']
