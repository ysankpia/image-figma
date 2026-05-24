from __future__ import annotations


def bbox_x2(bbox: list[int]) -> int:
    return bbox[0] + bbox[2]


def bbox_y2(bbox: list[int]) -> int:
    return bbox[1] + bbox[3]


def bbox_area(bbox: list[int]) -> int:
    return bbox[2] * bbox[3]


def intersection_area(left: list[int], right: list[int]) -> int:
    return max(0, min(bbox_x2(left), bbox_x2(right)) - max(left[0], right[0])) * max(
        0,
        min(bbox_y2(left), bbox_y2(right)) - max(left[1], right[1]),
    )


def union_bbox(left: list[int], right: list[int]) -> list[int]:
    x1 = min(left[0], right[0])
    y1 = min(left[1], right[1])
    x2 = max(bbox_x2(left), bbox_x2(right))
    y2 = max(bbox_y2(left), bbox_y2(right))
    return [x1, y1, x2 - x1, y2 - y1]


def overlap_ratio(left: list[int], right: list[int]) -> float:
    intersection = intersection_area(left, right)
    if intersection <= 0:
        return 0.0
    return round(intersection / max(1, min(bbox_area(left), bbox_area(right))), 6)

