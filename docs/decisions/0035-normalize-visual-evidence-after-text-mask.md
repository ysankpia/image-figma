# ADR 0035: Normalize Visual Evidence After Text Mask

## Status

Accepted.

## Context

M29 established the correct `PNG -> visual primitive graph` direction, and M29.0.2 showed that Paddle/text masks can separate a large amount of text noise from media evidence. The remaining problem is not that many visible pictures/icons are unseen. They are often present as `m29_blocked`, `m29_symbol`, `m29_unknown`, or `m291_group`, but the source label is being mistaken for the final decision.

Lowering M29 image thresholds directly would make text, prices, badges, and UI fragments leak into accepted image output.

## Decision

Add M29.0.3 as a script-only Visual Evidence Normalization harness after M29.0.2:

```text
M29.0.2 mediaEvidence -> VisualEvidenceItem -> accepted/candidate/noise buckets
```

Every M29.0.2 evidence item is preserved exactly once and receives an original-source crop. `source` remains provenance only; `visualKind` and `decision` carry the current judgment.

M29.0.3 does not change M29 `nodes.json`, M29.1 `group_nodes.json`, upload APIs, DSL, Renderer, or Figma output.

## Consequences

- Visible objects that were already detected no longer disappear because their source bucket was `blocked` or `symbol`.
- Text noise becomes an explicit `text_noise` bucket instead of being deleted or mixed into primary media review.
- Media/image promotion can be tuned against a stable evidence layer before any future main-pipeline migration.
- M20-M28 remain historical experiments; M29+ evidence is the new source for visual reconstruction work.
