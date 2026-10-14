# Environmental P0 capability matrix

This is an application-capability catalogue, not a claim that a permit requires
every variable and not a provider-availability check. Retrieval remains
permit-driven and explicitly user-triggered.

| Variable | Status | Provider / source variable | Unit | Notes |
| --- | --- | --- | --- | --- |
| Significant wave height | SUPPORTED | Copernicus `VHM0` | m | Source-backed model evidence only. |
| Mean wave period | SUPPORTED | Copernicus `VTM02` | s | Provider semantics preserved. |
| Mean wave direction | SUPPORTED | Copernicus `VMDR` | degrees | Provider direction convention is not converted. |
| Eastward current U | SUPPORTED | Copernicus `uo` | m/s | Shared `uo`/`vo` retrieval; independently projected. |
| Northward current V | SUPPORTED | Copernicus `vo` | m/s | Shared `uo`/`vo` retrieval; independently projected. |
| Current speed | SUPPORTED | `sqrt(uo² + vo²)` | m/s | Derived locally. |
| Current direction | SUPPORTED | Derived from `uo`/`vo` | degrees | Towards, clockwise from north. |
| Wind speed at 10 m | SUPPORTED | Open-Meteo `wind_speed_10m` | m/s | ECMWF IFS via Open-Meteo. |
| Wind direction at 10 m | SUPPORTED | Open-Meteo `wind_direction_10m` | degrees | Provider field preserved. |
| Wind gust | SUPPORTED | Open-Meteo `wind_gusts_10m` | m/s | Provider field preserved. |
| Precipitation | SUPPORTED | Open-Meteo `precipitation` | mm | Accumulated over the preceding provider hour. |
| Visibility | PARTIAL | Open-Meteo `visibility` | m | Explicit field required; missing/incorrect units fail visibly. |
| Air temperature | SUPPORTED | Open-Meteo `temperature_2m` | °C | 2 m field, not a 10 m measurement. |
| Sea-surface height | UNAVAILABLE | No verified mapping | m | Never represented as chart datum, tide-gauge truth or navigational clearance. |

Dissolved oxygen is separately supported as a daily Copernicus 3-D model
requirement when the permit supplies an explicit compatible depth. Raw units,
normalized mg/L, selected depth and conversion provenance are retained. It is
always labelled modelled supportive evidence and never substitutes for
in-situ monitoring.
