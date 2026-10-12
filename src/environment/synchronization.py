"""UTC alignment and advisory-only environmental window evaluation."""
from collections import defaultdict
from datetime import datetime, timezone

def parse_utc(value: str) -> datetime:
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    return (parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc))

def hour_key(value: str) -> str:
    return parse_utc(value).replace(minute=0, second=0, microsecond=0).isoformat().replace('+00:00','Z')

def aggregate_hourly(times: list[str], values: list[float | None], method: str = 'mean') -> dict[str, float | None]:
    """Aggregate only real samples within an hour; missing samples do not get filled."""
    buckets=defaultdict(list)
    for time,value in zip(times,values):
        if value is not None: buckets[hour_key(time)].append(float(value))
    if method not in {'mean','max','min'}: raise ValueError('unsupported aggregation method')
    fn={'mean':lambda xs:sum(xs)/len(xs),'max':max,'min':min}[method]
    return {time:fn(values) for time,values in buckets.items()}

def shared_hourly_grid(series: dict[str, tuple[list[str], list[float | None], str]]) -> tuple[list[str], dict[str, list[float | None]]]:
    """Return union UTC grid; values remain None where a source has no sample."""
    mapped={name:aggregate_hourly(times,values,method) for name,(times,values,method) in series.items()}
    grid=sorted({timestamp for points in mapped.values() for timestamp in points})
    return grid,{name:[points.get(timestamp) for timestamp in grid] for name,points in mapped.items()}

def advisory_intervals(times: list[str], values: dict[str, list[float | None]], thresholds: dict[str,float],
                       quality: dict[str,bool], minimum_hours: int=1) -> list[dict]:
    """AND semantics: missing, stale or unrepresentative required evidence is UNKNOWN."""
    if set(values)!=set(thresholds) or set(values)!=set(quality) or any(len(v)!=len(times) for v in values.values()):
        raise ValueError('required variable sets and lengths must match')
    labels=[]
    for index,time in enumerate(times):
        missing=[name for name,items in values.items() if not quality[name] or items[index] is None]
        exceeded=[name for name,items in values.items() if quality[name] and items[index] is not None and items[index]>thresholds[name]]
        labels.append(('UNKNOWN' if missing else 'NON_WORKABLE' if exceeded else 'WORKABLE', missing or exceeded))
    intervals=[]; start=0
    for index in range(1,len(times)+1):
        if index==len(times) or labels[index][0]!=labels[start][0] or labels[index][1]!=labels[start][1]:
            duration=index-start
            intervals.append({'status':labels[start][0],'start':times[start],'end':times[index-1],
                              'duration_hours':duration,'limiting_variables':labels[start][1],
                              'meets_minimum_duration':labels[start][0]=='WORKABLE' and duration>=minimum_hours,
                              'advisory':True})
            start=index
    return intervals

def coverage_percent(values: list[float | None]) -> float:
    return 0 if not values else 100*sum(v is not None for v in values)/len(values)
