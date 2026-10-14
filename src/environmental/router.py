"""Pure provider routing. Preferred provider never means evidence is available."""
from .catalog import CATALOG, DERIVED_INPUTS, canonical

EXTERNAL_MODES = {'in_situ', 'local_sensor', 'laboratory', 'manual', 'ais', 'gnss', 'observation_required'}
WEATHER = {'wind_speed_10m': 'wind_speed_10m', 'wind_direction_10m': 'wind_direction_10m',
           'wind_gust': 'wind_gusts_10m', 'air_temperature': 'temperature_2m',
           'atmospheric_pressure': 'pressure_msl', 'precipitation': 'precipitation',
           'visibility': 'visibility'}
MARINE = {'significant_wave_height': ('waves', 'VHM0'), 'mean_wave_period': ('waves', 'VTM02'),
          'mean_wave_direction': ('waves', 'VMDR'), 'surface_current_speed': ('currents', 'current_speed'),
          'surface_current_direction': ('currents', 'current_direction'),
          'eastward_current': ('currents', 'uo'), 'northward_current': ('currents', 'vo'),
          'sea_surface_temperature': ('sst', 'thetao'), 'dissolved_oxygen': ('oxygen', 'o2'),
          'suspended_particulate_matter': ('spm', 'SPM'), 'turbidity': ('turbidity', 'TUR')}

# These variables have a verified marine catalogue mapping.  Keep this narrow:
# atmospheric historical/reanalysis variables must continue to route to ERA5.
MARINE_REANALYSIS = set(MARINE)


def route(variable, evidence_type='unspecified', **_):
    if variable in {'environmental_evidence_provenance', 'evidence_provenance'}:
        return {'canonical_variable':variable, 'preferred_provider':'NOT_APPLICABLE',
            'fallback_provider':None,'data_product_family':'EVIDENCE_PROVENANCE','retrieval_mode':'NOT_APPLICABLE',
            'compatibility_status':'INFORMATIONAL','implemented':False,'potential_source_variables':[],
            'notes':'Evidence/provenance requirement applying to retrieved results, not a physical variable. No provider retrieval applicable.'}
    name = canonical(variable)
    family = CATALOG.get(name)
    historical = evidence_type in {'historical', 'reanalysis', 'seasonal'} or variable.startswith('historical_')
    external = family == 'EXTERNAL' or evidence_type in EXTERNAL_MODES
    provider = ('EXTERNAL' if external else 'DERIVED' if family == 'DERIVED' else
                'COPERNICUS_MARINE' if name in MARINE_REANALYSIS else
                'ERA5' if historical and family in {'ATMOSPHERE', 'WAVES'} else
                'ECMWF_FORECAST' if family == 'ATMOSPHERE' else
                'CAMS' if family == 'AIR_QUALITY' else
                'COPERNICUS_MARINE' if family in {'WAVES', 'CURRENTS', 'WATER_QUALITY', 'SEA_ICE'} else 'UNAVAILABLE')
    implemented = (provider == 'ECMWF_FORECAST' and name in WEATHER or
                   provider == 'ERA5' and name in WEATHER or
                   provider == 'COPERNICUS_MARINE' and name in MARINE)
    if name == 'sea_surface_height' and not implemented:
        note = 'NO_VERIFIED_DATASET_MAPPING: model sea-surface height is not available through a verified connector; never treat it as local tide or navigational clearance.'
    else:
        note = ('External deciding evidence required; model data cannot substitute.' if external else
                'Derived indicator: explicit inputs and methodology required; not a raw API variable.' if provider == 'DERIVED' else
                'Provider mapping available — live retrieval not yet implemented' if not implemented else
                'Availability, units, depth, geography and time must be checked at retrieval.')
    return {'canonical_variable': name, 'preferred_provider': provider, 'fallback_provider': None,
            'data_product_family': family, 'retrieval_mode': 'HISTORICAL' if historical else 'FORECAST',
            'compatibility_status': 'EXTERNAL_EVIDENCE_REQUIRED' if external else 'REQUIRES_VALIDATION',
            'implemented': bool(implemented), 'potential_source_variables': DERIVED_INPUTS.get(name, []),
            'notes': note}
