from __future__ import annotations

from ..region_relation_kernel import bbox_area, center_x, center_y, intersection_area, normalize_bbox, x2, y2


def containment_ratio(inner: list[int], outer: list[int]) -> float:
    return round(intersection_area(inner, outer) / max(1, bbox_area(inner)), 6)


def overlap_ratio(left: list[int], right: list[int]) -> float:
    return round(intersection_area(left, right) / max(1, min(bbox_area(left), bbox_area(right))), 6)


def area_ratio(inner: list[int], outer: list[int]) -> float:
    return round(bbox_area(inner) / max(1, bbox_area(outer)), 6)


def is_near_equal(left: list[int], right: list[int], threshold: float = 0.90) -> bool:
    return containment_ratio(left, right) >= threshold and containment_ratio(right, left) >= threshold


def padded_bbox(bbox: list[int], padding_x: int, padding_y: int, image_size: dict[str, int] | None = None) -> list[int]:
    x = bbox[0] - padding_x
    y = bbox[1] - padding_y
    right = x2(bbox) + padding_x
    bottom = y2(bbox) + padding_y
    if image_size:
        x = max(0, x)
        y = max(0, y)
        right = min(int(image_size.get("width") or right), right)
        bottom = min(int(image_size.get("height") or bottom), bottom)
    return [x, y, max(1, right - x), max(1, bottom - y)]


def aspect_ratio(bbox: list[int]) -> float:
    return round(bbox[2] / max(1, bbox[3]), 6)


def long_thin(bbox: list[int]) -> bool:
    return bbox[2] <= 4 and bbox[3] >= 18 or bbox[3] <= 4 and bbox[2] >= 18


def row_alignment_score(bboxes: list[list[int]]) -> float:
    if len(bboxes) < 2:
        return 0.0
    centers = [center_y(bbox) for bbox in bboxes]
    spread = max(centers) - min(centers)
    median_height = sorted(bbox[3] for bbox in bboxes)[len(bboxes) // 2]
    return round(max(0.0, 1.0 - spread / max(1.0, median_height * 1.5)), 3)


def gap_stability_score(bboxes: list[list[int]]) -> float:
    if len(bboxes) < 3:
        return 0.65 if len(bboxes) == 2 else 0.0
    ordered = sorted(bboxes, key=center_x)
    gaps = [center_x(ordered[index + 1]) - center_x(ordered[index]) for index in range(len(ordered) - 1)]
    mean_gap = sum(gaps) / len(gaps)
    if mean_gap <= 0:
        return 0.0
    variance = sum((gap - mean_gap) ** 2 for gap in gaps) / len(gaps)
    return round(max(0.0, 1.0 - (variance**0.5) / mean_gap), 3)
