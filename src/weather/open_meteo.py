"""Bounded Open-Meteo retrieval with explicit ECMWF model provenance."""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

BASE_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
ECMWF_MODEL = "ecmwf_ifs025"
VARIABLES = [
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m", "precipitation",
    "temperature_2m", "pressure_msl", "relative_humidity_2m", "cloud_cover", "visibility",
]

def cache_path(cache_dir: Path) -> Path:
    return cache_dir / "open_meteo_belfast.json"

def fetch_forecast(latitude: float, longitude: float, cache_dir: Path, forecast_days: int = 3,
                   timeout_seconds: int = 20, attempts: int = 3) -> dict:
    """Fetch a small hourly forecast and persist only response/provenance, never secrets."""
    if not 1 <= forecast_days <= 7:
        raise ValueError("forecast_days must be between 1 and 7")
    query = urlencode({"latitude": latitude, "longitude": longitude, "hourly": ",".join(VARIABLES),
                       "timezone": "UTC", "forecast_days": forecast_days, "models": ECMWF_MODEL})
    last_error = None
    for _ in range(attempts):
        try:
            with urlopen(f"{BASE_URL}?{query}", timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            hourly = payload.get("hourly", {})
            if not hourly.get("time"):
                raise ValueError("Open-Meteo returned no hourly time series")
            result = {"provider": "Open-Meteo", "model": ECMWF_MODEL,
                      "provenance_label": "ECMWF IFS via Open-Meteo",
                      "data_type": "FORECAST", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                      "requested_coordinates": [latitude, longitude], "response_latitude": payload.get("latitude"),
                      "response_longitude": payload.get("longitude"), "elevation": payload.get("elevation"),
                      "utc_offset_seconds": payload.get("utc_offset_seconds"), "hourly_units": payload.get("hourly_units", {}),
                      "hourly": hourly, "forecast_hours": len(hourly["time"]), "endpoint": BASE_URL}
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path(cache_dir).write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(f"Open-Meteo request failed after {attempts} attempts: {type(last_error).__name__}: {last_error}")

def load_cached_forecast(cache_dir: Path, max_age_hours: float | None = None, now: datetime | None = None) -> dict:
    payload = json.loads(cache_path(cache_dir).read_text(encoding="utf-8"))
    required = {"provider", "model", "provenance_label", "retrieved_at", "hourly", "hourly_units"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"incomplete weather cache metadata: {sorted(missing)}")
    retrieved = datetime.fromisoformat(payload["retrieved_at"].replace("Z", "+00:00"))
    age = ((now or datetime.now(timezone.utc)) - retrieved).total_seconds() / 3600
    payload["cache_age_hours"] = age
    payload["cache_fresh"] = max_age_hours is None or age <= max_age_hours
    return payload

def fetch_history(latitude: float, longitude: float, start_date: str, end_date: str, cache_dir: Path, timeout_seconds: int = 20) -> dict:
    """Fetch genuine ERA5 historical hourly values; never label them as IFS forecasts."""
    query=urlencode({"latitude":latitude,"longitude":longitude,"start_date":start_date,"end_date":end_date,
                     "hourly":",".join(VARIABLES),"timezone":"UTC","models":"era5"})
    try:
        with urlopen(f"{ARCHIVE_URL}?{query}",timeout=timeout_seconds) as response: payload=json.loads(response.read().decode('utf-8'))
    except (HTTPError,URLError,TimeoutError) as exc: raise RuntimeError(f'Open-Meteo historical request failed: {type(exc).__name__}: {exc}')
    hourly=payload.get('hourly',{})
    if not hourly.get('time'): raise ValueError('Open-Meteo archive returned no hourly history')
    result={'provider':'Open-Meteo','model':'era5','provenance_label':'ERA5 via Open-Meteo historical archive','data_type':'HISTORICAL','retrieved_at':datetime.now(timezone.utc).isoformat(),'requested_coordinates':[latitude,longitude],'start_date':start_date,'end_date':end_date,'hourly_units':payload.get('hourly_units',{}),'hourly':hourly,'hours':len(hourly['time']),'endpoint':ARCHIVE_URL}
    cache_dir.mkdir(parents=True,exist_ok=True); (cache_dir/f'era5_{start_date}_{end_date}.json').write_text(json.dumps(result,indent=2),encoding='utf-8'); return result
