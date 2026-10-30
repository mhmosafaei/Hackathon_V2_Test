from copy import deepcopy
from datetime import datetime,timedelta
import pytest
from src.environmental.catalog import canonical
from src.environmental.router import route
from src.environmental.service import evaluate
from src.environmental.fixture import mock_evidence
from tests.test_simple_environment import requirement,analysis,inputs

def test_surface_speed_alias_routes_to_the_existing_implementation():
    assert canonical('current_speed_surface')=='surface_current_speed'
    assert route('current_speed_surface')==route('surface_current_speed')
    assert route('current_speed_surface')['preferred_provider']=='COPERNICUS_MARINE'
    assert route('current_speed_surface')['implemented']

def test_alias_uses_the_shared_current_components_and_preserves_original_extraction(tmp_path):
    speed=requirement('current_speed_surface',condition_id='9',unit='m/s',operator='>',threshold=1,
        source_spans=[{'page':1,'quotation':'STOP condition: current speed greater than 1.0 m/s.'}])
    east=requirement('eastward_current_component',condition_id='10',unit='m/s',threshold=.6)
    document=analysis(speed,east)
    original=deepcopy(document)
    calls=[]
    def provider(request):
        calls.append(request)
        evidence=mock_evidence(request)
        moment=datetime.fromisoformat(request.start_time)
        finish=datetime.fromisoformat(request.end_time)
        evidence['points']=[]
        while moment<=finish:
            evidence['points'].append({'data_time':moment.isoformat(),'raw_value':.5,'unit':'m/s','component_values':{'uo':.3,'vo':.4}})
            moment+=timedelta(minutes=15)
        return evidence
    result=evaluate(document,inputs(),tmp_path,transports={'COPERNICUS_MARINE':provider})
    speed_row=result['requirements'][0]
    assert speed_row['canonical_variable']=='surface_current_speed'
    assert speed_row['routing']['preferred_provider']=='COPERNICUS_MARINE'
    assert speed_row['evidence']['points'][0]['raw_value']==pytest.approx(.5)
    assert speed_row['status']=='WITHIN_THRESHOLD'
    assert len(calls)==1
    assert document==original
