"""Load genuine cached seasonal samples and compute descriptive, non-forecast risk."""
import json
from pathlib import Path
from src.historical.analysis import series_stats, year_windows
from src.models.contract import CoverageStatus, YearCoverage, HistoricalRiskResult

def load_year(root:Path,year:int)->dict:
    base=root/'cache'/'historical'/'belfast'/str(year); result={}
    for name in ('wave','current','sst'):
        files=list(base.glob(f'{name}_*.json'))
        if files: result[name]=json.loads(files[0].read_text())
    weather=list(base.glob('era5_*.json'))
    if weather: result['weather']=json.loads(weather[0].read_text())
    return result
def _series(data,name):
    if name=='wave':
        rows=[x for x in data.get('wave',{}).get('observations',[]) if x['variable']=='VHM0']; return [x['time'] for x in rows],[x['value'] for x in rows],'m',data.get('wave',{})
    variable={'wind_speed':'wind_speed_10m','wind_gust':'wind_gusts_10m'}.get(name)
    if variable:
        weather=data.get('weather',{}); return [x+'Z' for x in weather.get('hourly',{}).get('time',[])],weather.get('hourly',{}).get(variable,[]),weather.get('hourly_units',{}).get(variable),weather
    if name=='current_speed':
        rows=[x for x in data.get('current',{}).get('observations',[]) if x['variable']=='current_speed']; return [x['time'] for x in rows],[x['value'] for x in rows],'m s-1',data.get('current',{})
    return [],[],None,{}
def analyse_history(root:Path,years:list[int],thresholds:dict[str,float])->dict:
    coverage=[]; annual=[]; caveats=['HISTORICAL SEASONAL WEATHER RISK — NOT A FORECAST. Historical exceedances are not project downtime, compensation, or entitlement.']
    for year in years:
        data=load_year(root,year); report={'year':year,'variables':{},'coverage_complete':True}
        for variable,threshold in thresholds.items():
            times,values,unit,provenance=_series(data,variable); expected=24 if variable=='wave' else 72
            pct=100*len(values)/expected if expected else 0; status=CoverageStatus.COMPLETE if pct>=99 else CoverageStatus.PARTIAL if pct else CoverageStatus.MISSING
            coverage.append(YearCoverage(year=year,variable=variable,requested_interval=f'{year}-04-09/{year}-04-11',coverage_pct=pct,status=status,product_id=provenance.get('product_id'),dataset_id=provenance.get('dataset_id'),covered_intervals=times[:1]+times[-1:] if times else [],missing_intervals=[]))
            report['variables'][variable]={'unit':unit,'coverage_pct':pct,'statistics':series_stats(values,threshold),'windows':year_windows(times,values,threshold,quality=status==CoverageStatus.COMPLETE)}
            report['coverage_complete'] &= status==CoverageStatus.COMPLETE
        annual.append(report)
    complete=[x['year'] for x in annual if x['coverage_complete']]
    if len(complete)<len(years): caveats.append('One or more required variables/years are incomplete or masked; UNKNOWN periods are excluded from workable and constrained totals.')
    return {'mode':'HISTORICAL_SEASONAL_WEATHER_RISK','result':HistoricalRiskResult(requested_years=years,analysed_years=complete,all_requested_complete=len(complete)==len(years),coverage=coverage,caveats=caveats,risk_label='DESCRIPTIVE SEASONAL WEATHER RISK').model_dump(mode='json'),'years':annual}
