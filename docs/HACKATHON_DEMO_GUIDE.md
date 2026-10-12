# PermitPulse Hackathon Demo Guide

## Start reliably

Install dependencies, then run `python scripts/pre_demo_verify.py`. Start with `streamlit run app.py`. The app is cache-first; this demo does not require network access once its stored artifacts are present.

## Five-minute sequence

1. **Permit Operations:** show the Belfast aggregate, a source quotation/page, coverage gaps and the recovery queue. Explain that confirmation is required and quote-unverified requirements are gated.
2. **Environmental Intelligence:** show cached Copernicus/ECMWF series, grid representativeness, freshness and advisory-only windows. Missing evidence is not favourable evidence.
3. **Permit Decision Intelligence:** show the real review-pending state, then run the isolated `TEST-FIXTURE` demonstration. It cannot alter Belfast records.
4. **Marine Contract Weather Intelligence:** load the labelled demo contract, show clause review, then describe forecast analysis as non-legal advisory intelligence only.
5. Select an out-of-horizon project period to show the historical-mode selection and cached genuine ERA5/Copernicus April source slices. State prominently that it is **NOT A FORECAST**.

## If internet is unavailable

Use existing caches only. Do not click retrieval controls. If a cache is absent/stale, present its visible unavailable/stale warning; do not claim a successful live response. The pre-demo script reports exactly which required artifacts are missing.

## Known limits

The Belfast coverage gate retains one partial source-condition finding; human permit review is outstanding. No live AIS, local sensor, laboratory, or deciding evidence integration exists. Historical Belfast current/SST subsets are masked; historical cache is limited to three 72-hour April source slices and is not climatology.
