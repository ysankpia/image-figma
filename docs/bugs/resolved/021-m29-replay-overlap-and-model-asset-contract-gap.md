# Bug: M29 Replay Overlap And Model Asset Contract Gap

- 状态：resolved
- 创建日期：2026-05-28
- 解决日期：2026-05-28
- 影响范围：M29.5 replay duplicate suppression, plan materializer icon asset selection

## Summary

Claude model-first audit identified two contract gaps in the active M29 mainline:

1. `plan_materializer/replay.py` does not allow `perception_model_foreground_claim` to use an existing `transparentAssetPath`, even though M29.5 cleanup/overlap and ownership conservation already treat that promotion source as valid foreground provenance.
2. `m29_replay_plan/overlap.py` uses the same `0.20` containment threshold for same-action `icon_replay` and `shape_replay`, which can suppress real adjacent foreground objects as duplicates.

## Reproduction

Code facts:

```text
backend/app/plan_materializer/replay.py::transparent_asset_path_for
backend/app/m29_replay_plan/overlap.py::should_suppress_visible_overlap
```

Risk scenario:

```text
two real adjacent small icon/marker source objects have ordinary overlap from bbox drift
-> M29.5 marks one suppress_duplicate
-> final DSL misses a selectable foreground object
```

Asset scenario:

```text
perception model source object has transparentAssetPath
-> materializer rejects its promotionSource
-> icon falls back to raw crop instead of existing transparent asset
```

## Root Cause

The replay/materializer layers have source provenance contracts that drifted after the model-first pivot:

- M29.5 overlap/cleanup recognizes `perception_model_foreground_claim`.
- Materializer transparent asset selection only recognizes legacy M29.6 foreground sources.
- Same-action overlap suppression asks only “is smaller-box containment >= 0.20?” instead of “are these source objects the same visual entity?”

This is a contract bug, not a model detection bug and not a Renderer/Figma plugin bug.

## Fix

Implemented fix:

- `plan_materializer/replay.py` now treats `perception_model_foreground_claim` as a valid transparent-asset provenance when M29.5 already carries an existing `transparentAssetPath`.
- Missing or nonexistent transparent assets still fall back to source crop; the materializer does not create source objects, assets, cleanup authorization, or replay permission.
- M29.5 same-action overlap suppression now uses source-role-aware duplicate evidence:
  - `near_equal` remains a strong duplicate signal;
  - high IoU duplicates are suppressed;
  - near-full containment of compatible same-role/source objects is suppressed;
  - ordinary adjacent icon/shape/marker overlap is preserved.
- Ownership conservation diagnostics now use the same duplicate contract as replay planning, so accepted adjacent foreground overlaps are not reported as false visible ownership conflicts.

## Regression Guard

Covered tests:

- `test_model_foreground_icon_uses_existing_transparent_asset`
- `test_model_foreground_icon_falls_back_to_crop_when_transparent_asset_is_missing`
- `test_m295_keeps_adjacent_small_icons_with_partial_bbox_overlap`
- `test_m295_suppresses_high_iou_same_icon_duplicate`
- `test_m295_keeps_adjacent_markers_with_partial_bbox_overlap`
- `test_adjacent_icon_overlap_accepted_by_replay_plan_is_not_reported_as_conflict`
- `test_high_iou_same_icon_overlap_is_still_reported_as_conflict`

## Validation Evidence

Targeted regression:

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py tests/test_m29_perception_fate_trace.py -q
```

Result:

```text
89 passed
```

Representative model-first batch:

```bash
cd backend
UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/m29 \
  --poll-timeout 300
```

Evidence ledger:

```text
backend/tmp/validation/upload_preview_batch_20260527_180306_969454_35407/upload_preview_batch_validation.json
```

Summary:

```json
{
  "inputCount": 16,
  "completedTaskCount": 16,
  "failedTaskCount": 0,
  "backendCrashCount": 0,
  "totalVisibleReplayClaimCount": 2196,
  "totalVisibleOwnershipOverlapConflicts": 0,
  "totalMaterializedVisibleNodeCount": 2196,
  "ownershipConflictTypeCounts": {}
}
```

Hard regression sample:

```bash
cd backend
UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/storage/uploads/task_4e22c557223a \
  --poll-timeout 300
```

Evidence ledger:

```text
backend/tmp/validation/upload_preview_batch_20260527_181106_297892_45198/upload_preview_batch_validation.json
```

Summary:

```json
{
  "inputCount": 1,
  "completedTaskCount": 1,
  "backendCrashCount": 0,
  "totalVisibleReplayClaimCount": 77,
  "totalVisibleOwnershipOverlapConflicts": 0,
  "totalPlannedShapeReplayCount": 10,
  "totalPlannedIconReplayCount": 35,
  "totalMaterializedVisibleNodeCount": 77
}
```

## Prevention Notes

Do not repair duplicate suppression by choosing a larger global threshold. The source-chain invariant is:

```text
duplicate = same visual entity proven by relation + role + source evidence
```

Overlap area alone is insufficient. Fixes must avoid filename, text, brand, color, coordinate, fixed bbox, screenshot, or task-id rules.
