from pathlib import Path
from uuid import uuid4

import pytest

from src.documents.live_budget import AcceptanceDispatchLedger, usd,reserve,eligible
def test_usd_per_million_conversion(): assert usd(1_000_000,1_000_000)==2.0
def test_reservation_includes_images_and_max_output(): assert reserve(20_000,2,6_000)==.4*(10_000+20_000)/1e6+1.6*6_000/1e6
def test_cap_budget_and_unknown_dispatch_prevent_reuse():
 d=[{'batch':2,'status':'OUTCOME_UNKNOWN','estimated_upper_cost_usd':.2}]
 assert not eligible(d,2,9,1,.1)
 assert not eligible(d,3,1,1,.1)
 assert not eligible(d,3,9,.25,.1)
 assert eligible(d,3,9,1,.1)


def _ledger() -> AcceptanceDispatchLedger:
 path = Path('tmp') / f'ledger-{uuid4().hex}.json'
 return AcceptanceDispatchLedger(path, run_id='acceptance-test-0001', model='gpt-4.1-mini', request_cap=5, budget_cap_usd=.15)


def test_persistent_ledger_caps_requests_and_records_actual_usage():
 ledger = _ledger()
 def response(): return {'_response_metadata': {'input_tokens': 100, 'output_tokens': 20, 'request_id': 'req-test'}}
 for index in range(5):
  ledger.call(dispatch_id=f'd-{index}', stage='TEST', input_text='evidence', input_token_ceiling=100, output_token_ceiling=25, invoke=response)
 assert all(item['status']=='SUCCEEDED' for item in ledger.dispatches)
 assert ledger.dispatches[0]['actual_cost_usd'] > 0
 with pytest.raises(RuntimeError, match='request cap'):
  ledger.call(dispatch_id='d-6', stage='TEST', input_text='evidence', input_token_ceiling=100, output_token_ceiling=25, invoke=response)


def test_ledger_reserves_before_dispatch_and_never_retries_unknown_outcome():
 ledger = _ledger(); calls=[]
 def interrupted():
  calls.append(1); raise TimeoutError('network timeout')
 with pytest.raises(TimeoutError):
  ledger.call(dispatch_id='candidate-1', stage='CANDIDATE_EXTRACTION', input_text='evidence', input_token_ceiling=100, output_token_ceiling=25, invoke=interrupted)
 assert ledger.dispatches[0]['status']=='OUTCOME_UNKNOWN'
 with pytest.raises(RuntimeError, match='halted after prior OUTCOME_UNKNOWN'):
  ledger.call(dispatch_id='candidate-1', stage='CANDIDATE_EXTRACTION', input_text='evidence', input_token_ceiling=100, output_token_ceiling=25, invoke=interrupted)
 assert len(calls)==1


def test_unknown_outcome_halts_every_later_dispatch_and_survives_restart():
 ledger = _ledger(); calls=[]
 with pytest.raises(TimeoutError):
  ledger.call(dispatch_id='candidate-1', stage='CANDIDATE_EXTRACTION', input_text='evidence', input_token_ceiling=100, output_token_ceiling=25, invoke=lambda: (_ for _ in ()).throw(TimeoutError('network timeout')))
 with pytest.raises(RuntimeError, match='halted after prior OUTCOME_UNKNOWN'):
  ledger.call(dispatch_id='candidate-2', stage='CANDIDATE_EXTRACTION', input_text='evidence', input_token_ceiling=100, output_token_ceiling=25, invoke=lambda: calls.append('candidate-2'))
 restarted = AcceptanceDispatchLedger(ledger.path, run_id='acceptance-test-0001', model='gpt-4.1-mini', request_cap=5, budget_cap_usd=.15)
 with pytest.raises(RuntimeError, match='halted after prior OUTCOME_UNKNOWN'):
  restarted.call(dispatch_id='stage1', stage='STAGE1', input_text='evidence', input_token_ceiling=100, output_token_ceiling=25, invoke=lambda: calls.append('stage1'))
 assert not calls


@pytest.mark.parametrize('failed_stage,later_stage', [
 ('STAGE1', 'STAGE2'), ('STAGE2', 'STAGE3'), ('STAGE3', 'AFTER_STAGE3'),
])
def test_unknown_intelligence_stage_halts_later_stages(failed_stage, later_stage):
 ledger = _ledger()
 with pytest.raises(ConnectionError):
  ledger.call(dispatch_id=failed_stage.lower(), stage=failed_stage, input_text='evidence', input_token_ceiling=100, output_token_ceiling=25, invoke=lambda: (_ for _ in ()).throw(ConnectionError('offline')))
 with pytest.raises(RuntimeError, match='halted after prior OUTCOME_UNKNOWN'):
  ledger.call(dispatch_id=later_stage.lower(), stage=later_stage, input_text='evidence', input_token_ceiling=100, output_token_ceiling=25, invoke=lambda: pytest.fail('later stage must not be invoked'))


def test_ledger_refuses_a_reservation_above_budget_before_invocation():
 ledger = _ledger(); invoked=[]
 with pytest.raises(RuntimeError, match='budget cap'):
  ledger.call(dispatch_id='expensive', stage='TEST', input_text='x'*1000, input_token_ceiling=1000, output_token_ceiling=100_000, invoke=lambda: invoked.append(True))
 assert not invoked
