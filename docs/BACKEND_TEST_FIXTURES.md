# Backend test fixture classes

The backend suite distinguishes deterministic regressions from source-backed integration checks.

`regression` tests use checked-in fixtures or construct synthetic inputs in `tmp_path` and are safe to run in every CI job.

`source_backed` tests require authorized artifacts that are intentionally excluded by `.gitignore`, including:

- `cache/document_runs/<run>/candidate_aggregate.json` and `source.pdf`
- `cache/extractions/<run>/aggregate.json` and `coverage_audit.json`
- `cache/simple_analysis/<document_sha256>/<run>/analysis.json`
- `cache/historical/belfast/<year>/wave_*.json`, `era5_*.json`, `current_*.json`, and `sst_*.json`
- `cache/copernicus/*` and `cache/weather/*`

These checks must not be satisfied with fabricated source identity or provider provenance. In CI without the authorized artifacts they are reported as **NOT VERIFIED**, not passed or silently skipped. To run them, place the authorized cache snapshot at the paths above, verify its manifest/document hashes independently, then run `python -m pytest -m source_backed -q`.
