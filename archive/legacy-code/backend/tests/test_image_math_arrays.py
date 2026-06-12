from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from app.image_math.arrays import crop_array, image_to_rgb_array, image_to_rgba_array, png_bytes_to_rgb_array, rgb_array_to_image


def test_image_to_rgb_array_normalizes_channels() -> None:
    image = Image.new("RGBA", (2, 1), (10, 20, 30, 40))

    array = image_to_rgb_array(image)

    assert array.dtype == np.uint8
    assert array.shape == (1, 2, 3)
    assert array.tolist() == [[[10, 20, 30], [10, 20, 30]]]


def test_image_to_rgba_array_preserves_alpha() -> None:
    image = Image.new("RGBA", (1, 1), (1, 2, 3, 4))

    array = image_to_rgba_array(image)

    assert array.tolist() == [[[1, 2, 3, 4]]]


def test_png_bytes_to_rgb_array_decodes_png() -> None:
    image = Image.new("RGB", (1, 1), (7, 8, 9))
    output = BytesIO()
    image.save(output, format="PNG")

    array = png_bytes_to_rgb_array(output.getvalue())

    assert array.tolist() == [[[7, 8, 9]]]


def test_crop_array_clamps_bbox_to_bounds() -> None:
    array = np.arange(4 * 5 * 3, dtype=np.uint8).reshape((4, 5, 3))

    crop = crop_array(array, [-1, 1, 4, 3])

    assert crop.shape == (3, 3, 3)
    assert crop.tolist() == array[1:4, 0:3].tolist()


def test_crop_array_rejects_empty_clamped_bbox() -> None:
    array = np.zeros((4, 5, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="empty"):
        crop_array(array, [20, 20, 2, 2])


def test_rgb_array_to_image_validates_shape() -> None:
    with pytest.raises(ValueError, match="channels"):
        rgb_array_to_image(np.zeros((2, 2, 4), dtype=np.uint8))
