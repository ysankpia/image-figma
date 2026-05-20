# ADR: Preserve OCR Text Evidence Before Materialization Decision

- 状态：accepted
- 日期：2026-05-20

## Context

M34 introduced OCR angle/polygon metadata and tried to stop artistic or rotated text from becoming bad Figma text layers. The useful part was the evidence metadata. The wrong part was the timing: the upload pipeline dropped risky OCR text boxes before M29.

That made the system lose source truth. M29 and M31 could no longer audit those text boxes, and M30 could not explain whether text was skipped because it was absent, invalid, or intentionally preserved in fallback.

The primitive fact is:

```text
OCR text block = evidence that text pixels exist
Figma text layer = materialization decision
```

Those are different contracts.

## Decision

Do not delete graphic or rotated OCR text boxes before M29.

All OCR text evidence remains available to M29/M31/M29.0.2. M30 materialization performs a separate text editability decision:

```text
editable_text
graphic_text_preserve_in_fallback
review_text
```

Only `editable_text` becomes visible `m30_text_member`. Preserved graphic text and review text stay in fallback, are reported, and are not passed to fallback erasure.

`OCR_ARTISTIC_TEXT_FILTER_ENABLED` remains only as a legacy alias for the new preserve behavior. New active configuration uses:

```text
OCR_TEXT_EDITABILITY_ENABLED
OCR_GRAPHIC_TEXT_PRESERVE_ENABLED
```

## Consequences

Benefits:

- OCR/M29/M31 evidence chain stays auditable.
- M30 can explain why a text item was not materialized.
- Graphic text in media-heavy or stylized regions is not erased and redrawn with a generic font.
- Plain UI text remains editable.

Costs:

- M30 report becomes larger because it carries text editability diagnostics.
- The default policy is conservative; some text that could technically be edited may remain in fallback until later reconstruction validation exists.

Explicit non-goals:

- No font recognition.
- No handwritten text reconstruction.
- No VLM classification.
- No inpainting.
- No DSL schema or renderer change.
- No M32/M33/M34 redesign in this stage.
