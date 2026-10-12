"""Nearest valid ocean-cell selection with explicit coastal representativeness."""
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
@dataclass(frozen=True)
class GridSelection: requested_lat:float; requested_lon:float; selected_lat:float|None; selected_lon:float|None; distance_km:float|None; representativeness:str
def haversine_km(a,b,c,d):
    x=sin(radians(c-a)/2)**2+cos(radians(a))*cos(radians(c))*sin(radians(d-b)/2)**2
    return 6371*2*asin(sqrt(x))
def nearest_valid(requested_lat,requested_lon,cells):
    valid=[x for x in cells if x[2] is not None]
    if not valid:return GridSelection(requested_lat,requested_lon,None,None,None,'UNKNOWN')
    lat,lon,_=min(valid,key=lambda x:haversine_km(requested_lat,requested_lon,x[0],x[1])); distance=haversine_km(requested_lat,requested_lon,lat,lon)
    return GridSelection(requested_lat,requested_lon,lat,lon,distance,'GOOD' if distance<=5 else 'MODERATE' if distance<=20 else 'POOR')
