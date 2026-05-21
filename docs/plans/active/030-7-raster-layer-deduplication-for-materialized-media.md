# M30.7 Raster Layer Deduplication For Materialized Media

- 状态：active
- 日期：2026-05-21
- 负责人：Codex

## Goal

M30.7 fixes two physical layer problems exposed after M30.6:

```text
copied product image asset still contains baked text
+ editable M30 text node renders above it
-> dragged text reveals duplicate text inside product image
```

and:

```text
large carousel/banner is M29.0.5 partially_separated composite media
-> no M30 image node
-> Figma cannot select or drag the carousel as a block
```

M30.7 is an internal M30 materialization policy. It does not add a runtime stage.

## Scope

Included:

- Clean editable text bboxes from M30 copied `m30_visual_asset` PNGs when the text is almost fully contained by the image bbox.
- Keep the upper `m30_text_member` nodes visible and editable.
- Materialize large M29.0.5 `partially_separated` composite media objects with `combinedAssetPath` as `role=m30_composite_media_asset` image nodes.
- Reuse existing fallback image erasure so fallback gives way under product images and composite media.
- Report materialized composite count, cleaned copied-image count, erased text bbox count, and skipped composite count.
- Add tests for pixel deduplication, external text isolation, composite materialization, safety skips, config, and upload report shape.

Excluded:

- No OCR or OCR re-probe.
- No M29.4 image-internal overlay promotion.
- No `1/6` recovery.
- No parent image cleanup stage.
- No M29/M31/M37/M38 artifact mutation.
- No M38 geometry-match relaxation.
- No glyph-level inpainting.
- No Auto Layout, vectorization, Figma Component/Instance, or card grouping policy change.

## Policies

### Materialized Image Text Erasure

M30.7 runs after M30 has appended image/text nodes and before report writing. It only edits M30 copied assets, never M29.0.5 source assets.

The first version erases a text bbox from a copied image asset when:

```text
M30_IMAGE_ASSET_TEXT_ERASURE_ENABLED=true
image role in {m30_visual_asset, m30_composite_media_asset}
text role == m30_text_member
text bbox containment inside image bbox >= 0.98
asset URL is a local M30 copied PNG
```

The text page bbox is mapped to image-local pixels using `scaleX/scaleY` when the copied asset dimensions differ from DSL layout dimensions. The local bbox is filled with a sampled ring or edge background color. If sampling fails, M30 uses the same conservative fallback color used by existing fallback erasure and records a warning.

### Composite Media Materialization

M30.7 adds `append_composite_media_nodes` after `append_image_nodes`.

The first version accepts an object only when:

```text
M30_COMPOSITE_MEDIA_MATERIALIZATION_ENABLED=true
decision == partially_separated
combinedAssetPath exists
bbox is valid and area >= M30_COMPOSITE_MEDIA_MIN_AREA
risks do not contain split_needed or wide_source
no high-IoU duplicate image asset is already materialized
```

The output node is:

```text
type = image
role = m30_composite_media_asset
sourceKind = m2905_composite_media_object
```

Composite media keeps its baked internal title/art text in the image. It is materialized as one movable raster block.

## Outputs

M30.7 changes existing M30 outputs:

```text
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json
storage/m30_1_uploads/{taskId}/m30/m30_materialization_report.json
storage/m30_1_uploads/{taskId}/m30/assets/m30_visual_assets/*.png
storage/m30_1_uploads/{taskId}/m30/assets/m30_composite_media_assets/*.png
```

Report summary fields:

```text
materializedCompositeMediaCount
cleanedMaterializedImageAssetCount
erasedTextFromMaterializedImageAssetCount
skippedCompositeMediaCount
```

## Acceptance

- Product images remain independent `m30_visual_asset` image nodes.
- Text such as `穿搭 / 探店 / 1/9 / 旅行 / 美妆` remains upper editable `m30_text_member`.
- Dragging those text nodes no longer reveals baked duplicate text inside the product image asset.
- Carousel `[18,236,817,241]` becomes an independent `m30_composite_media_asset` image node.
- Carousel internal art text stays baked in the composite image for this phase.
- Fallback does not show obvious product image or carousel duplication.
- M37/M38 keep zero absolute-position drift and do not move `fallback_region` or `original_reference`.

## Verification

```bash
cd backend
uv run pytest \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_m30_upload_pipeline.py \
  tests/test_m37_hierarchy_readiness.py \
  tests/test_hierarchy_materialization.py \
  tests/test_config_env.py -q
cd ..
pnpm run check
git diff --check
```
