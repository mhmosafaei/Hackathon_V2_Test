from types import SimpleNamespace
from unittest.mock import patch
import subprocess
from src.environmental.connections import check_connections

def inputs():
    from datetime import datetime, timezone
    return SimpleNamespace(latitude=54,longitude=-6,start_time=datetime(2026,10,30,tzinfo=timezone.utc))

def mapping(*providers):
    return [{'routing':{'preferred_provider':name}} for name in providers]

def test_missing_credentials_does_not_attempt_auth(monkeypatch):
    monkeypatch.delenv('COPERNICUSMARINE_SERVICE_USERNAME',raising=False)
    monkeypatch.delenv('COPERNICUSMARINE_SERVICE_PASSWORD',raising=False)
    with patch('src.environmental.connections.map_requirements',return_value=mapping('COPERNICUS_MARINE')),patch('src.environmental.connections.subprocess.run') as run:
        result=check_connections({},inputs())
    assert not result['checks']['COPERNICUS_MARINE']['connected']
    assert 'Credentials required' in result['checks']['COPERNICUS_MARINE']['message']
    run.assert_not_called()

def test_auth_is_bounded_and_does_not_return_secrets(monkeypatch):
    monkeypatch.setenv('COPERNICUSMARINE_SERVICE_USERNAME','test-user')
    monkeypatch.setenv('COPERNICUSMARINE_SERVICE_PASSWORD','secret-test-password')
    with patch('src.environmental.connections.map_requirements',return_value=mapping('COPERNICUS_MARINE')),patch('src.environmental.connections.subprocess.run',side_effect=subprocess.TimeoutExpired('python',25)) as run:
        result=check_connections({},inputs())
    assert not result['checks']['COPERNICUS_MARINE']['connected']
    assert 'secret-test-password' not in str(result)
    assert run.call_args.kwargs['timeout']==25
    assert 'secret-test-password' not in str(run.call_args)

def test_weather_checks_metadata_without_requesting_variables():
    response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'latitude':54})
    with patch('src.environmental.connections.map_requirements',return_value=mapping('ECMWF_FORECAST')),patch('src.environmental.connections.httpx.Client') as client:
        client.return_value.__enter__.return_value.get.return_value=response
        result=check_connections({},inputs())
    assert result['checks']['ECMWF_FORECAST']['connected']
    params=client.return_value.__enter__.return_value.get.call_args.kwargs['params']
    assert 'hourly' not in params and 'current' not in params

def test_connection_endpoint_requires_current_session_and_never_sets_evidence(tmp_path):
    import asyncio
    import httpx
    from src.permit.simple_api import create_app
    app=create_app(root=tmp_path)
    app.state.analyses['run']={'analysis_id':'run'}
    body={'analysis_id':'run','latitude':54,'longitude':-6,'start_time':'2026-10-30T12:00:00Z','end_time':'2026-10-31T12:00:00Z'}
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
            assert (await client.post('/api/environmental/connections',json=body)).status_code==409
            headers={'X-Session-Id':app.state.boot_id}
            with patch('src.environmental.connections.check_connections',return_value={'checks':{},'provider_status':{}}) as check:
                assert (await client.post('/api/environmental/connections',json=body,headers=headers)).status_code==200
                check.assert_called_once()
            assert app.state.environmental_results=={}
            assert (await client.post('/api/environmental/connections',json=body,headers={**headers,'Origin':'https://unrelated.example'})).status_code==403
    asyncio.run(exercise())
