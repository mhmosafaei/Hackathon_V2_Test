# PermitPulse MVP frozen baseline — 2026-10-26

This checkpoint contains the verified hackathon MVP snapshot for the
`mhmosafaei/Hackathon_Test` repository.

## Verified scope

- Single FastAPI service with the compiled React dashboard.
- One OpenAI extraction request per Analyze; incomplete environmental
  extraction fails closed.
- Deterministic source verification, page reconciliation, routing, unit and
  depth safeguards.
- Explicit environmental Fetch only; no provider calls during restore or
  decision evaluation.
- F09 remains advisory only and preserves STOP > UNKNOWN > WORK precedence.
- Human interpretation and applicability review remain mandatory.
- Informational wind/current/wave directions are non-gating.
- Missing, stale, incompatible, or inaccessible turbidity evidence remains an
  auditable UNKNOWN evidence status, excluded from MVP F09 aggregation under
  the evidence-availability policy. It is not a turbidity pass or work
  authorization; NTU is never converted to FNU.

## Verification record

The local verification included the focused environmental evidence-availability
and decision lifecycle tests, the focused Decision & Work Windows frontend
tests, Python compilation, and `git diff --check`. No OpenAI request,
environmental-provider request, Analyze, Fetch, or GitHub push was performed
for this checkpoint.

The previously validated assessment remains an advisory result: nine numerical
conditions passed, unavailable turbidity remains visible as UNKNOWN locally
with its warning, and STOP precedence is unchanged. Any saved assessment must
be explicitly re-evaluated from its existing evidence before its displayed
decision is considered current.

## Limitations and recovery

This is not regulatory approval, a compliance conclusion, safe-to-work
certification, or operational authorization. Provider availability, native
timestamps, spatial suitability, depth compatibility, source verification and
human applicability decisions remain binding safeguards.

To recover locally, clone the tagged checkpoint, install dependencies from
`requirements.txt` and `frontend/package.json`, create `.env` from
`.env.example` with credentials kept local, then start the documented FastAPI
service on port 8531. Do not commit `.env`, caches, generated evidence, or
assessment artifacts.
