from __future__ import annotations


def bbox_x2(bbox: list[int]) -> int:
    return bbox[0] + bbox[2]


def bbox_y2(bbox: list[int]) -> int:
    return bbox[1] + bbox[3]


def bbox_area(bbox: list[int]) -> int:
    if len(bbox) != 4:
        return 0
    return max(0, bbox[2]) * max(0, bbox[3])


def bbox_intersects(left: list[int], right: list[int]) -> bool:
    return min(bbox_x2(left), bbox_x2(right)) > max(left[0], right[0]) and min(bbox_y2(left), bbox_y2(right)) > max(left[1], right[1])


def bbox_contains(outer: list[int], inner: list[int]) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and bbox_x2(outer) >= bbox_x2(inner) and bbox_y2(outer) >= bbox_y2(inner)


def bbox_iou(left: list[int], right: list[int]) -> float:
    if not bbox_intersects(left, right):
        return 0.0
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(bbox_x2(left), bbox_x2(right))
    y2 = min(bbox_y2(left), bbox_y2(right))
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = bbox_area(left) + bbox_area(right) - intersection
    return intersection / max(1, union)


def bbox_gap_distance(left: list[int], right: list[int]) -> int:
    x_gap = max(0, max(left[0], right[0]) - min(bbox_x2(left), bbox_x2(right)))
    y_gap = max(0, max(left[1], right[1]) - min(bbox_y2(left), bbox_y2(right)))
    return max(x_gap, y_gap)


def bbox_clamp(bbox: list[int], image_width: int, image_height: int) -> list[int] | None:
    if len(bbox) != 4:
        return None
    x1 = max(0, min(image_width, round(bbox[0])))
    y1 = max(0, min(image_height, round(bbox[1])))
    x2 = max(0, min(image_width, round(bbox[0] + bbox[2])))
    y2 = max(0, min(image_height, round(bbox[1] + bbox[3])))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2 - x1, y2 - y1]


def bbox_in_bounds(bbox: list[int], image_width: int, image_height: int) -> bool:
    return len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0 and bbox[0] >= 0 and bbox[1] >= 0 and bbox_x2(bbox) <= image_width and bbox_y2(bbox) <= image_height


def bbox_intersection_area(left: list[int], right: list[int]) -> int:
    if not bbox_intersects(left, right):
        return 0
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(bbox_x2(left), bbox_x2(right))
    y2 = min(bbox_y2(left), bbox_y2(right))
    return max(0, x2 - x1) * max(0, y2 - y1)


def bbox_vertical_overlap_ratio(left: list[int], right: list[int]) -> float:
    overlap = max(0, min(bbox_y2(left), bbox_y2(right)) - max(left[1], right[1]))
    return overlap / max(1, min(left[3], right[3]))


def union_bbox(bboxes: list[list[int]]) -> list[int] | None:
    valid = [bbox for bbox in bboxes if len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0]
    if not valid:
        return None
    x1 = min(bbox[0] for bbox in valid)
    y1 = min(bbox[1] for bbox in valid)
    x2 = max(bbox_x2(bbox) for bbox in valid)
    y2 = max(bbox_y2(bbox) for bbox in valid)
    return [x1, y1, x2 - x1, y2 - y1]


def pad_bbox(bbox: list[int], padding: int) -> list[int]:
    return [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding * 2, bbox[3] + padding * 2]

