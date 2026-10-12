"""Cache-only Belfast dashboard view model with explicit gaps and provenance."""
import json
from datetime import datetime, timezone
from pathlib import Path
from src.copernicus.adapter import load_cached_product
from src.weather.open_meteo import load_cached_forecast

MARINE_PRODUCTS = ("waves", "currents", "sst", "spm", "oxygen")

def load_belfast(root: Path) -> dict:
    cache = root / "cache"
    marine = {}
    for name in MARINE_PRODUCTS:
        try:
            marine[name] = load_cached_product(name, cache / "copernicus", max_age_hours=48)
        except FileNotFoundError:
            marine[name] = {"missing": True, "reason": "no cached result"}
    synchronized=cache/'copernicus'/'synchronized'/'manifest.json'
    if synchronized.exists():
        for result in json.loads(synchronized.read_text()).get('results',[]):
            if 'error' not in result:
                retrieved=datetime.fromisoformat(result['retrieved_at'].replace('Z','+00:00'))
                result['cache_age_hours']=(datetime.now(timezone.utc)-retrieved).total_seconds()/3600
                result['cache_fresh']=result['cache_age_hours']<=12
                marine[result['name']]=result
    try:
        weather = load_cached_forecast(cache / "weather", max_age_hours=12)
    except FileNotFoundError:
        weather = {"missing": True, "reason": "no cached result"}
    return {"marine": marine, "weather": weather}

def marine_series(product: dict, variable: str) -> tuple[list[str], list[float | None], str | None]:
    values=[]; times=[]; unit=None
    for row in product.get("observations", []):
        if row.get("variable") == variable:
            times.append(row["coordinates"].get("time")); values.append(row.get("value")); unit=row.get("unit")
    return times, values, unit

def weather_series(weather: dict, variable: str) -> tuple[list[str], list[float | None], str | None]:
    hourly=weather.get("hourly", {})
    times=[time if time.endswith('Z') else time+'Z' for time in hourly.get("time", [])]
    return times, hourly.get(variable, []), weather.get("hourly_units", {}).get(variable)

def evidence_readiness(root: Path) -> list[dict]:
    aggregate=root / "cache" / "extractions" / "ml2025054" / "aggregate.json"
    decisions=root / "cache" / "extractions" / "ml2025054" / "review_decisions.json"
    if not aggregate.exists(): return []
    states=json.loads(decisions.read_text()) if decisions.exists() else {}
    rows=[]
    for c in json.loads(aggregate.read_text())["conditions"]:
        evidence=c.get("evidence_requirements") or []
        rows.append({"condition_id":c["condition_id"], "clause":c.get("clause"), "page":c.get("page_number"),
                     "source_text":c.get("source_text"), "quote_verified":c.get("quote_verified"),
                     "review_state":states.get(c["condition_id"],{}).get("decision", "UNREVIEWED"),
                     "evidence_required":", ".join(evidence) or "UNKNOWN", "automation_status":c.get("automation_status"),
                     "environmental_role":"EXTERNAL/DECIDING REQUIRED" if any(x in {"LOCAL_SENSOR","AIS_GNSS","LAB_RESULT"} for x in evidence) else "SUPPORTIVE OR PREDICTIVE ONLY"})
    return rows
