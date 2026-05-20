# ADR: Sample Text Foreground Color From Source Pixels

- 状态：accepted
- 日期：2026-05-20

## Context

M30 materialized text used a single default color, `#111827`. That is legible on light backgrounds but fails on dark cards, colored buttons, and media overlays.

The primitive source of truth is the source PNG pixel field. If a text bbox is editable, its foreground strokes are the pixels inside the bbox that differ most from the local background.

## Decision

For emitted `m30_text_member` nodes, sample the dominant local background from bbox edges, then sample foreground pixels from the bbox interior.

Foreground sampling:

```text
clamp bbox to image bounds
shrink by 1px
filter pixels with RGB distance <= 64 from local background
bucket remaining pixels by RGB // 16
use dominant bucket average as text color
fallback to black/white contrast color when no foreground pixels are available
```

Record the source in node meta and M30 report summary:

```text
sampled_foreground
default_contrast
default_text_color_fallback
```

## Consequences

Benefits:

- Fixes dark-on-dark and gray-on-color text without changing DSL schema or Renderer.
- Keeps the decision grounded in source pixels.
- Applies only to text already considered editable.

Costs:

- M30 materialization now performs extra pixel reads per emitted text node.
- Complex antialiasing can still degrade to contrast fallback.

Explicit non-goals:

- No M31 hierarchy usage.
- No font recognition.
- No VLM classification.
- No reconstruction of preserved graphic text.
