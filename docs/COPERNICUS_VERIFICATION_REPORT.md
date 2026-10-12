# Copernicus Marine Stage 2A verification

Verified live on 2026-10-09 with the official Copernicus Marine Toolbox (v2.4.1). Authentication succeeded. The cache contains small real subsets only; credentials, headers, and tokens are never stored in it.

| Capability | Official dataset ID | Product / selected catalogue version | Variables (source units) | Cadence / spatial evidence | Belfast request and outcome |
| --- | --- | --- | --- | --- | --- |
| Waves | `cmems_mod_nws_wav_anfc_1.5km_PT1H-i` | `NWSHELF_ANALYSISFORECAST_WAV_004_014`; version `202511` | `VHM0` (m), `VTM02` (s), `VMDR` (degree), `VTPK` (s) | 1-hour / 1.5 km; 2024-08-06 through 2026-10-14 23:00 UTC | SUCCESS: 25 hourly steps, nearest valid cell 54.635139, -5.878788, 4.139 km, GOOD spatial representativeness. |
| Currents | `cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT15M-i` | `NWSHELF_ANALYSISFORECAST_PHY_004_013`; version `202511` | `uo`, `vo` (m s-1); derived `current_speed` (m s-1) | 15-minute / 1.5 km; 2024-08-04 00:15 through 2026-10-15 UTC | SUCCESS: 97 steps, nearest valid cell 54.635139, -5.878788, 4.139 km, GOOD. |
| SPM/turbidity | `cmems_obs_oc_nws_bgc_tur-spm-chl_nrt_l3-hr-mosaic_P1D-m` | catalogue version `202107` selected | `SPM` (g m-3), `TUR` (FNU) | daily satellite observation mosaic; 2020-01-01 through 2026-10-07 UTC | Retrieval SUCCESS (2026-10-07, the last available day at request time), but all cells in the tight Belfast Harbour subset were masked. No selected cell/value; representativeness UNKNOWN. |
| Dissolved oxygen | `cmems_mod_nws_bgc-o2_anfc_7km-3D_P1D-m` | `NWSHELF_ANALYSISFORECAST_BGC_004_002`; version `202511` | `o2` (mmol m-3) | daily model mean / 7 km; 2024-07-29 through 2026-10-15 UTC; 24 depths | Retrieval SUCCESS (two daily times, surface grid check), but the subset grid cell was masked. No selected cell/value; representativeness UNKNOWN. |
| Sea-surface temperature | `cmems_mod_nws_phy-sst_anfc_1.5km-2D_PT1H-i` | `NWSHELF_ANALYSISFORECAST_PHY_004_013`; version `202511` | `thetao` (degrees_C) | 1-hour / 1.5 km; 2024-08-04 01:00 through 2026-10-15 UTC | SUCCESS: 25 hourly steps, nearest valid cell 54.635139, -5.878788, 4.139 km, GOOD. |

## Access and normalization

- All catalogue checks and subset requests used `copernicusmarine.describe` / `copernicusmarine.open_dataset`, authenticated from environment variables only. Catalogue services include file delivery, WMTS, and the ARCO geoseries/Zarr service used by the Toolbox requests.
- Requests used longitude -5.98 to -5.85, latitude 54.55 to 54.65, and one-day windows. The SPM window was shifted to 2026-10-07 because a real initial request established that 2026-10-08 onward was outside its advertised coverage at the time.
- Cached observation timestamps are normalized to UTC (`Z`). Source values and units are preserved. Current speed is derived as `sqrt(uo^2 + vo^2)`. Oxygen conversion is guarded and only permits confirmed `mmol m-3` / `mmol/m3` units; no conversion was needed because no valid local cell was available.
- The visible source `creation_date` is provenance metadata, not a semantic dataset-version substitute. Cached records retain it separately as `version`.

## Cache and offline behaviour

`cache/copernicus/{waves,currents,spm,oxygen,sst}.json` retain dataset ID, requested time/area, source units, grid decision, retrieval time, source product/version metadata, and compact real observations when a valid cell exists. `manifest.json` holds each result independently. `load_cached_product` reads those records without network credentials and returns cache age/freshness metadata.

## Limitations and safeguards

- The requested point (54.6, -5.9) is an indicative Belfast-Harbour request coordinate, not a legal activity coordinate from the licence. A 4.139 km ocean cell is coastal-context information, not an in-harbour measurement.
- The SPM and oxygen result is deliberately **not** represented as a zero, interpolation, or substitute value: the selected tight subset had no valid ocean cell.
- Satellite SPM/turbidity and model oxygen remain SUPPORTIVE only. They never replace required local monitoring. No AIS integration exists; AIS/GNSS remains external-data-required.
- Stage 2B/3 provide advisory environmental intelligence only. No unconfirmed permit condition uses these data to make a compliance decision, and Stage 4 operational compliance execution has not started.

## Dashboard integration update

The verified cache is now consumed by the unified Stage 2B/3 Environmental Intelligence dashboard alongside a separately cached, explicitly selected ECMWF IFS forecast from Open-Meteo. This does not change the evidence role of any marine source: waves/currents are predictive context; SST, satellite SPM and model oxygen are supportive context; local monitoring and AIS requirements remain external deciding evidence where a permit requires them.
