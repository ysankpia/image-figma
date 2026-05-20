# ADR: Bind Image Internal Overlays Before Materialization

- 状态：accepted
- 日期：2026-05-21

## Context

Accepted image regions can contain real UI overlays such as counters, badges, or icons. If the whole region remains a single bitmap owner, downstream stages cannot tell which pixels belong to the base image and which are overlay evidence.

Mask carve-outs are not enough. They rely on later detectors to rediscover pixels and lose the parent image ownership link.

## Decision

Add M29.3 as an audit-only image internal overlay ownership stage:

```text
source PNG + OCR boxes + M29 nodes + M29.0.2 accepted images
-> parent-bound image internal overlays
-> report only
```

Each overlay records the accepted image parent, original M29 image node when available, bbox, anchor, decision, kind, OCR de-duplication, and metrics. It remains non-materialized.

## Consequences

Benefits:

- Preserves parent-child ownership before any future text or symbol promotion.
- Avoids mutating OCR JSON or M29 nodes.
- Keeps M30, fallback erasure, M31, M37, Renderer, and visible Figma output unchanged.
- Gives later supplemental materialization a safer source contract.

Costs:

- First version still does not make tiny overlays editable.
- It duplicates some M29.2 detection mechanics because the output contract is different.

Explicit non-goals:

- No string recognition.
- No OCR re-probe.
- No visible layer creation.
- No business-specific rules or fixed coordinates.
