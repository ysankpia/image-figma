# Bug: Residual media overlays foreground claims

- 状态：resolved
- 创建日期：2026-05-27
- 修复日期：2026-05-27
- 影响范围：M29.5 replay plan layer order, plan-driven materializer output

## Summary

Model-first source ownership can correctly promote a media-contained control background, but the parent residual media image can still render above the foreground shape. The visible result is a washed-out or hollow control: cleanup removes pixels from the residual asset, then that residual asset covers the newly replayed foreground node.

## Reproduction

1. Upload `/Users/luhui/Downloads/城邦图/修好/ChatGPT Image 2026年5月25日 18_43_05 1.png`.
2. Inspect `backend/storage/upload_previews/task_89e156fcbbb0/m29_perception_fate_trace/perception_fate_trace_report.json`.
3. Confirm `perception_candidate_0002` is compiled as `m292_perception_control_0002`, replayed as `m29_shape_0004`, and cleaned from parent media `m292_object_0072`.
4. Inspect `materialized_design/design.dsl.json`: `m29_shape_0004` appears before `m29_image_0040`, so the residual media image overlays the foreground button shape.

## Root Cause

M29.5 used a fixed action sort order:

```text
shape_replay -> image_replay -> icon_replay -> text_replay
```

That order was valid for ordinary background shapes under full-raster media, but it is wrong for residual media ownership. When a foreground claim has a copied-image cleanup target or source evidence pointing to a parent media/control source object, the parent residual replay must be below the foreground claim.

## Fix

Replace the final fixed action-only layer ordering with dependency-aware ordering:

```text
parent residual media/control replay -> foreground claim replay
```

The dependency source is M29.5's own contract:

- `cleanupTargets[].target == copied_image_asset`
- `cleanupTargets[].targetSourceObjectId`
- `sourceEvidence.mediaSourceObjectId`
- `sourceEvidence.parentControlSourceObjectId`
- `sourceEvidence.foregroundClaimId`

No file name, visible text, task id, fixed bbox, theme color, or sample-specific rule is allowed.

## Regression Guard

Added regressions:

- `tests/test_m29_replay_plan.py::test_m295_residual_media_is_ordered_below_foreground_claims`
- `tests/test_m29_plan_materializer.py::test_residual_media_plan_order_keeps_foreground_shape_above_parent_image`

These prove the final plan/DSL order places parent residual media before foreground shape/text, using M29.5 ownership dependency rather than action type or sample-specific matching.

## Validation Evidence

Targeted:

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py -q
# 51 passed

uv run pytest tests/test_perception_source_compiler.py tests/test_m29_perception_fate_trace.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py -q
# 96 passed
```

Real sample:

```bash
cd backend
UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /tmp/m29-residual-layer-order-sample.Ln0uOm \
  --poll-timeout 300
```

Result:

```text
taskId=task_c946c53cb1be
completedTaskCount=1
backendCrashCount=0
missingArtifactCount=0
ownershipConflictCount=0
```

Artifact check:

```text
m29_image_0036 [290,107,1365,111]
-> m29_shape_0036 [1479,136,144,50]
-> m29_text_0012 [1500,147,102,24]
```

The parent residual media now renders below the promoted foreground button and its text.

## Prevention Notes

Layer order must come from ownership dependency, not action type. Residual media is a background owner for claimed foreground pixels, not an overlay that can cover its own promoted children.
