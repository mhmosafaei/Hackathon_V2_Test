# Simple AI extraction + React dashboard

## Environmental Intelligence (2026-10-12)

The existing single strict extraction now returns environmental requirements.
A separate React tab routes them locally and fetches evidence only on explicit
user action. Permit Intelligence retains exactly four charts and its existing
review safeguards. Offline verification: 192 backend tests and 20 frontend
tests passed; mock browser upload/fetch/reset/mobile checks passed. No live calls.
See [full delivery report and live-test instructions](SIMPLE_ENVIRONMENTAL_INTELLIGENCE.md)
for supported variables, explicit unsupported priorities and coastal-data gating.

## Geofence enhancement (2026-10-12)

The same single extraction request now also returns `geofences[]`: name,
description, supported type, nullable source-written coordinates/boundary,
restriction and physical source pages, with exact quotation spans. The updated
prompt prohibits converting mere place mentions into boundaries or inferring
coordinates. No maps are geocoded and no boundary is enforced automatically.

An At a Glance GEOFENCE card appears only for nonempty results. Multiple items
show a count and the leading restriction in the model's significance ordering.
Coordinate lists stay in expandable details, alongside all source pages and
quotations. Unverified page/boundary evidence remains marked for review. The
table, four charts, clean start, no retries and approval safeguards are unchanged.

Latest offline suite: **144 backend tests passed (8.72s)** and **12 frontend
tests passed (60.46s total runner duration)**. Six dedicated frontend cases cover
presence, absence/legacy output, multiple items, coordinate suppression, detailed
source pages and New Analysis reset. Four new backend cases cover contract/source
preservation, invalid type/page conflicts, location-only absence and unsupported
boundary review gating. Mocked browser inspection verified the expanded card
and mobile layout. No live OpenAI requests occurred. Historical results were
preserved without adding geofences retroactively.

## Architecture and scope

Primary entry point: `python -m src.permit.simple_api`. The loopback FastAPI
server serves the compiled React/Vite frontend and its same-origin API. React
19.1, Recharts 3.10.1 and Lucide icons are bundled locally, not fetched from CDNs.
This is an application-specific upload/results composition, not a warehouse or
published Data App. The dashboard skill informed local chart calculations,
source visibility, null handling and rendered responsive checks.

`POST /api/analyze` accepts PDF bytes, filename and the current boot identity.
It reuses the existing Python PDF parser, with physical `--- PAGE n ---` markers.
The only live dispatch is `chat.completions.create` with native strict JSON
schema. There is no candidate extractor, deduplication, Stage 1/2/3, rule engine
or automatic recovery pass in this path. The old modules remain unchanged.

The existing global ceiling remains 5 requests / $0.15 per ledger; this route
dispatches once. The response ceiling is 12,000 tokens, timeout 120 seconds,
SDK retries zero, no temperature. Inputs over 60,000 prompt/text characters are
rejected locally, not truncated or silently divided. The conservative input
ceiling is 40,000 tokens including serialized schema. At configured gpt-4.1-mini
ledger pricing, the ceiling reservation is at most $0.0352; actual live usage
is **not verified**. Unknown model pricing refuses dispatch. No model is
hard-coded into the request; `OPENAI_MODEL` controls it.

## Exact prompt and schema

- [Exact extraction prompt](../prompts/simple_permit_v1.txt)
- [Complete strict response schema](SIMPLE_PERMIT_RESPONSE.schema.json)
- Runtime definitions: `PROMPT` and `response_schema()` in
  `src/permit/simple_analysis.py`. Published copies were generated from these
  definitions during implementation.

The schema contains `summary`, `conditions[]` and `key_limits[]`. Every object
disallows extra properties and explicitly requires its declared fields. Absent
summary facts, limits and timing are nullable. Phases/categories use controlled
lists; values and deadlines stay strings. Each record includes physical-page
source quotations; cross-page conditions can use multiple spans.

Finish reason and refusal are checked before parsing. Incomplete, refused,
empty, invalid JSON and schema-invalid output fails safely without automatic
repair or retry. The original SDK response is persisted before parsing. Safe
metadata and the ledger remain available offline; secrets and request headers
are never written. User-facing errors contain no stack traces or SDK detail.

## State and safety

- Application initialization: `currentAnalysis = null`; no local/session-storage
  analysis restoration and no history API.
- New Analysis clears file, result, filters (through unmount), errors and active
  state without deleting artifacts. It is disabled while a request is running.
- Every backend start creates a new boot identity. Existing browsers poll it;
  a changed identity clears the active result. Old-session dispatch is rejected.
- No analysis executes on mount, health polling, reload or restart.
- New artifacts: `cache/simple_analysis/<raw-pdf-sha256>/<unique-run-id>/`.
  Original PDF, page-marked input, schema, response, manifest, source inventory
  and final result are retained. Existing document namespaces are never written.
- All conditions are UNREVIEWED and non-executable. There are no confirm,
  compliance-decision, rule-creation or WORK-authorization controls in this UI.
- Source quotation checks prove text presence only, not correct interpretation.
  Source-unverified records remain visible with warnings and exact evidence.
- A lightweight existing source inventory detects missing numbered identifiers
  where reliable. It does not establish full legal/obligation coverage or invent
  records to fill gaps. No environmental availability is inferred.

## Dashboard

Clean startup: branded header, disabled Analyze until a PDF is selected,
upload card, and “No permit analyzed yet. Upload a permit to begin.”

Result: six summary cards, Key Permit Limits, searchable/phase-filterable table
with exact-source expandable evidence, then exactly four charts:

1. Conditions by Phase — bar.
2. Conditions by Requirement Type — bar.
3. Permit Conditions by Phase — pie/donut.
4. Conditions with Explicit Limits — pie/donut.

Charts always describe all returned conditions, independent of the explicitly
table-scoped search/phase filter. Totals derive from records in React; no chart
data is requested from AI. Explicit-limit membership means a nonempty limit or
deadline field. This is not an independently verified legal-limit count.

No raw JSON is displayed. Null facts show “Not stated”. No environment or
contract modules were redesigned. No history browser, accounts or database was
added. Historical Streamlit remains accessible separately; it is not the new
React startup workflow.

## Offline verification

Backend: **140 passed, 0 failed, 8.61s**. Ten new simple-path tests cover one
mocked SDK dispatch, exact page markers, strict schema, finish/refusal/JSON
handling, original-response persistence, no retry, budgets, safety, duplicate
number rejection, missing-source warnings, oversized input rejection, restart
identity, cross-origin rejection and historical preservation. The original 130
regression tests also pass. One upstream Starlette/httpx deprecation warning.

Frontend: **6 passed, 0 failed, 15.00s runner duration**. Tested clean startup
despite existing browser storage, upload/result/reset, all 22 rows, exactly four
charts, chart totals, search/filter, loading/error with no retry and server boot
identity clearing. jsdom tests mock responsive measurement only; real chart
rendering was checked separately in the browser.

Production build passed. Advisory: JS bundle 592.59kB / 177.06kB gzip exceeds
Vite's default 500kB chunk warning; no build failure or broken chart resulted.

Actual browser: compiled app on http://127.0.0.1:8530/ with `--mock` only.
Uploaded the generated synthetic six-page PDF through the real chooser and
clicked Analyze. Verified 22 rows, four real SVG charts, phase filter (6 prior,
then all 22), source drill-down, final page-6 reference, New Analysis reset,
invalid PDF's generic error/Try Again, refresh and automatic clearing after an
actual backend restart. No browser error logs. Desktop 1440 and 1024, mobile
390: no page overflow or clipped chart titles; mobile table scrolls internally.

Screenshots: `tmp/permitpulse-react-empty.jpg` and
`tmp/permitpulse-react-result.jpg`. Test PDF:
`tmp/synthetic-marine-permit.pdf`, generated with
`python scripts/create_simple_demo_pdf.py`. Data is explicitly synthetic, not
an extraction or evaluation of real Kilkeel requirements.

## Files created / changed

New: `src/permit/simple_analysis.py`, `simple_api.py`, `simple_fixture.py`;
`frontend/package.json`, `package-lock.json`, `index.html`, `vite.config.js`,
`src/main.jsx`, `src/App.jsx`, `src/styles.css`, `src/test-setup.js`,
`src/App.test.jsx`; `tests/test_simple_permit.py`;
`scripts/create_simple_demo_pdf.py`; `prompts/simple_permit_v1.txt`;
`docs/SIMPLE_PERMIT_RESPONSE.schema.json`, this report.

Updated: `requirements.txt`, `.gitignore`, `README.md`,
`docs/IMPLEMENTATION_JOURNAL.md`. Generated assets/screenshots/logs and mocked
run artifacts are under frontend/dist, tmp and cache/simple_analysis only.

## ONE live Kilkeel test — only after separate authorization

1. Build using `cd frontend; npm ci; npm run build; cd ..`.
2. Ensure the existing `.env` configures `OPENAI_MODEL=gpt-4.1-mini` and the
   existing API key. Do not print or place the key in frontend files.
3. Leave the offline mock preview alone and start one live server on a separate
   unused loopback port: `python -m src.permit.simple_api --port 8531`.
4. Open http://127.0.0.1:8531/. Confirm the dashboard is empty and there is **no
   offline/mock banner**.
5. Select the intended six-page Kilkeel ML2022019 Var-1 PDF. Click Analyze once.
6. If it fails, stop; do not click Try Again during the one-run acceptance test.
   Inspect the saved safe manifest/response/ledger offline.
7. If successful, compare all returned numbered conditions and exceptions
   against the original 22 source conditions. Check quotes, pages, summary,
   quantities/deadlines and all four chart totals. Do not infer completeness
   merely from the condition count or verified quotations.
8. Inspect `cache/simple_analysis/<sha>/<run>/analysis.json`, `response.json`,
   `manifest.json`, `dispatch_ledger.json`. Expect exactly one dispatch and no
   intelligence-stage dispatches. No approvals/rules should exist.
9. Click New Analysis; verify empty. Restart the live server and verify empty
   again. Saved audit files must remain unchanged.

No live request was performed during implementation. Large/scanned PDFs,
image-only maps or complex table semantics are not solved by this small-document
text-only route; it must not silently claim those are completely interpreted.
Human review and real live extraction quality remain unverified.
