# ADR: Clean Text-Symbol Leakage With Projection Gap Before Materialization

- 状态：accepted
- 日期：2026-05-20

## Context

OCR can classify a small UI icon as a text glyph. The observed case is a magnifier-like icon becoming leading `Q` inside an otherwise editable text member. If M30 emits that text unchanged, Figma shows a bogus character and fallback erasure can remove the original icon pixels.

M31 runs before M30, so M30 must not create a symbol bbox and feed it back into M31. The correct local fix is to clean the emitted text and shrink the emitted text bbox.

## Decision

M30 performs a conservative M34.3 cleanup only for editable text:

```text
leading uppercase Q
+ projection gap between left ink group and right text ink group
-> trim Q and emit cleanedBBox
```

The fallback erasure function is not changed. It already consumes `M30MaterializedNode.bbox`, so using `cleanedBBox` naturally preserves the protected symbol pixels outside the text bbox.

## Consequences

Benefits:

- Fixes bogus leading symbol text without changing OCR/M29/M31.
- Keeps icon pixels in fallback without adding visible icon layers.
- Keeps the decision auditable in M30 report/meta.

Costs:

- First version intentionally covers only high-confidence uppercase leading `Q`.
- Other symbol-like leakage classes remain future review items.

Explicit non-goals:

- No M31 backflow.
- No icon recovery or vectorization.
- No business-specific words, page coordinates, or app-specific rules.
