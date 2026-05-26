from __future__ import annotations

from typing import Any


def parse_xyxy_bbox(value: Any, *, image_width: int, image_height: int) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(item) for item in value]
    except (TypeError, ValueError):
        return None
    x1 = max(0.0, min(float(image_width), x1))
    y1 = max(0.0, min(float(image_height), y1))
    x2 = max(0.0, min(float(image_width), x2))
    y2 = max(0.0, min(float(image_height), y2))
    if x2 <= x1 or y2 <= y1:
        return None
    left = int(round(x1))
    top = int(round(y1))
    right = int(round(x2))
    bottom = int(round(y2))
    if right <= left or bottom <= top:
        return None
    return [left, top, right - left, bottom - top]


def parse_xywh_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [int(round(float(item))) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def bbox_area(bbox: list[int]) -> int:
    return max(0, bbox[2]) * max(0, bbox[3])


def intersection_area(left: list[int], right: list[int]) -> int:
    return max(0, min(x2(left), x2(right)) - max(left[0], right[0])) * max(0, min(y2(left), y2(right)) - max(left[1], right[1]))


def containment_ratio(inner: list[int], outer: list[int]) -> float:
    return intersection_area(inner, outer) / max(1, bbox_area(inner))


def overlap_ratio(left: list[int], right: list[int]) -> float:
    return intersection_area(left, right) / max(1, bbox_area(left))


def bbox_iou(left: list[int], right: list[int]) -> float:
    intersection = intersection_area(left, right)
    if intersection <= 0:
        return 0.0
    return intersection / max(1, bbox_area(left) + bbox_area(right) - intersection)


def x2(bbox: list[int]) -> int:
    return bbox[0] + bbox[2]


def y2(bbox: list[int]) -> int:
    return bbox[1] + bbox[3]

