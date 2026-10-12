"""Pure analytics. Advisory thresholds never yield legal compliance decisions."""
from math import isnan

def summary(values: list[float | None]) -> dict:
    usable = sorted(float(v) for v in values if v is not None and not isnan(float(v)))
    if not usable:
        return {"count": 0, "mean": None, "maximum": None, "p50": None, "p90": None}
    def percentile(p: float) -> float:
        position = (len(usable)-1)*p; low=int(position); high=min(low+1,len(usable)-1)
        return usable[low]+(usable[high]-usable[low])*(position-low)
    return {"count": len(usable), "mean": sum(usable)/len(usable), "maximum": max(usable),
            "p50": percentile(.5), "p90": percentile(.9)}

def rainfall_total(values: list[float | None]) -> float:
    return sum(float(v) for v in values if v is not None and not isnan(float(v)))

def advisory_windows(times: list[str], required: dict[str, list[float | None]], thresholds: dict[str, float]) -> list[dict]:
    """Return windows only where every required value exists and is within its advisory threshold."""
    if not times or set(required) != set(thresholds) or any(len(v) != len(times) for v in required.values()):
        return []
    windows=[]; start=None
    for i in range(len(times)+1):
        okay = i < len(times) and all(values[i] is not None and not isnan(float(values[i])) and float(values[i]) <= thresholds[name] for name,values in required.items())
        if okay and start is None: start=i
        if not okay and start is not None:
            windows.append({"start": times[start], "end": times[i-1], "samples": i-start, "advisory": True})
            start=None
    return windows

def exceedance_hours(values: list[float | None], threshold: float, step_hours: float = 1) -> float:
    return sum(step_hours for value in values if value is not None and not isnan(float(value)) and float(value) > threshold)
