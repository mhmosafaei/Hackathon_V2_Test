# Simple Environmental Intelligence — offline verification

## Spatial-contract correction (2026-10-12)

Current source version: simple-permit-v1.4-spatial-context. Spatial items now
include nullable easting/northing and physical source_page, plus controlled
point/route/polygon/area/unknown geometry. Multiple locations remain an array.
The one-request prompt explicitly covers particulars and other non-condition
sections. Original IGR coordinates remain display-only, not WGS84 coordinates.
An explicit IGR abbreviation supports the label Irish Grid Reference; grid
values and source-page attribution are independently checked against quotations.
No coordinate conversion or new external call is introduced. Historical results
are not backfilled. Narrow Water fixture passes through strict parsing, saved
analysis and the frontend's API response; invalid numeric grid attribution is
flagged. Full offline backend regression: 198 passed, 0 failed.

## Permit-defined location and time UX (2026-10-12)

Added compact source cards immediately above Retrieve relevant evidence, with
desktop side-by-side and narrow-screen stacked layout. The existing one-request
schema now supports spatial_context (multiple original locations/CRS/geometry,
nullable explicit decimal WGS84 point, quotations) and temporal_context (validity,
operation dates, restrictions, quotations). Version: simple-permit-v1.3-source-context.
Published prompt/schema match runtime. No separate AI call or provider-routing
change. Existing summary validity and geofence text remain usable as display-only
fallbacks; older results are not rewritten or backfilled.

Only a source-verified explicit WGS84 point can populate coordinate fields, after
a click. Other CRS coordinates stay original, conversion is required, and areas
never become midpoints. Multiple locations require selection. Validity is clearly
distinguished from operations. Use dates copies only source-verified explicit UTC
times; date-only source values stay display-only, without invented midnight or
timezone. The user can enter planned times manually. Copy actions never fetch;
Fetch retains its explicit action, 48-hour limit and all evidence safeguards.

Full offline suites: 196 backend tests passed, 0 failed (44.72 seconds);
28 frontend tests passed, 0 failed (26.46 seconds). Production build passed.
Mock browser upload and Use location verified 54.1/-6.1 synthetic coordinates,
empty planned times and no provider request. Zero browser errors. Desktop cards
share a row; narrow cards stack. Screenshots: tmp/permit-defined-context.png and
tmp/permit-defined-context-desktop.png. The PDF fixture is explicitly synthetic.

Live server was not restarted or re-analyzed, preserving the user's active permit.
Its existing result can use summary/geofence fallbacks after a UI refresh; new
spatial/temporal extraction fields require backend restart before a future,
separately authorized analysis. No live calls or existing-artifact changes.

Files for this UX change: src/permit/simple_analysis.py, simple_fixture.py;
frontend/src/PermitContext.jsx, PermitContext.test.jsx, Environmental.jsx,
styles.css, Environmental.test.jsx; tests/test_simple_context.py; prompts/simple_permit_v1.txt;
docs/SIMPLE_PERMIT_RESPONSE.schema.json; scripts/create_environment_demo_pdf.py;
this report and IMPLEMENTATION_JOURNAL.md.

2026-10-12. Offline-tested implementation; live extraction/provider access has
not been validated in this task.

## Architecture and schema

PDF → ONE strict OpenAI extraction → Permit Intelligence → deterministic router
→ explicit Fetch Environmental Data → provider evidence. No additional LLM
stage, candidate pipeline or change to the global five-request/$0.15 ceiling.

`simple-permit-v1.2-environment` adds environmental_requirements to the existing
response: condition_id, source_page, requirement_text, variable,
canonical_variable, operator, threshold, unit, temporal_requirement,
depth_requirement, geographic_scope, evidence_type, explicit_requirement,
notes and exact source_spans. Missing numeric fields remain null. Local checks
verify quotation/page/condition linkage; everything remains UNREVIEWED and
non-executable. Verified quotation does not mean confirmed legal interpretation.

## Complete catalogue and routing

All **120 canonical names** are listed in `src/environmental/catalog.py::FAMILIES`.
Catalogue recognition is not a claim of provider availability.

| Family | Names | Preferred route |
| --- | ---: | --- |
| Atmosphere | 20 | ECMWF_FORECAST; historical → ERA5 |
| Waves | 15 | COPERNICUS_MARINE; historical → ERA5 |
| Currents / sea level | 16 | COPERNICUS_MARINE |
| Water quality | 22 | COPERNICUS_MARINE |
| Sea ice | 9 | COPERNICUS_MARINE |
| Air quality | 10 | CAMS, not implemented |
| Derived | 15 | DERIVED, never raw API lookup |
| External | 13 | EXTERNAL, no weather query |

Unknown variables route UNAVAILABLE. In-situ/local/laboratory evidence overrides
model routing suggestions. Derived-input lists are potential dependencies, not
invented thresholds, automatic fetches or implemented workability calculations.
Fallback metadata never causes silent substitution.

## Retrieval implemented, but not live-validated

| Adapter | Variables |
| --- | --- |
| ECMWF IFS via Open-Meteo | wind_speed_10m, wind_direction_10m, wind_gust, air_temperature, atmospheric_pressure, precipitation |
| ERA5 via Open-Meteo archive | Same six weather variables; reanalysis, not forecast or direct CDS |
| Official Copernicus Marine Toolbox | significant_wave_height, mean_wave_period, mean_wave_direction (wave_direction alias), surface_current_speed, surface_current_direction, sea_surface_temperature, dissolved_oxygen, suspended_particulate_matter, turbidity |

Still unsupported: salinity (no verified product configured), visibility
(selected-model support unverified), ERA5 waves, direct CDS, CAMS, route-wide
sampling, other catalogue variables and derived indicators. Therefore the whole
initial-priority list is **not yet delivered**. Unsupported rows remain visible
with an explanation and insufficient-data status, not fabricated values.

Copernicus reuses existing locally verified product references; fresh official
catalogue verification remains outstanding. Subsets use ±0.05° around an explicit
point, <=48 hours, selected variable/depth, a 60-second worker timeout and a 5 MB
subset estimate limit. Nearest valid ocean cell must be within 5 km. Marine
quality remains COASTAL_REVIEW_REQUIRED: retrieval alone cannot establish
harbour representativeness or pass a threshold comparison. No alternative
dataset is silently selected. Credentials stay backend-only; presence is not
authentication. Worker stdout/stderr is never forwarded to the UI.

Weather requests use 25-second HTTP timeout, verified TLS, no automatic retries,
explicit variables/dates and UTC. Missing values/units are preserved. Forecast
initialization remains null when not supplied. Current speed uses u/v; direction
is clockwise from north **towards** flow, not a wave-direction convention.

## UI and safeguards

Both tabs begin empty. Permit Intelligence retains its conditions, geofences
and exactly two bar/two pie charts. Environmental Intelligence adds five routing
summary cards, source-linked requirements, safe provider statuses, geofence
details, explicit point/UTC period/depth inputs and evidence cards/raw points.
Only Fetch invokes providers. Complex geofences require a sampling strategy or
explicit point-only scope; a midpoint is never invented as whole-route evidence.

Only WITHIN_THRESHOLD, THRESHOLD_EXCEEDED, INSUFFICIENT_DATA, INFORMATIONAL and
EXTERNAL_EVIDENCE_REQUIRED are used. They never authorize work. Checks cover
physical variable, source-supported threshold/unit, dimensions, depth, location,
evidence type, freshness and interval coverage. No interpolation, missing-as-zero,
NTU-to-SPM conversion or substitution of model DO for required local sampling.
Unresolved calendar/event/statistical requirements remain insufficient.

New Analysis clears both tabs; restart does not restore prior results. Caches
are isolated by boot/analysis/request/provider configuration with freshness
checks. Twelve provider requests maximum per Fetch; remaining rows stay visible.
Successful evidence survives another provider's failure within the same analysis.

## Verification

- Full backend suite: **192 passed, 0 failed**, 14.60 s; one existing
  Starlette/httpx warning.
- Frontend suite: **20 passed, 0 failed**, 8.69 s.
- Production build passed, 8.01 s; existing >500 kB bundle advisory remains.
- Published schema/prompt match runtime versions.
- Real mock browser: synthetic PDF upload → Analyze → 22 conditions/four charts
  → source drilldown → Environmental tab → explicit synthetic Fetch passed.
  Synthetic wave evidence was 1.2 m against <=2.5 m, three hourly points; it is
  labelled mock, not authenticated, and is not real permit/environmental evidence.
- New Analysis and restart isolation passed; mobile 390 px has no page overflow.
  Zero browser error logs. Hidden Recharts panel emits a nonfatal zero-width
  warning; visible charts render correctly.
- Native datetime-input commit issue found in browser, corrected with onInput
  handling and UTC-payload regression test.
- **Zero live OpenAI/Copernicus/ECMWF/ERA5/CDS/CAMS calls.**

Screenshots: `tmp/environment-requirements-preview.png`,
`tmp/environment-evidence-preview.png`. Fixture generator:
`python scripts/create_environment_demo_pdf.py`; upload
`tmp/pdfs/synthetic-environment-permit.pdf` to the explicit mock server.

## Controlled live Copernicus check — NOT EXECUTED

1. Obtain separate authorization for a bounded provider test. Do not Analyze or
   call OpenAI as part of connectivity verification.
2. Use the project backend's existing environment. Check credential presence
   only; do not print credentials, change credential files or forward logs.
3. Use official Toolbox catalogue describe to verify the configured wave dataset,
   version, VHM0/units, geographic coverage and actual available dates. Stop if
   unavailable; do not substitute another product.
4. Choose an explicitly authorized ocean point and one-hour UTC interval inside
   verified coverage. Construct `EnvironmentalRequest` for
   significant_wave_height, provider COPERNICUS_MARINE, those coordinates/times
   and surface depth only where metadata supports it. Invoke
   `src.environmental.copernicus.retrieve(request)` once in the backend.
5. Report safe error class or actual dataset/version/units, selected coordinates,
   distance, times and quality only. Stop on failure; no retry. A successful
   subset confirms that product's access, not harbour representativeness.
6. A later React Fetch requires an active analyzed session and separately bounded
   authorization; do not make an extra OpenAI call to test provider connectivity.

## Controlled live ECMWF check — NOT EXECUTED

1. Obtain separate authorization for one public provider request. No OpenAI or
   API-key authentication request is required by this Open-Meteo adapter.
2. Choose an explicit authorized point and one-hour UTC interval within current
   forecast coverage; do not silently use execution time.
3. Construct `EnvironmentalRequest` for wind_speed_10m, provider ECMWF_FORECAST,
   evidence_mode forecast and that point/time. Invoke
   `src.environmental.ecmwf.retrieve(request)` once in the backend.
4. It targets https://api.open-meteo.com/v1/forecast with model ecmwf_ifs025,
   only wind_speed_10m, UTC/m/s, 25-second timeout and verified TLS. No key is sent.
5. Record actual HTTP outcome, units, returned time/grid coordinates and distance.
   Stop on error; no retries. Missing issue time remains unknown. Provider
   connectivity is not proof that all permit comparisons are supported.

## Files

New: `src/environmental/{__init__,catalog,models,router,units,ecmwf,era5,
copernicus,service,fixture}.py`, `frontend/src/Environmental.jsx`,
`frontend/src/Environmental.test.jsx`, `tests/test_simple_environment.py`,
`scripts/create_environment_demo_pdf.py`, this report.

Updated: `src/permit/{simple_analysis,simple_api,simple_fixture}.py`,
`frontend/src/{App.jsx,styles.css}`, `prompts/simple_permit_v1.txt`,
`docs/SIMPLE_PERMIT_RESPONSE.schema.json`, README, Simple dashboard report and
implementation journal. Existing reviews, raw historical responses and
credential files were not changed. No rules or public deployment were created.
