# Turbidity and 2 m air temperature — focused fixes (2026-10-12)

## Scope and evidence

No live OpenAI, Copernicus, ECMWF or Open-Meteo calls. No extraction prompt/schema
changes, historical artifacts or review changes. Other variables' existing
paths and scientific gates remain intact. This work changes local mapping,
manual screening input and the related existing environmental view only.

Air-temperature diagnosis used saved LIVE analysis
`63e6d528640740eea17c71d3ed7dcf37` under document hash
`0d88aa8af8ef687153fcfb21ff726cedfee52189e50eed9734a3302501164439`.

## A. Turbidity

Existing limitation: NTU/FNU mismatch correctly prevented comparison, but no
separate manual FNU input existed. Provider mapping is the configured Copernicus
TUR product in FNU, not a universal physical conversion from NTU.

### Workflow

- Permit FNU / provider FNU: DIRECTLY_COMPARABLE; compare source threshold.
- Permit NTU / mapped FNU without manual value: MANUAL_FNU_REQUIRED. Do not fetch
  or compare that row until the required manual value is supplied.
- Permit NTU / valid positive finite manual FNU: READY_WITH_MANUAL_FNU. Preserve
  original operator/value/unit and evaluate the FNU series against the manual
  value, explicitly USER_SUPPLIED, not permit-derived or automatically converted.
- Unsupported units: UNIT_INCOMPATIBLE; no guessing or conversion.
- Missing original operator/threshold or source interpretation remains blocked.
- Evidence mode, freshness, time, distance, local-sensor and source gates remain
  mandatory. A satellite product does not silently replace required forecast or
  local deciding evidence. Readiness of the manual threshold is not evidence
  suitability or authorization.

`EvaluationInput.manual_fnu_thresholds` is keyed by the existing document-scoped
requirement index. Values must be strict numeric, finite and >0. Strings,
booleans, null, blank, NaN, infinity, zero and negatives cannot unlock screening.
Manual values for unrelated variables or FNU-native requirements are ignored.

Rows retain e.g. original `{operator: ">", value: 25, unit: "NTU"}` and separate
`manual_comparison_threshold: {value: 27, unit: "FNU", source: "USER_SUPPLIED",
entered_at: ...}`. Source checks still validate the original NTU threshold
against its source, not against the user value. Point normalization/comparison
uses FNU only for the explicit manual branch. Raw provider values/units stay
unchanged. Manual screening audit JSON is stored separately under the current
environmental cache's `manual_comparisons/` folder, including both thresholds,
request, evidence, provenance, UNREVIEWED and executable=false. Each application
has a distinct audit identity; no previous provider evidence is overwritten.

### Frontend

Manual input appears inside source/retrieval details only for turbidity with
original NTU and mapped FNU evidence. It shows the original value, provider unit,
no-automatic-conversion explanation and user-supplied provenance. Entering a
value makes no network call. The existing explicit **Fetch Environmental Data**
action applies it; fresh cached series are reused with no Copernicus call. If
evidence is absent/stale or other request inputs change, that explicit action
may fetch normally. No new endpoint, automatic fetch, LLM or conversion logic.

Card and check labels show the manual FNU threshold separately from the NTU
permit threshold, never presenting a comparison of FNU data against NTU units.
Document changes reset input through the existing analysis-ID component key.
No rules or approvals result from this screening.

## B. 2 m air temperature

### Actual trace before correction

| Stage | Actual | Expected | Result / reason |
|---|---|---|---|
| Source, physical page 8, condition 29 | 2 m air temperature; below -2 deg C or above 25 deg C; informational only | Same | PASS |
| Saved raw AI requirement | air_temperature_2m; forecast; unit deg C; threshold/operator null | Supported alias and two source-backed checks | Partial: limits only in quotation |
| Normalized requirement | Same variable/fields, source_verified=true | Preserve source, recognize alias | Source PASS; alias FAIL |
| catalog.canonical | air_temperature_2m unchanged | air_temperature | FAIL: missing alias |
| route | UNAVAILABLE; family null; implemented=false | ECMWF_FORECAST | FAIL downstream of alias |
| service.evaluate | `if not routing['implemented']` adds blocker and skips request construction | Dispatch implemented weather request | Not dropped: requirement remains visible without evidence |
| ECMWF adapter | Already maps air_temperature to temperature_2m | temperature_2m | Support existed, not reached |
| Provider response / API evidence | No temperature request or evidence | Real response if available | Not a provider failure |
| Frontend grouping | No temperature evidence card because no evidence exists | One card/two checks | Not an informational-data filter or dedup loss |

### Correction

Recognize `air_temperature_2m`, `temperature_2m`, `air temperature`,
`2 m air temperature`, and `temperature 2m` as the existing canonical key
`air_temperature`. Keep original key as provenance on mapped rows and preserve
raw extraction. The existing ECMWF adapter requests `temperature_2m` with
`models=ecmwf_ifs`, Celsius units and `cell_selection=nearest`.

Reuse the existing narrow verified-source temperature-range derivation for
air temperature as well as SST. One unambiguous verified expression with both
explicit numbers and units creates `< -2 °C` and `> 25 °C` checks for this source,
with DERIVED_FROM_VERIFIED_SOURCE_TEXT provenance. No source-specific numbers
or condition IDs are embedded in production code. Ambiguous or unverified text
does not yield guessed thresholds; unresolved interpretation remains visible.

Both checks share one request identity, retrieval and card. Informational-only
qualification remains in the source text/notes; comparisons are literal
TRIGGERED / NOT_TRIGGERED / NOT_DETERMINED, not breaches or authorization.
Actual requested/selected coordinates, distance, 9 km nominal resolution,
nearest policy, timestamps and temporal/spatial checks are retained by the
existing adapter/evaluator. An outside-bound cell still blocks screening.

## Verification

Focused backend suite: 21 passed. Tests cover strict manual input rejection,
original/manual separation, audit preservation, cached re-evaluation with zero
additional transport calls, FNU direct comparison, absent-manual blocking,
aliases, source-backed temperature range, ambiguous range, extraction/persistence,
one-card/two-check grouping, adapter parameters/units and visible failure.

Full backend: 303 passed, one existing Starlette/httpx deprecation warning.
Full frontend: 55 passed (3 test files). Production React build passed; existing
large-bundle advisory remains. UI mocks cover conditional input, no request on
typing, invalid value omission, explicit Fetch and SST/air two-check cards.
No live provider success is claimed.

## Changed files and restart

- src/environmental/catalog.py
- src/environmental/models.py
- src/environmental/service.py
- frontend/src/Environmental.jsx
- frontend/src/Environmental.test.jsx
- tests/test_turbidity_air_temperature.py
- docs/TURBIDITY_AIR_TEMPERATURE_FIXES.md
- docs/IMPLEMENTATION_JOURNAL.md
- Generated ignored frontend/dist production bundle

Backend restart is required to load new mappings/input handling. Frontend rebuild
is required and **already completed**. Restart only FastAPI/Uvicorn on port 8531,
preserving its current live connector/permit-analysis configuration, then hard
refresh the browser. No separate frontend server or old Streamlit restart.
No automatic restart or live acceptance was performed.
