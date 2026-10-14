"""Static application capability matrix, separate from provider availability."""

P0_CAPABILITIES = [
    {'canonical_variable':'significant_wave_height','display_name':'Significant wave height (Hs)','provider_family':'COPERNICUS_MARINE','implementation_status':'SUPPORTED','unit':'m','derived':False,'notes':'VHM0 from the verified North-West European shelf waves product.'},
    {'canonical_variable':'mean_wave_period','display_name':'Mean wave period','provider_family':'COPERNICUS_MARINE','implementation_status':'SUPPORTED','unit':'s','derived':False,'notes':'VTM02; source direction/period semantics remain provider-labelled.'},
    {'canonical_variable':'mean_wave_direction','display_name':'Mean wave direction','provider_family':'COPERNICUS_MARINE','implementation_status':'SUPPORTED','unit':'degrees','derived':False,'notes':'VMDR; direction convention is preserved as provider-defined and is not converted to from/towards.'},
    {'canonical_variable':'eastward_current','display_name':'Eastward current U','provider_family':'COPERNICUS_MARINE','implementation_status':'SUPPORTED','unit':'m/s','derived':False,'notes':'uo is retrieved in the shared current vector request and independently projected; evidence remains modelled coastal context.'},
    {'canonical_variable':'northward_current','display_name':'Northward current V','provider_family':'COPERNICUS_MARINE','implementation_status':'SUPPORTED','unit':'m/s','derived':False,'notes':'vo is retrieved in the shared current vector request and independently projected; evidence remains modelled coastal context.'},
    {'canonical_variable':'current_speed','display_name':'Current speed','provider_family':'COPERNICUS_MARINE','implementation_status':'SUPPORTED','unit':'m/s','derived':True,'notes':'Public alias for surface_current_speed; sqrt(uo² + vo²).'},
    {'canonical_variable':'current_direction','display_name':'Current direction','provider_family':'COPERNICUS_MARINE','implementation_status':'SUPPORTED','unit':'degrees','derived':True,'notes':'Public alias for surface_current_direction; towards, clockwise from north.'},
    {'canonical_variable':'wind_speed_10m','display_name':'Wind speed at 10 m','provider_family':'ECMWF_FORECAST','implementation_status':'SUPPORTED','unit':'m/s','derived':False,'notes':'ECMWF IFS via Open-Meteo.'},
    {'canonical_variable':'wind_direction_10m','display_name':'Wind direction at 10 m','provider_family':'ECMWF_FORECAST','implementation_status':'SUPPORTED','unit':'degrees','derived':False,'notes':'Provider direction field preserved.'},
    {'canonical_variable':'wind_gust','display_name':'Wind gust','provider_family':'ECMWF_FORECAST','implementation_status':'SUPPORTED','unit':'m/s','derived':False,'notes':'Open-Meteo wind_gusts_10m.'},
    {'canonical_variable':'precipitation','display_name':'Precipitation','provider_family':'ECMWF_FORECAST','implementation_status':'SUPPORTED','unit':'mm','derived':False,'notes':'Hourly accumulated precipitation; interval metadata is retained.'},
    {'canonical_variable':'turbidity','display_name':'Turbidity (FNU)','provider_family':'COPERNICUS_MARINE','implementation_status':'SUPPORTED','unit':'FNU','derived':False,'notes':'Verified TUR path; supportive/model evidence only. No NTU↔FNU conversion and no substitution for required local/in-situ monitoring.'},
    {'canonical_variable':'visibility','display_name':'Visibility','provider_family':'ECMWF_FORECAST','implementation_status':'PARTIAL','unit':'m','derived':False,'notes':'Open-Meteo exposes an explicit visibility field, but live unit metadata must be present; missing units fail visibly rather than being invented.'},
    {'canonical_variable':'air_temperature','display_name':'Air temperature','provider_family':'ECMWF_FORECAST','implementation_status':'SUPPORTED','unit':'°C','derived':False,'notes':'Open-Meteo temperature_2m.'},
    {'canonical_variable':'sea_surface_height','display_name':'Sea-surface height','provider_family':'COPERNICUS_MARINE','implementation_status':'UNAVAILABLE','unit':'m','derived':False,'notes':'No verified dataset/variable mapping or datum suitable for local tidal clearance is present.'},
]

def capability_matrix():
    return [dict(item) for item in P0_CAPABILITIES]


def capability_for(variable):
    """Return the single capability record for a router canonical variable.

    The public matrix retains the historical ``current_speed`` and
    ``current_direction`` names.  Lookup is canonicalized here so router names
    (``surface_current_speed`` and ``surface_current_direction``) do not create
    a second competing vocabulary or require service-layer special cases.
    """
    from .catalog import canonical
    name = canonical(variable)
    aliases = {
        'surface_current_speed': 'current_speed',
        'surface_current_direction': 'current_direction',
    }
    lookup_name = aliases.get(name, name)
    for item in P0_CAPABILITIES:
        if item['canonical_variable'] == lookup_name:
            return dict(item, canonical_variable=name)
    return None
