"""Fetch a bounded Belfast ECMWF IFS weather forecast into the local cache."""
from pathlib import Path
import json, sys
root = Path(__file__).parents[1]
sys.path.insert(0, str(root))
from src.weather.open_meteo import fetch_forecast

result = fetch_forecast(54.6, -5.9, root / "cache" / "weather", forecast_days=3)
print(json.dumps({"provider": result["provider"], "model": result["model"],
                  "provenance_label": result["provenance_label"], "forecast_hours": result["forecast_hours"],
                  "variables": list(result["hourly"].keys()), "units": result["hourly_units"]}, indent=2))
