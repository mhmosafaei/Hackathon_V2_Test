# Comprehensive Permit Intelligence Analysis

## Scope

This layer extends the established document-wide candidate workflow; it does
not replace it. Candidate extraction, source inventory, quotation verification,
recovery, coverage, review decisions, and executable-rule safeguards remain
the source-of-truth workflow.

## Stages

1. **Document extraction** converts the retained candidate/source register
   into atomic, source-linked requirements. The model contract allows only
   `PENDING` source verification; the local verifier supplies the actual
   canonical verification state.
2. **Operational relevance** classifies each requirement for operational use
   and records uncertainty explicitly.
3. **Environmental mapping** proposes data needs and constraint candidates.
   Provider availability is always `NOT_CHECKED` until a deterministic adapter
   verifies it.

All stage payloads use strict Pydantic schemas and are independently validated
against the supplied Stage 1–3 schemas. The assembled output validates against
the supplied `permitpulse.intelligence.v1` contract.

## Resumption and isolation

Stage responses are saved under
`cache/document_runs/<existing-run>/intelligence/<identity>/`. The identity is
derived from the raw document SHA-256, selected model label, contract version,
and the three prompt versions. A completed checkpoint is reused only within
that identity. The source run and original model response are never modified;
the root `intelligence_analysis_v1.json` is a UI-facing, document-scoped
canonical pointer.

An explicitly selected fresh live acceptance run additionally incorporates a
user-visible `analysis_run_id` in the run namespace. It is mirrored in the
browser URL so a refresh or resumption uses the same checkpoints. The standard
deterministic cache identity remains unchanged when no run ID is requested.

## Capped live-acceptance profile

The narrow acceptance profile is dormant unless explicitly selected in the UI.
It refuses to start unless it can plan exactly two candidate batches, followed
by the three intelligence stages. Its persistent ledger enforces five total
requests, a $0.15 conservative reservation ceiling, known configured-model
pricing, local input-token ceilings and provider output-token ceilings. Before
each call it records `DISPATCH_STARTED`; a failure becomes `OUTCOME_UNKNOWN`
and permanently blocks automatic redispatch. Successful responses record the
request ID, actual token usage and estimated cost. The Audit view displays this
ledger and the per-stage usage/cost data.

## Numbered condition accountability

Stage 1 must link numbered source conditions to atomic requirements or flag
them unresolved. A deterministic `stage1_condition_accountability.json`
artifact lists every structural numbered source condition, page, source record,
authority disposition, source evidence, linked requirements, interpretation
state, and review-needed exceptions/dependencies/thresholds/deadlines. It never
manufactures a requirement for an omitted source span.

## Safety posture

- No stage output confirms a requirement or creates an executable rule.
- A failed quotation remains visible and review-gated.
- Missing/unsupported data remains unavailable, not favorable evidence.
- Work windows are `NOT_EVALUATED` until appropriate human-confirmed rules and
  deciding evidence exist.
- Mock mode is local and explicitly opt-in for sanitized tests. It sends no
  document text to OpenAI.

## Dashboard

The Permit Operations dashboard shows five document-scoped views:

- **Overview:** authority, operational-role, evidence-readiness, lifecycle,
  and environmental-domain charts calculated locally from canonical records.
- **Requirements:** search/filter controls, evidence drilldown, source IDs,
  quotations, and page provenance.
- **Environmental Intelligence:** proposed constraints, data needs,
  deterministic-feasibility state, and open review flags.
- **Work Windows:** deliberately non-authorizing status and blockers.
- **Audit & Exports:** stage ledger, per-page state, canonical JSON, CSV and
  Excel exports.

No dashboard metric or chart is accepted from an unverified model assertion.
