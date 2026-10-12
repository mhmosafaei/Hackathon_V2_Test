# Stage 1 Extraction Audit

## Scope and identity

The audit covers selected physical pages 4 through 10 of `ML2025054.pdf`. SHA256: `7e8e26705bf2b788657bf6de661a9b49d390f2600f03f461f500b58340294252`.

## Accounting

| Category | Count |
| --- | ---: |
| Raw model items | 53 |
| Validation-rejected items | 8 |
| Within-page exact duplicates removed | 2 |
| Cross-page duplicates removed | 0 |
| Final unique schema-valid conditions | 43 |
| Quote verified | 40 |
| Quote unverified and review-required | 3 |

Every persisted raw item has an item-level disposition in its per-page reconciliation report. Validation errors are `threshold` (7) and `condition_type` (1); the page-5 rejected items are retained as a recovery queue rather than discarded.

## Evidence classification

| Automation status | Count |
| --- | ---: |
| AUTOMATIC | 1 |
| EXTERNAL_DATA_REQUIRED | 4 |
| MANUAL_INPUT_REQUIRED | 6 |
| NOT_EVALUABLE | 32 |

`NOT_EVALUABLE` is generally justified for document, method, notification, and advisory obligations that lack a Stage 1 deciding-data mapping. It is a mapping/review queue, not a PASS. Local suspended-solids and dissolved-oxygen conditions remain external local-monitoring requirements; no Copernicus evidence is used as compliance evidence.

## Review and recovery queue

- Three quote-unverified schema-valid conditions require human review.
- Eight validation-rejected raw items require recovery review, notably page-5 calendar/deadline and nonnumeric-field items.
- All extracted conditions are UNREVIEWED. The rule factory rejects unconfirmed conditions, so none can make a compliance decision.

## Acceptance status

Deterministic recovery added 12 source-backed unconfirmed candidates (conditions 1,5,6,7,9,10,17,18,19,20 station capability,22,23) and page 3 contributed four validated records (2,3,4,8). The aggregate now contains 59 records: 56 quote verified and 3 quote unverified. Every recovered candidate is unconfirmed and carries recovery provenance. Stage 1 remains blocked on completing actual human review/recovery of material rejected/unverified items; no reviewer decisions have yet been recorded.

## Stage 1A orchestration

The engineering workflow now identifies numbered-condition pages independently of keyword priority, uses document/model/prompt cache identity, checkpoints each page, isolates failures, and resumes COMPLETE pages. The coverage gate marks a document incomplete unless all selected condition pages complete. Stage 1B remains the human-review phase.
