from __future__ import annotations

import pytest

from app.region_relation_kernel import M29RegionRelationOptions, classify_region_relation


def test_disjoint_rectangles_have_disjoint_primary_relation() -> None:
    relation = classify_region_relation([0, 0, 20, 20], [50, 0, 20, 20])

    assert relation.primary_set_relation == "disjoint"
    assert relation.metrics["intersectionArea"] == 0


def test_left_contains_right_when_right_is_mostly_inside_left() -> None:
    relation = classify_region_relation([0, 0, 100, 80], [10, 10, 20, 20])

    assert relation.primary_set_relation == "contains"
    assert relation.metrics["rightInLeftRatio"] == 1.0


def test_left_contained_by_right_when_left_is_mostly_inside_right() -> None:
    relation = classify_region_relation([10, 10, 20, 20], [0, 0, 100, 80])

    assert relation.primary_set_relation == "contained_by"
    assert relation.metrics["leftInRightRatio"] == 1.0


def test_near_equal_for_almost_same_ocr_and_m29_bbox() -> None:
    relation = classify_region_relation([10, 10, 50, 20], [11, 10, 50, 20])

    assert relation.primary_set_relation == "near_equal"


def test_partial_covering_rectangles_overlap() -> None:
    relation = classify_region_relation([0, 0, 30, 30], [20, 0, 30, 30])

    assert relation.primary_set_relation == "overlaps"
    assert relation.metrics["intersectionArea"] == 300


def test_close_row_text_and_icon_have_near_left_and_center_alignment() -> None:
    relation = classify_region_relation([10, 10, 16, 16], [30, 9, 60, 18])

    assert relation.primary_set_relation == "disjoint"
    assert {"near", "left_of", "aligned_center_y"} <= set(relation.secondary_geometry_relations)
    assert "above" not in relation.secondary_geometry_relations
    assert "below" not in relation.secondary_geometry_relations


def test_vertical_icon_and_text_keep_directed_flow() -> None:
    relation = classify_region_relation([20, 10, 20, 20], [19, 36, 22, 12])

    assert relation.primary_set_relation == "disjoint"
    assert {"near", "above", "aligned_center_x"} <= set(relation.secondary_geometry_relations)
    assert "left_of" not in relation.secondary_geometry_relations
    assert "right_of" not in relation.secondary_geometry_relations


def test_thin_separator_six_pixels_away_is_still_near() -> None:
    relation = classify_region_relation([0, 0, 300, 1], [0, 7, 200, 40])

    assert relation.metrics["gapDistance"] == 6
    assert relation.metrics["nearThreshold"] >= 6
    assert "near" in relation.secondary_geometry_relations


def test_thin_separator_twenty_five_pixels_away_is_not_near() -> None:
    relation = classify_region_relation([0, 0, 300, 1], [0, 26, 200, 40])

    assert relation.metrics["gapDistance"] == 25
    assert relation.metrics["nearThreshold"] < 25
    assert "near" not in relation.secondary_geometry_relations


def test_long_bar_does_not_attract_far_regions_by_its_long_edge() -> None:
    relation = classify_region_relation([0, 0, 1000, 2], [0, 80, 120, 40])

    assert relation.metrics["nearThreshold"] <= 24
    assert "near" not in relation.secondary_geometry_relations


def test_same_width_height_and_size_relations_are_stable() -> None:
    relation = classify_region_relation([0, 0, 100, 40], [120, 0, 102, 42])

    assert {"same_width", "same_height", "same_size"} <= set(relation.secondary_geometry_relations)


@pytest.mark.parametrize(
    "bbox",
    [
        [0, 0, 0, 10],
        [0, 0, 10, -1],
        [0, 0, 10],
        ["x", 0, 10, 10],
    ],
)
def test_invalid_bbox_raises_value_error(bbox: list[object]) -> None:
    with pytest.raises(ValueError):
        classify_region_relation(bbox, [0, 0, 10, 10])  # type: ignore[arg-type]


def test_options_can_tighten_near_relation() -> None:
    relation = classify_region_relation(
        [0, 0, 20, 20],
        [25, 0, 20, 20],
        M29RegionRelationOptions(near_base_px=2, near_max_px=2),
    )

    assert relation.metrics["gapDistance"] == 5
    assert relation.metrics["nearThreshold"] == 2
    assert "near" not in relation.secondary_geometry_relations
