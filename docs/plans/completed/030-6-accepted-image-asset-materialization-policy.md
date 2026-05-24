# M30.6 Accepted Image Asset Materialization Policy

- 状态：completed
- 日期：2026-05-21
- 负责人：Codex

## Goal

M30.6 fixes the current blocking point for large product/banner images:

```text
M29.0.5 accepted image_asset
-> M30 skipped by safe_visual_text_overlap_max = 0.0
-> no DSL image node
-> nothing for Figma or M38 to move
```

The first version keeps M30 conservative for ordinary icon and visual assets, but allows large accepted image assets with very low text overlap and recoverable raw M29 lineage to become `m30_visual_asset` DSL image nodes.

This is an M30 materialization policy, not a new stage.

## Scope

Included:

- Add M30 accepted-image options and env variables.
- Let only large `assetUse=image_asset` entries bypass the old zero text-overlap rule.
- Recover lineage from M29.0.5 through M29.0.4 and M29.0.3 back to raw M29 image ids.
- Record recovered lineage in M30 image node meta for downstream M37 direct-match.
- Keep fallback image erasure for materialized image bboxes so dragged image layers do not reveal obvious duplicate pixels underneath.
- Add tests for low-overlap materialization, high-risk blocking, missing lineage blocking, small icon isolation, config, and upload report shape.

Excluded:

- No OCR.
- No image-internal overlay recovery.
- No `1/6` recovery.
- No parent image cleanup or cleaned asset generation.
- No M29/M31/M37/M38 artifact mutation.
- No new bbox detection.
- No M38 grouping policy change.
- No Auto Layout, vectorization, or Figma Component/Instance work.

## Policy

M30.6 applies only when all conditions are true:

```text
M30_ACCEPTED_IMAGE_MATERIALIZATION_ENABLED=true
assetUse == image_asset
decision in {candidate, accepted}
bbox area >= M30_ACCEPTED_IMAGE_MIN_AREA
textOverlapRatio <= M30_ACCEPTED_IMAGE_MAX_TEXT_OVERLAP
assetPath exists
risks do not contain high-risk text/boundary flags
lineage resolves to raw M29 image node id
```

High-risk flags remain blocking:

```text
contains_text
text_overlay_shape
text_touching_visual
high_text_overlap
unresolved_boundary
split_needed
```

Ordinary icon and visual assets still use the existing strict `safe_visual_text_overlap_max=0.0` rule.

## Lineage

The resolver follows the current repository artifact chain:

```text
M29.0.5 visualAsset.sourceEvidenceNodeIds[]
-> M29.0.4 evidenceNodes[].id
-> M29.0.4 evidence.sourceId
-> M29.0.3 items[].id
-> M29.0.3 item.sourceEvidenceId, such as m29_image_003
-> raw M29 node id, such as image_003
```

If any link is missing, the bypass is not used and the old skip behavior remains.

M30 image node meta records:

```text
sourceVisualAssetId
sourceEvidenceNodeIds
sourceM2904EvidenceNodeIds
sourceM2903ItemIds
sourceM2903SourceEvidenceIds
sourceM29NodeIds
m30AcceptedImageMaterialization
acceptedImageTextOverlapRatio
```

## Outputs

M30.6 does not create a new directory. It changes existing M30 outputs:

```text
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json
storage/m30_1_uploads/{taskId}/m30/m30_materialization_report.json
storage/m30_1_uploads/{taskId}/m30/assets/m30_visual_assets/*.png
```

The report summary includes:

```text
materializedAcceptedImageCount
```

Materialized image node reasons include:

```text
accepted_image_low_text_overlap
raw_m29_lineage_recovered
```

## Acceptance

- Low-overlap large accepted image assets become visible DSL `image` nodes with `role=m30_visual_asset`.
- The image node can be selected and dragged in Figma as an independent layer.
- Fallback image pixels under the materialized image bbox are erased using surrounding background sampling to avoid obvious duplication.
- High-overlap, high-risk, missing-lineage, and small icon assets are still skipped.
- M37/M38 keep their existing safe direct-match rules and report zero absolute-position drift.

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
