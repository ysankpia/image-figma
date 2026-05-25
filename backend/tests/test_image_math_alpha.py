from __future__ import annotations

import numpy as np

from app.image_math.alpha import alpha_bbox, alpha_coverage, alpha_from_mask, apply_alpha, rgba_png_bytes, soft_alpha
from app.png_tools.metadata import is_png, read_png_metadata


def test_alpha_from_mask_and_coverage() -> None:
    mask = np.array([[False, True], [True, True]])

    alpha = alpha_from_mask(mask)

    assert alpha.dtype == np.uint8
    assert alpha.tolist() == [[0, 255], [255, 255]]
    assert alpha_coverage(alpha) == 0.75
    assert alpha_bbox(alpha) == [0, 0, 2, 2]


def test_apply_alpha_and_encode_png_bytes() -> None:
    rgb = np.array([[[10, 20, 30], [40, 50, 60]]], dtype=np.uint8)
    alpha = np.array([[0, 255]], dtype=np.uint8)

    rgba = apply_alpha(rgb, alpha)
    png = rgba_png_bytes(rgba)

    assert rgba.tolist() == [[[10, 20, 30, 0], [40, 50, 60, 255]]]
    assert is_png(png)
    metadata = read_png_metadata(png)
    assert metadata is not None
    assert metadata.width == 2
    assert metadata.height == 1
    assert metadata.color_type == 6


def test_alpha_bbox_returns_none_for_empty_alpha() -> None:
    assert alpha_bbox(np.zeros((2, 3), dtype=np.uint8)) is None


def test_soft_alpha_smooths_binary_edges() -> None:
    alpha = np.array([[0, 0, 0], [0, 255, 0], [0, 0, 0]], dtype=np.uint8)

    softened = soft_alpha(alpha, radius=1)

    assert softened[1, 1] < 255
    assert softened[1, 1] > 0
