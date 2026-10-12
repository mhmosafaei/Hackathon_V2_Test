"""Pure mode selection, equivalent-period construction and historical statistics."""
from datetime import date, datetime, timedelta
from statistics import median
from src.environment.synchronization import advisory_intervals

def select_mode(start: datetime, end: datetime, required: list[str], coverage: dict[str,tuple[datetime,datetime]], parameters_complete: bool) -> str:
    if not parameters_complete or not required: return 'REQUIRES_INPUT'
    if any(variable not in coverage for variable in required): return 'HISTORICAL_SEASONAL_WEATHER_RISK'
    complete=all(coverage[x][0]<=start and coverage[x][1]>=end for x in required)
    return 'FORECAST_ANALYSIS' if complete else 'HISTORICAL_SEASONAL_WEATHER_RISK'

def equivalent_periods(start: date,end: date,years:int=3)->list[tuple[int,date,date]]:
    if years<1: raise ValueError('years must be positive')
    result=[]
    for year in range(start.year-1,start.year-years-1,-1):
        def replace(value,target_year):
            try:return value.replace(year=target_year)
            except ValueError:return value.replace(year=target_year,day=28) # leap-day equivalent
        start_value=replace(start,year)
        end_value=replace(end,year+1 if (end.month,end.day)<(start.month,start.day) else year)
        result.append((year,start_value,end_value))
    return result

def series_stats(values:list[float|None],threshold:float|None=None)->dict:
    usable=sorted(float(x) for x in values if x is not None)
    if not usable:return {'samples':0,'mean':None,'p50':None,'p90':None,'maximum':None,'exceedance_hours':None,'exceedance_pct':None}
    p90=usable[round((len(usable)-1)*.9)]
    exceed=sum(x>threshold for x in usable) if threshold is not None else None
    return {'samples':len(usable),'mean':sum(usable)/len(usable),'p50':median(usable),'p90':p90,'maximum':max(usable),'exceedance_hours':exceed,'exceedance_pct':100*exceed/len(usable) if exceed is not None else None}

def year_windows(times,values,threshold,quality=True):
    if not times:return {'windows':[],'workable_count':0,'longest_workable_hours':0,'median_workable_hours':None,'weather_constrained_hours':0,'unknown_hours':0}
    rows=advisory_intervals(times,{'threshold':values},{'threshold':threshold},{'threshold':quality},1)
    work=[x['duration_hours'] for x in rows if x['status']=='WORKABLE']; unknown=sum(x['duration_hours'] for x in rows if x['status']=='UNKNOWN')
    return {'windows':rows,'workable_count':len(work),'longest_workable_hours':max(work,default=0),'median_workable_hours':median(work) if work else None,'weather_constrained_hours':sum(x['duration_hours'] for x in rows if x['status']=='NON_WORKABLE'),'unknown_hours':unknown}
