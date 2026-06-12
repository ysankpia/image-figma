from __future__ import annotations


def bbox_x2(bbox: list[int]) -> int:
    return bbox[0] + bbox[2]


def bbox_y2(bbox: list[int]) -> int:
    return bbox[1] + bbox[3]


def bbox_area(bbox: list[int]) -> int:
    return max(0, bbox[2]) * max(0, bbox[3])


def containment_ratio(parent_bbox: list[int], child_bbox: list[int]) -> float:
    child_area = bbox_area(child_bbox)
    if child_area <= 0:
        return 0.0
    return intersection_area(parent_bbox, child_bbox) / child_area


def intersection_area(left: list[int], right: list[int]) -> int:
    return max(0, min(bbox_x2(left), bbox_x2(right)) - max(left[0], right[0])) * max(
        0,
        min(bbox_y2(left), bbox_y2(right)) - max(left[1], right[1]),
    )


def oversize_ratio(parent_bbox: list[int], child_bbox: list[int]) -> float:
    child_area = bbox_area(child_bbox)
    if child_area <= 0:
        return 0.0
    return bbox_area(parent_bbox) / child_area


def padding_imbalance(parent_bbox: list[int], child_bbox: list[int]) -> float:
    left = child_bbox[0] - parent_bbox[0]
    right = bbox_x2(parent_bbox) - bbox_x2(child_bbox)
    top = child_bbox[1] - parent_bbox[1]
    bottom = bbox_y2(parent_bbox) - bbox_y2(child_bbox)
    horizontal = abs(left - right) / max(1, parent_bbox[2])
    vertical = abs(top - bottom) / max(1, parent_bbox[3])
    return min(1.0, round((horizontal + vertical) / 2, 6))
