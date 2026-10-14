# Missing dissolved oxygen — local diagnosis, 2026-10-12

## Confirmed source identity and cause

Latest saved LIVE analysis: `63e6d528640740eea17c71d3ed7dcf37`.
Filename: `Kilkeel_ML2022019_UNOFFICIAL_PERMITPULSE_TEST.pdf`, **9 pages**.
Raw source SHA256:
`0d88aa8af8ef687153fcfb21ff726cedfee52189e50eed9734a3302501164439`.

The saved PDF, its complete parsed input, raw OpenAI environmental requirements,
normalized analysis and environmental mapping contain **no dissolved oxygen
requirement**. No page of the saved PDF text contains oxygen. Visual inspection
of physical page 8 confirms synthetic conditions 23–31 omit oxygen; physical
page 9 supplies mapping/location context. This is not normalization loss or a
provider error. The standalone software fixture is a different document and
contains the intended oxygen requirement as T2.

Evidence files under `cache/simple_analysis/<SHA256>/<run_id>/` were inspected
read-only: `source.pdf`, `input.txt`, `response.json`, `analysis.json`,
`manifest.json`. The live manifest is COMPLETE with 31 conditions; no new AI
dispatch was performed. No historical extraction has been corrected/injected.

## Actual versus intended end-to-end trace

| Stage | Actual latest run | Intended oxygen test | Result / reason |
|---|---|---|---|
| Original PDF text | No oxygen clause | Modelled DO below 6.0 mg/L at 1 metre below sea surface | FAIL: wrong synthetic input for oxygen testing |
| Parsed model input | No oxygen clause | Same exact source wording | Not an ingestion loss; matches PDF |
| Raw OpenAI response | No oxygen environmental requirement | Source-backed oxygen item | Expected absence, not proved AI omission |
| Normalized requirement | Absent | dissolved_oxygen | No item discarded |
| Operator / threshold / unit | Absent | < / 6.0 / mg/L | Never supplied by source in this run |
| Depth | Absent | 1.0 m, source-backed | No surface default |
| Provider routing | Not reached for oxygen | COPERNICUS_MARINE | Existing route passes mocked tests |
| Dataset / variable | Not requested | cmems_mod_nws_bgc-o2_anfc_7km-3D_P1D-m / o2 | Configuration matches intended product |
| Request coordinates/time | No oxygen request | Explicit selected point; outward daily UTC bounds | No fabricated request |
| Vertical query | No oxygen request | minimum_depth=maximum_depth=1 | Mocked Toolbox confirms |
| Response normalization | No oxygen response | Original mmol m-3 retained, mg/L normalized | Existing conversion passes |
| Evidence result | No oxygen evidence | MODEL_FORECAST, supportive caveat, coastal review | Existing path passes offline |
| Environmental API | No oxygen requirement to return | Oxygen row/evidence or visible blocker | Mocked full API round-trip passes |

## Exact control flow

`src/environmental/service.py:map_requirements` iterates only the extracted
environmental requirements. There is no oxygen item to iterate for this run.
`evaluate` therefore never constructs an oxygen request. No downstream function
drops an oxygen record. Adding one here would invent a source requirement.

For a valid item, `sampling.source_depth` accepts `1 metre below sea surface`
only with supporting source quotation and produces 1.0. `router.MARINE` maps
DO to oxygen/o2. `copernicus.products` resolves the configured dataset.
`copernicus.worker` requests a small +/-0.05 degree box, selected daily UTC
query bounds and min/max depth 1; it validates supported 3-D dimensions, checks
returned vertical level (existing 0.5 m worker tolerance), selects the nearest
valid ocean cell within 5 km and retains actual selected depth. Evaluation
still requires its existing exact requested/evidence depth agreement. A nearby
but different vertical level does not silently pass.

## Units, cadence and qualifications

Existing oxygen-specific conversion:
`mg/L = mmol/m3 * 0.031998`. Accepted existing source spellings are `mmol/m3`
and `mmol m-3`; unsupported units fail, not guessed. Original raw value and unit
remain intact. Mock test: 200 mmol m-3 -> 6.3996 mg/L; `< 6.0` is NOT_TRIGGERED.

Cadence is 86400 seconds. Daily bracketing and daily maximum gaps determine
temporal coverage; no hourly requirement is imposed on this product. Daily
output cannot resolve subdaily excursions. Modelled oxygen remains supportive
and not equivalent to required in-situ monitoring. Actual local monitoring
requirements continue to route externally. Coastal qualification alone does
not suppress otherwise compatible numerical screening.

Illustrative **mocked** API evidence fields (not a live result):

```json
{
  "canonical_variable": "dissolved_oxygen",
  "provider": "COPERNICUS_MARINE",
  "dataset_id": "cmems_mod_nws_bgc-o2_anfc_7km-3D_P1D-m",
  "dataset_variable": "o2",
  "depth": 1.0,
  "requested_depth": 1.0,
  "data_type": "MODEL_FORECAST",
  "temporal_resolution": 86400,
  "retrieval_status": "SUCCESS",
  "temporal_coverage_status": "COVERED",
  "quality_status": "COASTAL_REVIEW_REQUIRED",
  "threshold_evaluation": "NOT_TRIGGERED"
}
```

Failures retain the oxygen row, INSUFFICIENT_DATA, and safe specific notes or
provider diagnostic category. Missing source depth prevents dispatch; no default
surface depth is applied. Provider failure tests cover depth, variable, temporal,
spatial, unit and runtime categories without dropping the requirement.

## Changes, tests and next action

No production backend or frontend change is justified by the confirmed cause.
Added `tests/test_oxygen_path.py`: **9 passed**, including mocked extraction ->
backend -> persisted analysis -> daily 3-D Toolbox -> environmental API.
Full backend regression: **282 passed**, one existing Starlette/httpx warning.
Existing wave/current/SST/wind/coordinate tests pass unchanged. No external API
requests, new confirmations or executable rules. The PDF skill directed the
original-source rendering/visual check; diagnostic image:
`tmp/pdfs/oxygen-diagnosis-upload-page08.png`.

No backend restart required: production code did not change. Restarting alone
cannot add a source requirement to this saved run. For a future explicitly
authorized manual extraction use the already-existing standalone
`output/pdf/PermitPulse_UNOFFICIAL_Environmental_Test.pdf`, which contains T2
with oxygen, or a separately corrected labelled synthetic document. Do not
alter the real licence or this historical run. Verify oxygen appears in the
analysis before Fetch. A later live fetch may still fail legitimately on daily
time coverage, a compatible vertical level or masked/distant coastal cells;
no successful live oxygen retrieval is claimed here.
