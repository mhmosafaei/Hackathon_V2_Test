# Hinkley live-run offline audit

Run: `HINKLEY_AI_FIRST_LIVE_EVAL_01`. Source checksum:
`a9dec163f30956e1e4b99208df4b482a54df1d5db666598ef9f93fee2a1d19da`.

The dispatch ledger proves nine successful dispatches, not an interrupted
two-dispatch run. Batch 2 has request ID `req_e85550dfdb7a4f208d73b1b628ccf715`,
9,404 input tokens, 7,473 output tokens, and its persisted raw response. All
46 pages were processed. No recovery is possible or needed for batch 2.

Batch 1 has 19 retained, quote-verified, human-review-required candidates on
pages 7–8. They map to clauses 1.1.1–1.1.3, 2.1.1, 2.2.1, 2.3.1–2.3.2,
2.4.1–2.4.2, 2.5.1, 3.1.1–3.1.2, 3.2.1–3.2.2, 3.3.1–3.3.4 and 4.1.1.
Their full source quotation, category, structured text and state are retained
in `candidate_batch_001.json`. Clause 4.1.1 is partial because its source
quotation ends on page 8 and further subclauses continue on page 9; it remains
review-required. The other 18 quotes are complete within their quoted spans.

The pre-fix runner rejected 113 later raw candidates because it incorrectly
validated the model-provided `state=active`. Raw responses are preserved. The
corrected validator now treats verification state as application-owned; this
requires an offline revalidation/aggregate rebuild, not another model call.

Actual recorded usage is 81,944 input plus 40,740 output tokens. At $0.40/M
input and $1.60/M output, usage-derived cost is $0.0979616. The original
pre-dispatch estimator was wrong by a second million-token division, so its
recorded reservations cannot establish prior budget enforcement retrospectively.
No continuation is permitted: all nine original dispatches are already used.
