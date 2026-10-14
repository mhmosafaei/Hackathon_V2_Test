import pytest

from src.documents.live_budget import AcceptanceDispatchLedger, usd
from src.permit.simple_analysis import OUTPUT_TOKEN_CEILING


def test_full_p0_output_ceiling_is_16000_and_cost_is_within_cap():
    assert OUTPUT_TOKEN_CEILING == 16_000
    # Existing configured gpt-4.1-mini pricing: $0.40/M input, $1.60/M output.
    assert usd(7_754, OUTPUT_TOKEN_CEILING) == pytest.approx(0.0287016)
    assert usd(7_754, OUTPUT_TOKEN_CEILING) < 0.15
    # The ledger's conservative pre-dispatch estimate for the recorded full
    # request was 18,803 input tokens; it remains below the same cap too.
    assert usd(18_803, OUTPUT_TOKEN_CEILING) == pytest.approx(0.0331212)
    assert usd(18_803, OUTPUT_TOKEN_CEILING) < 0.15


@pytest.mark.parametrize(
    ('output_tokens', 'expected'),
    [(14_000, 0.0255016), (16_000, 0.0287016),
     (18_000, 0.0319016), (20_000, 0.0351016)],
)
def test_candidate_capacity_costs_use_configured_pricing(output_tokens, expected):
    assert usd(7_754, output_tokens) == pytest.approx(expected)


def test_sixteen_thousand_token_reservation_is_allowed_before_dispatch(tmp_path):
    ledger = AcceptanceDispatchLedger(
        tmp_path / 'ledger.json', run_id='output-capacity-test',
        model='gpt-4.1-mini', request_cap=5, budget_cap_usd=.15,
    )
    called = []
    ledger.call(
        dispatch_id='permit-extraction', stage='PERMIT_EXTRACTION',
        input_text='x' * 15_508, input_token_ceiling=8_000,
        output_token_ceiling=16_000,
        invoke=lambda: called.append(True) or {
            '_response_metadata': {'input_tokens': 7_754, 'output_tokens': 10},
        },
    )
    assert called == [True]
    assert ledger.dispatches[0]['output_token_ceiling'] == 16_000
    assert ledger.dispatches[0]['reserved_cost_usd'] == pytest.approx(0.0287016)


def test_over_cap_reservation_is_refused_before_invoke(tmp_path):
    ledger = AcceptanceDispatchLedger(
        tmp_path / 'ledger.json', run_id='output-capacity-over-cap',
        model='gpt-4.1-mini', request_cap=5, budget_cap_usd=.15,
    )
    called = []
    with pytest.raises(RuntimeError, match='budget cap'):
        ledger.call(
            dispatch_id='permit-extraction', stage='PERMIT_EXTRACTION',
            input_text='x' * 15_508, input_token_ceiling=8_000,
            output_token_ceiling=100_000,
            invoke=lambda: called.append(True),
        )
    assert called == []
