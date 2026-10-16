"""Read-only position linkage regression for existing reviewed source data."""
from pathlib import Path
from datetime import datetime, timezone
from copy import deepcopy
import pytest

from src.permit.persisted_analysis import load_persisted_analysis
from src.permit.review_overlays import list_reviews
from src.permit.decision_engine import evaluate_prerequisite
from tests.test_decision_engine import fixture,run


@pytest.fixture
def persisted_reviews():
    root=Path('.')
    digest='8fcffc25fbf2c29a56bcf33eb02725d57cafeb1135263bea9ee75062b2a6f552'
    run_id='eaec3e9838a64e34813b1e65f70788e0'
    folder=root/'cache/simple_analysis'/digest/run_id
    review=root/'cache/simple_reviews'/digest/run_id/'review_overlays.json'
    if not folder.exists():pytest.skip('Local persisted fixture absent')
    paths=[p for p in folder.iterdir() if p.is_file()]+[review]
    before={p:p.read_bytes() for p in paths}
    result=list_reviews(root,load_persisted_analysis(root,digest,run_id))
    yield result
    assert before=={p:p.read_bytes() for p in paths}


@pytest.mark.parametrize('coordinates,code',[
    ([54.025,-5.925],'POSITION_CONFIRMED'),
    (None,'POSITION_UNRESOLVED'),
    ([54.025,5.925],'POSITION_UNRESOLVED')])
def test_exact_request_point_not_model_grid(persisted_reviews,coordinates,code):
    raw={'prerequisite':'position','context':persisted_reviews['decision_context'],
         'review_rows':persisted_reviews['requirements']}
    row={'evidence':{'latitude':54.025,'longitude':-5.925}}
    if coordinates is not None:row['request']={'coordinates':coordinates}
    start=datetime(2026,10,15,tzinfo=timezone.utc)
    result=evaluate_prerequisite(raw,{'requirements':[row]},start,start)
    assert result[0]==code


def test_reviewed_position_provenance_required(persisted_reviews):
    reviews=deepcopy(persisted_reviews)
    for row in reviews['requirements']:
        if str(row['condition_id'])=='1':row['state']='UNREVIEWED'
    raw={'prerequisite':'position','context':reviews['decision_context'],'review_rows':reviews['requirements']}
    start=datetime(2026,10,15,tzinfo=timezone.utc)
    result=evaluate_prerequisite(raw,{'requirements':[{'request':{'coordinates':[54.025,-5.925]}}]},start,start)
    assert result[0]=='POSITION_UNRESOLVED'


def test_persisted_time_still_confirmed(persisted_reviews):
    raw={'prerequisite':'time','context':persisted_reviews['decision_context'],
         'review_rows':persisted_reviews['requirements']}
    result=evaluate_prerequisite(raw,None,datetime(2026,10,15,tzinfo=timezone.utc),datetime(2026,10,15,2,tzinfo=timezone.utc))
    assert result[0]=='TIME_CONFIRMED'


def test_stop_precedes_wrong_request_position():
    reviews,env=fixture(value=3)
    env['requirements'][0]['request']['coordinates']=[54,6]
    env['requirements'][0]['evidence'].update(requested_coordinates=[54,6],latitude=54,longitude=6)
    result=run(reviews,env)['current_assessment']
    assert result['status']=='STOP'
    assert next(r for r in result['rule_results'] if r['condition_id']=='position')['status']=='UNKNOWN'
