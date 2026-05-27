# Bug: M29 Replay Overlap And Model Asset Contract Gap

- 状态：open
- 创建日期：2026-05-28
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

Planned fix:

- Align materializer transparent asset selection with the accepted model-first foreground source set.
- Replace same-action overlap suppression with relation/source-aware duplicate logic:
  - keep `near_equal` as strong duplicate evidence;
  - suppress high-IoU / nearly contained same-role duplicates;
  - keep adjacent small foregrounds under ordinary overlap;
  - preserve parent media/control foreground exceptions;
  - keep text-owned fragment suppression separate from promoted/model foreground icon-label overlap.

## Regression Guard

Planned tests:

- `perception_model_foreground_claim + transparentAssetPath` uses transparent asset.
- missing/nonexistent transparent asset path falls back to crop.
- adjacent small icons/markers with 20-35% ordinary overlap both replay.
- near_equal/high-IoU duplicates still suppress.
- parent media/control raster crop does not suppress internal foreground icon.
- text-owned icon fragment can suppress, but promoted/model foreground icon plus label remains replayable.

## Validation Evidence

Pending.

## Prevention Notes

Do not repair duplicate suppression by choosing a larger global threshold. The source-chain invariant is:

```text
duplicate = same visual entity proven by relation + role + source evidence
```

Overlap area alone is insufficient. Fixes must avoid filename, text, brand, color, coordinate, fixed bbox, screenshot, or task-id rules.
