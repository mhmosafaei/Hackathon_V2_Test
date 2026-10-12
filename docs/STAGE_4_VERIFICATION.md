# Stage 4A/4B verification

## Belfast licence safety state

`ML2025054` has 59 aggregated extracted requirements. At this checkpoint it has zero persisted human confirmations, so it has **zero executable rules**. All 59 remain in the readiness assessment rather than being silently omitted. The decision UI therefore displays no operational timeline and explicitly states that this is not permission to operate.

Environmental feeds are not used as Belfast deciding evidence. Requirements classified as local sensor, AIS/GNSS, authority/manual, or unmapped remain external/manual/unsupported. Copernicus and Open-Meteo retain their predictive/supportive roles.

## Demonstration isolation

The Decision Intelligence tab contains an opt-in `ENGINE DEMONSTRATION — NOT AN OPERATIONAL AUTHORIZATION` action. It constructs in-memory rules with `TEST-FIXTURE-*` IDs and synthetic evidence; it does not read/write review decisions or associate data with Belfast. It demonstrates calendar restriction failure, threshold failure, and stale-evidence UNKNOWN with trace/provenance fields.

## Status vocabulary

Stage 4A deterministically emits `YES`, `STOP`, `RESUME`, and `UNKNOWN`. `NO` and `WARN` remain defined vocabulary values but have no implemented transition semantics and are intentionally not presented as supported results.

## Test result

The full suite is recorded in the implementation journal. UI/review/evidence isolation, trace rendering, administrative visibility, and rule safety gates have automated coverage.
