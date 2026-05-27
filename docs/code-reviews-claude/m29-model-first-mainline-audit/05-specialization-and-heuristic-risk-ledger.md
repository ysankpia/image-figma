# 05 Specialization and Heuristic Risk Ledger

## Fact: Heuristic Specialization Check
We audited `backend/app/` (specifically compiler, replay plan, and materializer packages) for:
* Sample-specific labels or strings.
* Theme/color heuristics (e.g., hardcoded brand colors).
* Hardcoded coordinate checks or sample filename rules.

We confirmed that **none** of these heuristics exist in the runtime logic. All background/foreground colors are sampled dynamically from PNG pixels or derived from shape overrides, coordinates are parsed dynamically from JSON inputs, and image processing relies on mathematical bboxes.

---

## Fact: Bug 020 Multi-Item Navigation Fix
The resolution of Bug 020 implemented the function `is_multi_item_text_container` in [perception_source_compiler/pipeline.py L1064-1083](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/perception_source_compiler/pipeline.py#L1064-L1083):
```python
def is_multi_item_text_container(bbox: list[int], contained_text: list[Any], options: PerceptionSourceCompilerOptions) -> bool:
    text_boxes = [parse_xywh_bbox(getattr(box, "bbox", None)) for box in contained_text]
    valid_boxes = [box for box in text_boxes if box is not None]
    if len(valid_boxes) < 3:
        return False
    centers = sorted(box[0] + box[2] / 2 for box in valid_boxes)
    vertical_centers = sorted(box[1] + box[3] / 2 for box in valid_boxes)
    text_widths = sorted(box[2] for box in valid_boxes)
    text_heights = sorted(box[3] for box in valid_boxes)
    median_text_width = text_widths[len(text_widths) // 2]
    median_text_height = text_heights[len(text_heights) // 2]
    horizontal_span = centers[-1] - centers[0]
    vertical_span = vertical_centers[-1] - vertical_centers[0]
    gaps = [right - left for left, right in zip(centers, centers[1:], strict=False)]
    min_gap = min(gaps) if gaps else 0.0
    return (
        horizontal_span >= max(median_text_width * 3.0, bbox[2] * 0.45)
        and vertical_span <= max(median_text_height * 2.5, bbox[3] * 0.35)
        and min_gap >= max(median_text_width * 1.3, bbox[2] * 0.12)
    )
```

### Inference & Generalization Analysis
1. **Mathematical Soundness**:
   - The check requires at least 3 text boxes.
   - It computes horizontal span to ensure text elements cover a wide horizontal range (`>= 45%` of the bbox width or `3x` the median text width).
   - It clamps vertical span to ensure elements are aligned on a single row/strip (`<= 35%` of the bbox height or `2.5x` the median text height).
   - It enforces a minimum gap between center coordinates to ensure items are separate columns (`>= 1.3x` the median text width or `12%` of the bbox width).
2. **Safety Against False Positives**:
   - For ordinary complex buttons or single large controls with multi-word labels (e.g. "Save and Continue"), the individual word text boxes are tightly packed. The gaps between centers will be very small (often less than the width of the words themselves), failing the `min_gap >= median_text_width * 1.3` constraint.
   - Therefore, ordinary multi-word labels are **not** misidentified as multi-item navigation bars, and can still walk the standard selectable raster crop fallback path safely.

## Risk
The check is highly robust. There is a minor risk for screens with very high text density where overlapping label/button clusters in a grid could accidentally trigger this row check, but the horizontal/vertical alignment gates are tight enough to minimize this.

## Recommendation
Keep this function. It represents a model-first first-principles approach to structure discovery that avoids sample-specific coordinate hardcoding.
