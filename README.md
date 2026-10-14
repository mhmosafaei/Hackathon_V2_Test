# PermitPulse

## Primary hackathon application: React

The primary UI is now **Upload → Analyze → Results**, with a clean React dashboard
and a single strict-schema OpenAI request for a small, text-readable PDF. It does
not use candidate batches or the experimental intelligence stages. Startup and
New Analysis begin empty; historical artifacts are never automatically restored
or deleted. All results remain unreviewed and non-authorizing.

```powershell
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
python -m src.permit.simple_api --mock --port 8530
```

Open http://127.0.0.1:8530/. `--mock` is an explicitly labelled synthetic preview
and makes **no OpenAI calls**. Create the test PDF with
`python scripts/create_simple_demo_pdf.py`.

For a separately authorized live test, start without `--mock`, with the existing
environment-driven `OPENAI_API_KEY` and `OPENAI_MODEL`. No credentials belong in
the React frontend. See [implementation, verification and live-test steps](docs/SIMPLE_REACT_DASHBOARD.md).

The Simple React application also provides **Environmental Intelligence**.
The same single extraction identifies source-backed environmental requirements;
local code routes them, and only **Fetch Environmental Data** requests evidence
for an explicit location and UTC period. New Analysis clears both tabs. The
mock server uses clearly labelled synthetic provider responses. See
[supported variables, verification, limitations and controlled live-test steps](docs/SIMPLE_ENVIRONMENTAL_INTELLIGENCE.md).

## Legacy Streamlit application

The existing Streamlit, candidate-extraction, environmental and contract modules
remain intact. Their historical runs and human review decisions are unchanged.
The instructions below describe that legacy application, not the new React UI.

PermitPulse turns marine permits and contracts into evidence-backed environmental decision intelligence. The MVP has two modules: Permit Operations and Marine Contract Weather Intelligence.

## Stage 0 status

The foundation is implemented. It provides a validated settings loader, shared Pydantic models, a source-registry stub, and a two-tab Streamlit shell. Document extraction, live data retrieval, deterministic evaluation, and contract analysis are deliberately deferred to later blueprint stages.

## Run

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Run tests: `python -m pytest`
4. Start the shell: `streamlit run app.py`

Credentials are not required for Stage 0. Add secrets only to `.env`, never to source control.

## Demo readiness and offline rehearsal

Run `python scripts/pre_demo_verify.py` before a demo. It performs no network calls and checks the cached Belfast permit, coverage gate, forecast/wave cache, historical source-slice integrity, and labelled contract artifact. A failed coverage gate is intentional safety information, not permission to proceed. See `docs/HACKATHON_DEMO_GUIDE.md` and `docs/FINAL_MVP_READINESS_REPORT.md`.

## Multi-document review

The Permit Operations tab has an explicit Active permit selector. Completed document runs are isolated by document SHA256 and processing version, retain their own coverage audit and review decisions, and never inherit Belfast environmental evidence. A non-Belfast permit shows `DATA REQUIRED` until its operating coordinates and matching environmental cache are confirmed.

## Stage 1A workflow

Upload a permit PDF in Permit Operations, select Analyze, then review consolidated requirements. Processing is cache-isolated by document hash, model and prompt version; successful page checkpoints are reusable after interruption. Extraction, source verification, coverage assessment and human review are separate steps. No condition is executable until a reviewer confirms it.

## AI-first universal upload workflow

New uploads use document-wide candidate discovery: every readable PDF page is
processed in bounded, resumable batches with neighbouring continuation context.
The workflow supports permits and contracts without requiring a conventional
numbered-conditions heading. It records candidates, malformed responses,
source-quote verification and page-level coverage separately; processed pages
are never presented as proof of legal completeness. In Permit Operations, the
explicit **Use local mocked AI response** control can exercise the same path
with a sanitized fixture without sending text to OpenAI. See
`docs/AI_FIRST_EXTRACTION.md`.

## Comprehensive Intelligence analysis (offline-capable)

After the existing evidence-preserving candidate workflow finishes, PermitPulse
can assemble a resumable three-stage intelligence analysis: source-backed
atomic requirements, operational relevance, and proposed environmental evidence
mapping. The resulting document-scoped canonical artifact conforms to
`permitpulse.intelligence.v1` and drives the **Permit Intelligence · Document
Analysis** panel in Permit Operations. It provides Overview, Requirements,
Environmental Intelligence, Work Windows, and Audit & Exports views.

The three stage checkpoints are isolated by raw document SHA-256, configured
model label, intelligence-contract version, and all three prompt versions.
Mocked local transport is used only when the explicit sanitized-test option is
selected. A live analysis requires separate authorization and configured
credentials. In either mode, derived records remain unreviewed, data
feasibility stays unverified until a deterministic adapter establishes it, and
work windows are **NOT_EVALUATED** until human review and deciding evidence are
complete. See `docs/COMPREHENSIVE_INTELLIGENCE_ANALYSIS.md`.

For an explicitly authorized acceptance exercise, select **Fresh capped live
acceptance run** after uploading a PDF. The UI persists a stable run ID in the
URL, uses a separate run namespace, and applies a five-request, $0.15
reservation cap. This profile requires exactly two candidate batches followed
by Stages 1–3, has no automatic retries, and refuses an interrupted dispatch
rather than silently repeating it.

## Copernicus Stage 2A

Copernicus adapters are cache-safe and preserve source provenance. The five Belfast candidate datasets were catalogue-checked and live-verified with small requests on 2026-10-09; the results, coastal limitations, and access provenance are in `docs/COPERNICUS_VERIFICATION_REPORT.md`. Run `python scripts/prefetch_copernicus_belfast.py` only with credentials in `.env`; it creates small independently cached records under `cache/copernicus/`. SPM and dissolved oxygen remain supportive only and do not replace required local monitoring.

## Unified Environmental Intelligence (Stages 2B + 3)

The **Environmental Intelligence** tab combines the cached Belfast marine scenario with an explicitly selected `ecmwf_ifs025` Open-Meteo forecast. Run `python scripts/prefetch_open_meteo_belfast.py` to fetch a bounded three-day forecast into `cache/weather/`; it is labelled **ECMWF IFS via Open-Meteo** only when that model is requested and returned. The dashboard works offline whenever those caches exist, shows source units, freshness, grid representativeness and missing-data states, and provides advisory-only analytics. It does not make permit compliance decisions.

To refresh the matching small marine forecast subset for the cached Belfast weather range, run `python scripts/synchronize_belfast_forecasts.py`. It cache-isolates waves, currents and SST by dataset/source version, coordinates and valid time. The dashboard aligns raw data on a shared hourly UTC grid: 15-minute current speed is aggregated conservatively by hourly maximum; source-hourly values are not interpolated. Missing, stale or insufficiently representative required evidence becomes `UNKNOWN`, never workable.

## Permit Decision Intelligence (Stage 4B)

The **Permit Decision Intelligence** tab provides a read-only readiness view for Belfast: review state, quote status, required deciding source, evidence gaps, administrative obligations, source quotation/page, and rule-execution eligibility. It never changes a review decision and never treats an empty timeline as permission to operate. Its opt-in engine demonstration uses isolated `TEST-FIXTURE` rules and synthetic values only; it is not Belfast evidence or an operational authorization. See `docs/STAGE_4_VERIFICATION.md`.

## Marine Contract Weather Intelligence (Stages 5–6)

The **Marine Contract Weather Intelligence** tab accepts contract PDFs or the labelled demonstration contract. It discovers weather-related clauses deterministically, preserves exact source text/page, quote-verifies each record, and requires contract-specific human confirmation before analysis. If every required variable covers the requested period, it uses forecast analysis; otherwise it selects **HISTORICAL SEASONAL WEATHER RISK — NOT A FORECAST**. Historical output is descriptive only and never determines downtime compensation, liability, extension-of-time entitlement, or permit compliance.

The Belfast offline demonstration caches three genuine equivalent April periods (2024–2026): Copernicus Marine North-West Shelf wave reanalysis and Open-Meteo's ERA5 historical archive. Current and SST subsets are retained as masked/no-observation results rather than substituted. The historical panel refuses to reuse that April cache for another date range and labels uncached periods as requiring historical data. See `docs/HISTORICAL_WEATHER_VERIFICATION.md`.
