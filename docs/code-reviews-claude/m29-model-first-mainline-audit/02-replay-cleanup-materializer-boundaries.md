# 02 Replay, Cleanup, and Materializer Boundaries Audit

## Fact: Aggressive Overlap Suppression Threshold (P1)
In [overlap.py L76-78](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_replay_plan/overlap.py#L76-L78), we find:
```python
        if left_action in {"icon_replay", "shape_replay"}:
            threshold = 0.20 if left_action == "icon_replay" else 0.20
            return containment_ratio >= threshold
```
Where `containment_ratio` is calculated as `intersection / min(left_area, right_area)`.

### Inference & Risk
For adjacent small icons, tab markers, status dots, and table markers, a 20% overlap threshold is extremely low and easily triggered by minor bbox margins or alignment drift. If two icons or markers are placed close to each other and share a few rows of pixels, one of them will be suppressed as `suppress_duplicate`. This directly risks dropping real, separate foreground elements from the final Figma design.

---

## Fact: Redundant Threshold Ternary Dead Code (P1)
In [overlap.py L77](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_replay_plan/overlap.py#L77):
```python
            threshold = 0.20 if left_action == "icon_replay" else 0.20
```
This ternary always returns `0.20` regardless of whether `left_action` is `icon_replay` or `shape_replay`.

### Inference & Risk
This indicates a missed design differentiation. Shape overlaps should typically have a higher tolerance (or different threshold) than icon overlaps, but here they are hardcoded to the same aggressive value.

---

## Fact: Asymmetric Text/Icon Suppression (P2)
In [overlap.py L95-98](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_replay_plan/overlap.py#L95-L98):
```python
    if actions == {"text_replay", "icon_replay"}:
        if is_promoted_internal_icon_label_overlap(left, right):
            return False
        return left_action == "text_replay" and containment_ratio >= 0.25
```
Because the list of plan items is sorted by `overlap_priority_sort_key` where `text_replay` has rank 1 and `icon_replay` has rank 3, `text_replay` items always iterate first and end up as `left`, while `icon_replay` items end up as `right`.

### Inference & Risk
Line 98 will return `True` (suppressing the icon `right`) if `left_action == "text_replay"` and containment is >= 25%. However, if the icon is processed as `left` (for any reason, e.g., different confidence sorting), it will return `False` since `left_action` is `"icon_replay"`. This asymmetry means text can suppress overlapping icons but icons can never suppress overlapping text. In label-icon combos with high overlap, this might result in one of the nodes being dropped incorrectly.

---

## Fact: Missing Perception Promotion Source in Materializer (P2)
In [plan_materializer/replay.py L221-231](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/replay.py#L221-L231):
```python
def transparent_asset_path_for(item: dict[str, Any], output_dir: Path) -> Path | None:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    if evidence.get("promotionSource") not in {"m29_6_internal_icon_candidate", "m29_6_foreground_claim"}:
        return None
```
However, the M29.5 cleanup system and overlap code recognize three promotion sources: `"m29_6_internal_icon_candidate"`, `"m29_6_foreground_claim"`, and `"perception_model_foreground_claim"`.

### Inference & Risk
Perception-model-promoted icons (which have `"promotionSource": "perception_model_foreground_claim"`) will always return `None` from this function, causing them to fall back to `crop_pixels` in the materializer instead of using their transparent alpha mask, even when `transparentAssetPath` is populated. This is a silent asset quality degradation.

---

## Fact: Hardcoded Fonts and Alignment in Materializer (P2)
In [plan_materializer/replay.py L75-77](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/replay.py#L75-L77), replayed text nodes have hardcoded styles:
```python
                        "fontFamily": "Inter",
                        "fontWeight": 400,
                        "textAlign": "left",
```

### Inference & Risk
The materializer is supposed to be a plan-driven translation layer, but here it injects standard defaults. While acceptable for a basic layout, it means font styling is ignored.

---

## Fact: Dead Code in C-Stage Structure Materializer (P2)
In [plan_materializer/structure.py L25-75](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/structure.py#L25-L75), we see that group materialization mode is hardcoded to `"report_only"`:
```python
        accepted.append(asdict(candidate) | {"groupNodeId": group_id, "materializationMode": "report_only"})
```
The helper functions `build_group_node` and `replace_members_with_group` are defined at lines 231 and 275 but are **never called** in the active pipeline execution (no references exist outside their definitions).

### Inference & Risk
These functions are dead code. While safe, they increase maintenance overhead and could be wired in accidentally.

---

## Fact: Cleanup Authorization and Replay Conservation (Good)
1. **Cleanup Targets only from M29.5**: As verified in [cleanup.py L179-234](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/plan_materializer/cleanup.py#L179-L234), the materializer only erases pixels if `plan_allows_copied_image_cleanup`, `plan_allows_internal_asset_copied_image_cleanup`, or `plan_allows_shape_copied_image_cleanup` return `True` by matching targets in the M29.5 plan.
2. **Replay Conservation**: If a cleanup risk fails (e.g. `cleanup_rejected_text_overlap_risk`), M29.5 skips adding the copied-image cleanup target but does NOT cancel the visible replay of that element. The visible node is still material-replayed.
