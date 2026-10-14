# PermitPulse MVP baseline frozen — 2026-10-14

Fresh Analyze and Environmental Intelligence are frozen at this backup.
F04 Human Review and F09 deterministic decision engine remain design-only;
their proposed implementation is not part of this accepted baseline.

Accepted immutable analysis: `b76a0adc67e341fe8b810834fe78bc7d`.
Document SHA-256: `0a665f53ba058e48da31f094723f6e3af679699d5a1cea3658a66f4b8d96b585`.
Authoritative environmental candidates: 7, 20, 24–41.
Deterministic replay: 20 requirements, 11 Copernicus variables, 6 ECMWF
variables, 0 ERA5 variables, 2 unique external-evidence variables.

Preserved safeguards include one extraction request, fail-closed completeness,
source verification/reconciliation, explicit environmental Fetch, hourly
precipitation accumulation semantics, oxygen depth safeguards, unsupported SSH,
and strict FNU/NTU separation. Evidence does not authorize operations.

Last reported offline checks: normalization 20 passed; environmental
completeness 16 passed; environmental suite 57 passed with the known hanging
TestClient test excluded; relevant permit tests 4 passed; compilation and
git diff --check passed. These are recorded results, not a new test run.

Git backup contains application source, tests, documentation and branding.
Credentials, dependency installations, generated bundles, private permit PDFs,
runtime logs and cached analysis/provider artifacts remain local and are not
included in the GitHub backup. Existing persisted artifacts are unchanged.
