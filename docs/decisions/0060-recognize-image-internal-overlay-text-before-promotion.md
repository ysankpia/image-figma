# ADR: Recognize Image Internal Overlay Text Before Promotion

- 状态：accepted
- 日期：2026-05-21

## Context

M29.3 establishes that an overlay belongs to a parent accepted image, but it does not know whether the overlay contains text, what the text says, or whether it is safe to promote. Promoting directly from ownership evidence would mix detection, recognition, cleanup, and materialization in one step.

## Decision

Add M29.4 as an audit-only recognition gate between M29.3 and any future M30 promotion.

M29.4 uses M29.2/M29.3 agreement, optional local OCR re-probe, and a narrow counter pattern:

```text
^[0-9]{1,2}/[0-9]{1,2}$
```

Matching items may be marked `promotion_ready`, but remain non-materialized.

## Consequences

Benefits:

- Keeps OCR recognition evidence separate from parent ownership evidence.
- Gives future M30 promotion a stable source contract.
- Avoids mutating OCR JSON, M29 nodes, M29.2, M29.3, M30 DSL, parent image assets, fallback erasure, M31, M37, or Renderer behavior.
- Keeps false positives low by limiting v1 recognition to image-internal counter overlays.

Costs:

- M29.4 does not make overlays editable.
- Real recognition requires explicitly enabling local re-probe, which may call the configured OCR provider.

Explicit non-goals:

- No parent image cleanup.
- No visible text layer creation.
- No business-word or coordinate-specific recognition.
