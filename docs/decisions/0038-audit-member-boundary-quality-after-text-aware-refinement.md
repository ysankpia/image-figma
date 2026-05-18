# ADR 0038: Audit Member Boundary Quality After Text-Aware Refinement

## Status

Accepted.

## Context

M29.0.5 is stable and conservative. Batch smoke over mobile screenshots shows that it can consume M29.0.4 outputs, but it also exposes many unresolved members and duplicate visual assets. The dominant unresolved cause is not formal visual assets being blocked by OCR text boxes; it is weak visual text-noise evidence being repeatedly consumed by the M29.0.4 object/member graph.

Reducing unresolved by loosening M29.0.5 thresholds or upgrading weak visual evidence would pollute the formal visual asset layer.

## Decision

Add M29.0.6 as an audit-only member boundary quality harness. It diagnoses why M29.0.5 could not safely separate members by auditing unresolved attribution, weak text-noise dominance, source/member duplication, duplicate visual assets, split/wide evidence, shape text overlays, and a success baseline.

M29.0.6 may inspect pixels for hash, top-K examples, and overlays. It must not create new object/bbox/formal visual assets, repair prior M29 outputs, delete or merge duplicate assets, or enter DSL/Figma/Renderer.

## Consequences

- M29.0.5 remains conservative and does not become a detector.
- Unresolved counts become explainable with raw and dedup counts.
- Duplicate source/member topology is separated from visual asset duplicate audit.
- Suggested upstream layers are evidence with confidence, not automatic repair actions.
- Future fixes can target M29.0.2, M29.0.3, M29.0.4, M29.1, or asset dedup only after attribution is clear.
