from __future__ import annotations

from typing import Any

from ..visual_primitive_graph import M29PrimitiveMetrics, bbox_area, bbox_in_bounds, bbox_x2, bbox_y2
from .types import M2904Options, VisualObjectCandidate, VisualObjectEvidenceNode


def assert_unique(values: list[str], label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate M29.0.4 {label} id: {value}")
        seen.add(value)
    return seen

def count_by(items: list[Any], key_fn: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(key_fn(item))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))

def is_icon_like_text_noise(bbox: list[int], metrics: M29PrimitiveMetrics) -> bool:
    area = bbox_area(bbox)
    max_edge = max(bbox[2], bbox[3])
    aspect = bbox[2] / max(1, bbox[3])
    return 16 <= area <= 12000 and max_edge <= 128 and aspect <= 3.0 and (metrics.color_count >= 6 or metrics.texture_score >= 0.04)

def is_wide_bbox(bbox: list[int], options: M2904Options) -> bool:
    aspect = bbox[2] / max(1, bbox[3])
    return aspect >= options.wide_aspect_ratio and bbox[2] >= options.near_distance * 3

def truncate_text(text: str | None, max_chars: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= max_chars else text[:max_chars] + "..."

def expand_bbox(bbox: list[int], padding: int) -> list[int]:
    return [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding * 2, bbox[3] + padding * 2]

def center_x(bbox: list[int]) -> float:
    return bbox[0] + bbox[2] / 2

def center_y(bbox: list[int]) -> float:
    return bbox[1] + bbox[3] / 2

def same_row_like(left: list[int], right: list[int], options: M2904Options) -> bool:
    return abs(center_y(left) - center_y(right)) <= options.row_tolerance

def same_column_like(left: list[int], right: list[int], options: M2904Options) -> bool:
    return abs(center_x(left) - center_x(right)) <= options.alignment_tolerance

def center_alignment_score(left: list[int], right: list[int]) -> float:
    delta = min(abs(center_x(left) - center_x(right)), abs(center_y(left) - center_y(right)))
    return max(0.0, 1.0 - delta / 64)

def baseline_alignment_score(left: list[int], right: list[int], options: M2904Options) -> float:
    return max(0.0, 1.0 - abs(bbox_y2(left) - bbox_y2(right)) / max(1, options.row_tolerance * 2))

def compact_union_score(bboxes: list[list[int]], options: M2904Options) -> float:
    union = bbox_union(bboxes)
    area_sum = sum(bbox_area(bbox) for bbox in bboxes)
    if bbox_area(union) <= 0:
        return 0.0
    ratio = bbox_area(union) / max(1, area_sum)
    return max(0.0, 1.0 - (ratio - 1.0) / max(1.0, options.compact_area_multiplier))

def size_compatibility(left: list[int], right: list[int]) -> float:
    left_area = bbox_area(left)
    right_area = bbox_area(right)
    if left_area <= 0 or right_area <= 0:
        return 0.0
    ratio = max(left_area, right_area) / max(1, min(left_area, right_area))
    return max(0.0, 1.0 - (ratio - 1.0) / 8.0)

def out_of_reasonable_bounds(bbox: list[int], width: int, height: int) -> bool:
    return not bbox_in_bounds(bbox, width, height) or bbox_area(bbox) > width * height * 0.35

def bbox_union(bboxes: list[list[int]]) -> list[int]:
    if not bboxes:
        return [0, 0, 1, 1]
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox_x2(bbox) for bbox in bboxes)
    y2 = max(bbox_y2(bbox) for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]

def dedupe_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
