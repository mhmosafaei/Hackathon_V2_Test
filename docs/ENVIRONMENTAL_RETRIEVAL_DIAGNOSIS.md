# Narrow Water environmental retrieval diagnosis — offline

Inspected live analysis 7101f6540f724154b8a48f4ab008016e and its existing
environmental caches. No source extraction or coordinate-conversion LLM behavior
was changed. No provider/model requests were made during this investigation.

## Root causes and corrections

| Issue | Evidence / exact failure path | Correction / remaining limitation |
|---|---|---|
| 24 Turbidity | MARINE maps TUR; products() selects the verified satellite mosaic. Catalogue report records TUR in FNU, not NTU. Child exception messages were discarded by the worker and parent; exact historical RuntimeError cannot be recovered. | Explicit NTU/FNU incompatibility diagnostic before network access. No invented conversion. |
| 25 Oxygen | Maps daily 3-D o2; worker previously raised generic errors for depth, masked cells, layouts etc. Actual historical exception was erased, so its precise cause remains unknown. Request has depth=null; 3-D connector cannot select a level implicitly. | Explicit depth diagnostic before access; stage-specific layout/variable/coverage diagnostics. Existing mmol m-3 → mg/L conversion remains guarded and tested. Daily/coarse model data cannot prove hourly in-situ evidence. |
| 27 Wind | Running server injected only COPERNICUS_MARINE transport. service.evaluate indexed transports['ECMWF_FORECAST'], producing the KeyError. | Partial marine overrides now retain existing ECMWF adapter; absent transports have a controlled diagnostic. Missing hourly fields/units/array lengths have explicit response errors. |
| 28 Gust | Model returned wind_gust_10m_forecast; vocabulary only recognized wind_gust or wind_gusts_10m. | Add aliases to existing scalar gust variable wind_gusts_10m; no derivation from sustained wind. |
| 30 SST | source_page/source_spans cite physical page 6; actual condition is page 5. Quote includes U+00C2 U+00B0 where original PDF extraction has U+FFFD. Exact quote occurs on no physical page. Structured requirement prose additionally drops an article, but that prose is not the quotation-verification input. | Keep source_verified=false and retrieval blocked. This is not a safe whitespace-only repair. Requires separately reviewed source correction; historical evidence is not rewritten. |
| 31 Provenance | environmental_evidence_provenance was outside physical-variable catalogue. | Explicit informational NOT_APPLICABLE routing, visible requirement, zero provider retrieval. |
| Points table | Actual cached point keys and React fields agree: data_time/raw_value/unit. Browser expansion showed populated wave rows. Global min-width:940px clipped the values in two narrow cards. | Compact two-column table, local min-width override; per-point normalization/notes in expandable details. Tests cover 48 and 192 populated rows. No unsupported field-name assumption. |
| Coverage | Endpoint times genuinely missing, not a count bug. | Keep INSUFFICIENT_DATA; show requested/actual UTC ranges and NOT DETERMINED FOR REQUESTED PERIOD. |

## Exact saved periods (UTC)

Requested: **2026-10-12 16:05 → 2026-10-14 16:05**.

- Waves: **2026-10-12 17:00 → 2026-10-14 16:00**, 48 points.
- Currents: **2026-10-12 16:15 → 2026-10-14 16:00**, 192 points.

No interpolation/extrapolation or endpoint tolerance was added. Source coastal
quality is COASTAL_REVIEW_REQUIRED, independently preventing favorable period
conclusions even for a fully time-covered request. Raw values remain visible.

## Final provider mappings

| Condition | Provider / product | Dataset | Variables / source units | Expected state |
|---|---|---|---|---|
| 24 | Copernicus / OCEANCOLOUR_NWS_BGC_HR_L3_NRT_009_203 | cmems_obs_oc_nws_bgc_tur-spm-chl_nrt_l3-hr-mosaic_P1D-m | TUR / FNU | NTU requirement insufficient; no substitution. |
| 25 | Copernicus / NWSHELF_ANALYSISFORECAST_BGC_004_002 | cmems_mod_nws_bgc-o2_anfc_7km-3D_P1D-m | o2 / mmol m-3; existing compatible mg/L conversion | Needs explicit depth; spatial masking/daily cadence may remain insufficient. Supportive model only. |
| 26 | Copernicus / NWSHELF_ANALYSISFORECAST_WAV_004_014 | cmems_mod_nws_wav_anfc_1.5km_PT1H-i | VHM0 / m | Existing successful retrieval path retained; suitability/coverage checks remain. |
| 27 | ECMWF IFS via Open-Meteo | ecmwf_ifs025 | wind_speed_10m / requested m/s | Existing scalar adapter now reachable; live outcome not retested. |
| 28 | ECMWF IFS via Open-Meteo | ecmwf_ifs025 | wind_gusts_10m / requested m/s | Existing gust adapter now reachable through aliases; live outcome not retested. |
| 29 | Copernicus / NWSHELF_ANALYSISFORECAST_PHY_004_013 | cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT15M-i | uo, vo / m/s; hypot magnitude | Existing successful path/components retained. |
| 30 | Copernicus / NWSHELF_ANALYSISFORECAST_PHY_004_013 | cmems_mod_nws_phy-sst_anfc_1.5km-2D_PT1H-i | thetao / degrees_Celsius | Valid existing mapping, but this record remains source-blocked; informational, no invented numeric comparison. |

Product/units descriptions use existing locally saved catalogue verification,
not a new live catalogue query. Runtime returns provider-reported units and
available issue time, or explicitly null when initialization is absent.

## Diagnostics / safety

Provider diagnostics preserve controlled category/message, error type, provider,
dataset, variable and requested times. Untrusted exception strings, credentials,
headers, stack traces and filesystem paths are never forwarded. Structured safe
failure artifacts are persisted separately under the environmental errors folder.
Worker-specific reasons include depth, unit, size, missing variable/time, layout,
and no representative valid ocean cell. Generic unexpected errors are classified
conservatively, not declared to be a proven provider-side root cause.

Unverified quotes stay gated; local sensor/laboratory deciding evidence remains
external; no compliance authorization, rules or new model requests are introduced.

## Verification

Files changed in this task: src/environmental/errors.py, catalog.py, router.py,
service.py, copernicus.py, ecmwf.py; src/permit/simple_api.py;
frontend/src/Environmental.jsx, Environmental.test.jsx, styles.css;
tests/test_environmental_retrieval_fixes.py; this report and IMPLEMENTATION_JOURNAL.md.
No extraction prompt/schema, coordinate-conversion behavior, historical analysis
or review decisions were changed.

Full offline suite: 232 backend tests passed; 42 frontend tests passed. Production
build passed (existing bundle advisory). Existing coordinate tests pass. The
actual browser's saved wave table was inspected without fetching. Live provider
acceptance remains unverified and must be performed manually after backend restart.
