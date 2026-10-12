# Universal structure-to-obligation mapping

The deterministic layer stores sections, clauses, schedules, tables, source spans, and explicit references before any AI extraction. It produces review-required candidates only; it never creates a legal rule, confirmation, threshold interpretation, or evidence value.

Tables are represented as source nodes and continuation links. Layout-derived rows/cells are intentionally not inferred from plain text when headers or cell boundaries are ambiguous; those spans remain `INTERPRETATION_REQUIRED`. Incorporated plans are `EXTERNAL_DOCUMENT_REQUIRED` unless the source document is supplied.

The layout layer uses detected PDF vector tables and records cell geometry. It does not copy values across merged or empty cells without source-supported layout evidence.

## AI-first execution boundary

The universal structural inventory is supporting evidence, not an ingestion
gate. `src.documents.ai_first` batches every physical page, checkpoints each
mocked/live transport result independently, and persists a document-wide
coverage manifest. Candidate discovery accepts generic permits and contracts;
deterministic verification validates source quotation/provenance and preserves
unresolved candidates for human review. It does not create `ExecutableRule`
objects or alter the downstream permit and contract specialisations.
