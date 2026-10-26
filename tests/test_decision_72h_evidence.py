"""Downstream 72-hour evidence regression: fixtures only, no transports."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace

import pytest

from src.environmental.models import EvaluationInput
from src.permit.decision_engine import assess, evaluate_requirement
from src.permit.simple_api import create_app, DecisionInput
from tests.test_decision_engine import fixture, T


@pytest.mark.parametrize('hours', [48, 72])
@pytest.mark.parametrize('variable,step,unit', [
    ('significant_wave_height', 3600, 'm'),
    ('surface_current_speed', 900, 'm/s'),
])
def test_native_points_survive_session_json_and_decision_through_end(tmp_path, monkeypatch, hours, variable, step, unit):
    reviews, environment = fixture(variable, hours=hours, step=step, unit=unit)
    # Real Hs data are instantaneous; use the existing 90-minute policy.
    for point in environment['requirements'][0]['evidence']['points']:
        for key in ('temporal_semantics', 'valid_start', 'valid_end'):
            point.pop(key, None)
    before = deepcopy(environment)
    app = create_app(root=tmp_path, transport=lambda *_: pytest.fail('No model calls'))
    app.state.analyses['run'] = {'analysis_id': 'run', 'document_sha256': 'a'*64}
    app.state.environmental_results['run'] = environment
    endpoints = {route.path: route.endpoint for route in app.routes if hasattr(route, 'endpoint')}
    session = json.loads(json.dumps(asyncio.run(endpoints['/api/session']())))
    points = session['environmental_result']['requirements'][0]['evidence']['points']
    assert len(points) == hours*3600//step + 1
    assert points[-1]['data_time'] == (T+timedelta(hours=hours)).isoformat()
    monkeypatch.setattr('src.permit.simple_api.list_reviews', lambda *_: reviews)
    monkeypatch.setattr('src.permit.decision_engine.assess',
                        lambda data, evidence, **options: assess(data, evidence, now=T, **options))
    request = SimpleNamespace(headers={'x-session-id':app.state.boot_id}, base_url='http://test/')
    # F09 supports 24/72h horizons; a 48h request correctly leaves later cells UNKNOWN.
    result = asyncio.run(endpoints['/api/decision/evaluate'](DecisionInput(
        analysis_run_id='run', document_sha256='a'*64, start=T.isoformat(),
        horizon_hours=72, duration_hours=2), request))
    covered = [cell for cell in result['timeline'] if cell['end'] <= (T+timedelta(hours=hours)).isoformat()]
    assert covered[-1]['end'] == (T+timedelta(hours=hours)).isoformat()
    assert all(cell['status'] == 'WORK' for cell in covered)
    if hours == 72:
        assert any(cell['start'] == (T+timedelta(hours=48)).isoformat() for cell in covered)
    else:
        assert result['timeline'][-1]['status'] == 'UNKNOWN'
    assert app.state.environmental_results['run'] == before
    assert app.state.decisions['run'] == result


def test_first_48h_results_unchanged_when_72h_native_evidence_added():
    reviews, environment = fixture(hours=72)
    long_result = assess(reviews, environment, start=T, now=T)
    shorter = deepcopy(environment)
    shorter['requirements'][0]['evidence']['points'] = shorter['requirements'][0]['evidence']['points'][:49]
    shorter['requirements'][0]['evidence']['coverage']['requested_end'] = (T+timedelta(hours=48)).isoformat()
    short_result = assess(reviews, shorter, start=T, now=T)
    def decisions(cells):
        cells = deepcopy(cells[:48])
        for cell in cells:
            for rule in cell['rule_results']:
                # Requested coverage provenance necessarily differs; rule
                # outcomes and evaluated native values must not differ.
                rule.pop('evidence_references', None)
                rule.pop('diagnostics', None)  # Inventory count/range reflects the full fetched series.
        return cells
    assert decisions(long_result['timeline']) == decisions(short_result['timeline'])


def test_turbidity_sample_already_24h_old_expires_after_48h_not_point_truncation():
    reviews, environment = fixture('turbidity', hours=72, unit='FNU', threshold=25)
    evidence = environment['requirements'][0]['evidence']
    evidence.update(data_type='SATELLITE_OBSERVATION', temporal_resolution=86400)
    evidence['points'] = [{'data_time':(T-timedelta(hours=24)).isoformat(),
                           'raw_value':1.1488773822784424, 'unit':'FNU',
                           'status':'WITHIN_THRESHOLD', 'validation_notes':[]}]
    row = reviews['requirements'][0]
    at_boundary = T+timedelta(hours=48)
    # The instant at exactly 72h age is accepted, but a cell extending past it is not.
    assert evaluate_requirement(row, environment, at_boundary, at_boundary, T, set())['status'] == 'WORK'
    last_valid = evaluate_requirement(row, environment, at_boundary-timedelta(hours=1), at_boundary, T, set())
    assert last_valid['status'] == 'WORK'
    expired_cell = evaluate_requirement(row, environment, at_boundary, at_boundary+timedelta(hours=1), T, set())
    assert expired_cell['status'] == 'UNKNOWN'
    assert expired_cell['reason_code'] == 'STALE_TURBIDITY_EVIDENCE'


def test_over_72h_fetch_remains_rejected():
    with pytest.raises(ValueError):
        EvaluationInput(analysis_id='run', start_time=T,
                        end_time=T+timedelta(hours=72, microseconds=1))
