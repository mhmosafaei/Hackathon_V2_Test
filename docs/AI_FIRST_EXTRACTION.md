# AI-first document extraction

New uploads use a document-wide candidate workflow rather than requiring a
recognised `Part 2 – Conditions` heading. Every readable physical page belongs
to one primary batch; adjacent pages are supplied only as continuation context.
Each completed batch is persisted independently under a cache identity derived
from source bytes, configured model, and `ai-first-candidates-v1`.

The model discovers flexible `CandidateObligation` records. It must preserve a
verbatim quotation and physical source page, and it may leave all semantic
fields null. Deterministic code then validates the record, quote-verifies its
source, records malformed records separately, removes only exact source-level
duplicates, and creates a coverage manifest. Candidates remain review-gated:
`SOURCE_VERIFIED` means that quotation was found, not that its legal meaning
or operational applicability has been approved.

The coverage display distinguishes processing completion from semantic
coverage. A processed page with zero candidates is `REVIEW_REQUIRED`; no
document can claim substantive/legal completeness merely because batches
finished. Historical permit extraction, reviews, rules and Hinkley v1/v2
evaluation artifacts are not migrated or overwritten.

For a safe local UI demonstration, Permit Operations exposes an explicit
**Use local mocked AI response** option. It is intended only for sanitized
fixtures and exercises the identical checkpoint, verification, review and
coverage paths without sending an upload to OpenAI.
