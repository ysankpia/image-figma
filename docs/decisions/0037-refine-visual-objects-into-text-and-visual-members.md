# ADR 0037: Refine Visual Objects Into Text And Visual Members

## Status

Accepted.

## Context

M29.0.4 proves that generic visual object candidate audit can expose relationships among existing M29+ evidence without UI-pattern probes. The next problem is not detecting more UI. The problem is that an audit object crop can legitimately contain both visual and text members, while later reconstruction needs separate visual assets, text members, unresolved risks, and shape-like evidence.

Using M29.0.4 combined crops directly as production visual assets would duplicate text and make editable text recovery worse.

## Decision

Add M29.0.5 as a script-only text-aware visual object refinement harness:

```text
M29.0.4 VisualObjectCandidate
-> RefinedVisualObject
-> RefinedVisualAsset / ShapeCandidate / RefinedTextMember / UnresolvedMember
```

M29.0.5's refinement universe is only M29.0.4 objects and their members. M29.0.3 visual evidence and M29.0.2 text boxes are lookup refs only. It does not create new objects, does not detect new bboxes, does not call OCR providers, and does not modify upload APIs, DSL, Renderer, Figma output, or prior M29 artifacts.

All formal visual asset crops come from the original source PNG. Text masks may be used for overlap/risk/debug evidence only; erased, masked, inpainted, or synthesized pixels are never exported as formal visual assets.

## Consequences

- Combined object crops remain audit-only relationship evidence.
- Formal visual assets are separated from text members when existing member bboxes make that safe.
- Shape-like members become shape candidates rather than forced PNG image assets.
- Unsafe text/visual overlap remains explicit as unresolved evidence instead of being hidden by aggressive cropping.
- Split and wide-source evidence stays split-needed and cannot produce accepted child assets.
