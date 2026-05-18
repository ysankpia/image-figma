# ADR 0039: Route Text-Owned Evidence Before Object Graph

## Status

Accepted.

## Context

M29.0.6 showed that M29.0.5 unresolved members are dominated by weak text-noise evidence. The root issue is not that M29.0.5 is too conservative. The issue is that text-like evidence can enter the M29.0.4 object-forming visual side, then later becomes unresolved because it should have been owned by OCR/text evidence.

Loosening text overlap thresholds or promoting weak evidence would pollute formal visual assets. Replacing pixels would create fake image assets and would still not solve object ownership.

## Decision

Add M29.0.7 as a script-only Text Ownership Gate. It consumes existing M29.0.3 visual evidence and M29.0.2 textBoxes, then emits ownership decisions and routing views:

```text
text_owned
visual_owned
shape_owned
mixed_or_uncertain
audit_only
```

M29.0.7 does not rewrite facts or produce a clean M29.0.4 document. It only recommends whether each existing evidence item may participate as object-forming visual side, text side, or audit-only evidence.

M29.0.4 may optionally consume `text_visual_ownership_gate.json`. Without that input, M29.0.4 remains baseline. With it, M29.0.4 attaches routing metadata by source id and requires `allowedForObjectFormingVisualSide=true` for visual-side object formation. Text-owned evidence can still be used as text side when allowed, preserving relationship evidence without treating text pixels as visual assets.

## Consequences

- Text-like weak visual evidence is blocked at the object-forming visual entrance.
- OCR/text evidence becomes the owner of text pixels when overlap and confidence support it.
- Real visual candidates are not suppressed solely because OCR overlaps them; high overlap becomes mixed/uncertain risk unless the source is text-noise.
- Image-internal text is recorded as overlay risk; no text-erased image is generated.
- M29.0.7 can be adopted incrementally because M29.0.4 baseline behavior is unchanged unless ownership JSON is supplied.
- Future regression should compare baseline M29.0.4 -> M29.0.5 -> M29.0.6 against the with-ownership chain, looking for lower weak text-noise unresolved ratios without collapse of successful visual assets.
