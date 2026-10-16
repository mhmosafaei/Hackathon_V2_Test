# PermitPulse Operator Guide

Practical instructions for the current FastAPI + built React hackathon app. All outputs are advisory evidence assessments, not regulatory approval, legal compliance confirmation, vessel-master approval, permit-to-work authorization or safe-to-work certification.

## 1. Start the app

Run from the repository root in PowerShell. One FastAPI process serves the built frontend and API on **8531**; normal use needs no separate frontend runtime.

### Install dependencies and build

Use the same Python environment for installation, startup and provider workers:

```powershell
python -m pip install -r requirements.txt
python -c "import fastapi, uvicorn, jsonschema, openai, httpx, copernicusmarine, xarray, numpy; print('Runtime imports OK')"
cd frontend
npm ci
npm run build
cd ..
```

These are setup instructions, not automatic app actions. Resolve missing imports in the intended environment before live use. The ECMWF adapter directly imports `httpx`; OpenAI/Copernicus installations normally bring runtime dependencies, but the import preflight is the check, not an assumption. Do not substitute an interpreter lacking the provider SDK.

### Environment configuration

Use a local repository-root `.env`. Never commit it, print its contents during a demo or place secrets in frontend code.

| Setting | Purpose |
|---|---|
| `OPENAI_API_KEY` | Server-side credential for explicit Analyze. |
| `OPENAI_MODEL` | Required extraction model selection; use a model compatible with current strict structured output and token configuration. |
| `COPERNICUSMARINE_SERVICE_USERNAME` | Copernicus worker account username. |
| `COPERNICUSMARINE_SERVICE_PASSWORD` | Copernicus worker account password. |

The configured ECMWF adapter uses the public Open-Meteo endpoint without a secret. Dataset/capability configuration lives in `config/environmental_data_sources.json`; `config/environmental_limits.json` sets the 72h request maximum. Recency policies are application policies, not credential/environment overrides. Do not change configuration to bypass a failed qualification.

### Check port 8531

```powershell
Get-NetTCPConnection -LocalPort 8531 -State Listen | Select-Object OwningProcess
```

If a listener exists, identify the process before deciding whether to reuse or stop it. Do not start competing backends or stop an arbitrary PID.

### Accepted Windows startup

The accepted environment uses this existing interpreter. Substitute your own provisioned interpreter path on another machine:

```powershell
& 'C:\Users\nedan\AppData\Local\Python\pythoncore-3.14-64\python.exe' -c "from dotenv import load_dotenv; from src.permit.simple_api import create_app, ROOT; from src.permit.simple_analysis import VERSION; from src.environmental.copernicus import retrieve as copernicus_retrieve; from src.environmental.ecmwf import retrieve as ecmwf_retrieve; import uvicorn; load_dotenv(ROOT / '.env'); print('PermitPulse build: ' + VERSION, flush=True); uvicorn.run(create_app(environmental_transports={'COPERNICUS_MARINE': copernicus_retrieve, 'ECMWF_FORECAST': ecmwf_retrieve}), host='127.0.0.1', port=8531)"
```

The shorter repository entry point also loads `.env` and uses normal adapters:

```powershell
python -m src.permit.simple_api --port 8531
```

Open <http://127.0.0.1:8531/>. After backend changes or a static frontend rebuild, restart the intended backend and reload the browser. A successful build alone does not prove the browser is displaying it.

### Restore a paid extraction after restart

The frontend retains an exact hash/run reference in browser storage and also accepts:

```text
http://127.0.0.1:8531/?document_sha256=<document_sha256>&analysis_run_id=<analysis_run_id>
```

Replace both placeholders with the intended persisted identity. Restoration checks the run, reapplies current deterministic source verification/mapping in memory and leaves artifacts unchanged, with no OpenAI/provider call. Check the displayed run and completeness indicator. Incomplete historical extraction remains explicitly incomplete. Filename/page count alone is not identity.

Environmental evidence and decisions are backend-session state. A clean restart does not restore evidence just because the permit was restored. An intentional Fetch is needed if the new session has no evidence. Never re-Analyze solely to recover a paid extraction.

## 2. Permit Intelligence: upload and Analyze

1. Click **Upload Permit**, choose a text-readable marine permit PDF (UI maximum 25 MB).
2. Click **Analyze** once and wait. Do not repeatedly click **Try Again** without understanding the error.
3. Confirm filename and run ID.
4. Inspect permit location, validity versus operation timing, conditions, source quotations/physical pages, thresholds, operators, units and environmental mappings.
5. Verify interpretations in Human Review before decision use.

After local preflight, the current path makes exactly one OpenAI extraction request, with strict structured output and no second LLM/automatic repair stage. Candidate omissions fail closed as `EXTRACTION_INCOMPLETE`; valid JSON is not proof of completeness. A manual retry is a new potentially paid request, not restoration.

Results remain unreviewed and non-authorizing. Check source evidence rather than accepting plausible-looking interpretations.

## 3. Environmental Intelligence: query and fetch

| Exact field/control | Input |
|---|---|
| **Latitude** | Decimal WGS84 latitude. |
| **Longitude** | Decimal WGS84 longitude; west is negative. |
| **Planned start (UTC)** | Actual planned UTC date/time, not local time. |
| **Planned end (UTC)** | Later UTC time, at most 72h after start. |
| **Depth (m, when applicable)** | Compatible source-required depth; blank is missing, numeric `0` is explicit zero. |
| **Evaluate this confirmed point only, not an entire route or polygon.** | Confirm only a genuine point assessment; this does not verify an entire area. |

For the current synthetic demo's **54.025000 N, 5.925000 W**, enter **54.025** and **-5.925**. This is an example, not a default for other permits.

1. Confirm the operation point against the reviewed permit. A selected provider grid point is not the permitted operation point.
2. Enter both planned UTC times explicitly. Do not invent midnight/timezone from date-only source wording. Future requests can use available forecasts, but provider coverage may be shorter than the requested period.
3. Enter **0** m for the current synthetic permit's explicit oxygen sea-surface model-level requirement. Depth is variable-scoped: wind and 2D waves/currents do not acquire marine depth. Follow other permits' actual source-required depths; no arbitrary override.
4. Click **Fetch Environmental Data**. Only this explicit action retrieves evidence; tab mounting, session polling, copying settings and restoration do not fetch.
5. Inspect provider/product/dataset/variable, native timestamp, requested versus selected coordinates, distance, cadence, depth, temporal coverage, evidence mode, threshold result and representativeness.

Configured sources include **Copernicus Marine** and **ECMWF Forecast via Open-Meteo**. Waves/weather are commonly hourly and configured currents 15-minute. Compatible future model timestamps can be assessed without treating them as observations. Partial coverage remains partial; no interpolation/extrapolation fabricates missing data.

Fetch has a 12-dispatch cap per click and reuses identical retrievals. A skipped requirement is not successful evidence. Turbidity may be reference/satellite evidence; oxygen is modelled supportive evidence, not an in-situ substitute. Model values never establish local truth.

Hourly precipitation values are accumulated **mm over one hour**, not rates. Comparison requires compatible 3600-second accumulation metadata; source wording remains auditable. No generic mm/hour conversion or resampling is performed.

## 4. Human Review

1. Open **Human Review**. Select a row in **Conditions & requirements**; search/filter as needed.
2. Compare **Original source clause**, physical page/source verification, **AI / extracted interpretation** and **Effective reviewed interpretation**.
3. Set **Applicability** to **Applicable**, **Not Applicable** or **Unassessed**. Enter **Reviewer** and **Reviewer notes / justification**. Not Applicable requires justification; rejection is not non-applicability.
4. Use **Approve interpretation** for a supported interpretation. To correct fields, use **Edit interpretation**, enable specific corrections and **Save correction**. Use **Reject interpretation** or **Keep pending** when unresolved.
5. **Approve all pending (N)** opens confirmation. **Approve eligible pending** accepts eligible verified pending interpretations only; it does not set applicability or supply evidence. Inspect skipped/failed records.

Reviews/corrections are overlays preserving the immutable extraction. Never approve invented thresholds, dates, geometry or conversions to force WORK.

### Current synthetic-demo pattern only

For the current synthetic marine test permit, review general **Condition 1** (position) and **Condition 19** (validity) as Applicable when supported. Review **environmental copies of Conditions 3–15** as Applicable when correct. **5, 8 and 12** remain informational/non-gating. Administrative/process clauses do not automatically become numerical F09 gates.

The navigator may show a general condition and environmental copy with the same number. The environmental copy supplies the physical check; general records retain source/context audit, including time/position prerequisites. These condition numbers and 0 m depth are demo-specific, not generic routing exceptions.

## 5. Decision & Work Windows

1. Confirm reviews and current session environmental evidence exist.
2. Set **Start UTC (blank = evaluation time)**. Use an explicit time within fetched coverage for that planned period; blank does not mean fetch-period start.
3. Select **Timeline horizon**: **24h / 48h / 72h**.
4. Select **Required continuous duration**: **2h / 4h / 6h / 12h**.
5. Select **Rank candidates**: **Earliest candidate** or **Longest candidate**.
6. Choose **Include conditional windows requiring additional verification**.
7. Click **Evaluate existing evidence**. This uses stored evidence/reviews only, not providers or OpenAI. Changed controls apply on evaluation; displayed audit values show the actual parameters. Reopening restores the session decision/controls.
8. Inspect current decision, timeline, **Interval details**, **Candidate continuous windows**, **Selected window details**, **Missing evidence & required actions**, exclusions and **Constraint inspector**. **Download assessment JSON** exports the assessment audit.

| State | Meaning within evaluated MVP scope |
|---|---|
| **STOP** | An applicable reviewed gating constraint is demonstrably triggered. |
| **UNKNOWN** | No STOP established, but required gating evidence is insufficient/incompatible. |
| **WORK** | All applicable evaluated gating constraints pass with sufficient evidence for the full interval. |

Precedence is **STOP > UNKNOWN > WORK** for actual gates. STOP names triggered constraints; UNKNOWN names blockers, such as “Insufficient evidence: Dissolved oxygen data is stale; Surface current speed data is unavailable.” Detailed codes/provenance remain auditable.

Fresh compatible turbidity can STOP. Missing/stale/incompatible turbidity is separately excluded from MVP aggregation, **not marked PASS**. Source/review/interpretation safeguards are not bypassed.

Mean wave, wind and current directions are informational, not independent gates. Current direction derives from compatible U/V as **TOWARDS, clockwise from true north**; mean wave direction retains its provider convention.

### Candidate work windows

Without conditional inclusion, candidates require uninterrupted WORK for the selected duration; UNKNOWN and STOP break those runs. Ranking changes order, not qualification.

With conditional inclusion, continuous non-STOP runs containing UNKNOWN can also appear as **CONDITIONAL**. They require further verification, not confirmed workability. STOP always breaks a run. Select a candidate to inspect its actual interval-specific rules.

A WORK candidate is an evidence-assessment result, not regulatory approval, compliance confirmation, vessel-master approval, permit-to-work authorization or safe-to-work certification.

## 6. Evidence policy quick reference

| Evidence | Current policy |
|---|---|
| Significant wave height | Newest compatible native sample at/before assessment instant, max **90 min**; no interpolation or hold beyond expiry. |
| Turbidity | Compatible **FNU**, max **72h**; fresh evidence gates, missing/stale/incompatible evidence excluded but auditable. No NTU=FNU assumption. |
| Dissolved oxygen | For explicit **0 m** model level, max **24h**, conservative 0.5 m depth tolerance; modelled, not in-situ. Missing/stale evidence blocks when applicable. |
| Currents | Existing analysis/forecast product; compatible future `MODEL_FORECAST` native values accepted with grid/time provenance. No fabricated extrapolation. |
| Weather | ECMWF via Open-Meteo forecast/model evidence; timestamps/grid qualification retained. Precipitation requires verified hourly accumulation. |

These are explicit PermitPulse policies, not provider-declared continuous validity. Native timestamps are unchanged. A 72h query does not make an older reference value fresh for all 72h. SSH remains unsupported without verified mapping, not local tide/clearance.

## 7. Troubleshooting

| Symptom | Likely cause / corrective action |
|---|---|
| Port 8531 occupied | Inspect `OwningProcess`; identify the intended backend before changing processes. |
| Old UI after rebuild | Check `frontend/dist/index.html` references new assets; restart intended backend and reload/hard-refresh. Do not re-Analyze to refresh code. |
| No environmental data | Confirm explicit Fetch, run identity and session result. Restart clears session evidence; permit restore does not fetch it. |
| Wrong location | Check WGS84 and negative west longitude; separate operation point from model grid point. |
| Query over 72h/reversed | Supply both UTC times with positive duration at most 72h; shorten query rather than bypass validation. |
| Missing location/time | Enter both coordinates and confirmed UTC start/end; date-only permit wording is not operational time. |
| Depth incompatible | Check source-required depth/model level. Zero is valid, blank absent; do not widen tolerance or substitute levels. |
| Provider unavailable/skipped | Inspect safe diagnostic, credentials, dataset/time coverage and per-click cap. Do not substitute unverified sources. |
| Stale evidence | Check native timestamp and age at assessment time, not only retrieval time. Hs/DO can block; unavailable turbidity is excluded, not passed. |
| UNKNOWN | Read named source/review, unit/depth, time/position or coverage blocker. Do not infer missing evidence. |
| No candidate windows | Inspect STOP/UNKNOWN, duration and coverage. Conditional inclusion shows unresolved runs; it does not turn them into WORK. |
| Analyze disabled/not started | Select PDF, wait for session, check backend/port and model/key setup. Avoid repeated paid submissions. |
| Environment not loaded | Use documented entry point from repo root and correct interpreter; verify configuration without printing secrets; restart after environment changes. |
| Extraction incomplete | Preserve run/audit and inspect missing candidates. No automatic retry; another Analyze is a new explicit potentially paid request. |
| Reviews unavailable | Check current backend review endpoints, exact restored run and boot session. Do not re-Analyze to recover an existing run. |

## 8. Demo checklist

- Backend on 8531; app opens with current built controls.
- Correct permit/run loaded; completeness checked.
- Human interpretations/applicability reviewed; no secrets visible.
- WGS84 point, longitude sign, UTC period and applicable depth confirmed.
- Explicit Environmental Fetch completed; provider evidence/provenance visible.
- Decision evaluated; horizon/duration match displayed audit.
- Candidate windows inspected if available; UNKNOWN/exclusions understood.
- No stale bundle; WORK presented as advisory, not permission to operate.

Return to the [main README](../README.md).
