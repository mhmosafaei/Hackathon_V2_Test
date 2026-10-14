# PermitPulse Implementation Journal

## 2026-10-12 — Environmental retrieval diagnostics and presentation fixes

Diagnosed Narrow Water live analysis/cache offline and inspected the existing
browser results without fetching. Weather KeyError was missing transport wiring;
gust was an unmapped canonical alias. Added precise safe worker/service errors,
explicit NTU/FNU and missing oxygen-depth guards, existing forecast adapter
wiring, gust aliases and informational provenance routing. Historical Copernicus
exception reasons were discarded and cannot be retroactively identified.
SST is genuinely misquoted and wrongly attributed, not a verifier formatting bug;
retained source-verification block and did not rewrite source evidence.
Actual point fields already matched React; 940px global minimum table width
clipped card content. Added compact populated tables and explicit indeterminate
threshold conclusions/UTC coverage ranges. Real cached waves/currents genuinely
miss requested endpoints; temporal/coastal safeguards are unchanged.

Full offline tests: 232 backend passed (12.12s, one existing Starlette warning),
42 frontend passed (13.38s). Build passed (8.10s, existing bundle warning).
No live provider/OpenAI calls. No backend restart or manual acceptance performed.
See ENVIRONMENTAL_RETRIEVAL_DIAGNOSIS.md for exact periods, mappings, gaps and
source-verification findings. User must restart and run live acceptance manually.

## 2026-10-12 — Replace local conversion with explicit online action

Per user specification, replaced PROJ4js conversion with a dedicated explicit-
click-only /api/coordinates/convert service. Initial permit extraction remains
unchanged and source coordinates are not converted automatically. Configured
OpenAI model is gpt-4.1-mini; strict structured response, 60-second timeout,
600-token output ceiling, zero retries and per-attempt persistent one-request
ledger. Minimal source-only input; no geocoding or environmental fetch.
Backend gates finite/ranged WGS84 values, enums, exact original-coordinate
identity, high confidence and converted status. UI keeps independent location
states, blocks double clicks, caches results, and enables Use location only for
eligible results. Copying never fetches environmental data or creates rules.
Original permit results/reviews remain untouched. Removed superseded local
conversion utility/tests/dependency. See COORDINATE_CONVERSION.md for contract,
provenance and the limitation that model confidence/bounds are not independent
proof of mathematical/geodetic accuracy.

Full offline backend regression: 219 passed, one existing Starlette warning,
12.23 seconds. Frontend: 40 passed, 9.33 seconds. Build passed, 7.80 seconds,
existing bundle-size advisory. Zero real API requests. Backend restart is
required to load the new route; no active user analysis was cleared during
implementation. No live conversion acceptance was attempted.

## 2026-10-12 — Local Irish Grid environmental-query conversion

Added local PROJ4js transformation for explicit source-verified point coordinates
in Irish Grid (IGR/Irish Grid Reference, EPSG:29902/29903). The UI requires an
explicit confirmation/conversion click before enabling Use location. Generic IGR
is displayed as an EPSG:29903 interpretation requiring datum confirmation, not
as a datum proved by the document. Original quotations, grid coordinates and
analysis artifacts remain untouched; the derived point and method are separate
client-side query inputs. Seven-parameter Helmert conversion is approximate,
not survey/navigation-grade. No geocoding, route midpoint or offshore-cell
substitution. Unverified, inconsistent, out-of-range and unsupported coordinates
remain blocked. Conversion and copying do not fetch environmental evidence or
authorize work. Copernicus coastal/ocean-cell suitability checks remain separate.

Frontend offline tests: 32 passed, 0 failed; production build passed with the
existing bundle-size advisory. Production dependency audit: zero vulnerabilities
(development-tool audit warnings remain outside this scoped change). No live
OpenAI/Copernicus/weather requests. Served static assets are rebuilt; refresh
loads the updated controls without restarting the backend or losing its analysis.

## 2026-10-12 — Narrow Water spatial-contract correction (offline)

Inspected historical run 35a615c8e3eb4d5db26594228211cdf2, source SHA256
172291571418bd927fe904f9b8e924c8bb9903ccf82a37f083dd68d3f0d1c82a.
Its manifest records simple-permit-v1.2-environment. The exact IGR pair is present
in input.txt, but schema.json, the raw response and analysis.json have no
spatial_context field. This is an old-runtime/schema omission, not an API or
frontend field-dropping bug. The newer v1.3 schema also lacked easting/northing.

Version v1.4 adds nullable original grid values, physical source_page and a
controlled geometry enum to the same one-request contract. Prompt explicitly
includes non-condition particulars and preserves multiple locations. IGR may
be labelled Irish Grid Reference only with explicit source evidence. Local
verification checks E/N suffix values and source page; no CRS conversion or
geocoding occurs. Only verified explicit WGS84 coordinates remain eligible for
the environmental query-point copy action. Validity and operating timing stay
separate. Original saved runs and raw responses are unchanged.

Offline Narrow Water fixture exercises strict SDK-response parsing, backend
validation, persistence and the actual /api/analyze response consumed by the
React Environmental view. A changed Easting fails source verification without
discarding the evidence. Full pytest: 198 passed, 0 failed, 1 existing
Starlette/httpx deprecation warning, 18.67 seconds. No live OpenAI or environmental
requests. Existing live process/result was not restarted or re-analyzed; a
normal backend restart is needed to load this source version for future uploads.

## 2026-10-12 — Permit-defined location/time cards

Scoped UX extension, not a new extraction architecture. Added source-backed
spatial/temporal fields to the existing ONE request and compact cards before the
environmental request form. Reused summary/geofence fallbacks for older results.
WGS84 explicit verified points copy only on click; other CRS values and routes
remain display-only. Validity never becomes operations silently. Date-only or
timezone-unspecified dates do not receive inferred UTC times. Copy actions do
not fetch data; all existing provider/evidence/review safeguards remain intact.

Offline backend suite passed 196 tests (0 failed, 44.72 s); frontend suite passed
28 tests (0 failed, 26.46 s). Production build passed, with the existing bundle
size advisory. Browser mock upload/source
cards/point copy passed, zero browser errors. The live server/current result was
left untouched; future extraction schema needs a normal backend restart, not
automatic re-analysis. No live calls, review changes, new credentials or changes
to historical outputs. Detailed verification and limitations are documented in
SIMPLE_ENVIRONMENTAL_INTELLIGENCE.md.

## 2026-10-12 — Simple React Environmental Intelligence, offline delivery

Extended the ONE strict OpenAI response with source-linked environmental
requirements, without another LLM stage or budget changes. Added a 120-name
catalogue, deterministic router, unit/compatibility checks, bounded Copernicus
Toolbox and Open-Meteo ECMWF/ERA5 adapters, session-isolated evidence cache and
explicit Fetch endpoint. Added the Environmental Intelligence tab while
preserving Permit Intelligence's four charts and geofences. Manual point/time
is required; complex areas require point-only confirmation or sampling review.
No approval, executable rule or work authorization is created.

Full backend suite: 192 passed, 0 failed (14.60 s). Frontend: 20 passed, 0 failed
(8.69 s). Production build passed (8.01 s), with bundle-size advisory. Actual
mock browser upload, four-chart display, source drilldown, synthetic evidence
fetch, tab switching, New Analysis and restart isolation passed. Mobile 390 px
had no page overflow; zero browser error logs. Fixed a browser-observed native
datetime-input commit issue and added its UTC-payload regression test.

No live external calls or credential changes. Historical reviews/responses
preserved. Salinity, visibility, ERA5 waves, direct CDS/CAMS, derived indicators
and route sampling remain unsupported. Copernicus coastal representativeness
remains review-gated. Live extraction/provider access still requires separate
authorization. Complete results, changed files, screenshots and exact controlled
provider-test instructions: SIMPLE_ENVIRONMENTAL_INTELLIGENCE.md.

## 2026-10-12 — Focused geofence enhancement to the single-pass React workflow

Added a strict `geofences` array to the existing one-request schema and prompt.
Supported types: radius, coordinate boundary, route, corridor, polygon, exclusion
zone, restricted segment, named area and other. Ordinary place mentions and
inferred/geocoded boundaries are explicitly excluded. Each item retains its
name, description, source-written boundary, restriction, physical source pages
and exact quotation spans. Local checks flag conflicting pages or boundary text
not present in the quotations. All items remain UNREVIEWED/non-executable.

Added one conditional At a Glance GEOFENCE card. Empty arrays/older results omit
it; multiple items show their count and the first source-ordered restriction.
The prompt requests operational-significance ordering, not a compliance decision.
The compact summary suppresses coordinate lists. Native expandable details
preserve full boundaries, restrictions, quotations and source pages. New Analysis
clears this data through the existing session reset. Existing conditions table
and exactly four charts are unchanged.

Offline verification: **144 backend tests passed in 8.72s** (one existing
Starlette/httpx deprecation warning); **12 frontend tests passed**, including
all six requested geofence cases (60.46s runner duration). Production build
passed in 19.37s with the existing advisory chunk-size warning. Mocked browser
upload verified the radius summary, expandable original page-2 source, mobile
390px layout without page/card overflow, four charts and New Analysis clearing.
Screenshot: `tmp/geofence-card-preview.jpg`. No OpenAI requests were made.

Published prompt/schema copies were updated from runtime definitions. Existing
historical run artifacts were not migrated. Verified no analysis was pending
before restarting the two identified React workers to load the update; LIVE is
still available at 8531 and the separate mocked preview at 8530. No live Analyze
action was invoked. Source-backed extraction quality on real permits remains
for the user's separately initiated live test.

## 2026-10-12 — Single-pass Python extraction and clean React dashboard

Implemented the user-requested primary hackathon UI in `frontend/`, served by
`src.permit.simple_api` on loopback. Reused the existing PDF parser, conservative
quote normalization, direct TLS-verified OpenAI transport, response-metadata
helpers and persistent budget ledger. The new route performs one strict-schema
extraction request for bounded text-readable PDFs, with no candidate engine,
deduplication or intelligence-stage dispatch. Existing Streamlit modules,
historical artifacts and review decisions were not migrated or changed.

The frontend holds active analysis only in memory. New Analysis clears it;
backend boot-ID polling clears an open browser on restart, and stale sessions
cannot dispatch. No history is restored. All newly returned conditions are
UNREVIEWED and non-executable. Exact quotations and physical pages remain
inspectable; missing numbered-source records and failed quotation checks are
warnings rather than fabricated replacements.

Offline validation: **140 backend tests passed in 8.61 seconds**, with one
upstream Starlette/httpx deprecation warning. **6 frontend tests passed** (15.00s
total runner duration). Production Vite build passed (26.69s), with an advisory
bundle-size warning (592.59kB JS, 177.06kB gzip). Real browser testing on the
compiled mock preview verified 22 rows, exactly two bar/two pie charts, phase
filter/reset, source evidence, safe invalid-PDF error, New Analysis, reload and
server restart clearing. Widths 1440/1024/390 had no page overflow or clipped
chart titles; mobile table scrolling was intentional. No browser error logs.

No OpenAI API calls, approvals, operational decisions or executable rules were
created. Synthetic UI test runs are isolated under `cache/simple_analysis/`.
Preview remains mocked. Single-pass live quality and completeness require a
separately authorized real test; quotation presence is not semantic verification.
See `SIMPLE_REACT_DASHBOARD.md` for prompt/schema, files, limitations and steps.

## 2026-10-12 — Deterministic permit finalization after candidate extraction

Removed the default live Stage 1/2/3 dependency from `analyze_ai_first_upload`.
The old chain remains explicit experimental code, not a silent fallback. No
OpenAI calls were made in this implementation. Successful candidate extraction
now produces a local canonical analysis, review dataset, coverage groups,
evidence classifications and exports. Failed extraction still fail-stops.

Reused the 37 retained candidates from acceptance-b13ab39680004131b1a013dfd25505e1.
All original run files, responses, ledger reservations and review history were
preserved; the projection is under `deterministic-permit-v1/`. Verification
remains 30 SOURCE_VERIFIED, 4 SOURCE_NOT_FOUND, 3 CONTEXT_UNRESOLVED; 3 removed
duplicates remain in the audit. Source inventory contains 41 records and all
22 numbered conditions. Exact source-span coverage: 13 CAPTURED, 6 PARTIAL
(7,10,18,19,20,22), 1 REVIEW_REQUIRED (13), 2 NOT_CAPTURED (1,2).
These are conservative span comparisons, not certified obligation-level recall.

Condition 19's original candidate page 4 is preserved in the audit. Its derived
page is corrected to 3 only after unique quotation matching against the original
PDF, because the inventory's condition-19 span includes continuation on page 4.
No quotation was rewritten and no verification state was promoted.

Existing capability mapping yields 2 EXTERNAL_DATA_REQUIRED (AIS_GNSS),
9 MANUAL_INPUT_REQUIRED and 26 NOT_EVALUABLE. No environmental caches were
inherited and no automatic rules were created. Human authority/semantic review
remains outstanding. XLSX now reversibly escapes XML-illegal control characters;
canonical JSON and raw evidence retain original text. Conditional export metadata
preserves legacy sheet layouts for unaffected exports.

Default document selection restores the run URL after restart; failed uploads
select their own saved run rather than silently leaving Belfast active.
Final offline suite: **130 passed in 8.72 seconds, 0 failed**, including production
cached-dashboard AppTest with both API transports blocked. Real browser checks
and current runtime identity are recorded in HACKATHON_PERMIT_RELIABILITY.md.

## Project overview

### Final extraction acceptance — Hinkley LIVE selector, exports, and isolation

The final offline acceptance pass corrected two presentation/export defects without altering extraction logic or permit data. The Hinkley LIVE active-document selection now keys review and source tables by document, preventing stale Belfast table state after document switches. Candidate-mode metrics now correctly display 46 processed pages and 114 review-gated records. The Excel exporter now converts the persisted `processed_pages` list into 46 Coverage rows rather than emitting an empty Coverage sheet.

Visible-browser checks selected Hinkley Point C — live AI evaluation, verified its 114 review-gated candidates and 558-record source inventory, exposed `UNRESOLVED_CONTEXT` table relationships, switched Belfast → Marine Licence 07203/20/0 → Hinkley without cross-document data inheritance, and opened all four tabs without application exceptions. Browser-triggered downloads were checked locally: obligation CSV 114 rows, source CSV 558 rows, JSON 114 candidates/558 source records, and Excel sheets Document summary, Source inventory (558), Obligation register (114), Coverage (46), and Review status (114).

Offline source sampling verified the PDF SHA-256 `a9dec163f30956e1e4b99208df4b482a54df1d5db666598ef9f93fee2a1d19da`, 46 pages, 114 candidates, and 558 source records. Its 22-record stratified sample produced 18 direct linear matches, 2 layout-serialization non-linear records, and 2 source-span review-required records. No result was promoted based on those uncertain checks. Full regression: `python -m pytest tests -p no:cacheprovider` collected **83** tests and passed **83** in 1.84 seconds. No OpenAI API calls occurred. Engineering status: **EXTRACTION_ENGINEERING_COMPLETE**; human legal/semantic review and unresolved table applicability remain non-engineering operational constraints.

PermitPulse is a hackathon MVP that converts marine permits and contracts into evidence-backed environmental decision intelligence. It has two modules: Permit Operations and Marine Contract Weather Intelligence. Its frozen scope excludes local-sensor, AIS/GNSS and laboratory integrations; those remain evidence-source classifications only. Copernicus Marine is planned as the primary ocean source and weather as a complementary source. The LLM will structure document content, but deterministic Python will make decisions only after human confirmation.

## Development environment

- Operating system: Windows development environment.
- Python: 3.11 or newer expected.
- Package manager: pip in a project virtual environment.
- Install: `python -m pip install -r requirements.txt`
- Run: `streamlit run app.py`
- Test: `python -m pytest`

## Repository structure

```
permitpulse/
  app.py                    Streamlit entry point
  config/                   validated settings and controlled source registry
  docs/                     architecture and implementation record
  src/                      application packages and Pydantic models
  tests/                    deterministic foundation tests
  data/                     future source documents and golden data; do not store secrets
  cache/                    future normalised external-data cache; do not commit retrieved data
```

## Stage log

### Stage 0 Foundation

Objective: establish a testable skeleton without calling external services.

Files added: `app.py`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `config/settings.yaml`, `config/sites.yaml`, `config/keywords.yaml`, `config/environmental_data_sources.json`, `src/config.py`, `src/models/*`, `src/mapping/capability_registry.py`, `tests/*`, and this documentation.

Implementation: the Streamlit app shows the two empty MVP tabs. `src/config.py` loads strict YAML settings. `src/models` provides Pydantic structures and enums for conditions, confirmed rules, observations, decisions, evidence and contract historical coverage. Naive datetimes are rejected on environmental and decision boundary models. The registry is a no-network stub; local sensor requirements deterministically become `EXTERNAL_DATA_REQUIRED`, while manual approvals become `MANUAL_INPUT_REQUIRED`.

Why: establishing controlled vocabularies and strict inputs first preserves provenance and makes later core functions testable. No adapters exist yet, preventing simulated or accidental evidence use.

Acceptance criteria: met. `python -m pytest tests -p no:cacheprovider` passed 7/7 tests. A Streamlit `AppTest` rendered both required tabs without application exceptions.

Status: **STAGE COMPLETE**. No later-stage implementation has started.

Checkpoint: attempted to create the Stage 0 Git checkpoint, but the workspace denied creation of `.git/index.lock`. Source files remain present and uncommitted; no existing user files were modified.

### Stage 1 Document intelligence vertical slice

Objective: implement the real-PDF pipeline from page extraction through human-confirmed executable rules and evidence-source classification, without environmental API calls or any simulated local-sensor/AIS/laboratory data.

Planned files: `src/documents/pdf_parser.py`, `ocr.py`, `page_filter.py`, `quote_verifier.py`, `extractor.py`, `validator.py`; `src/permit/*`; `src/ui/*`; extraction prompt and cache support; app updates; fixtures and Stage 1 tests.

Acceptance criteria: the real ML2025054 permit is parsed with preserved physical page numbers; relevant pages are selected; structured extraction validates and quote verification is enforced; only user-confirmed rows create executable rules; source and automation status are honestly classified; the Permit tab demonstrates the workflow; no environmental data is simulated or retrieved.

Source availability: `data/permits/ML2025054.pdf` was supplied and copied into the repository on 2026-10-08. It has 14 physical pages and a usable text layer. The key permit conditions, including darkness restriction (condition 17), sampling approval (condition 18), local suspended-solids/dissolved-oxygen monitoring (conditions 19–20), AIS (condition 9), and notifications are now read from the real licence rather than prior summaries.

Implementation so far: added the PDF parser, OCR interface only, keyword filter with adjacent-page inclusion, normalized quote verifier, batch-safe validation/deduplication, confirmation-gated rule factory, and source/automation classification. The Streamlit Permit tab parses the real permit and displays selected physical pages. Local sensor, AIS/GNSS and laboratory evidence remain classification-only; no environmental data, simulator, adapter, or sample stream was created.

Current blocker: live OpenAI structured extraction has not been enabled because no `OPENAI_API_KEY` or approved model has been provided. The extraction adapter accepts a mockable structured-response transport and malformed responses are isolated per page; it must be connected to the OpenAI SDK and verified against the real licence after credentials are provided. No document content has been transmitted externally.

Live extraction update: credentials were later explicitly authorized for reuse. The client reads `OPENAI_API_KEY` and `OPENAI_MODEL` only from environment variables via `python-dotenv`; neither is logged, rendered, or committed. The initial configured-model request failed with HTTP 400 because it rejected `temperature=0`. The parameter was removed rather than hard-coding a model-specific alternative. A subsequent full audit invocation against the seven relevant pages did not produce a response or write `cache/extractions/stage1_ml2025054_audit.json` before the local execution window closed. Therefore no live condition count, quote-verification aggregate, or model-derived extraction result is claimed.

Testing after the live-client change: `python -m pytest tests -p no:cacheprovider` collected 15 tests and passed all 15 in 0.21 seconds. These tests cover filtering, normalized quote verification, fabricated-quote rejection, malformed response containment, exact deduplication, review requirement for null thresholds, confirmation gate, rule creation, and automation-status classifications.

Stage 1 final status: **BLOCKED**. Exact blocker: the configured OpenAI client invocation does not complete and produce an auditable response in this execution environment, so the mandatory persisted live structured-extraction record cannot be generated. Stage 2 has not started.

Page 5 extraction diagnosis and rerun: the initial `gpt-4.1-mini` response contained nine material clauses from conditions 16–23, but all were rejected by Pydantic because the prompt did not constrain `condition_id` to string, `condition_type` to the controlled enum, `evidence_requirements` to a list, or `required_action` to its controlled enum. The source text itself was healthy: 3,246 characters, physical page 5, and it was persisted as `cache/extractions/ml2025054/page_05_input.txt`. The raw initial response and validation errors were retained in the page audit artifact.

Correction: the prompt now explicitly requests all permit condition categories, including non-numeric clauses; requires the controlled enum values and list types; permits null numeric values; and requires verbatim source wording. The rerun completed with `gpt-4.1-mini`: 15 raw items, 6 validated items, 7 validation errors, 6 quote-verified and 0 quote failures. The checkpoint is `COMPLETE` in `cache/extractions/ml2025054/manifest.json` and the per-page artifact is `page_05.json`. Relevant regression tests: `python -m pytest tests/test_stage1.py -p no:cacheprovider` collected 8 and passed 8 in 0.19 seconds.

Stage 1 status remains **PARTIAL**: page 5 is now demonstrably extracting and quote-verifying material conditions, but the remaining selected pages have not been processed as directed.

Resumable page processing update: pages 4 and 6 were processed sequentially after page 5, each with its exact PDF input, raw structured response, validated output, reconciliation artifact, and manifest checkpoint persisted under `cache/extractions/ml2025054/`. Page 4: 6 raw, 5 valid, 1 validation rejection (`condition_type`), 0 duplicates, 5 quote verified and 0 failed; classifications were AUTHORITY_APPROVAL/MANUAL_INPUT_REQUIRED (3) and UNKNOWN/NOT_EVALUABLE (2). Page 6: 8 raw, 8 valid, 0 validation rejections, 0 duplicates, 6 quote verified and 2 quote failures; classifications were AUTHORITY_APPROVAL/MANUAL_INPUT_REQUIRED (1) and UNKNOWN/NOT_EVALUABLE (7). Quote failures remain review-required evidence and are not silently accepted for execution. `python -m pytest tests/test_stage1.py -p no:cacheprovider` passed 8/8 in 0.19 seconds.

Page 6 local verification correction: condition 27 now verifies after preserving a semantic line-break hyphen in the email address. Condition 30 remains `quote_verified=false` and `review_required=true` because the source PDF extraction contains `ofworks` while the model supplied `of works`; no fuzzy legal-text acceptance was used. Page 6 final counts are 8 schema-valid, 7 verified and 1 failed/review-required.

Pages 7 and 8 were subsequently processed sequentially with the same resumable artifacts. Page 7: 1 raw, 1 valid, 0 rejected, 0 duplicates, 1 verified; UNKNOWN/NOT_EVALUABLE (1). Page 8: 6 raw, 6 valid, 0 rejected, 0 duplicates, 5 verified and 1 failed/review-required; UNKNOWN/NOT_EVALUABLE (5), AUTHORITY_APPROVAL/MANUAL_INPUT_REQUIRED (1). All raw inputs, raw responses, validated records and reconciliation outputs are retained; no cross-page aggregation has begun.

Final selected-page extraction update: pages 9 and 10 completed sequentially without revisiting previous pages. Page 9: 11 raw, 11 valid, 0 rejected, 0 duplicates, 10 quote-verified and 1 quote-unverified/review-required; all 11 classify UNKNOWN/NOT_EVALUABLE. Page 10: 6 raw, 6 valid, 0 rejected, 0 duplicates, 6 verified; CALENDAR/AUTOMATIC (1) and UNKNOWN/NOT_EVALUABLE (5). No validation errors occurred on either page. The selected-page set (4–10) now has 43 schema-valid conditions, 40 quote-verified and 3 quote-unverified/review-required conditions. `python -m pytest tests/test_stage1.py -p no:cacheprovider` collected 9 and passed 9 in 0.65 seconds. Cross-page aggregation remains intentionally deferred.

Cross-page aggregation and acceptance audit: persisted outputs for pages 4–10 were aggregated without API calls. The document SHA256 is `7e8e26705bf2b788657bf6de661a9b49d390f2600f03f461f500b58340294252`. Raw accounting reconciles as 53 raw = 43 valid + 8 validation-rejected + 2 within-page exact duplicates + 0 cross-page duplicates. Aggregate outcomes are 40 quote-verified and 3 quote-unverified/review-required. Validation errors are threshold (7) and condition_type (1). `docs/STAGE_1_AUDIT.md` records the recovery queue, capability distribution, and remaining acceptance gaps. Full local suite: `python -m pytest tests -p no:cacheprovider`, 16 passed in 0.68 seconds. Stage 1 remains blocked pending human review/recovery and UI workflow verification; Stage 2 has not started.

Human-review workflow update: Streamlit now loads the aggregated Belfast conditions, provides type filtering, source quotation and physical-page display, explicit confirm/reject controls, persistent decisions in `review_decisions.json`, and a validation-recovery queue. Generic confirmation of an unverified quotation raises an error; no unreviewed extraction can create a rule. Review persistence and unverified-confirmation gating have automated coverage. Current UI smoke test loaded successfully. Full suite after this work: 18 passed in 0.81 seconds.

Full-document deterministic coverage audit: the 14-page PDF has 31 numbered licence conditions. The page filter omitted physical page 3, producing confirmed gaps in conditions 1–8 and contributing to the condition-9 AIS stop-work gap. Condition 10 is also not extracted. Coverage status: 15 captured, 1 partially captured (condition 20), 5 recovery items (17,18,19,22,23), and 10 not extracted (1–10). The source-backed audit and queue are recorded in `coverage_audit.json` and `STAGE_1_COVERAGE_AUDIT.md`; no new conditions, confirmations, or executable rules were created.

Coverage architecture and recovery update: numbered-condition pages now override keyword-only selection and carry their successor page for continuation text; a deterministic coverage gate flags non-captured source conditions. Page 3 was recovered through the checkpointed extractor: conditions 2,3,4 and 8 validated and quote-verified; conditions 1,5,6,7 and 9 were retained as rejected recovery items, including the AIS stop-work clause. Page 4 was preserved unmodified; condition 10 remains a source-backed missing UKHO-notification gap. Updated coverage is 19 captured, 1 partial, 10 recovery and 1 missing. No AIS integration or fabricated evidence was added.

Deterministic recovery and reaggregation: source-backed candidates were created for 1,5,6,7,9,10,17,18,19, the station-capability subclause of 20,22 and 23. Candidate fields are derived directly from the physical PDF; no API call occurred. The candidate set quote-verifies 12/12 and keeps all records UNREVIEWED. Condition 9 is explicitly classified AIS_GNSS/EXTERNAL_DATA_REQUIRED. Reaggregation appended the four validated page-3 records and 12 recovery candidates without overwriting prior evidence: 59 records, 56 quote-verified and 3 quote-unverified. Full suite after recovery: 20 passed in 0.77 seconds. Human confirmation and review of recovery candidates remain mandatory.

Stage 1A engineering finalization: added a document-level orchestrator with SHA256/model/prompt-version cache identity, numbered-condition selection independent of keyword filtering, per-page checkpoints, bounded worker pool (maximum three), failure isolation, and resume semantics. The Streamlit shell now accepts an upload and presents the Analyze workflow without exposing cache internals. The persisted Belfast review and coverage queues remain available. Full test suite: 22 passed in 0.72 seconds; Streamlit smoke test passed. The host emitted only a non-fatal temporary-directory cleanup warning after the harness exited.

Stage 2A started: added candidate Copernicus registry entries, cache-keyed adapter primitives, nearest-valid-cell selection, current and guarded oxygen derivations, and local tests. Live catalogue and Belfast retrieval remain unverified because neither Copernicus username nor password is configured. Candidate IDs are documented in `COPERNICUS_VERIFICATION_REPORT.md` and are not represented as live verified.

Page 5 accounting reconciliation: all 15 raw items are now explicitly traced: 6 valid (`16`, `20a`, `20c_stop`, `20d`, `20e_stop`, `21`), 7 validation-rejected (`17`, `18`, `19`, `20b`, `20f_resume`, `22`, `23`), and 2 exact duplicate removals (`17a`, `17b`). Thus `15 = 6 + 7 + 2 + 0`. The seven rejected items raised nine field-level errors: `threshold` 7 and `threshold_upper` 2. None were rejected merely because a numeric threshold was absent; all rejections were nonnumeric strings supplied in numeric fields. The six retained items quote-verify against the real PDF, preserve their source text, use controlled enums, and classify as AUTHORITY_APPROVAL/MANUAL_INPUT_REQUIRED (condition 16), LOCAL_SENSOR/EXTERNAL_DATA_REQUIRED (conditions 20a–20e), or UNKNOWN/NOT_EVALUABLE (condition 21). No dataset IDs or evidence measurements were introduced.

## Data model documentation

- `ExtractedCondition`: an LLM-extracted, reviewable document clause. Created by the future extraction service and consumed by human review; it is never itself executable.
- `ExecutableRule`: a human-confirmed deterministic rule. It records confirmation identity/time, source bindings, and automation status.
- `RuleGroup`: an AND/OR collection of future executable rules.
- `EnvironmentalObservation`: one normalised environmental value with provider, source, data type, quality, provenance and optional grid metadata. Timestamps must be timezone aware.
- `SourceBinding`: describes whether a source can decide a rule.
- `RuleResult`, `Window`, `EvidenceItem`: audit-ready deterministic outputs, deliberately separating operational status and required actions.
- `YearCoverage` and `HistoricalRiskResult`: future historical seasonal-risk output structures; these must not be presented as prediction.
- `AutomationStatus`, `SourceType`, and `SourceRole`: controlled values used to preserve the distinction between available deciding evidence, advisory data and unavailable evidence.

## Evidence-source classification

Stage 0 registry handles only classification. `LOCAL_SENSOR`, `AIS_GNSS`, and `LAB_RESULT` have no adapters. A local-sensor requirement maps to `EXTERNAL_DATA_REQUIRED`; a manual input or authority approval maps to `MANUAL_INPUT_REQUIRED`; an unknown variable maps to `NOT_EVALUABLE`. This prevents missing data from becoming a green result.

## External dependencies and accounts

- OpenAI API: deferred to Stage 1. `OPENAI_API_KEY` is documented in `.env.example` only.
- Copernicus Marine credentials: deferred to Stage 2. Username/password variable names are documented in `.env.example` only.
- Open-Meteo and optional ERA5/CDS: deferred to later stages.
- No external service was called in Stage 0 and no secret values were stored.

## Assumptions and limitations

- Default display timezone is `Europe/London`; model timestamps require timezone awareness.
- Dataset IDs and live coverage are unverified placeholders until Stage 2.
- No permit PDF is bundled in this repository; the real ML2025054 PDF remains needed for Stage 1.
- This stage has no extraction, decision engine, cache, Copernicus/weather retrieval, or contract analysis.

## Important decisions ADR log

| Date | Decision | Why | Consequence |
| --- | --- | --- | --- |
| 2026-10-08 | Use Streamlit shell | Blueprint-defined MVP delivery path | Two empty tabs are available before services exist |
| 2026-10-08 | Use strict Pydantic models | Prevent invalid and provenance-poor data entering later stages | Models reject unknown fields and naive datetime boundaries |
| 2026-10-08 | Keep registry adapter-free | Foundation must not imply live data support | Stage 2 must verify and add datasets before data retrieval |

## Testing log

| Test file | Behaviour | Expected result | Actual result |
| --- | --- | --- | --- |
| `tests/test_config.py` | settings load and unknown-field rejection | valid settings load; extra settings fail | PASS |
| `tests/test_models.py` | timezone-aware model boundary | naive timestamp fails; aware timestamp passes | PASS |
| `tests/test_registry.py` | registry, classification and oxygen conversion | registry loads; local sensor is external; 100 mmol/m3 = 3.2 mg/L | PASS |
| Streamlit `AppTest` | shell rendering | two named product tabs render without application exceptions | PASS |

Command used: `python -m pytest tests -p no:cacheprovider` (7 passed).

## Development timeline

| Stage | Status | Scope | Next step |
| --- | --- | --- | --- |
| 0 Foundation | COMPLETE | Skeleton, config, models, registry stub, docs | Await approval for Stage 1 |
| 1 Document intelligence | PARTIAL | PDF/quote/classification tests pass | Needs OpenAI credential and UI confirmation wiring | Awaiting credential |
| 2–7 | DEFERRED | Blueprint-defined later stages | Explicit approval required |

## Final implementation status

| Component | Status | Tested | Demo-ready | Notes |
| --- | --- | --- | --- | --- |
| Repository skeleton | COMPLETE | Yes | Yes | Stage 0 only |
| Config loader | COMPLETE | Yes | Yes | strict YAML validation |
| Data models | COMPLETE | Yes | Yes | no external I/O |
| Registry stub | COMPLETE | Yes | Yes | no verified datasets/adapters |
| Streamlit shell | COMPLETE | Yes | Yes | two empty tabs |
| Extraction, providers, evaluation, windows, contract analysis, cache | DEFERRED | No | No | future stages |

## Bug and issue log

| Issue | Cause | Fix or impact | Status |
| --- | --- | --- | --- |
| Pytest default collection hit inaccessible `pytest-cache-files-*` directories created by the constrained workspace | Workspace permissions | Target tests explicitly and disable pytest cache provider: `python -m pytest tests -p no:cacheprovider` | Resolved for Stage 0 verification |
| Streamlit test cleanup emitted a temporary-directory permission warning after successful render | Host temporary-directory permissions | App test passed; warning is external to application code | Known environment limitation |
| Git checkpoint could not be created | Workspace denied `.git/index.lock` creation | Stage 0 files remain uncommitted | Blocked by workspace permissions |
| Stage 1 real permit absent | `data/permits/` contains only `.gitkeep` | Cannot begin required real-PDF extraction workflow or build golden set | BLOCKED — REAL BELFAST PDF REQUIRED |
| Live structured extraction not configured | No OpenAI credential/model supplied | Offline Stage 1 code is testable; the real licence has not been sent to an LLM | Awaiting user credential |

## Rebuild from scratch

1. Install Python 3.11+.
2. Create and activate a virtual environment.
3. Run `python -m pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` only when later-stage credentials are available.
5. Run `python -m pytest`.
6. Run `streamlit run app.py`.

### Stage 2A live Copernicus Marine verification (2026-10-09)

The local Copernicus username and password environment variables were detected without reading them into output. Official Toolbox authentication completed successfully using `copernicusmarine.login(..., check_credentials_valid=True)`. The official `describe` endpoint resolved all five configured candidate IDs, and small `open_dataset` requests were made for the Belfast Harbour bounding box (longitude -5.98 to -5.85, latitude 54.55 to 54.65).

Live results: wave, current, SPM/turbidity, dissolved-oxygen and SST requests completed. Waves, currents and SST selected the nearest valid ocean cell at 54.635139, -5.878788, 4.139 km from the indicative request coordinate (GOOD coastal-context representativeness). Wave source variables were VHM0 (m), VTM02/VTPK (s), VMDR (degree); current source variables were uo/vo (m s-1), with current speed derived from them; SST was thetao (degrees_C). The verified source products were NWSHELF_ANALYSISFORECAST_WAV_004_014 and NWSHELF_ANALYSISFORECAST_PHY_004_013, both catalogue version 202511. SPM/TUR returned source units g m-3/FNU (catalogue version 202107) and oxygen returned mmol m-3 (NWSHELF_ANALYSISFORECAST_BGC_004_002, version 202511), but all cells in the narrow coastal subset were masked. These two results are recorded as retrieval-success/no-valid-cell, never as zero or as invented measurements.

Successful cache files retain source units, UTC timestamps, product/version provenance, request bounds, selected-grid metadata and compact real series where a valid cell exists. `load_cached_product` was added to load those records with no network access and expose freshness metadata. SPM and oxygen remain SUPPORTIVE; they do not replace required local monitoring. Stage 2B and Stage 3 were not started.

Verification: `python -m pytest tests -p no:cacheprovider` collected and passed 27 tests in 0.78 seconds. A separate offline read of `cache/copernicus/waves.json` returned 100 persisted observations and fresh-cache metadata with no credentials loaded.

### Combined Stage 2B + Stage 3 environmental intelligence (2026-10-09)

Added a bounded Open-Meteo adapter that explicitly requests `ecmwf_ifs025`, retries bounded transport failures, persists the raw provider response and metadata, and serves cache-only reads with freshness status. A live Belfast request completed with 72 hourly forecast values for wind speed/direction/gusts, precipitation, air temperature, pressure, relative humidity, cloud cover and visibility. The returned source units are preserved (wind/gust km/h, precipitation mm, temperature °C, pressure hPa, humidity/cloud cover %, and visibility unit `undefined` from the provider). The data are labelled `ECMWF IFS via Open-Meteo` because the request explicitly selected that model; they are forecast, not historical observations.

The Streamlit Environmental Intelligence tab is a unified marine/atmospheric dashboard over cached Belfast data. It displays Plotly charts, provenance, cache freshness, coastal-grid representativeness, masked/missing states, descriptive summaries and advisory-only thresholds. Combined advisory windows require aligned, present, sufficiently representative data; absent or asynchronous evidence is displayed as unavailable rather than favourable. Permit-to-evidence rows retain their source quotation, review state and source requirement. No weather or Copernicus feed is allowed to promote unconfirmed conditions or replace local SPM/DO/AIS evidence.

Verification: full pytest collected 31 tests and passed all 31 in 0.25 seconds. The Streamlit `AppTest` rendered both Permit Operations and Environmental Intelligence tabs with zero application exceptions. Host temporary-directory cleanup still emits a non-fatal Windows permission warning after the smoke-test process exits.

### Environmental synchronization and advisory-window validation (2026-10-09)

Initial raw cache overlap was only the timestamp 2026-10-09 00:00 UTC: Copernicus marine data ended there, while the ECMWF IFS via Open-Meteo forecast began there and continued to 2026-10-11 23:00 UTC. Three new bounded, real Copernicus requests refreshed waves, currents and SST for the full weather interval. All selected the same nearest valid ocean cell (54.635139, -5.878788), 4.139 km from the indicative Belfast request coordinate, with GOOD representativeness. The shared hourly UTC period is now 2026-10-09 00:00 through 2026-10-11 23:00 UTC (72 hours). Coverage is 100% for significant wave height, wind speed, wind gust and current speed. Raw 15-minute currents are retained; their aligned hourly advisory value is the maximum, never an interpolation.

With the dashboard defaults (wave <= 1.5 m, wind <= 30 km/h, gust <= 45 km/h, current <= 1.0 m/s, two-hour minimum), the real cached scenario contains a 27-hour advisory WORKABLE interval from 2026-10-10 18:00 UTC through 2026-10-11 20:00 UTC. All other intervals are advisory NON_WORKABLE and are limited by wind speed and/or gust. This is exploratory environmental intelligence only, not a permit decision. The evaluator supports WORKABLE, NON_WORKABLE and UNKNOWN intervals; required missing/stale/unrepresentative evidence propagates to UNKNOWN.

The live retrieval architecture now accepts validated coordinates and time ranges, chooses and records nearest valid grid cells, and cache-isolates successful results by dataset/source version, coordinates and valid period. Belfast remains the preload. No local sensor/AIS data were simulated and no Stage 4 execution was started.

Final synchronization verification: `python -m pytest tests -p no:cacheprovider` collected and passed 34 tests in 0.92 seconds. The Streamlit smoke test rendered Permit Operations and Environmental Intelligence with zero application exceptions. The same host temporary-directory cleanup warning remains non-fatal and external to the application.

### Stage 4A deterministic permit-rule engine (engineering only)

Reused the existing `ExecutableRule`, `RuleGroup`, `SourceBinding`, controlled status/action enums, classification registry, and confirmation-gated rule factory. The factory now additionally requires a quote-verified condition before it can create an executable rule. Added the pure `permit.evaluator` core: calendar restriction evaluation in an explicit IANA timezone (including DST), instant thresholds, continuous duration-breach detection, stop/resume hysteresis, AND/OR three-valued group logic, and signature-safe decision-window merging. Rule results preserve source condition/page/quotation, evidence identifiers/timestamps/freshness, input values/units, actions, outcome and trace.

Authorization is strict: a rule must be AUTOMATIC, have a deciding binding, and receive matching PRIMARY_COMPLIANCE evidence. Local SPM/DO, AIS/GNSS and authority/manual rules return UNKNOWN with external-evidence or approval actions; predictive/supportive forecast evidence is never promoted. New scenarios use clearly identified synthetic unit-test evidence only; they are not Belfast evidence. Persisted human-review decisions and recovered conditions were not modified. Stage 4B UI integration was not started.

Verification: `python -m pytest tests -p no:cacheprovider` collected and passed 39 tests in 0.92 seconds. Streamlit smoke testing completed with zero application exceptions; the known host temporary-directory cleanup warning remains non-fatal.

### Stage 4B explainable decision-intelligence UI

Added the read-only Permit Decision Intelligence Streamlit tab. It loads the persisted Belfast aggregate and review-decision store without mutating either, shows document identity, review/evidence-readiness counts, all unresolved conditions, administrative obligations, source quotations/pages, evidence requirements and automation/source classifications. At implementation time Belfast has 59 aggregate conditions and zero persisted confirmations; therefore its confirmed executable-rule count is zero and no operational timeline is shown. The UI states that this is review-pending and not permission to operate.

Added an opt-in `ENGINE DEMONSTRATION — NOT AN OPERATIONAL AUTHORIZATION` panel. Its calendar, threshold, and stale-evidence cases are in-memory `TEST-FIXTURE-*` rules with synthetic values. They neither use Belfast forecasts nor modify review state. Status audit: Stage 4A emits YES, STOP, RESUME and UNKNOWN. NO and WARN are controlled vocabulary values but have no implemented/tested transition semantics, so the UI explicitly does not claim them as supported results. Stage 4B did not add contract intelligence or alter human review.

Verification: `python -m pytest tests -p no:cacheprovider` collected and passed 42 tests in 0.94 seconds. Streamlit `AppTest` rendered all three tabs with zero application exceptions; the host temporary-directory cleanup warning remains non-fatal.

### Stage 5 Marine Contract Weather Intelligence

Added a dedicated contract workflow and `ContractWeatherClause` model. Contract PDFs are parsed from uploaded bytes; weather-related source spans are retained with physical page, deterministic variable/threshold/unit detection where explicit, quote-verification status, consequence/risk wording, ambiguity and independent review state. There is also a clearly labelled demonstration contract, never presented as a project contract. The contract review store is namespaced by a contract-content hash and is fully separate from Belfast permit decisions.

Only quote-verified, human-confirmed contract thresholds with an explicit unit can enter forecast analysis. The analysis reuses the synchronized cached Belfast forecast to produce forecast-only workable/non-workable/unknown windows, coverage and limiting-variable provenance. Standby/downtime/risk/extension wording appears as potential exposure requiring human legal/commercial assessment. Outputs are permanently labelled NOT LEGAL ADVICE and do not determine liability, compensation, entitlement or permit compliance. Stage 6 historical analysis was not started.

Verification: `python -m pytest tests -p no:cacheprovider` collected and passed 46 tests in 0.95 seconds. Streamlit `AppTest` rendered all four tabs with zero application exceptions; the host temporary-directory cleanup warning remains non-fatal.

### Stage 6 Historical Seasonal Weather Risk Intelligence

Implemented a cache-first historical analysis path that is explicitly separate from forecasts and compliance. The selector returns `FORECAST_ANALYSIS` only when every required confirmed contract variable has complete forecast coverage over the requested period; it returns `HISTORICAL_SEASONAL_WEATHER_RISK` for partial/out-of-range forecast coverage and `REQUIRES_INPUT` when confirmed parameters are absent. It is deliberately all-or-nothing for a requested variable set: it does not fill a forecast gap with historical data.

Verified and retrieved bounded real Belfast equivalent-period data for 2024–2026 April 9–11. Copernicus Marine wave reanalysis is `MetO-NWS-WAV-RAN` / `NWSHELF_REANALYSIS_WAV_004_015` / version `202007`, variable `VHM0` in m at PT3H. The current and SST historical datasets are `cmems_mod_nws_phy-uv_my_7km-2D_PT1H-i` and `cmems_mod_nws_phy-sst_my_7km-2D_PT1H-i`, product `NWSHELF_MULTIYEAR_PHY_004_009`, version `202112`, with `uo`/`vo` in m s-1 and `thetao` in degrees_C at PT1H. Their tight Belfast-harbour subsets were masked; this successful source result is persisted as zero observations and never treated as a zero environmental value. Atmospheric history comes only from the Open-Meteo archive endpoint with `models=era5`, labelled `ERA5 via Open-Meteo historical archive`; it is never labelled or reused as the current ECMWF IFS forecast.

Each historical cache record preserves its original unit, UTC timestamp, source/dataset/product/version, requested range, grid selection result and retrieval timestamp. The demo has 24 native three-hourly wave values and 72 hourly ERA5 values per year. Analytical output includes mean, P50, P90, maximum, threshold exceedance and UNKNOWN-safe workable/weather-constrained windows; raw source series remain separate. The UI only enables its cached demo result for its exact pre-fetched April period. A different selected period is surfaced as `HISTORICAL DATA REQUIRED`, rather than silently reusing another period's cache.

The contract tab now shows **HISTORICAL SEASONAL WEATHER RISK — NOT A FORECAST** and retains contract confirmation/quote-verification gating. Historical output cannot decide downtime, compensation, entitlement, liability, permit compliance or operations. No local monitoring, AIS, laboratory, Copernicus SPM/DO, permit review, or executable-rule state was changed.

Verification: `tests/test_historical.py` passed 4 tests. Final full verification with `python -m pytest tests -p no:cacheprovider` collected 50 tests and passed all 50 in 0.94 seconds. A Streamlit `AppTest` loaded `app.py`, reported zero application exceptions, and found all four expected tabs. It still emitted the known non-fatal Windows temporary-directory cleanup `PermissionError` after the successful application run; that is host cleanup, not an app exception. See `docs/HISTORICAL_WEATHER_VERIFICATION.md` for the verified source and cache audit.

### Stage 7 Product hardening and demo readiness

Added an offline `pre_demo_verify.py` rehearsal that checks the permit aggregate, deterministic source-coverage gate, cached forecast/wave data, genuine historical source-slice audit, and labelled demonstration contract without network access or secrets. It correctly reports demo readiness as blocked by one `PARTIALLY_CAPTURED` coverage-inventory record rather than hiding it. Added a historical audit that validates cached VHM0/m samples, three-hour time indexing, selected GOOD grid provenance, ERA5 historical labeling/km/h units, 72-hour indexing, masked current/SST records, and source-file hashes. It does not claim an independent byte-level NetCDF verification because original source NetCDF files were not retained.

The Streamlit UI received restrained maritime visual polish and clearer product framing; all operational safety boundaries remain unchanged. Full test verification collected 51 tests and passed all 51 in 1.01 seconds. Streamlit `AppTest` reported zero application exceptions across all four tabs; the pre-existing host temporary cleanup warning remains non-fatal. See `docs/HACKATHON_DEMO_GUIDE.md` and `docs/FINAL_MVP_READINESS_REPORT.md`.

### Stage 7 final coverage reconciliation

Condition 20 was reconciled against original page-5 wording and aggregate/recovery records. Its previous partial status was stale: the separately retained `recovery-20_station` record quote-verifies and covers the station-capability sentence, while `20a`, `20c_stop`, `20d`, and `20e_stop` cover each threshold and stop behaviour. The coverage gate is now complete. This does not alter human-review, confirmation, evidence, or executable-rule gates. Pre-demo output now distinguishes engineering, data-cache, source-coverage, non-authorizing-demo and operational-compliance readiness; operational readiness remains false by design.

### AI-first universal upload integration (offline/mock implementation)

Added the `ai-first-candidates-v1` pipeline for newly uploaded documents. It
processes all readable physical pages in bounded batches with continuation
context, persists every successful batch before proceeding, resumes only
incomplete/failed work, preserves malformed candidates in a rejected queue,
and keeps exact source-level duplicates as an explicit disposition. It does
not require a recognised numbered Conditions heading; existing structural
detection remains coverage evidence. Quote verification produces
`SOURCE_VERIFIED`, `CONTEXT_UNRESOLVED`, or `SOURCE_NOT_FOUND`, all of which
remain human-review gated and non-executable.

The Permit Operations tab now loads document-scoped candidate aggregates as
well as historical recovered permits, shows source evidence/page/section and
page-level coverage gaps, and exposes an explicit local mocked-response mode
for sanitized browser tests. No API request was made, no historical document
cache/review was changed, and no candidate was automatically confirmed. Focused
offline regression tests cover unfamiliar headings, full-page processing,
malformed records, interruption/resume and no-repeat checkpoints.

### Hinkley AI-first mock-run diagnosis and live-adapter preparation

Audited document-run `2cf148c1…` against raw source SHA-256
`a9dec163f30956e1e4b99208df4b482a54df1d5db666598ef9f93fee2a1d19da`.
It is a local mock run, not a GPT run: all 103 retained IDs are `mock-p…`,
the stored batch outputs contain the local mock response format, and no request
or usage metadata exists. The configured model label is `gpt-4.1-mini`, but no
API inference was dispatched. The mock intentionally detects individual lines
containing modal/notification keywords, explaining the `UNCLASSIFIED` values,
fragments and zero candidates for S3.1/S3.2/S3.3 table pages.

Prepared (but did not invoke) the live adapter to send bounded rendered visual
context alongside text for table-bearing batches, ask for complete rather than
fragmentary obligation records with flexible categories, and persist request ID
and input/output token metadata in each checkpoint. Full regression: 73 passed.
## Final extraction acceptance audit (offline)

- Rebuilt the Hinkley source inventory from the authorized source PDF without any API call: 558 source records, including 327 geometry-backed table rows.
- Added conservative cross-page list continuation and explicit clause/table cross-reference linking; non-explicit continuation remains visibly ambiguous.
- Table-row exports now expose only values found in labelled source cells. Blank or merged applicability remains `UNRESOLVED_CONTEXT`.
- Reconciled the independent 293-row register without importing it into production candidates. Of the legacy 189 narrow-matcher misses: 61 correspond to existing candidates, 4 are source-only, and 124 are preserved unresolved table/context records.
- Added active-document keys to candidate and source dataframes to prevent stale rows after a permit switch; visible-browser testing found the issue.
- No review decision, candidate, raw model response, executable rule or environmental record was changed.

### Kilkeel live-upload source-inventory repair (offline rebuild)

Diagnosed the missing source-inventory records in the normal AI-first upload path. `run_document_pipeline` checkpointed and aggregated candidates, but did not call the existing deterministic `build_source_inventory` or `link_candidates` functions; only the separately rebuilt historical Hinkley run performed those steps. The repair makes source-inventory construction and source-to-candidate linking mandatory after batch aggregation. It is local and resumable: rerunning a completed document rebuilds the aggregate from saved batch outputs and never dispatches a model request.

The generic structural detector now also inventories simple numbered clauses only inside a detected Conditions section, while retaining hierarchical-clause support. It records Part 1 particulars, map/context headings, legal notes and external-document references as source context rather than promoting them to operative conditions. Page coverage now distinguishes `PROCESSED_WITH_OBLIGATIONS`, `PROCESSED_SOURCE_ONLY`, `PROCESSED_REVIEW_REQUIRED`, `FAILED`, and `NOT_PROCESSED`.

Offline rebuild of the Kilkeel ML2022019 Var-1 live run used its saved six-page PDF and two COMPLETE checkpoints with a transport that raises on any attempted request. Results: 27 unchanged retained candidates, 41 source records across pages 1–6, all numbered conditions 1–22 represented as `CLAUSE` records, and all 27 candidates linked to at least one source record. Candidate states remain 24 `SOURCE_VERIFIED`, 2 `SOURCE_NOT_FOUND`, and 1 `CONTEXT_UNRESOLVED`; no approval or executable rule was created. Pages 5 (legal/context material) and 6 (Appendix A map) are correctly `PROCESSED_SOURCE_ONLY`.

The aggregate-only `register_id` protects review records when a model restarts its candidate-ID sequence in a later batch; it leaves raw saved responses and original model IDs untouched. The Streamlit register displays both stable review ID and original model ID. Local browser verification loaded Kilkeel, displayed 27 review-gated records, 41 inventory records, source filters and clause records. CSV, JSON and Excel exports all contain 41 source records. Full regression: `85 passed`.

### Comprehensive intelligence pipeline and dashboard (offline implementation)

Added the schema-constrained `permitpulse.intelligence.v1` layer without
rebuilding the AI-first candidate extractor. It runs three resumable stages:
atomic source-backed requirements, operational relevance, and proposed
environmental data mapping. The local postprocessor retains the existing quote
verification result, marks all derived requirements unreviewed, keeps provider
availability `NOT_CHECKED`, and emits `NOT_EVALUATED` work windows. It cannot
confirm a rule or authorize work.

Each stage is Pydantic-validated and persisted in an intelligence namespace
keyed by raw document SHA-256, configured model label, intelligence contract,
and prompt versions. This prevents accidental reuse after a model or prompt
change while preserving all original candidate checkpoints and model responses.
The canonical output was validated offline against the supplied canonical and
Stage 1–3 JSON Schemas. The Permit Operations UI now renders its persisted,
document-scoped dashboard with Overview, Requirements, Environmental
Intelligence, Work Windows, and Audit & Exports, including three local pie
charts, two local bar charts, source drilldowns, filters, stage progress and
JSON/CSV/Excel exports. No OpenAI request was made during implementation or
validation.

### Live three-stage acceptance preflight hardening (offline)

Added an explicit fresh analysis-run ID for the narrow live acceptance profile.
It changes only the new run namespace, is retained in the Streamlit URL across
refreshes, and leaves ordinary deterministic cache reuse and all historical
runs untouched. The profile refuses any document whose generic bounded-batch
plan is not exactly two candidate batches.

Added a persistent acceptance dispatch ledger: five total requests, $0.15
conservative reservation ceiling, configured-model pricing allowlist, explicit
input/output token ceilings, no SDK retries, and no automatic retry after an
uncertain dispatch. Each completed response records request ID, actual tokens
and estimated cost; the canonical stage ledger and Audit view expose those
facts. This guard has only been exercised using injected offline transports.

Stage 1 prompt/version was strengthened to require source-linked authority
classification and explicit unresolved condition IDs. A deterministic
condition-accountability artifact makes every numbered clause visible even if
the model returns no atomic requirement. Focused tests passed 22 tests; full
offline suite passed 93 tests. No live OpenAI call was made.

### 2026-10-12 — Focused environmental evidence sampling and deduplication

Added source-backed explicit metric depth handling, outward provider-timestep UTC
queries with unchanged actual-bracketing/freshness/coastal gates, documented ECMWF
HRES preference and conservative model-specific nearest-cell distance screening,
and per-fetch shared evidence with independent threshold evaluations. Preserved
FNU/NTU incompatibility, existing oxygen conversion, failed requirements, all
original analyses/licences, extraction prompts and human review gates. A narrowly
matched non-equivalence caveat no longer misroutes modelled O2 to local sensors;
actual in-situ obligations still route externally. Satellite observations are not
mislabelled as model forecasts for unspecified evidence requirements.

Created a separate clearly labelled synthetic fixture/PDF with >25 FNU, <6 mg/L
at 1 m below sea surface, waves, wind, gust, currents and two SST checks. No real
permit or historical unofficial upload was edited. Offline SST tests prove one
fetch, two checks and one card; source entries remain distinct. Depth round-trip
test covers one mocked extraction, persistence, API and environmental routing.
Final full backend: 253 passed (one existing warning); frontend: 44 passed.
Production build passed; PDF visually checked. No live provider/OpenAI calls.
Restart of FastAPI PID 39260 / port 8531 and browser refresh are required before
manual live acceptance; no automatic restart or fetch was performed.
Full rationale, changed files, provider limitations and restart instructions:
`docs/ENVIRONMENTAL_EVIDENCE_IMPROVEMENTS.md`.

## 2026-10-12 — Minimal environmental qualification and screening correction

Separated retrieval, temporal coverage, configured distance, applicability and
literal threshold screening. Coastal review alone no longer suppresses valid
numeric screening; real source/unit/depth/time/distance/value failures still
block. Kept coastal warnings, all approval gates and legacy enum compatibility.
Added narrow verified-source SST range recovery with explicit derivation audit,
two checks sharing one retrieval/card, and safe Celsius spelling aliases.
ECMWF explicitly requests nearest cells, persists that policy and isolates old
default-selection caches. Existing HRES 9/sqrt(2) bound remains unchanged and is
labelled approximate, not exact O1280 geometry. UI shows actual blockers and
separates displayed-point from any-point series screening.

Saved live evidence was evaluated read-only at its retrieval timestamp: marine
temporal/distance checks pass; SST checks both false; current trigger false;
wave displayed trigger false but later points trigger; saved wind remains
spatially insufficient. No new provider or AI requests and no historical
artifacts/reviews modified. Full backend 273 passed (one existing warning),
frontend 49 passed; production build passed (existing bundle advisory).
No automatic restart: restart FastAPI/Uvicorn on 8531 and hard-refresh before
manual live fetch. Full decision tree, files and limitations are recorded in
`docs/ENVIRONMENTAL_QUALIFICATION_FIXES.md`.

## 2026-10-12 — Oxygen-only end-to-end investigation

Latest LIVE run 63e6d528640740eea17c71d3ed7dcf37 uses a nine-page unofficial
test PDF whose synthetic conditions 23–31 omit oxygen. Confirmed absence in
every PDF page's text, parsed input, raw AI environmental requirements and
normalized mapping, plus visual inspection of physical page 8. The separate
standalone synthetic fixture contains T2 oxygen; it was not this uploaded PDF.
No production fix or invented requirement is appropriate. Historical artifacts
and UI were left unchanged. Added nine oxygen-focused offline tests proving
source-backed extraction/persistence/API, 1 m depth, configured o2 dataset,
3-D daily Toolbox selection, existing unit conversion, coastal/supportive
qualification, absent-source safety and visible provider failure diagnostics.
Full backend suite: 282 passed, one existing Starlette/httpx warning. No live
requests or executable rules. No restart needed; use oxygen-bearing source in
a future separately authorized analysis. Full trace and expected mock API shape:
`docs/OXYGEN_PATH_DIAGNOSIS.md`.

## 2026-10-12 — Focused turbidity manual FNU and air-temperature mapping

Added separate strictly finite positive user-supplied FNU input for original
NTU turbidity only, retaining source NTU values and separate screening audit
records. No NTU/FNU conversion or automatic fetch. Explicit Fetch applies the
manual threshold and reuses fresh cached evidence. Updated only related UI.

Saved condition 29 was source-verified but used unsupported alias
air_temperature_2m with two limits only in text. Missing catalog alias caused
UNAVAILABLE routing and pre-dispatch skip, not provider or frontend loss.
Added aliases to existing air_temperature -> ECMWF temperature_2m mapping;
reused narrow verified-source two-check temperature recovery without rewriting
raw output. One retrieval/card, two checks; informational and safety gates stay.
Focused tests 21 passed; final full backend 303 passed (one existing warning),
frontend 55 passed; production build passed (existing bundle advisory).
No live external requests, historical edits, rules or approvals. Backend restart
on 8531 plus browser hard refresh needed; bundle already rebuilt. Full trace,
manual provenance and limitations: `docs/TURBIDITY_AIR_TEMPERATURE_FIXES.md`.
Environmental P0 completion pass: added exact dissolved-oxygen aliases, explicit requested/selected depth and conservative vertical-level tolerance metadata, raw-unit/conversion provenance, shared current-vector projection for eastward U/northward V/speed/direction, explicit visibility routing with metre-unit refusal, hourly precipitation accumulation semantics, wave-direction provider-convention metadata, and the backend/frontend capability catalogue. Sea-surface height remains explicitly unavailable because no verified dataset/variable/datum mapping exists in the local catalogue. No live provider or OpenAI calls were made; historical permit/review data was not changed.

Offline verification note: changed Python modules pass AST parsing and routing/capability smoke checks. Full pytest collection was blocked in the available interpreter because project dependencies (`jsonschema`, `numpy`, and related packages) are not installed; frontend Vitest/build were blocked by OneDrive `EPERM` realpath restrictions. No provider or OpenAI request was attempted.

## 2026-10-12 — Current-speed historical-mode false positive

Diagnosed the surface-current result that had successful Copernicus retrieval,
covered UTC period and acceptable grid distance but displayed `Historical evidence
required`. The persisted request for condition 29 was labelled `reanalysis` while
the verified product returned `MODEL_FORECAST`; `compatible_points()` therefore
added that exact failure at the historical compatibility branch. The requested
interval was future/current at evidence retrieval time, so this was a
provider-mode/temporal classification mismatch, not a retrieval, timezone or
spatial failure.

The compatibility check now applies the historical safeguard only when the whole
requested interval ended before the evidence retrieval timestamp. It preserves
`Historical evidence required` for genuinely historical intervals, keeps all
timestamps timezone-aware UTC, and allows future/current forecast points to reach
threshold screening. Added focused offline regression coverage for current/future
forecast-labelled reanalysis metadata, genuine historical rejection and naive
evaluation-clock rejection. No live provider/OpenAI request or permit/review data
change was made.

## 2026-10-12 — P0 output headroom correction

The v1.5 FULL P0 permit response reached the configured 12,000-token ceiling
and OpenAI returned `finish_reason=length`; parsing, source verification and the
environmental completeness audit correctly did not run. Using the existing
gpt-4.1-mini pricing ($0.40/M input and $1.60/M output), a 7,754-token input plus
a 16,000-token output reservation is approximately $0.0287016, below the
existing $0.15 hard cap. Raised only the single permit-analysis output ceiling
to 16,000 via `OUTPUT_TOKEN_CEILING`; the single request, strict parsing,
fail-stop and budget guard remain unchanged. No live calls, batching, retries,
provider changes or semantic extraction changes were made.

## 2026-10-12 — Environmental source-candidate semantic boundary

Refined deterministic environmental source discovery from an any-keyword rule
to a measurement/evidence subject plus evidence-obligation semantics. AIS/GNSS,
provider names, forecast/reanalysis, fetch configuration and units are no longer
sufficient by themselves. Workflow-only fetch location/time clauses and
evidence reuse/deduplication clauses are excluded, while derived measurements
such as current direction remain eligible when explicitly recorded as evidence.
The FULL P0 fixture now yields exactly conditions 24–41 (18 candidates), excluding
11, 12, 23 and 42. Added regression coverage for thresholdless direction and
availability requirements, manual NTU/FNU handling, sampling/survey evidence,
provider-only wording and process-only clauses. No prompt, model schema,
normalization, provider, UI, output ceiling or completeness behavior changed.

## 2026-10-12 — P0 environmental extraction completeness gate

Added a deterministic, source-backed completeness audit to the existing single
OpenAI extraction response. The prompt now requires one environmental record for
every explicit environmental source condition, including informational,
direction/vector, derived, unsupported/unavailable, manual-evidence and
thresholdless conditions, while requiring the physical page containing each
quotation. Local preprocessing identifies numbered environmental source clauses
from the already supplied PDF text; it does not invent variables, thresholds,
providers or evidence values. Missing model representation is persisted as an
`EXTRACTION_INCOMPLETE` diagnostic with condition identity, exact source text,
physical page and source span. Representation completeness is kept separate from
quote/source verification, so a wrong-page citation remains a verification
failure rather than being silently repaired. Added the full P0 18-condition
fixture tests for omission, unsupported/manual conditions, diagnostic shape and
duplicate accounting. No live calls, provider changes, alias changes, UI changes,
or historical artifacts were made.
