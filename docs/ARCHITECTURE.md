# PermitPulse Technical Architecture

This document captures the approved Stage 0 architecture from `PermitPulse Technical Blueprint` (8 October 2026).

## Product and scope

PermitPulse converts static marine permits and contracts into evidence-backed environmental decision intelligence. The MVP comprises Permit Operations and Marine Contract Weather Intelligence. The LLM may interpret documents; deterministic Python will make decisions only from human-confirmed rules and verified evidence.

Frozen non-goals include local sensor, AIS/GNSS and laboratory integrations, routing/navigation, production infrastructure, authentication, payments, and machine-learning training. Missing deciding evidence must produce `UNKNOWN`, never `PASS`.

## Layering

Dependencies flow in one direction:

`Streamlit UI -> services -> deterministic core -> adapters -> cache/config`

The core must remain pure: no network, I/O, or clock access. Adapters normalise external data. Local sensors, AIS/GNSS and laboratory data remain classifications only in this MVP. Copernicus Marine is the primary ocean-data source; weather is complementary.

## Foundation implemented in Stage 0

- Streamlit shell with the two product tabs.
- YAML settings loader validated with Pydantic.
- Controlled enums and Pydantic data models, including timezone-aware environmental observations.
- JSON environmental-capability registry stub and tested unit conversions.
- Test foundation using pytest.

## Deferred architecture

Stages 1–7 will add document extraction and quote verification; human confirmation; deterministic evaluation; Copernicus and weather adapters; permit windows; contract forecast and historical seasonal risk; offline cache and hardening. Dataset identifiers are placeholders until live verification; no data provider is invoked in Stage 0.

## Environmental intelligence (Stages 2B + 3)

The Environmental Intelligence tab is a cache-first presentation layer above the Copernicus and Open-Meteo adapters. The Open-Meteo adapter explicitly requests `ecmwf_ifs025`; it labels its data `ECMWF IFS via Open-Meteo` only for that selected model and stores the returned units, UTC timestamps, endpoint, model and retrieval time. The marine cache retains its official Copernicus dataset/product provenance, source units and coastal grid decision.

`src/environment/analytics.py` is pure descriptive logic: summaries, rainfall totals, exceedance samples and advisory-only windows. It requires every requested input value to exist before emitting a window. It cannot produce legal compliance outputs. The UI joins time series only when they actually align; otherwise it exposes the coverage gap. Permit-to-evidence rendering reads the extracted source, review state and required evidence classification without changing it. Copernicus SPM/DO, weather forecasts, and unconfirmed conditions remain non-deciding.

`src/environment/synchronization.py` creates a shared UTC hourly grid without interpolation. It retains raw source values separately: 15-minute current speed is reduced using the hourly maximum (conservative for an upper advisory threshold), while already-hourly sources are summarized by their real hourly values. The evaluator uses deterministic AND logic. A stale/unrepresentative series or an absent sample produces `UNKNOWN`; only fully evidenced, below-threshold periods may be labelled advisory `WORKABLE`. Location-aware Copernicus retrieval validates latitude/longitude, uses a small bounding area, records nearest-valid-cell distance, and cache-isolates by dataset, source version, coordinates and valid time range.

## Stage 4A deterministic rule core

Stage 4A is a pure evaluator in `src/permit/evaluator.py`, deliberately separate from environmental advisory analytics and the Streamlit UI. The rule factory remains the only route to an `ExecutableRule`; it now requires both an explicit review confirmation and a verified quotation. The evaluator supports calendar restrictions with IANA time-zone conversion/DST handling, instant numeric thresholds, continuous duration breaches, stop/resume state hysteresis, and three-valued AND/OR groups. It returns PASS/FAIL/UNKNOWN alongside YES/STOP/RESUME/UNKNOWN operational states and separately records actions, source clause/page, evidence identity/timestamp, freshness, values, units and trace.

Automatic evaluation is permitted only for an AUTOMATIC rule with a legally deciding source binding and authorized PRIMARY_COMPLIANCE evidence. Local sensor, AIS/GNSS, laboratory and authority inputs remain external/manual gates. Missing, stale, non-primary, or predictive/supportive evidence is UNKNOWN. Stage 4A is test-fixture-only until Stage 1B review completes; it does not evaluate Belfast forecasts as legal evidence.

## Stage 4B explainability UI

The Permit Decision Intelligence tab is a read-only adapter over persisted aggregate/review state. It derives readiness counts, shows all unresolved obligations, and displays source/page/evidence/provenance without mutating condition records or decisions. Actual Belfast evaluation is withheld unless a condition is both confirmed and quote-verified, has an eligible rule, and provides authorized deciding evidence. An isolated demonstration constructs only in-memory synthetic fixture rules. It is visually labelled as non-operational and cannot write to the Belfast review store.

## Stages 5–6 contract weather intelligence and historical risk

Contract clauses use a separate `ContractWeatherClause` model and contract-hash cache namespace. Extraction is deterministic for recognisable weather wording and preserves source quotation/page; ambiguous or unitless wording remains review-required. Contract reviews are persisted separately from permit reviews. Forecast analysis includes only quote-verified, contract-confirmed supported thresholds and reuses the synchronized forecast engine to produce forecast windows, data coverage and limiting variables.

The Stage 6 historical path is intentionally separate from forecasts. Mode selection requires complete forecast coverage for every requested variable; partial coverage selects `HISTORICAL_SEASONAL_WEATHER_RISK`, while missing confirmed parameters selects `REQUIRES_INPUT`. `src/historical` retrieves/caches verified Copernicus reanalysis and Open-Meteo archive ERA5 data, computes descriptive mean/P50/P90/max, threshold exceedance and UNKNOWN-safe windows for equivalent calendar periods, and retains coverage/provenance per source/year. No source values are interpolated or extrapolated. The cached Belfast demo is date-scoped: a different requested interval is unavailable until matching historical data is fetched. Historical outputs are labelled **NOT A FORECAST** and cannot decide contractual liability, payment, entitlement or compliance.

## Core safeguards

- Unconfirmed extraction cannot create an executable rule.
- Provenance remains attached to observations, decisions, and evidence.
- Supportive/predictive evidence cannot silently become compliance evidence.
- Historical output is labelled historical seasonal weather risk, not a prediction.
- Stage 7's offline pre-demo verifier checks cache presence and source coverage without attempting network recovery; a missing or partial artifact remains visible and fails readiness.

## Comprehensive intelligence pipeline

`src/intelligence` layers a three-stage, schema-constrained analysis on top of
the existing AI-first extractor. It does not replace source inventory,
candidate checkpoints, quote verification, recovery queues, review decisions,
or rule gating. Stage 1 emits atomic source-backed requirements; Stage 2 emits
operational relevance; Stage 3 emits only proposed environmental mappings.
Each response is Pydantic-validated, persisted immediately in a versioned
document/model/prompt cache namespace, and assembled into the canonical
`permitpulse.intelligence.v1` artifact. The deterministic local postprocessor
attaches quote-verification facts from original extraction evidence; it never
promotes an unreviewed requirement, claims provider availability, or evaluates
a work window.

The Permit Operations dashboard consumes only this persisted artifact and has
five document-scoped views: Overview, Requirements, Environmental Intelligence,
Work Windows, and Audit & Exports. Its source drilldowns and exports preserve
the source IDs/pages and stage ledger. It is read-only with respect to approval
and executable-rule state; existing document-scoped review controls remain the
only path to confirmation.
