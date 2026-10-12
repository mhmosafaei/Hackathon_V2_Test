# Historical Seasonal Weather Verification — Belfast Harbour

Verified: 2026-10-09. This report documents real historical/reanalysis source retrievals used for the Stage 6 offline Belfast demonstration. It is not a forecast or an operational or contractual conclusion.

## Verified sources and bounded retrievals

| Variable | Official source | Dataset / product / version | Source variable and unit | Cadence / coverage | Belfast April 9–11 cache |
| --- | --- | --- | --- | --- | --- |
| Significant wave height | Copernicus Marine | `MetO-NWS-WAV-RAN` / `NWSHELF_REANALYSIS_WAV_004_015` / `202007` | `VHM0`, m | PT3H; 1980-01-01 to 2026-05-31 | 24 valid values in each of 2024, 2025 and 2026 |
| Current | Copernicus Marine | `cmems_mod_nws_phy-uv_my_7km-2D_PT1H-i` / `NWSHELF_MULTIYEAR_PHY_004_009` / `202112` | `uo`, `vo`, m s-1; derived speed | PT1H; 1993-01-01 to 2026-08-01 | Request succeeded, but tight Belfast subset is masked; zero values retained |
| Sea-surface temperature | Copernicus Marine | `cmems_mod_nws_phy-sst_my_7km-2D_PT1H-i` / `NWSHELF_MULTIYEAR_PHY_004_009` / `202112` | `thetao`, degrees_C | PT1H; 1993-01-01 to 2026-08-01 | Request succeeded, but tight Belfast subset is masked; zero values retained |
| Atmospheric weather | Open-Meteo historical archive | ERA5 via Open-Meteo historical archive | wind speed/gust, precipitation, air temperature, pressure | PT1H | 72 valid hours in each of 2024, 2025 and 2026 |

The marine requests used a small Belfast-centred bounding box (54.6, -5.9) and only the three-day equivalent windows. Cache files under `cache/historical/belfast/<year>/` preserve the source dataset/product/version, request range, selected-grid result, original units, UTC timestamps and retrieval timestamp. `cache/historical/belfast/manifest.json` records successful and masked responses. It contains no credentials.

## Data-quality result

Wave and ERA5 weather have complete coverage at their native three-hourly and hourly cadences for the cached equivalent periods. The current and SST grids are masked at the requested harbour subset, so their coverage is `MISSING`, not zero or favourable evidence. The application does not select a more distant cell or substitute another dataset. Any analysis requiring current or SST is consequently `UNKNOWN`/incomplete.

The Stage 6 demonstration’s default requested period is 2027-04-09 through 2027-04-11. Its equivalent cached periods are 2026, 2025 and 2024 April 9–11. The user interface will not reuse these cached April records for a different calendar period; it instead reports that matching historical data is required.

## Descriptive cached example

With illustrative thresholds of wave height <= 1.5 m and wind speed <= 30 km/h, the cached source data can be analysed descriptively only. Wave maxima were 0.324 m (2024), 0.008 m (2025), and 0.354 m (2026); ERA5 wind maxima were 32.9, 12.7, and 40.0 km/h respectively. These are source-specific samples, not a prediction of the requested project period, a downtime estimate, or a legal conclusion.

## Safety boundary

- Forecast values are never reused as historical observations.
- Historical values are never projected into a forecast or compliance result.
- Contract clauses must be quote-verified and separately human-confirmed before they supply thresholds.
- Missing, stale, masked, or insufficiently representative required evidence stays `UNKNOWN`.
- No permit confirmation, environmental integration, or legal/commercial decision is changed by this work.
