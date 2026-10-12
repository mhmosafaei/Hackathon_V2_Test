# Fresh Kilkeel acceptance preflight — 2026-10-12

Result: READY_FOR_FRESH_LIVE_ACCEPTANCE (offline preflight only).
No model requests were made, and no production analysis or dispatch ledger was created.

## Runtime and source

- Running Streamlit PID: 28408; interpreter: `C:\Users\nedan\AppData\Local\Python\pythoncore-3.14-64\python.exe`.
- Project: `C:\Users\nedan\OneDrive\Documents\ChatGPT\telegram integrity 2`.
- Build and loaded fingerprints both: `9098f2540c41b517e876307bf73a65614f8c526ac3a5a4ab7be13a87fcd27b0d`.
- Parser: `candidate-response-parser-v2`; candidate contract: `candidate-obligations-compact-v1`.
- Actual Streamlit diagnostic reports every pre-dispatch check passing.
- Configured model: `gpt-4.1-mini`.
- Kilkeel source SHA256: `bc9af6ef3c4f7a88f93cbdff108a0434cb204ae2bc096f514b34394bc3e48803`.
- Six physical pages; source inventory has 41 records and numbered condition identifiers 1–22.
- Actual batch planner: primary pages 1–4 with page 5 context; primary pages 5–6 with page 4 context.

## Isolation

Prepared browser run ID: `acceptance-b13ab39680004131b1a013dfd25505e1`.
Derived namespace: `94726c4cd85672f22deb19daededefa5fb72845b61bd18a60bbce4a1dbaba61e`.
The namespace does not exist. The browser URL carries the run ID; merely opening it does not create an analysis or dispatch.
On upload, the full-run diagnostic checkbox defaults to false. No PDF was uploaded or Analyze clicked in this preflight.

The historical run `acceptance-f4ba6ab6a3274be4a29ea112cdedaa82` remains FAILED with one OUTCOME_UNKNOWN dispatch, zero candidates and its reservation retained. Reading its ledger reports the prior-failure blocker. Checks before and after preflight found unchanged hashes:

- Manifest: `8332205f8c0c1fb26973ccc701b82443ddaa2be6f6c6e0664532fd3539be180b`.
- Dispatch ledger: `60d5d9d22560cdbb357a7076add4588f99ec75de61aaec25f5cf9b7be6ef5c5d`.

Fresh-run identity includes source bytes, configured model, candidate prompt version and explicit run ID. Intelligence-stage checkpoints are nested inside that run. The mock acceptance test verifies a failed neighbouring namespace is untouched and rerunning the same successful test namespace dispatches nothing further.

## Request and estimated cost budget

Configured pricing: $0.40 per million input tokens; $1.60 per million output tokens.

| Request | Input ceiling | Output ceiling | Cost at configured ceilings |
|---|---:|---:|---:|
| Candidate batch 1 | 16,000 | 8,000 | $0.0192 |
| Candidate batch 2 | 16,000 | 8,000 | $0.0192 |
| Stage 1 | 60,000 | 6,000 | $0.0336 |
| Stage 2 | 50,000 | 6,000 | $0.0296 |
| Stage 3 | 60,000 | 6,000 | $0.0336 |
| Total | 202,000 | 34,000 | $0.1352 |

Maximum five requests and $0.15 estimated cost; no automatic retries. Reservations persist before dispatch and unknown outcomes retain their reservation. Input tokens are estimated from text length; this is the application's configured cost estimate, not a measured provider invoice or exact tokenizer guarantee. Source images, if added for another document, require separate budgeting; the Kilkeel batch text does not trigger the table-image adapter.

## Offline verification

Full suite: **124 passed in 5.31 seconds**.
New test: `tests/test_fresh_acceptance_preflight.py`.
The new test exercises the production capped upload entry point using only mocked transports, asserts the 8,000/6,000 output ceilings, exactly two candidate calls followed by Stage 1/2/3, source links, canonical validation, persistent five-request ledger, unchanged historical namespace and no redispatch on resume.
Existing regression tests cover strict candidate parsing and schema rejection, incomplete output, fail-stop, runtime rejection, budget caps, review gating, document selection and exports.

Stage 1 receives the source inventory and candidate aggregate; Stage 2 receives Stage 1 requirements; Stage 3 receives those requirements plus Stage 2 assessments. The full workflow creates the canonical JSON only after these stages return. Human review remains required and work windows remain unevaluated unless independently supported.

## Remaining verification

Offline readiness is established. Real response size, interpretation accuracy, all-22-condition semantic coverage, live dashboard charts and canonical exports remain unverified until the separately authorized fresh live run. No success claim is based on the previous failed artifacts. The PDF must be selected in the prepared browser session with mock mode off and the diagnostic checkbox unchecked before any later Analyze action.
