# Layout-aware table reconstruction

The reconstruction layer uses PyMuPDF 1.28 `Page.find_tables()` and preserves detected cell bounding boxes, row/column index, header text, continuation links, and ambiguity status. No extra dependency was required.

`VERIFIED_STRUCTURE` requires detected non-empty headers and rows with cell geometry. `PARTIAL_STRUCTURE` and `STRUCTURE_REVIEW_REQUIRED` are never suitable for later AI interpretation. Repeated headers become continuations only when the header sequence matches exactly. Missing/merged headers are reported rather than propagated.

Hinkley Schedule 3 Table S3.1 is a stress target: it must be reconstructed page-by-page before any row-level semantic interpretation. Distinct waste streams, periods, percentiles, and operating modes are retained as separate source cells.

## Hinkley real-document validation

The local Hinkley audit detected 39 physical PyMuPDF table objects. The Schedule 3 Table S3.1 objects occur on pages 21-31; S3.2 is page 32; S3.3 pages 33-34; S4.1 pages 35-40; and S4.2 pages 40-41. S1.1-S1.4 occur on pages 11-18. All operational table objects are `PARTIAL_STRUCTURE`: their first detected row is a title row with merged/blank header cells. This is intentional conservative handling, not a parser success claim. No Schedule 3 row is suitable for AI interpretation until column/header association is verified from layout.
