from __future__ import annotations

import numpy as np

from app.image_math.masks import expand_bbox, mask_area, mask_bbox, mask_containment, mask_from_bbox, mask_iou, mask_or, mask_subtract


def test_mask_from_bbox_and_bbox_roundtrip() -> None:
    mask = mask_from_bbox(8, 6, [2, 1, 3, 4])

    assert mask_area(mask) == 12
    assert mask_bbox(mask) == [2, 1, 3, 4]


def test_mask_iou_and_containment() -> None:
    left = mask_from_bbox(8, 6, [1, 1, 4, 3])
    right = mask_from_bbox(8, 6, [3, 1, 4, 3])

    assert mask_iou(left, right) == 6 / 18
    assert mask_containment(left, mask_or(left, right)) == 1.0


def test_mask_subtract_removes_overlap() -> None:
    left = mask_from_bbox(8, 6, [1, 1, 4, 3])
    right = mask_from_bbox(8, 6, [3, 1, 4, 3])

    result = mask_subtract(left, right)

    assert mask_area(result) == 6
    assert mask_bbox(result) == [1, 1, 2, 3]


def test_expand_bbox_clamps_to_image_bounds() -> None:
    assert expand_bbox([1, 2, 3, 2], 4, 3, 10, 8) == [0, 0, 8, 7]


def test_empty_mask_bbox_is_none() -> None:
    assert mask_bbox(np.zeros((4, 4), dtype=bool)) is None
