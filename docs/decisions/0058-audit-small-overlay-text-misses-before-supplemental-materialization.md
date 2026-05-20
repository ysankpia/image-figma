# ADR: Audit Small Overlay Text Misses Before Supplemental Materialization

- 状态：accepted
- 日期：2026-05-20

## Context

Global OCR can miss tiny overlay counters inside image cards. The pixels still exist in the fallback image, but they are not available as OCR text evidence and therefore cannot become editable M30 text.

The wrong fix would be to let M29 invent text, patch `ocr.json`, or feed new boxes directly into M30. That would mix detection, recognition, and materialization in one step and would make the current one-way evidence pipeline harder to audit.

## Decision

Add M29.2 as an audit/proposal layer:

```text
accepted image evidence
+ source PNG pixels
+ existing OCR boxes
-> small overlay text candidates
-> optional local crop OCR re-probe
-> report only
```

The first detector is intentionally conservative. It looks for small high-contrast component groups near accepted image edges, dedupes existing OCR, and treats local re-probe as diagnostic evidence. The local recognition gate only accepts generic counter-shaped strings such as `^[0-9]{1,2}/[0-9]{1,2}$`.

M29.2 is enabled by default in the upload pipeline, but local OCR re-probe is disabled by default.

## Consequences

Benefits:

- Makes OCR-missed small overlay text auditable without changing visible output.
- Preserves the boundary between pixel proposal, OCR recognition, and future materialization.
- Keeps production artifacts small while retaining development overlays and crops when requested.
- Keeps failures non-blocking unless strict mode is explicitly enabled.

Costs:

- First version favors bright text on darker overlay badges and intentionally does not solve every text polarity.
- Recognized local text remains report-only until a later supplemental materialization stage defines its contract.

Explicit non-goals:

- No OCR JSON mutation.
- No M29 nodes mutation.
- No M30 text node creation.
- No fallback erasure change.
- No M31/M37 pollution.
- No business-specific vocabulary or fixed-coordinate rules.
