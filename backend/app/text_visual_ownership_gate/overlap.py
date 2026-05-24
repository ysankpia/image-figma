from __future__ import annotations

from typing import Any

from ..visual_primitive_graph import bbox_area, bbox_x2, bbox_y2


def overlapping_text_boxes(bbox: list[int], text_boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in text_boxes if intersection_area(bbox, item["bbox"]) > 0]

def overlap_with_text_union(bbox: list[int], text_boxes: list[dict[str, Any]], *, denominator: str) -> float:
    if not text_boxes:
        return 0.0
    intersection = sum(intersection_area(bbox, item["bbox"]) for item in text_boxes)
    if denominator == "text":
        total = sum(bbox_area(item["bbox"]) for item in text_boxes)
    else:
        total = bbox_area(bbox)
    return min(1.0, intersection / max(1, total))

def intersection_area(left: list[int], right: list[int]) -> int:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(bbox_x2(left), bbox_x2(right))
    y2 = min(bbox_y2(left), bbox_y2(right))
    return max(0, x2 - x1) * max(0, y2 - y1)
