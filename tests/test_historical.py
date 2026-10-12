from datetime import datetime, timezone, date
from pathlib import Path
from src.historical.analysis import select_mode,equivalent_periods,series_stats,year_windows
from src.historical.service import analyse_history,load_year

T=datetime(2027,4,9,tzinfo=timezone.utc); E=datetime(2027,4,11,23,tzinfo=timezone.utc)
def test_mode_selection_uses_all_required_provider_coverage():
 coverage={'wave':(T,E),'wind_speed':(T,E)}
 assert select_mode(T,E,['wave','wind_speed'],coverage,True)=='FORECAST_ANALYSIS'
 assert select_mode(T,E,['wave','wind_speed'],{'wave':(T,E)},True)=='HISTORICAL_SEASONAL_WEATHER_RISK'
 assert select_mode(T,E,['wave'],{'wave':(T,datetime(2027,4,10,tzinfo=timezone.utc))},True)=='HISTORICAL_SEASONAL_WEATHER_RISK'
 assert select_mode(T,E,['wave'],coverage,False)=='REQUIRES_INPUT'

def test_equivalent_periods_leap_and_year_crossing_are_deterministic():
 periods=equivalent_periods(date(2028,2,29),date(2028,3,2),3)
 assert periods[0][1]==date(2027,2,28) and len(periods)==3
 crossing=equivalent_periods(date(2027,12,31),date(2028,1,2),1)[0]
 assert crossing[1].year==2026 and crossing[2].year==2027

def test_historical_statistics_and_unknown_window_propagation():
 stats=series_stats([1,None,3],2)
 assert stats['samples']==2 and stats['exceedance_hours']==1 and stats['exceedance_pct']==50
 windows=year_windows(['2024-01-01T00:00:00Z','2024-01-01T01:00:00Z'],[1,None],2,quality=False)
 assert windows['unknown_hours']==2 and windows['workable_count']==0

def test_genuine_cached_belfast_history_is_available_offline_with_masked_current_explicit():
 data=load_year(Path('.'),2024)
 assert len(data['wave']['observations'])==24 and data['weather']['model']=='era5'
 assert data['wave']['dataset_id']=='MetO-NWS-WAV-RAN' and data['weather']['data_type']=='HISTORICAL'
 report=analyse_history(Path('.'),[2024,2025,2026],{'wave':1.5,'wind_speed':30})
 assert report['mode']=='HISTORICAL_SEASONAL_WEATHER_RISK' and len(report['years'])==3
 current=analyse_history(Path('.'),[2024],{'current_speed':1})
 assert not current['result']['all_requested_complete']
