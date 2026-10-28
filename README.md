# PermitPulse V 2.0

Source-backed marine permit review and deterministic environmental evidence assessment for the hackathon MVP.

**Advisory only:** not regulatory approval, legal compliance confirmation, vessel-master approval, permit-to-work authorization or safe-to-work certification.

For step-by-step startup, permit analysis, environmental retrieval, human review, and work-window evaluation, see the [PermitPulse Operator Guide](docs/PERMITPULSE_OPERATOR_GUIDE.md).

## PermitPulse V 2.0 release notes

V 2.0 improves UI usability, visual clarity, navigation, evidence presentation, human-review transparency, the 72-hour decision timeline, and candidate work-window reporting while preserving the environmental decision-engine behavior.

## Technology stack and prerequisites

PermitPulse uses Python/FastAPI, React/Vite, deterministic permit decision modules, Pytest, and Vitest. Install the dependencies listed by the repository's backend dependency file and use Node.js/npm.

```powershell
python -m pip install -r requirements.txt
cd frontend
npm install
cd ..
```

## Windows PowerShell startup

From the cloned repository root, start the backend:

```powershell
python -m uvicorn src.permit.simple_api:create_app --factory --host 127.0.0.1 --port 8531 --env-file ..\.env
```

`..\.env` is the existing development environment-file location in this setup. Change it for another clone; never commit `.env` files or secrets.

In a second PowerShell terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, normally `http://127.0.0.1:5175/`; Vite may select another available port. Keep both processes running. Stop them with `Ctrl+C` and restart with the same commands.

## Dashboard workflow

Start a permit analysis, inspect extracted conditions and source quotations, review environmental evidence and human-review states, then use **Decision & Work Windows** to evaluate existing evidence without fetching new provider data. Inspect candidate timelines, constraint details, provenance, and unresolved-evidence warnings.

`STOP` means a reviewed constraint was triggered. `UNKNOWN` means required review or evidence remains unresolved. `WORK` is advisory for the evaluated scope. `MVP CANDIDATE / CONDITIONAL` means MVP constraints pass while applicable permit conditions remain unresolved under the MVP evidence-availability policy.

## Environmental configuration and limitations

Provider configuration belongs in the local ignored environment file. Do not expose credentials in source, arguments, logs, screenshots, or Git history; the frontend never receives provider credentials.

PermitPulse is advisory evidence assessment, not regulatory approval, legal-compliance proof, permit-to-work authorization, or operational authorization. Model evidence does not establish local truth. Source verification, applicability, geography, units, depth, coverage, and human review remain explicit safeguards. Turbidity without compatible native FNU evidence remains UNKNOWN; any MVP exclusion is explicitly warned and is not a passing result. Assessment snapshots are session-scoped and exact hashes can vary with evaluation time.

## What PermitPulse does

PermitPulse extracts reviewable conditions from a text-readable marine permit PDF, maps explicit environmental requirements to configured sources, and evaluates stored evidence against reviewed operational constraints. Model evidence does not establish local truth; source verification, coastal representativeness, units, depth and coverage remain explicit.

## Hackathon application workflow

1. **Permit Intelligence:** Upload a PDF, click **Analyze**, inspect conditions, limits, locations, timing and source quotations.
2. **Environmental Intelligence:** Confirm a WGS84 point, planned UTC period and applicable depth; explicitly click **Fetch Environmental Data**.
3. **Human Review:** Verify interpretations, record applicability and approve/correct supported interpretations, or retain unresolved/rejected items.
4. **Decision & Work Windows:** **Evaluate existing evidence** against reviewed rules and find continuous candidates. Evaluation does not fetch data.

## Architecture

FastAPI serves the built React/Vite UI and same-origin APIs on **8531** in the documented configuration. No separate frontend runtime is required for normal use.

| Component | Responsibility |
|---|---|
| `src/permit/simple_analysis.py` | Single-request extraction, candidate completeness, source verification/reconciliation and run artifacts. |
| `src/permit/simple_api.py` | Session state, exact restoration, review and explicit evaluation endpoints. |
| `src/environmental/` | Deterministic canonicalization/routing, adapters and evidence qualification. |
| `src/permit/decision_engine.py` | Deterministic assessment of reviews and stored evidence. |
| `src/permit/informational_audit.py` | Non-gating direction evidence linkage. |
| `frontend/src/` | Four tabs and shared human-readable decision reasons. |

## Permit extraction

After local preflight, the current simple-analysis path makes **exactly one OpenAI extraction request**, using strict structured output. There is no second LLM stage or automatic repair completion.

A deterministic environmental candidate manifest is supplied in that request. Missing candidate records fail closed as `EXTRACTION_INCOMPLETE`; valid JSON alone is not completeness. Raw response and request/audit provenance are retained. Model extras do not override authoritative candidate eligibility.

Quotations are verified against physical PDF pages. Incorrect page attribution is reconciled only on a unique exact normalized quotation match, preserving original attribution. Unresolved sources remain unverified.

Runs persist under `cache/simple_analysis/<document_sha256>/<run_id>/`. Exact hash/run restoration reapplies current deterministic source verification and mapping **in memory**, without rewriting the analysis. Filename/page count is not a unique analysis identity.

## Human review

Pending, approved, corrected and rejected interpretation states are separate from **Unassessed**, **Applicable** and **Not Applicable** applicability. Rejection does not remove a source obligation. Review/correction overlays preserve the original extraction.

Bulk approval accepts eligible verified pending interpretations, but does not set applicability or establish evidence sufficiency. General source clauses and environmental copies may both appear; F09 links physical checks to environmental requirements rather than double-counting source clauses. Human acceptance is never operational authorization.

## Environmental Intelligence

### Supported environmental variables

Configured Copernicus Marine retrieval includes significant wave height, mean wave period/direction, surface current speed, signed eastward U/northward V, U/V-derived current direction, sea-surface temperature, turbidity and dissolved oxygen. ECMWF Forecast via Open-Meteo supplies 10 m wind speed/direction, gust, visibility, precipitation and air temperature. Mapping does not guarantee evidence availability for a place/time.

Thresholdless mean wave direction, wind direction and current direction are **informational/non-gating**. Current direction is derived from compatible U/V as **TOWARDS, clockwise from true north**. Wave direction retains the provider convention; no FROM/TOWARDS conversion is invented.

Hourly precipitation remains accumulated quantity, not instantaneous rate: numerical comparison requires compatible units and verified **3600-second accumulation** metadata. No generic mm-to-mm/hour conversion or resampling occurs.

### Forecast vs reference evidence

Waves, currents and weather can supply native future model/forecast timestamps. The configured current analysis/forecast dataset is `cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT15M-i`, product `NWSHELF_ANALYSISFORECAST_PHY_004_013`. Compatible future current values retain `MODEL_FORECAST` provenance, not observation labels.

Turbidity requires compatible **FNU**; NTU is not FNU, with no automatic conversion. Fresh compatible evidence can gate and STOP. Missing/stale/incompatible FNU evidence remains auditable as UNKNOWN but is excluded from MVP F09 aggregation; this is not a turbidity pass or authorization to work.

Dissolved oxygen is modelled supportive evidence, not equivalent to in-situ monitoring. The current synthetic demo explicitly requests the **0 m sea-surface model level**. Source-backed depth remains variable-scoped, with a conservative **0.5 m** model-level tolerance; arbitrary overrides are not accepted. Other source-required depths remain subject to compatibility checks.

### 72-hour fetch window

Fetch requires an explicit positive UTC period of **at most 72 hours**, configured in `config/environmental_limits.json`. Tab mounting, session polling and restoration never fetch providers. The per-click dispatch cap is **12**, with reuse of identical retrievals.

Provider coverage may be partial/unavailable. No missing future values are fabricated, interpolated, resampled or extrapolated to fill gaps.

### Provenance and representativeness

Evidence retains available provider/product/dataset/variable, native units/timestamps, cadence, mode, requested and selected grid point, distance, depth and coverage. Coastal/model suitability is separate from matching the operation point to a reviewed permitted point. Grid values are not local measurements.

Environmental results are backend-session state associated with an analysis, separate from immutable extraction. A backend restart loses that session evidence; restoring the permit does not restore environmental evidence.

## Decision & Work Windows

### STOP / UNKNOWN / WORK

Precedence is **STOP > UNKNOWN > WORK** for actual gating constraints:

- **STOP:** an applicable reviewed gating constraint is demonstrably triggered.
- **UNKNOWN:** no STOP established, but required gating evidence is insufficient/incompatible. Unavailable turbidity is the documented MVP evidence-availability exception and remains visible as UNKNOWN while excluded from aggregation.
- **WORK:** all applicable evaluated gating constraints represented in the MVP pass with sufficient evidence for the complete interval.

F09 evaluates source-backed decision-relevant numerical constraints plus permit time/position prerequisites. Missing review/applicability, mapping or compatible evidence is a blocking UNKNOWN, never an automatic scope exclusion. Only genuinely informational/out-of-scope or explicitly reviewed Not Applicable obligations are non-gating. Thresholds come from reviewed source interpretations.

STOP names triggers: “Triggered constraint: Significant wave height”. UNKNOWN names blockers: “Insufficient evidence: Dissolved oxygen data is stale; Surface current speed data is unavailable.” Detailed codes remain auditable. Unavailable turbidity remains an explicit UNKNOWN evidence status with a visible MVP exclusion warning.

### Work-window finder

Controls: **Start UTC** (blank uses evaluation time), **Timeline horizon** (24/48/72h), **Required continuous duration** (2/4/6/12h), **Rank candidates** (Earliest candidate/Longest candidate), and **Include conditional windows requiring additional verification**.

Controls apply on **Evaluate existing evidence**. Results retain the actual evaluated parameters; reopening restores the current session decision.

Without conditional inclusion, candidates require uninterrupted WORK for the selected duration. With inclusion, continuous non-STOP runs containing UNKNOWN may also appear as CONDITIONAL; these are not confirmed WORK windows. STOP breaks every candidate run.

### Evidence recency policies

| Evidence | Explicit MVP policy |
|---|---|
| Significant wave height | Newest compatible native sample at/before assessment instant; maximum **90 minutes**, with cells bounded by expiry. |
| Turbidity | Compatible FNU reference evidence; maximum **72 hours**. Unavailable/stale/incompatible evidence remains UNKNOWN and auditable, but is excluded from MVP F09 aggregation; it is not passed. |
| Dissolved oxygen at explicit 0 m | Compatible model evidence; maximum **24 hours**. Missing/stale evidence remains blocking when applicable. |

Original timestamps are retained. These are PermitPulse acceptance policies, **not provider-declared continuous validity intervals**. No interpolation, inferred crossing time or hold beyond expiry. A 72-hour query does not extend recency limits.

## Future forecast assessment

Select a future UTC period up to 72h, explicitly fetch available configured evidence, then evaluate stored forecasts. Compatible future wave/current/weather values can support candidate assessments. Missing required coverage remains UNKNOWN, without assuming absent evidence passes. This is forecast-based evidence assessment, not a safety prediction or authorization.

## Running locally

From the repository root, using a Python environment with provider dependencies:

```powershell
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
python -m src.permit.simple_api --port 8531
```

Open <http://127.0.0.1:8531/>. The module entry point loads `.env` and uses normal adapters. The [operator guide](docs/PERMITPULSE_OPERATOR_GUIDE.md) includes the accepted Windows interpreter/explicit-transport command and import preflight.

`OPENAI_API_KEY`, `OPENAI_MODEL` and Copernicus credentials remain environment-driven/server-side. Never put secrets in frontend code or commit `.env`. Build after frontend changes, restart the intended backend after backend/static updates, then reload the browser.

## Testing

Offline fixture/mock checks, not live acceptance commands:

```powershell
python -m pytest tests/test_f09_finder_controls.py tests/test_decision_engine.py tests/test_evidence_availability_policy.py tests/test_environmental_extraction_completeness.py -q
cd frontend
npm test -- src/DecisionWorkWindows.test.jsx src/decisionReason.test.js src/Environmental.test.jsx
npm run build
cd ..
git diff --check
```

Use an environment with existing test dependencies. The broader suite has a known hanging TestClient case and two previously identified App-test failures; do not confuse offline suite results with live provider acceptance.

## Safety and limitations

- Review acceptance and evidence sufficiency are distinct.
- WORK is not regulatory approval, legal compliance confirmation, vessel-master approval, permit-to-work authorization or safe-to-work certification.
- Unverified sources, unsupported geometry and incompatible units/depth/coverage cannot be inferred away.
- SSH remains unsupported without a verified mapping; it is not local tide or navigational clearance.
- Model evidence cannot substitute for mandatory external/local monitoring.
- Restart recovery preserves paid extraction, not volatile environmental session results.

## Legacy / experimental modules

Older Streamlit, staged extraction/intelligence, historical-weather and Belfast-specific experimental modules/reports remain in the repository. They are not the primary app/startup workflow. Historical reports may describe superseded behavior; use this README, the operator guide and current code/tests for the present MVP.
