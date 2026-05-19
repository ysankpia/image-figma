# ADR: Use Conservative Text Cover Before Fallback Masking

- 状态：accepted
- 日期：2026-05-20

## Context

M30.1 routes plugin upload through OCR + M29 + M30 and successfully returns M30 DSL to the renderer. The visible issue is now layer quality: editable text is drawn above a full fallback image that still contains the original text, causing double text.

Removing or masking fallback globally would be premature. The current materialized layers do not yet prove that large fallback regions can be safely hidden without creating visual gaps.

## Decision

Add M30.2 conservative text cover inside M30 materialization. For each safely materialized text member, sample a stable background color from the existing text bbox area and insert a DSL `shape` node with role `m30_text_cover` below the editable text.

The cover uses existing text bboxes and source traces. It skips uncertain cases instead of guessing background fill.

## Consequences

Benefits:

- Reduces the most obvious text ghosting while preserving fallback stability.
- Uses existing DSL shape rendering; no schema or renderer change is needed.
- Keeps M29 evidence boundaries intact.

Costs:

- Some text remains uncovered when the background is complex or overlaps visual assets.
- Solid fill covers cannot match gradients or textured regions.

Hard boundaries:

- Do not hide fallback.
- Do not do region masking, image inpainting, or new detection.
- Do not modify M29 JSON or M29 classification rules.
- Do not create new formal visual assets.
- Do not emit mixed, future, or audit-only evidence as visible DSL children.
