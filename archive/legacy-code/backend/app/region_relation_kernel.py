from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PrimarySetRelation = Literal["near_equal", "contains", "contained_by", "overlaps", "disjoint"]
SecondaryGeometryRelation = Literal[
    "near",
    "left_of",
    "right_of",
    "above",
    "below",
    "aligned_left",
    "aligned_center_x",
    "aligned_right",
    "aligned_top",
    "aligned_center_y",
    "aligned_bottom",
    "same_width",
    "same_height",
    "same_size",
]


@dataclass(frozen=True)
class M29RegionRelationOptions:
    near_equal_ratio: float = 0.90
    containment_ratio: float = 0.95
    near_base_px: int = 6
    near_max_px: int = 24
    near_scale: float = 0.08
    thin_min_dimension_px: int = 8
    alignment_base_px: int = 2
    alignment_max_px: int = 12
    alignment_scale: float = 0.04
    same_size_abs_px: int = 2
    same_size_ratio: float = 0.08


@dataclass(frozen=True)
class M29RegionRelation:
    primary_set_relation: PrimarySetRelation
    secondary_geometry_relations: list[SecondaryGeometryRelation]
    metrics: dict[str, float | int]

    def to_dict(self) -> dict[str, object]:
        return {
            "primarySetRelation": self.primary_set_relation,
            "secondaryGeometryRelations": self.secondary_geometry_relations,
            "metrics": self.metrics,
        }


def classify_region_relation(
    left_bbox: list[int] | tuple[int, int, int, int],
    right_bbox: list[int] | tuple[int, int, int, int],
    options: M29RegionRelationOptions | None = None,
) -> M29RegionRelation:
    options = options or M29RegionRelationOptions()
    left = normalize_bbox(left_bbox, "left_bbox")
    right = normalize_bbox(right_bbox, "right_bbox")

    intersection = intersection_area(left, right)
    left_area = bbox_area(left)
    right_area = bbox_area(right)
    left_in_right = intersection / left_area
    right_in_left = intersection / right_area

    primary = classify_primary_relation(
        intersection_area_value=intersection,
        left_in_right=left_in_right,
        right_in_left=right_in_left,
        options=options,
    )
    gap = bbox_gap_distance(left, right)
    near_threshold = compute_near_threshold(left, right, options)
    alignment_threshold = compute_alignment_threshold(left, right, options)
    secondary = classify_secondary_relations(left, right, gap, near_threshold, alignment_threshold, options)

    return M29RegionRelation(
        primary_set_relation=primary,
        secondary_geometry_relations=secondary,
        metrics={
            "intersectionArea": intersection,
            "leftInRightRatio": round(left_in_right, 6),
            "rightInLeftRatio": round(right_in_left, 6),
            "gapDistance": gap,
            "nearThreshold": near_threshold,
            "alignmentThreshold": alignment_threshold,
        },
    )


def normalize_bbox(value: list[int] | tuple[int, int, int, int], name: str) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"{name} must be [x, y, width, height]")
    try:
        bbox = [int(round(float(item))) for item in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain numeric values") from exc
    if bbox[2] <= 0 or bbox[3] <= 0:
        raise ValueError(f"{name} width and height must be positive")
    return bbox


def classify_primary_relation(
    *,
    intersection_area_value: int,
    left_in_right: float,
    right_in_left: float,
    options: M29RegionRelationOptions,
) -> PrimarySetRelation:
    if left_in_right >= options.near_equal_ratio and right_in_left >= options.near_equal_ratio:
        return "near_equal"
    if right_in_left >= options.containment_ratio:
        return "contains"
    if left_in_right >= options.containment_ratio:
        return "contained_by"
    if intersection_area_value > 0:
        return "overlaps"
    return "disjoint"


def classify_secondary_relations(
    left: list[int],
    right: list[int],
    gap: int,
    near_threshold: int,
    alignment_threshold: int,
    options: M29RegionRelationOptions,
) -> list[SecondaryGeometryRelation]:
    relations: list[SecondaryGeometryRelation] = []
    if gap <= near_threshold:
        relations.append("near")
    if x2(left) <= right[0]:
        relations.append("left_of")
    elif x2(right) <= left[0]:
        relations.append("right_of")
    if y2(left) <= right[1]:
        relations.append("above")
    elif y2(right) <= left[1]:
        relations.append("below")

    if abs(left[0] - right[0]) <= alignment_threshold:
        relations.append("aligned_left")
    if abs(center_x(left) - center_x(right)) <= alignment_threshold:
        relations.append("aligned_center_x")
    if abs(x2(left) - x2(right)) <= alignment_threshold:
        relations.append("aligned_right")
    if abs(left[1] - right[1]) <= alignment_threshold:
        relations.append("aligned_top")
    if abs(center_y(left) - center_y(right)) <= alignment_threshold:
        relations.append("aligned_center_y")
    if abs(y2(left) - y2(right)) <= alignment_threshold:
        relations.append("aligned_bottom")

    same_width = similar_dimension(left[2], right[2], options)
    same_height = similar_dimension(left[3], right[3], options)
    if same_width:
        relations.append("same_width")
    if same_height:
        relations.append("same_height")
    if same_width and same_height:
        relations.append("same_size")
    return relations


def compute_near_threshold(left: list[int], right: list[int], options: M29RegionRelationOptions) -> int:
    left_short = max(min(left[2], left[3]), options.thin_min_dimension_px)
    right_short = max(min(right[2], right[3]), options.thin_min_dimension_px)
    scaled = round(options.near_scale * min(left_short, right_short))
    return min(options.near_max_px, max(options.near_base_px, scaled))


def compute_alignment_threshold(left: list[int], right: list[int], options: M29RegionRelationOptions) -> int:
    scaled = round(options.alignment_scale * min(max(left[2], left[3]), max(right[2], right[3])))
    return min(options.alignment_max_px, max(options.alignment_base_px, scaled))


def similar_dimension(left_value: int, right_value: int, options: M29RegionRelationOptions) -> bool:
    diff = abs(left_value - right_value)
    if diff <= options.same_size_abs_px:
        return True
    return diff / max(1, max(left_value, right_value)) <= options.same_size_ratio


def bbox_area(bbox: list[int]) -> int:
    return bbox[2] * bbox[3]


def intersection_area(left: list[int], right: list[int]) -> int:
    return max(0, min(x2(left), x2(right)) - max(left[0], right[0])) * max(0, min(y2(left), y2(right)) - max(left[1], right[1]))


def bbox_gap_distance(left: list[int], right: list[int]) -> int:
    x_gap = max(0, max(left[0], right[0]) - min(x2(left), x2(right)))
    y_gap = max(0, max(left[1], right[1]) - min(y2(left), y2(right)))
    return max(x_gap, y_gap)


def x2(bbox: list[int]) -> int:
    return bbox[0] + bbox[2]


def y2(bbox: list[int]) -> int:
    return bbox[1] + bbox[3]


def center_x(bbox: list[int]) -> float:
    return bbox[0] + bbox[2] / 2


def center_y(bbox: list[int]) -> float:
    return bbox[1] + bbox[3] / 2
