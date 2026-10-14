"""Source-context checks use offline transport; no API or provider calls."""
import json
import pymupdf
import pytest
from src.permit.simple_analysis import analyze, response_schema, PROMPT
from src.permit.simple_fixture import mock_request
from jsonschema import Draft202012Validator


@pytest.mark.parametrize('crs,original,lat,lon,expected',[
    ('WGS84','WGS84 54.1 -6.1',54.1,-6.1,True),
    ('Irish Grid Reference','IGR 123456E 234567N',None,None,False),
    ('WGS84','WGS84 54.1 -6.1',55.5,-6.1,False)])
def test_context_source_verification_and_no_second_request(tmp_path,crs,original,lat,lon,expected):
    text=f'Work location: Synthetic Point. {crs}. {original}.\nPermit validity: 29 March 2024 to 28 March 2027.\n1. Retain records.'
    pdf=pymupdf.open();pdf.new_page().insert_text((50,60),text,fontsize=9);data=pdf.tobytes();pdf.close()
    calls=[]
    def transport(packet):
        calls.append(1);result=mock_request(packet)
        span=[{'page':1,'quotation':packet['pages'][0].text.strip()}]
        result['spatial_context']=[dict(location_name='Synthetic Point',coordinates_original=original,coordinate_system=crs,
            latitude=lat,longitude=lon,easting=None,northing=None,source_page=1,
            geometry_type='point',source_reference='Particulars',source_spans=span)]
        result['temporal_context'].update(permit_valid_from='29 March 2024',permit_valid_until='28 March 2027',source_spans=span)
        return result
    result=analyze(data,'synthetic-context.pdf',tmp_path,transport=transport)
    assert calls==[1] and result['spatial_context'][0]['point_verified']==expected
    assert result['temporal_context']['source_verified']
    assert result['temporal_context']['operation_start'] is None
    assert result['executable_rules']==0
    raw=json.loads(next((tmp_path/'cache/simple_analysis').rglob('response.json')).read_text())
    assert 'point_verified' not in raw['spatial_context'][0]


def test_context_strict_schema_and_published_contract():
    from pathlib import Path
    schema=response_schema();Draft202012Validator.check_schema(schema)
    assert schema['properties']['spatial_context']['items']['additionalProperties'] is False
    assert set(schema['properties']['temporal_context']['required'])==set(schema['properties']['temporal_context']['properties'])
    assert json.loads(Path('docs/SIMPLE_PERMIT_RESPONSE.schema.json').read_text())==schema
    assert Path('prompts/simple_permit_v1.txt').read_text().strip()==PROMPT.strip()


@pytest.mark.parametrize('bad_easting', [False, True])
def test_narrow_water_spatial_survives_strict_response_persistence_and_api(tmp_path, monkeypatch, bad_easting):
    from fastapi.testclient import TestClient
    from src.permit.simple_api import create_app
    from src.permit.simple_analysis import parse_response
    from types import SimpleNamespace as NS
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-4.1-mini')
    text = ('4. Location of works:\n'
            'Burren Roundabout, Warrenpoint, County Down IGR 312890E 319096N\n'
            'Permit validity: 29 March 2024 to 28 March 2027.')
    pdf = pymupdf.open(); pdf.new_page().insert_text((50, 60), text, fontsize=9)
    data = pdf.tobytes(); pdf.close()
    calls = []
    def transport(packet):
        calls.append(1)
        result = mock_request(packet)
        result['conditions'] = []  # Particulars are not invented operative conditions.
        result['key_limits'] = []
        span = [{'page': 1, 'quotation': packet['pages'][0].text.strip()}]
        result['spatial_context'] = [{
            'location_name': 'Burren Roundabout, Warrenpoint, County Down',
            'coordinates_original': 'IGR 312890E 319096N',
            'coordinate_system': 'Irish Grid Reference',
            'easting': 312891 if bad_easting else 312890, 'northing': 319096,
            'latitude': None, 'longitude': None, 'geometry_type': 'point',
            'source_page': 1, 'source_reference': '4. Location of works', 'source_spans': span}]
        result['temporal_context'].update(permit_valid_from='29 March 2024',
            permit_valid_until='28 March 2027', source_spans=span)
        response = NS(id='offline-fixture', usage=None, choices=[NS(finish_reason='stop',
            message=NS(content=json.dumps(result), refusal=None))])
        return parse_response(response, packet['model'])
    app = create_app(tmp_path, transport=transport)
    with TestClient(app) as client:
        boot = client.get('/api/session').json()['boot_id']
        response = client.post('/api/analyze', content=data,
            headers={'x-session-id': boot, 'x-filename': 'narrow-water-fixture.pdf'})
    assert response.status_code == 200 and calls == [1]
    body = response.json()
    saved = json.loads(next((tmp_path/'cache/simple_analysis').rglob('analysis.json')).read_text())
    assert body == saved == app.state.analyses[body['analysis_id']]
    context = body['spatial_context'][0]
    assert context['coordinates_original'] == 'IGR 312890E 319096N'
    assert context['northing'] == 319096 and context['source_page'] == 1
    assert context['source_verified'] is (not bad_easting)
    assert context['latitude'] is None and context['longitude'] is None
    assert context['point_verified'] is False  # Not a converted WGS84 query point.
    assert body['temporal_context']['source_verified']
    assert body['temporal_context']['operation_start'] is None
    assert body['review_state'] == 'UNREVIEWED' and body['executable_rules'] == 0
