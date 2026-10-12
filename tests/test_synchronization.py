import pytest
from src.environment.synchronization import aggregate_hourly, shared_hourly_grid, advisory_intervals, coverage_percent, parse_utc
from src.copernicus.live import fetch_product
from src.environment.location import retrieve_location, location_key
from pathlib import Path

def test_mixed_frequency_alignment_uses_documented_aggregation_without_interpolation():
 current=aggregate_hourly(['2026-01-01T00:00Z','2026-01-01T00:15Z','2026-01-01T01:00Z'],[1,3,2],'max')
 assert current['2026-01-01T00:00:00Z']==3
 grid,values=shared_hourly_grid({'current':(['2026-01-01T00:00Z','2026-01-01T00:15Z'],[1,3],'max'), 'wind':(['2026-01-01T01:00Z'],[5],'mean')})
 assert values['current']==[3.0,None] and values['wind']==[None,5.0]

def test_advisory_unknown_missing_quality_boundaries_and_limiters():
 times=['2026-01-01T00:00:00Z','2026-01-01T01:00:00Z','2026-01-01T02:00:00Z']
 result=advisory_intervals(times,{'wave':[1,2,1],'wind':[1,None,4]},{'wave':1,'wind':3},{'wave':True,'wind':True},minimum_hours=2)
 assert [x['status'] for x in result]==['WORKABLE','UNKNOWN','NON_WORKABLE']
 assert result[1]['limiting_variables']==['wind'] and not result[0]['meets_minimum_duration']
 assert coverage_percent([1,None,2])==pytest.approx(66.6666666667)

def test_stale_or_unrepresentative_input_is_unknown_and_invalid_locations_are_rejected():
 result=advisory_intervals(['2026-01-01T00:00:00Z'],{'wave':[1]},{'wave':2},{'wave':False})
 assert result[0]['status']=='UNKNOWN'
 with pytest.raises(ValueError): advisory_intervals(['x'],{'wave':[1]},{'wind':2},{'wave':True})
 with pytest.raises(ValueError): fetch_product('waves',91,0,'2026-01-01T00:00:00Z','2026-01-01T01:00:00Z',Path('.'))
 assert location_key(54.6,-5.9)==location_key(54.600001,-5.900001)
 with pytest.raises(ValueError): retrieve_location(Path('.'),100,0)
