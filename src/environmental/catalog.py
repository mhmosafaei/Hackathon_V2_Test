"""Canonical vocabulary, not a claim of provider availability or integration."""
FAMILIES = {
    'ATMOSPHERE': '''wind_speed_10m wind_direction_10m wind_gust wind_speed_100m hub_height_wind air_temperature apparent_temperature atmospheric_pressure pressure_tendency relative_humidity dew_point precipitation heavy_rainfall snowfall cloud_cover cloud_base visibility thunderstorm_risk solar_radiation atmospheric_stability'''.split(),
    'WAVES': '''significant_wave_height maximum_wave_height mean_wave_period peak_wave_period mean_wave_direction peak_wave_direction wind_wave_height swell_height swell_direction swell_period wave_energy wave_steepness wave_height_exceedance workable_sea_state_hours breaking_wave_conditions'''.split(),
    'CURRENTS': '''eastward_current northward_current surface_current_speed surface_current_direction subsurface_current_speed seabed_current_speed current_profile current_threshold_exceedance sea_surface_height sea_level_anomaly tidal_elevation tidal_current high_low_water_time storm_surge total_water_level water_depth under_keel_clearance sediment_transport_potential'''.split(),
    'WATER_QUALITY': '''sea_surface_temperature water_temperature_depth salinity dissolved_oxygen oxygen_saturation chlorophyll_a turbidity suspended_particulate_matter suspended_sediment_concentration water_transparency light_attenuation nitrate phosphate silicate ammonium ph dissolved_inorganic_carbon alkalinity phytoplankton_biomass primary_productivity sediment_plume_extent water_quality_threshold_exceedance'''.split(),
    'SEA_ICE': '''sea_ice_concentration sea_ice_thickness sea_ice_drift_speed sea_ice_drift_direction sea_ice_extent ice_edge_distance iceberg_location freezing_conditions sea_ice_threshold_exceedance'''.split(),
    'AIR_QUALITY': '''pm10 pm2_5 nitrogen_dioxide sulphur_dioxide ozone carbon_monoxide atmospheric_dust aerosol_optical_depth air_quality_threshold_exceedance atmospheric_dispersion_potential'''.split(),
    'DERIVED': '''weather_window continuous_workable_hours weather_downtime weather_delay_probability seasonal_weather_risk joint_wind_wave_exceedance environmental_operating_window safe_lifting_window dp_environmental_exposure sediment_dispersion_potential water_quality_excursion_duration metocean_return_period workability_percentage weather_standby_exposure combined_environmental_risk'''.split(),
    'EXTERNAL': '''ais_status gnss_position vessel_inside_geofence disposal_event_position licence_received report_submitted cemp_approved dredged_quantity archaeological_discovery vessel_logs trenching_location construction_activity laboratory_sample_result'''.split(),
}
CATALOG = {name: family for family, names in FAMILIES.items() for name in names}
ALIASES = {'wave_direction': 'mean_wave_direction', 'wind_speed': 'wind_speed_10m',
           # AI extraction may retain a descriptive suffix; these aliases keep
           # the provider-facing vocabulary canonical and deterministic.
           'mean_wave_direction_degrees': 'mean_wave_direction',
           'wave_direction_degrees': 'mean_wave_direction',
           'dissolved oxygen': 'dissolved_oxygen', 'oxygen': 'dissolved_oxygen',
           'dissolved_oxygen_1m_below_surface': 'dissolved_oxygen',
           'dissolved_oxygen_surface': 'dissolved_oxygen',
           'surface current speed': 'surface_current_speed',
           'current speed surface': 'surface_current_speed',
           'eastward current': 'eastward_current',
           'current component eastward': 'eastward_current',
           'eastward_current': 'eastward_current',
           'eastward_current_component': 'eastward_current',
           'eastward_current_component_u': 'eastward_current',
           'current_u': 'eastward_current', 'u current': 'eastward_current', 'uo': 'eastward_current',
           'northward current': 'northward_current',
           'current component northward': 'northward_current',
           'northward_current': 'northward_current',
           'northward_current_component': 'northward_current',
           'northward_current_component_v': 'northward_current',
           'current_v': 'northward_current', 'v current': 'northward_current', 'vo': 'northward_current',
           'surface current direction': 'surface_current_direction',
           'current_direction_towards_degrees': 'surface_current_direction',
           'current_direction_towards_true_north': 'surface_current_direction',
           'current_direction_degrees_towards_true_north': 'surface_current_direction',
           'current_direction_towards': 'surface_current_direction',
           'air_temperature_2m':'air_temperature', 'temperature_2m':'air_temperature',
           'air temperature':'air_temperature', '2 m air temperature':'air_temperature',
           'temperature 2m':'air_temperature',
           'wind_gusts_10m': 'wind_gust', 'wind_gust_10m_forecast': 'wind_gust',
           'wind_gust_10m': 'wind_gust', 'wind_direction_10m_degrees': 'wind_direction_10m',
           '10m_wind_speed': 'wind_speed_10m', '10m_wind_direction': 'wind_direction_10m',
           '10m_wind_gust': 'wind_gust',
           'hourly_precipitation_accumulated': 'precipitation',
           'precipitation_hourly_accumulated': 'precipitation',
           'hourly_precipitation': 'precipitation',
           'hourly_precipitation_mm': 'precipitation',
           '2m_air_temperature': 'air_temperature',
           'air_temperature_2m_celsius': 'air_temperature',
           'visibility_m': 'visibility',
           'sea_surface_temperature_celsius': 'sea_surface_temperature',
           'sea_surface_height_m': 'sea_surface_height',
           'dissolved_oxygen_mg_per_l': 'dissolved_oxygen',
           'current_speed': 'surface_current_speed',
           'current_speed_surface': 'surface_current_speed',
           'current_direction': 'surface_current_direction',
           'precipitation_accumulated_hourly': 'precipitation',
           'precipitation_hourly': 'precipitation',
           'hourly_accumulated_precipitation': 'precipitation',
           'turbidity_fnu': 'turbidity',
           'historical_wind_speed': 'wind_speed_10m'}
# Potential inputs only. Actual contract scope/thresholds are still required.
DERIVED_INPUTS = {name: [] for name in FAMILIES['DERIVED']}
for name in ('weather_window', 'continuous_workable_hours', 'weather_downtime',
             'environmental_operating_window', 'joint_wind_wave_exceedance'):
    DERIVED_INPUTS[name] = ['significant_wave_height', 'wind_speed_10m', 'surface_current_speed']
DERIVED_INPUTS['water_quality_excursion_duration'] = ['dissolved_oxygen', 'suspended_particulate_matter']


def canonical(name):
    return ALIASES.get(name, name)
