# ADR 0036: Generic Visual Object Candidates After Evidence Normalization

## Status

Accepted.

## Context

M29 established the `PNG -> visual primitive graph` direction. M29.1 groups symbol fragments, M29.0.2 separates text noise from media evidence, and M29.0.3 normalizes all seen media-like evidence into stable buckets. The remaining problem is not a specific UI pattern such as bottom navigation. The problem is that visible evidence can be scattered across visual buckets, text noise, wide sources, and grouped fragments without a generic object-candidate graph explaining how evidence relates.

The old M20-M28 path used UI-pattern probes such as bottom-nav and shortcut-specific candidates. Continuing that pattern would reintroduce brittle business/region rules.

## Decision

Add M29.0.4 as a script-only Generic Visual Object Candidate Audit harness after M29.0.3:

```text
M29.0.3 VisualEvidenceItem + M29.0.2 textBoxes
-> evidence nodes
-> evidence edges
-> VisualObjectCandidate
-> VisualObjectSetCandidate
-> edge audit / preview
```

M29.0.4's candidate universe is only M29.0.3 items plus M29.0.2 text boxes. M29 nodes, blocked evidence, M29.1 groups, and M29.0.2 mediaEvidence may be used for lookup/debug only and do not create candidates directly.

M29.0.4 does not introduce UI-pattern-specific contracts, does not crop accepted child objects from wide source bboxes, does not reclassify upstream `text_noise`, and does not change upload APIs, DSL, Renderer, Figma output, or prior M29 artifacts.

## Consequences

- Visible evidence can be reviewed as generic object candidates instead of hidden in source buckets.
- Wide or incomplete source evidence is represented as `split_candidate` instead of silently accepted or locally re-detected.
- `text_noise` can remain upstream noise while still serving as weak visual evidence when geometry supports review.
- Edge audit explains accepted, weak, and rejected relationships, making candidate grouping debuggable.
- M20-M28 UI probe concepts remain legacy references and are not reintroduced into M29+ contracts.
