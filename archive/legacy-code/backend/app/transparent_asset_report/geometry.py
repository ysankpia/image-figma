from __future__ import annotations

from ..region_relation_kernel import bbox_area, intersection_area, normalize_bbox


def overlap_ratio(left: list[int], right: list[int]) -> float:
    return round(intersection_area(left, right) / max(1, min(bbox_area(left), bbox_area(right))), 6)


def bbox_in_image(bbox: list[int], image_width: int, image_height: int) -> bool:
    return bbox[0] >= 0 and bbox[1] >= 0 and bbox[2] > 0 and bbox[3] > 0 and bbox[0] + bbox[2] <= image_width and bbox[1] + bbox[3] <= image_height
