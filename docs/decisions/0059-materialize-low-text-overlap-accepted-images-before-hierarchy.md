# ADR: Materialize Low-Text-Overlap Accepted Images Before Hierarchy

- 状态：accepted
- 日期：2026-05-21

## Context

M29.0.5 already emits large `image_asset` entries for product and banner images. M30, however, used `safe_visual_text_overlap_max=0.0` for all visual assets. That was correct for icons and small mixed visual candidates, but it blocked large accepted images with very small OCR overlap, such as roughly 0.7% to 1.6%.

The result was structurally wrong:

```text
large accepted image exists in evidence
-> M30 skips it as unsafe_text_overlap
-> final DSL has no independent image node
-> Figma cannot drag the image
-> M37/M38 have no node to group
```

This is not an OCR problem, not a `1/6` problem, and not an M38 grouping problem. The missing layer has to be materialized before hierarchy can do anything useful with it.

## Decision

Add M30.6 as an accepted image asset materialization policy inside M30.

Keep the old strict text-overlap rule for normal visual assets. Add a narrow bypass only for large `assetUse=image_asset` entries that:

```text
have decision candidate or accepted
have bbox area above M30_ACCEPTED_IMAGE_MIN_AREA
have textOverlapRatio <= M30_ACCEPTED_IMAGE_MAX_TEXT_OVERLAP
have no high-risk text or boundary flags
have an existing assetPath
resolve back to an original M29 image node id
```

When accepted, M30 emits a normal `m30_visual_asset` DSL image node, copies the existing M29.0.5 asset, records recovered lineage, and erases the same bbox from fallback pixels. It does not modify M29.0.5 assets in place.

The lineage resolver follows the current artifact chain:

```text
M29.0.5 sourceEvidenceNodeIds
-> M29.0.4 evidenceNodes
-> M29.0.3 accepted_image item
-> M29 sourceEvidenceId m29_image_NNN
-> raw M29 node id image_NNN
```

## Consequences

Benefits:

- Large product/banner images become independent Figma image layers.
- M37 can now see source ids such as `image_003` in M30 node metadata and direct-match them against M31 primitive refs.
- The implementation fixes the real missing-node problem before asking M38 to group anything.
- Icons and small visual assets remain protected by the existing strict rule.

Costs:

- M30 now has a second visual asset policy branch for accepted large images.
- Fallback erasure for image bboxes must sample outside the image bbox; sampling inside the bbox preserves the image pixels and leaves duplication.
- Some large media with text overlap above the threshold will still be skipped until a later, explicit cleanup stage exists.

Explicit non-goals:

- No OCR or OCR re-probe.
- No image-internal overlay recognition or promotion.
- No `1/6` recovery.
- No parent image asset cleanup.
- No M29/M31/M37/M38 mutation.
- No geometry-match relaxation in M38.
- No Auto Layout, vectorization, or Figma Component/Instance work.
