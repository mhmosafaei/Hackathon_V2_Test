# Candidate-first permit workflow verification — 2026-10-12

The normal Streamlit Analyze path makes candidate-extraction requests only.
Deterministic source normalization, validation, quotation state preservation,
numbered-condition grouping, coverage, evidence mapping, classification and
exports follow without additional LLM requests. `experimental_intelligence=True`
is the explicit service opt-in for the old three-stage chain; the UI does not
enable it. This is not a claim of a new successful live acceptance run.

## Kilkeel saved-evidence projection

- Parent run: acceptance-b13ab39680004131b1a013dfd25505e1.
- Raw source SHA256: bc9af6ef3c4f7a88f93cbdff108a0434cb204ae2bc096f514b34394bc3e48803.
- Run folder: cache/document_runs/94726c4cd85672f22deb19daededefa5fb72845b61bd18a60bbce4a1dbaba61e.
- Derived artifact directory: deterministic-permit-v1/ (does not rewrite the failed parent run).
- 40 raw candidates, 37 retained, 3 duplicates preserved, 0 schema-rejected.
- 30 SOURCE_VERIFIED, 4 SOURCE_NOT_FOUND, 3 CONTEXT_UNRESOLVED.
- 41 source records; 22 independently inventoried numbered conditions.
- 13 captured source spans; partial spans 7,10,18,19,20,22; review-required 13;
  no candidate for conditions 1 and 2. Partial spans include inventory continuation
  and adjacent context; they require inspection rather than automatic completion.
- Condition 19: original candidate page 4; unique exact-normalized PDF match on
  page 3; derived page corrected to 3 with original attribution and source IDs
  retained in normalization_audit.json. State remains SOURCE_VERIFIED.
- Automation: 2 EXTERNAL_DATA_REQUIRED, 9 MANUAL_INPUT_REQUIRED,
  26 NOT_EVALUABLE; 0 AUTOMATIC. No deciding evidence acquired or inherited.
- All records UNREVIEWED/non-executable; authority and atomic semantic completeness
  remain unresolved. This workflow creates no ExecutableRules or WORK decisions.

## Persisted outputs

- intelligence_analysis_v1.json: strict canonical contract.
- candidate_aggregate.json: derived candidate view, original quotations/states,
  condition groups, evidence mapping and audited page correction.
- coverage_audit.json: explicit gap/partial/review groups.
- normalization_audit.json: parent aggregate hash, corrections, groups, duplicates,
  mapping and classification justifications.
- requirements.csv: all 37 requirements with evidence/automation columns.
- intelligence.xlsx: sources, requirements, condition groups, evidence mapping,
  attribution corrections, duplicates, review flags and non-authorizing status.

XLSX control-character escapes are reversible and documented in the workbook;
canonical JSON and raw outputs preserve the exact original characters. Download
controls build from the same canonical artifact and local audit as saved exports.

## Verification

- Full regression suite: 130 passed, 0 failed, 8.72 seconds.
- Offline production upload regression: candidate batches only; no Stage 1/2/3
  calls; scoped ledger, checkpoint reuse and historical isolation verified.
- Real-evidence regressions: 37 candidates, states, 22 source groups, missing
  1/2, AIS external classification, original-page audit, duplicate preservation,
  XLSX/CSV counts, stable projection, unverified approval rejection.
- Cached Streamlit AppTest: actual app, fresh run URL restored, 37 records,
  gaps visible, no exceptions, API transports patched to fail if called.
- Original run files byte hashes unchanged during offline projection.
- Real browser: Kilkeel selected from its run URL after restart; 37 reviewable
  records; coverage gaps visible; requirement search and condition-19 page-3
  evidence drilldown verified; evidence mapping and DATA REQUIRED warning visible;
  audit, correction, duplicate and download controls rendered. Bar chart marks
  inspected. At the narrow browser width, long chart titles remain clipped;
  this is an existing presentation limitation, not a data omission.
- Source-condition summary counters now agree with the local gap inventory rather
  than displaying processed-page counts as condition coverage. Runtime was
  restarted with the tested code. No Analyze action or API call was made.

## Limitations

Deterministic mappings are conservative, not a substitute for semantic legal
review. The source inventory may include continuation/context tails. Unmatched
quotes and context uncertainty are not repaired or approved. No live run was
made after these changes. Environmental availability remains DATA REQUIRED.
