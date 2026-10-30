"""Explicit bounded connection preflight. Does not create environmental evidence."""
from datetime import datetime, timezone
import os
import subprocess
import sys
import httpx
from .service import map_requirements


def check_connections(analysis, inputs):
    providers = {row['routing']['preferred_provider'] for row in map_requirements(analysis)}
    statuses = {}
    for provider in sorted(providers):
        connected = False
        message = 'No live connector is available for this source.'
        try:
            if provider == 'COPERNICUS_MARINE':
                if not (os.getenv('COPERNICUSMARINE_SERVICE_USERNAME') and os.getenv('COPERNICUSMARINE_SERVICE_PASSWORD')):
                    message = 'Credentials required. Configure the Copernicus Marine username and password.'
                else:
                    # Check only; never write credentials or expose subprocess output.
                    code = ('import os,sys,copernicusmarine; '
                            'sys.exit(0 if copernicusmarine.login('
                            'username=os.environ["COPERNICUSMARINE_SERVICE_USERNAME"],'
                            'password=os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"],'
                            'check_credentials_valid=True) else 1)')
                    result = subprocess.run([sys.executable, '-c', code], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, timeout=25, check=False)
                    connected = result.returncode == 0
                    message = 'Credentials verified. Dataset access is checked during retrieval.' if connected else 'Credential verification failed. Check credentials and network access.'
            elif provider in {'ECMWF_FORECAST', 'ERA5'}:
                url = 'https://archive-api.open-meteo.com/v1/archive' if provider == 'ERA5' else 'https://api.open-meteo.com/v1/forecast'
                params = {'latitude': inputs.latitude, 'longitude': inputs.longitude, 'timezone':'UTC'}
                if provider == 'ERA5':
                    day = inputs.start_time.date().isoformat()
                    params.update(start_date=day, end_date=day, models='era5')
                else:
                    params.update(models='ecmwf_ifs', forecast_days=1)
                # No weather variables requested: this checks API metadata only.
                with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    metadata = response.json()
                    connected = isinstance(metadata, dict) and not metadata.get('error') and 'latitude' in metadata
                message = 'Public API reachable. Requested variable and time coverage are checked during retrieval.' if connected else 'Public API did not return valid location metadata.'
        except (httpx.HTTPError, ValueError, OSError, subprocess.TimeoutExpired):
            message = 'Connection check failed or timed out. Check network access and provider configuration.'
        statuses[provider] = {'connected':connected, 'message':message}
    return {'checks':statuses, 'provider_status':{name:('Connected · connection check passed' if state['connected'] else 'Not connected · '+state['message']) for name,state in statuses.items()},
        'checked_at':datetime.now(timezone.utc).isoformat()}
