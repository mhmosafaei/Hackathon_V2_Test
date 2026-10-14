# Environmental qualification fixes — 2026-10-12

## Scope

Local evaluation and presentation only. No OpenAI, Copernicus, ECMWF or
Open-Meteo requests were made. Extraction prompts, raw AI responses, saved live
evidence and permit reviews were not edited. No rules or approvals were created.

## Decision tree

1. Routing/source interpretation/depth/location/time prerequisites must pass
   before fetching. Actual local monitoring requirements remain external.
2. A completed retrieval is separately recorded as SUCCESS (cache state remains
   FETCHED/CACHED/REUSED). Retrieval is not evidence suitability.
3. Temporal coverage is COVERED only with bracketing endpoints and no cadence
   gaps. This dimension is independent of spatial and applicability checks.
4. Distance must pass the existing configured bound. Weather uses the existing
   model-specific bound; marine uses the existing 5 km cap. No bound increased.
5. Source identity, variable, evidence mode, freshness, depth, units and values
   must also pass. Genuine failures remain INSUFFICIENT_DATA/NOT_DETERMINED.
6. COASTAL_REVIEW_REQUIRED alone is a qualification, not missing evidence.
   It remains visible and never implies compliance or operating authorization.
7. Literal screening is TRIGGERED / NOT_TRIGGERED / NOT_DETERMINED. A series
   triggers if any returned point does. Displayed-point and series outcomes are
   labelled separately. Existing legacy status enums remain for compatibility;
   they are not regulatory pass/fail conclusions.

## Narrow SST recovery

Only verified SST quotations with one exact unambiguous expression of the form
`Values below N deg C or above M deg C shall be flagged for review` (supported
Celsius spellings) and N < M yield two derived checks. Both AI numeric fields
must originally be null. Each derived check records
DERIVED_FROM_VERIFIED_SOURCE_TEXT and the matched expression. Raw extraction is
unchanged. Other or ambiguous wording is not repaired or guessed.

One retrieval identity and one evidence card serve both independent checks.
`deg C`, `°C`, `degrees_C`, `degree_C`, `degrees C` normalize to °C. Raw source
units remain preserved. No new scientific conversion was introduced.

## Saved-evidence validation (offline)

Read-only evaluation of the previously saved run at its original retrieval
timestamp (not a claim that old data are fresh now):

| Variable | Temporal | Distance | Displayed literal check | Series screening |
|---|---|---|---|---|
| Waves | COVERED | within bound (~0.967 km) | 0.846 > 1.5: NOT_TRIGGERED | TRIGGERED at later points |
| Currents | COVERED | within bound (~0.967 km) | 0.032 > 1: NOT_TRIGGERED | NOT_TRIGGERED |
| SST | COVERED | within bound (~0.967 km) | 14.265 < 2 and > 22: both NOT_TRIGGERED | both NOT_TRIGGERED |
| Saved wind | COVERED | outside bound (~7.849 km) | NOT_DETERMINED | NOT_DETERMINED |

All marine entries retain coastal applicability review. None authorize work.

## Weather selection and uncertainty

Open-Meteo requests explicitly set `cell_selection=nearest`, also persisted in
request parameters/evidence provenance and retrieval cache identity. Older
default-selection cache entries remain intact but cannot be reused as nearest
requests. Returned coordinates, source resolution and distance remain visible.

The HRES bound remains 9/sqrt(2) = ~6.364 km. It is explicitly an approximate
nominal-grid check, **not exact O1280 reduced-Gaussian cell geometry**. A returned
cell outside it remains insufficient. No claim is made that nearest will return
a different cell until a separately performed manual live fetch. Hourly provider
output may interpolate native model cadence; PermitPulse does not interpolate.

## UI and verification

Actual temporal, spatial, unit, depth and source-interpretation blockers replace
the misleading universal period-failure label. Retrieval, temporal coverage,
distance, coastal qualification, cell policy and literal screening are separate.
No four-chart permit dashboard changes were made.

Full backend pytest: **273 passed**, one existing Starlette/httpx deprecation
warning. Full frontend Vitest: **49 passed**, 3 test files. Production build
passed; existing >500 kB bundle advisory remains. All provider tests use injected
offline responses. No browser/live provider acceptance is claimed.

## Files changed

- src/environmental/service.py
- src/environmental/units.py
- src/environmental/ecmwf.py
- frontend/src/Environmental.jsx
- frontend/src/Environmental.test.jsx
- tests/test_environmental_sampling.py
- tests/test_environmental_qualifications.py
- docs/ENVIRONMENTAL_QUALIFICATION_FIXES.md
- docs/IMPLEMENTATION_JOURNAL.md
- frontend/dist (generated production bundle; ignored build output)

## Before manual fetch

Restart only the PermitPulse **FastAPI/Uvicorn worker serving port 8531** using
the existing Python 3.14 interpreter and project directory, preserving its
current configured live Copernicus transport and permit-analysis mode. The
React production bundle is rebuilt and served by this worker; no separate
frontend server is needed. Then hard-refresh the browser. Do not restart the
old Streamlit app. No automatic restart or live fetch was performed here.
