# ADR: Context-Aware UI Text Editability With Generic Geometry

- 状态：accepted
- 日期：2026-05-20

## Context

M34.1 preserved OCR text evidence and moved text materialization into M30. That fixed the source-truth loss, but the first editability policy remained too local:

```text
single OCR angle >= threshold -> preserve
text overlaps visual asset -> preserve
```

Those are useful risk signals, not final decisions. OCR angle can contain measurement noise, and image overlap cannot distinguish photo text from UI overlay text.

The primitive fact is:

```text
UI text editability is a reconstruction decision from visual context.
```

## Decision

Keep OCR/M29/M31 evidence unchanged. In M30 text editability, add generic geometry counter signals:

```text
aligned_text_row
compact_overlay_badge
metadata_text_cluster
stable_local_background
```

These signals use relative bbox geometry, local pixel measurements, and existing M29.0.5 text/visual members. They must not inspect business words, page identity, fixed coordinates, or fixed viewport-specific pixel constants.

M30 report records both:

```text
metrics.preserveSignals
metrics.editableCounterSignals
```

The final decision remains one of:

```text
editable_text
graphic_text_preserve_in_fallback
review_text
```

## Consequences

Benefits:

- Reduces false-positive preservation of ordinary UI chrome and overlay badge text.
- Keeps graphic text protection from M34.1 intact.
- Makes the decision auditable by showing both negative signals and counter signals.
- Avoids business-specific rules.

Costs:

- M30 materialization now carries more geometry policy.
- Some visual/icon recovery remains out of scope; nearby small icons may stay in fallback until later layer recovery stages.

Explicit non-goals:

- No text content matching.
- No font recognition.
- No handwritten text reconstruction.
- No VLM classification.
- No inpainting.
- No icon or location-pin layer recovery.
- No DSL schema or renderer change.
