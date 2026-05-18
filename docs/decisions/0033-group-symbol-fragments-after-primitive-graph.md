# ADR 0033: Group Symbol Fragments After Primitive Graph Evidence

## Status

Accepted.

## Context

M29 proved the `PNG -> visual primitive graph` axis, but connected components can split one visual object into several fragments. Search, cart, location, plus, badge, and icon-button patterns are often multiple disconnected pieces. Direct SVG/Figma replay on those fragments would preserve half-assets instead of editable visual objects.

M29.0.1 upgraded blocked evidence so M29.1 can consume rejected fragments without becoming a second detector.

## Decision

M29.1 adds a script-only symbol fragment grouping harness after M29:

```text
M29 accepted symbols + eligible blocked fragments -> grouped symbol candidates
```

It requires `meta.blockedEvidenceVersion=0.2`, builds a fragment edge audit, groups only high-confidence fragment clusters, exports accepted grouped symbol assets, and preserves original M29 nodes/assets unchanged.

M29.1 does not rerun detection, does not scan the whole image for new components, does not connect OCR/SAM2/SVG/Figma/DSL, and does not enter the upload pipeline.

## Consequences

- Half-symbol and fragmented icon evidence can be diagnosed before SVG/vectorization.
- Edge audit explains both accepted and rejected grouping decisions.
- Original M29 output remains the lower-level truth; M29.1 is an additive evidence layer.
- OCR text masking, SVG vectorization, layout reconstruction, and Figma replay remain later phases.
