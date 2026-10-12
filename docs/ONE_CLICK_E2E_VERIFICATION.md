# One-click upload reliability verification

The automated regression fixture builds a sanitized four-page marine-permit PDF in a temporary directory. It contains a Part 2 conditions section, a continuation page, notification, geographic, and numeric wave requirements. It uses a mocked structured-response function: no permit contents or credentials are sent to OpenAI.

The test verifies PDF parsing, numbered-condition page discovery, per-page checkpointing, source quote verification, recovered aggregation, deterministic coverage auditing, manifest completion, and an offline rerun. On rerun, the request function raises if invoked, proving completed pages are resumed from cache rather than re-extracted.

The visible Streamlit acceptance check is deliberately non-destructive: it does not submit real review decisions, invoke an extraction, or load synthetic decision evidence. For a non-Belfast active permit, Environmental Intelligence now displays **DATA REQUIRED** and uses an empty site-matched view rather than Belfast cache data.

Remaining limitations: browser automation can validate the UI controls and rendered safety messages, but human review decisions and real environmental retrievals require deliberate operator action and are not performed by this fixture.
