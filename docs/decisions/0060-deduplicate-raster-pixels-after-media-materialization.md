# ADR: Deduplicate Raster Pixels After Media Materialization

- 状态：accepted
- 日期：2026-05-21

## Context

M30.6 correctly materialized large low-overlap product images as independent `m30_visual_asset` nodes. That fixed image mobility, but exposed a second physical invariant: once text is a separate editable layer, the same text pixels must not remain baked into the raster layer underneath it.

Without this invariant:

```text
product image layer contains baked "穿搭"
editable text layer draws "穿搭" above it
user drags editable text
-> baked "穿搭" remains visible underneath
```

The carousel/banner problem is different. The current sample carousel is not a low-text-overlap accepted image asset. M29.0.5 classifies it as `partially_separated` composite media with high text overlap and a `combinedAssetPath`. Treating that as a normal accepted image would require loosening M30.6 and would pollute product-image safety. The correct model is a composite raster block: movable as one image, with internal art text preserved.

## Decision

Add M30.7 as two narrow M30 policies:

1. Clean editable text bboxes from already copied M30 media assets when the text bbox is almost fully contained inside the media bbox.
2. Materialize large M29.0.5 `partially_separated` objects with `combinedAssetPath` as `m30_composite_media_asset` image nodes.

Both policies run inside M30. No new runtime stage is added.

The copied image asset cleanup uses page-to-local pixel mapping and ring/edge background sampling, then fills the local bbox. It edits only M30 copied assets under `m30/assets/`, never M29.0.5 source assets.

Composite media materialization keeps internal image text baked into the raster. This is intentional: the first product goal is block mobility, not editable carousel title recovery.

## Consequences

Benefits:

- Product images and their editable text no longer duplicate the same raster pixels.
- Carousel/banner blocks can be selected and dragged as independent Figma image layers.
- M30 keeps the physical pixel ownership logic close to asset copying and fallback erasure.
- M37/M38 remain structural stages and do not gain pixel IO or relaxed matching rules.

Costs:

- M30 now edits copied raster assets after node materialization.
- Bbox-level fill can leave a simple local patch rather than perfect inpainting. That is acceptable for the first version and matches the existing fallback-erasure visual behavior.
- Composite media is movable but its internal title/art text is not editable in this phase.

Explicit non-goals:

- No OCR or OCR re-probe.
- No M29.4 image-internal overlay promotion.
- No `1/6` recovery.
- No parent image cleanup.
- No M29/M31/M37/M38 mutation.
- No M38 geometry-match relaxation.
- No glyph-level inpainting.
- No Auto Layout, vectorization, or Figma Component/Instance work.
