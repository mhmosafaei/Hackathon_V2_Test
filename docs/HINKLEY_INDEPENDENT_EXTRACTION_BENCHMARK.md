# Hinkley independent extraction benchmark

## Scope and evidence

- Source: `Hinkley-Point-C-varied-permit-July-2023.pdf`, raw SHA-256
  `a9dec163f30956e1e4b99208df4b482a54df1d5db666598ef9f93fee2a1d19da`.
- Production input: `HINKLEY_AI_FIRST_LIVE_EVAL_01` recovered analysis.
- Reference register: the supplied 293-row
  `Hinkley_Permit_Extracted_Register.csv`, used exclusively by the offline
  evaluator. It is not copied into, or used to repair, production output.

The register is source-oriented rather than certified ground truth. The results
below are not precision or recall: rows with table context serialized in a
different order require source-geometry review.

## Recovered output

The immutable raw GPT responses contain 132 records. Offline revalidation with
application-owned verification state retained 114 unique candidates and logged
18 exact quotation/page duplicates. All 114 quotations are source-verified;
this verifies a span only, not legal interpretation or table applicability.

| Source area | Candidate evidence | Assessment |
|---|---:|---|
| Main conditions (pp. 7–10) | 30 | Core hierarchy represented; clause 4.1.1 is partial at a page boundary. |
| Activities / operating techniques (pp. 11–12) | 2 | Low apparent coverage; requires reference or source review. |
| IC1–IC4 (p. 13) | 4 | Candidate evidence present. |
| PO1–PO18 (pp. 14–18) | 33 | Candidate evidence present but requires item-level comparison. |
| S3.1 limits / monitoring (pp. 21–31) | 34 | Limits are represented, but some physical table pages have no distinct candidate. |
| S3.2 / S3.3 (pp. 32–34) | 2 | Under-represented; applicability/row context unresolved. |
| Schedule 4 reporting (pp. 35–41) | 10 | Partial apparent coverage. |
| Schedule 5 notification (pp. 42–43) | 2 | Partial apparent coverage. |
| Definitions / plans (pp. 44–46) | 0 | Contextual material is inventoried only, not claimed as obligations. |

The deterministic source inventory now contains 558 records: 104 clauses, 31
tables, 16 schedules, 327 geometry-backed rows, plus definition/reference and
cross-page context records. Table rows preserve explicitly labelled parameter,
limit, period, monitoring-frequency and compliance-statistic cells. Blank or
merged applicability remains `UNRESOLVED_CONTEXT`.

## Stratified source review

Pages 7–8 show complete source-backed candidates for management, record
retention, authorised activities, improvement notification, pre-operational
measures, emissions limits, monitoring, and MCERTS/monitoring-point duties.
Those candidates are materially meaningful rather than modal-keyword fragments.

High-risk numerical material in S3.1 is source-quoted, but is not independently
confirmed row-by-row for discharge stream, period, compliance statistic, and
operating mode. Percentile and tidal-mean associations therefore remain
`INTERPRETATION_UNRESOLVED`, not numerically correct by assertion.

## Known material gaps / review burden

1. No independent reference file: no defensible recall/precision calculation.
2. Table-row provenance is incomplete; S3.1/S3.2/S3.3 applicability needs
   human review, especially pages 24, 26–28 and 34 with no unique candidate.
3. Schedule 4 and 5 page coverage is sparse.
4. Cross-page clauses need explicit continuation links.
5. Definitions, incorporated plans and exceptions are source inventory/context,
   not automatically promoted to obligations.

Estimated review burden: all 114 candidates require review, with priority on
the 32 emission limits, 6 monitoring duties, 17 reporting duties and 8
notifications. Table-derived candidates should be reviewed against their page
image and reconstructed header context before any operational use.

## Product safety and recommendation

The Streamlit register keeps source inventory separate from review-gated
obligations; no confirmation or executable-rule pathway is triggered by this
analysis. Belfast and 07203 files are not changed.

Priority improvements: (1) make table rows/cells source records with explicit
header/provenance links, (2) establish cross-page clause context, (3) supply
the independent CSV or a separately reviewed stratified benchmark before
reporting recall or completeness.

## Supplied independent-register comparison

The supplied 293-row CSV was evaluated without adding any reference record to
the production register. Page plus normalized source-span matching found 41
`FULLY_MATCHED`, 63 `PARTIALLY_MATCHED`, and 189
`MISSING_FROM_PERMITPULSE` records. This is not reported as precision/recall:
the reference is source-oriented and includes acknowledged unresolved table
context.

| Group | Full | Partial | Missing |
|---|---:|---:|---:|
| Core permit conditions | 16 | 10 | 3 |
| Authorized activities | 3 | 0 | 4 |
| Incorporated operating techniques | 0 | 0 | 15 |
| Improvement conditions | 3 | 1 | 0 |
| Pre-operational measures | 8 | 10 | 0 |
| Emission limits / monitoring | 0 | 28 | 103 |
| Discharge and monitoring points | 0 | 8 | 17 |
| Reporting requirements | 8 | 6 | 44 |
| Supporting instructions | 3 | 0 | 3 |

The machine-readable evaluation is
`HINKLEY_AI_FIRST_LIVE_EVAL_01/independent_benchmark.json`.

## Reconciliation of the 189 narrow-matcher misses

The original comparison only matched a reference span against a GPT quotation
on the same page. The offline reconciliation retained that result for
reproducibility and classified exactly those 189 rows without changing any
candidate:

| Disposition | Count | Meaning |
|---|---:|---|
| A — present candidate, matcher missed it | 61 | Broader normalised source/identifier matching finds an existing candidate. |
| B — source-only retained record | 4 | Source exists but no candidate is claimed. |
| C — unresolved source context | 124 | Mostly table rows with blank/merged applicability or column-order differences. |
| D/E/F | 0 | No row was automatically called absent, defective or semantically resolved by this reconciliation. |

This does **not** prove the 61 candidate matches are legally complete, and it
does not promote the 124 context-unresolved rows into obligations. Four direct
Schedule 3 samples illustrate the reason: the reference renders labelled table
columns as prose while the PDF text layer extracts visual columns separately.
They remain layout-serialization comparisons, not proof of missing source.
