# Final extraction acceptance — Hinkley Point C

## Scope

This is an offline acceptance audit of the existing `HINKLEY_AI_FIRST_LIVE_EVAL_01` run. No OpenAI request, confirmation, executable rule or reference-register-to-production import occurred.

## Final evidence state

| Measure | Result |
|---|---:|
| PDF pages / raw SHA-256 | 46 / `a9dec163…d19da` |
| Raw GPT candidates | 132 |
| Unique recovered candidates | 114 |
| Source-quote verified candidates | 114 |
| Human-confirmed / executable | 0 / 0 |
| Source inventory records | 558 |
| Clauses / tables / schedules / geometry rows | 104 / 31 / 16 / 327 |
| Directly audited representative records | 22 |

The 22-record sample covers main conditions, operating techniques, improvement and pre-operational requirements, numerical limits, monitoring locations, reporting and notifications. Eighteen have a direct linear source-span match. Two Schedule 3 records are explicitly `LAYOUT_SERIALIZATION_NONLINEAR`, because the source register serializes visual columns in a different order. Two records remain `REVIEW_REQUIRED`; neither is treated as an absent legal requirement or silently promoted.

## Independent-register reconciliation

The retained legacy mechanical benchmark is 41 full, 63 partial and 189 unmatched rows out of 293. The 189 rows were investigated without changing the obligation register:

| Classification | Count |
|---|---:|
| Present candidate, narrow matcher missed it | 61 |
| Source captured but no candidate | 4 |
| Source present, applicability/context unresolved | 124 |
| Automatically declared absent/defective | 0 |

The 124 unresolved cases are concentrated in Schedule 3–4 table rows. They are visible source material, not silently discarded and not treated as complete semantic extraction. The matcher has no authority to resolve inherited table applicability.

## Product and safety checks

- Source inventory and candidate register are distinct, linked datasets.
- Cross-page list continuation is linked only when the continuation is explicit; uncertain page endings remain flagged.
- Explicit clause/table/definition/external-reference links are retained without inventing values.
- Blank and merged table cells remain null or `UNRESOLVED_CONTEXT`.
- All 114 candidates remain review-gated; no candidate produces an executable rule.
- Visible-browser acceptance selected the Hinkley LIVE run, verified the separate 114-record obligation register and 558-record source inventory, displayed unresolved table context, switched Belfast → 07203 → Hinkley without stale rows, and opened all four application tabs without an application exception.
- Visible-browser export downloads were validated: the obligation CSV has 114 rows, the source CSV has 558 rows, JSON has the same 114/558 counts, and the downloaded Excel workbook has five sheets with 558 source, 114 obligation, 46 coverage, and 114 review-status rows.
- Excel, JSON and two CSV exports are generated from the same persisted records used by the UI.
- Measured offline rebuild plus benchmark time: 5.95 seconds on this workspace. This is not a live-model performance claim.

## Acceptance verdict

**EXTRACTION_ENGINEERING_COMPLETE**

The engineering acceptance criteria in scope pass: the active-document correction is live, the real browser sequence completed, exports reproduce their displayed records, document isolation holds, all 83 regression tests pass, and the safety gates remain intact. This is **not** a declaration of legal or operational readiness: the 124 Schedule 3/4 context-unresolved rows, two source-span review items in the stratified audit, and all 114 human-review-gated candidates require review before substantive compliance use.
