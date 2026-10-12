# Stage 1 Full Document Coverage Audit

The 14-page ML2025054 source contains 31 explicitly numbered licence conditions. Deterministic page and condition-number review found that the original keyword filter selected pages 4–10 and omitted physical page 3, which contains conditions 1–9 and the beginning of condition 9.

| Status | Source conditions |
| --- | ---: |
| CAPTURED | 19 |
| PARTIALLY_CAPTURED | 1 |
| REJECTED RECOVERY | 10 |
| NOT EXTRACTED | 1 |
| REVIEW REQUIRED overlay | 4 |

## Coverage gaps

The numbered-condition page gate recovered page 3 without reprocessing completed pages. Conditions 2, 3, 4 and 8 now have validated source-backed records; conditions 1, 5, 6, 7 and 9 are retained recovery items after schema rejection. Condition 9 remains an AIS/positioning stop-work requirement and must become EXTERNAL_DATA_REQUIRED only after structured recovery. Condition 10 remains missing: the prior page-4 response did not extract the UKHO notification requirement and is preserved rather than silently overwritten. Conditions 17, 18, 19, 22 and 23 are also recovery items. Condition 20 is partially captured: its local SPM/DO thresholds are present, but the real-time monitoring-station capability clause needs review.

Deterministic recovery now supplies source-backed candidates for every numbered condition, including the UKHO notification in condition 10 and AIS stop-work obligation in condition 9. These candidates remain unconfirmed and therefore cannot create executable rules or convert missing evidence into a PASS. Condition 20's station-capability candidate remains separate from the local-monitoring threshold rules.

## Stage 7 condition 20 reconciliation

Condition 20 is now `CAPTURED`, not `PARTIALLY_CAPTURED`. The previous state was stale: it predated aggregate inclusion of the separately recovered, exact-quote-verified `recovery-20_station` capability obligation. The obligation matrix is: monitoring station real-time monitoring/reporting capability (`recovery-20_station`, LOCAL_SENSOR / EXTERNAL_DATA_REQUIRED); suspended solids 300 mg/l for six hours plus 600 mg/l instantaneous (`20a`); suspended-solids stop behaviour (`20c_stop`); dissolved oxygen 4 mg/l minimum (`20d`); and dissolved-oxygen stop/resume behaviour (`20e_stop`). All originate on PDF page 5, retain source provenance, and remain unconfirmed/non-executable.
