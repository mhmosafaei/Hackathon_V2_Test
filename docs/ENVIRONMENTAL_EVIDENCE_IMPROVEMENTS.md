# Focused environmental evidence improvements — 2026-10-12

Offline implementation only. No OpenAI, Copernicus, ECMWF or Open-Meteo data
request was made. Provider documentation was consulted to confirm model names.
Extraction prompts/schema, coordinate conversion, original licences, historical
analyses and human reviews were not changed.

## Changes and rationale

1. **Synthetic units/depth:** a separate fixture and generated PDF explicitly say
   UNOFFICIAL / SOFTWARE TEST / NOT ISSUED BY DAERA / NOT FOR REGULATORY OR
   OPERATIONAL USE. Turbidity is >25 FNU; oxygen is <6 mg/L at 1 metre below sea
   surface. The fixture also contains wave, wind, gust, current and two SST checks.
   No real NTU requirement is rewritten; FNU/NTU stays incompatible. The original
   Narrow Water licence and existing unofficial upload are not overwritten.
2. **Depth:** the existing nullable `depth_requirement` survives the one-request
   extraction, saved result and API. A metric source depth is parsed only when
   its value and below-surface context occur in the cited quotation. An explicit
   conflicting user depth blocks retrieval. Missing oxygen depth blocks retrieval
   unless explicitly selected by the user; it never defaults to surface.
   Actual selected vertical level and requested depth are separate provenance.
   A different selected level cannot pass the service's depth check.
3. **Time:** `sampling.py` floors/ceils UTC bounds to known adapter timesteps:
   waves/SST/weather hourly; currents 15 minutes; oxygen/TUR/SPM daily. These are
   declared product/output cadences, not interpolation implemented by PermitPulse.
   Requested, query and actual periods are distinct. Actual endpoints must bracket
   the original request and no cadence-sized gaps may be missing. Missing/invalid
   values, stale evidence, source verification and coastal gates remain independent.
4. **ECMWF:** preferred model `ecmwf_ifs`, documented HRES O1280 nominal 9 km,
   via the existing Open-Meteo forecast endpoint. Fallback `ecmwf_ifs025` occurs
   only after an explicit HTTP 400 model-unavailability/invalid-model response,
   not for network/server failures; it is labelled and its provenance preserved.
   There is at most one fallback attempt and no transport retry loop. The legacy
   model can also be explicitly selected by the adapter's local `model` argument.
5. **Spatial:** weather uses half the nominal cell diagonal, not a universal
   5 km. HRES maximum is 9/sqrt(2) = 6.364 km. A 0.25 degree grid uses
   111.32*0.25 km north-south and cos(latitude) times that east-west, divided
   by two after taking the diagonal. At 54 degrees this is about 16.1 km:
   a 25.5 km offset still fails. Unknown model metadata fails. This is a
   conservative geometric screening bound, not proof of local representativeness.
   Marine 5 km and COASTAL_REVIEW_REQUIRED safeguards are unchanged.
6. **Deduplication:** retrieval identity includes document analysis ID, provider,
   dataset/configuration, variable, coordinates, explicit depth, evidence mode
   and expanded query bounds, but excludes condition ID and threshold. One fetch
   (or one failed fetch) is shared within a click. Raw successful evidence is saved
   before separate per-condition evaluation. Cache schema version 2 avoids reusing
   incompatible old query artifacts without deleting them. All requirements remain
   in the table; `evidence_groups` exposes one card per request with multiple checks.
7. **Display:** original/query/actual periods, selected/requested coordinates,
   model resolution/distance, fallback and source failure remain visible. Checks
   display literal comparison true/false, not automatic compliance conclusions:
   an extracted `>` may be a review trigger rather than an acceptable upper limit.
   Existing evaluator state fields are preserved for compatibility. No WORK decision
   or executable rule is produced.

## Examples (mocked, not environmental measurements)

| Requested UTC | Product cadence | Provider query UTC |
|---|---|---|
| Oct 12 16:41 → Oct 13 16:41 | hourly | Oct 12 16:00 → Oct 13 17:00 |
| Oct 12 16:41 → Oct 13 16:41 | 15 minutes | Oct 12 16:30 → Oct 13 16:45 |
| Oct 12 16:41 → Oct 13 16:41 | daily | Oct 12 00:00 → Oct 14 00:00 |

Mocked returned endpoints equal to these expanded bounds pass **temporal**
bracketing; inner endpoints still fail. Other evidence checks can still fail.
Mock SST at 14.3 C: one provider call, two false comparisons (<2 and >22), one
evidence group/card. This is not a real temperature or work authorization.

Oxygen dataset: `cmems_mod_nws_bgc-o2_anfc_7km-3D_P1D-m`, variable `o2`.
Source `mmol m-3` / `mmol/m3` is retained alongside normalized `mg/L` using the
already tested oxygen-specific factor 0.031998. No new conversion was introduced.
TUR dataset: `cmems_obs_oc_nws_bgc_tur-spm-chl_nrt_l3-hr-mosaic_P1D-m`,
satellite observation in FNU, not a model forecast. Unspecified evidence accepts
known observation/model types without inventing a forecast requirement; explicitly
forecast-only or in-situ requirements retain their type gates.

## Limits and verification

Daily model/observation evidence cannot establish subdaily excursions. Optical
satellite products may be masked/cloud-obscured and cannot provide future forecasts.
Coastal cells remain review-required. Open-Meteo documents that hourly API output
can interpolate native 3/6-hour forecasts; this provider transformation is disclosed,
not a PermitPulse interpolation. Initialization time remains unknown when absent.
HRES nominal resolution is not independently measured per irregular Gaussian cell.
Modelled oxygen remains supportive, never equivalent to required in-situ monitoring.

Provider references (no live retrieval verification):
- https://open-meteo.com/en/docs/ecmwf-api
- https://raw.githubusercontent.com/open-meteo/open-meteo-website/main/src/routes/en/docs/ecmwf-api/+page.svelte

Final backend suite: **253 passed**, one existing Starlette/httpx deprecation warning.
Final frontend suite: **44 passed**. Synthetic PDF rendered and visually checked.
React production build passed (existing large-bundle advisory only).
Existing wave, current, coordinate conversion and review safety tests pass.

## Files changed in this task

- src/environmental/sampling.py (new)
- src/environmental/models.py
- src/environmental/service.py
- src/environmental/copernicus.py
- src/environmental/ecmwf.py
- frontend/src/Environmental.jsx
- frontend/src/Environmental.test.jsx
- tests/test_simple_environment.py
- tests/test_environmental_sampling.py (new)
- tests/fixtures/synthetic_environment_requirements.json (new)
- scripts/create_synthetic_evidence_pdf.py (new; installed PyMuPDF, no dependency added)
- docs/ENVIRONMENTAL_EVIDENCE_IMPROVEMENTS.md (new)
- docs/IMPLEMENTATION_JOURNAL.md

Generated fixture: `output/pdf/PermitPulse_UNOFFICIAL_Environmental_Test.pdf`.
Preview: `tmp/pdfs/synthetic-evidence-preview.png`. Both are diagnostic/test
artifacts, not amended licences. No environmental data was added to real caches.

## Before manual live acceptance

Stop/restart **only the FastAPI/Uvicorn PermitPulse worker on 127.0.0.1:8531**
(observed PID 39260, Python 3.14 executable). Keep the existing live Copernicus
transport configuration. The React production bundle has already been rebuilt;
this server serves it, so no separate frontend process is required. Hard-refresh
the browser. The server was intentionally not restarted during this task.
Manual live provider acceptance remains outstanding; no connection success is claimed.
