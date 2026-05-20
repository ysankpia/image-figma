# ADR: Weight Text Foreground Sampling By Contrast Not Count

- 状态：accepted
- 日期：2026-05-20

## Context

M36 sampled editable text color from source PNG pixels, but selected the largest RGB bucket after background filtering. That is wrong for small badges and media overlays: real text strokes can contain fewer pixels than local texture, shadow, or photo noise.

The primitive source remains the decoded PNG pixel field. The bug is the bucket selection target function, not OCR, editability classification, or hierarchy.

## Decision

Keep the M36 sampling pipeline, but choose the foreground bucket by contrast-weighted scoring:

```text
score =
  min(sqrt(count), 6.0)
  * rgb_contrast_factor
  * luminance_polarity_factor
  * luminance_delta_factor
```

Count is deliberately sublinear and capped. It prevents single-pixel noise from winning, but cannot dominate contrast and readability.

## Consequences

Benefits:

- Small high-contrast text strokes can beat larger low-contrast texture buckets.
- The algorithm stays grounded in source pixels and remains content-agnostic.
- M30 DSL, Renderer, plugin, and report contracts remain unchanged.

Costs:

- Foreground selection is slightly more computationally expensive per text bbox.
- The scoring is still a heuristic and does not attempt font or stroke-shape recognition.

Explicit non-goals:

- No OCR text filtering changes.
- No M31 hierarchy consumption.
- No graphic text reconstruction.
- No business-specific vocabulary or coordinates.
