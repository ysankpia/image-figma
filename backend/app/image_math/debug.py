from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from .arrays import rgb_array_to_image
from .masks import ensure_bool_mask


def draw_bboxes(rgb: np.ndarray[Any, Any], bboxes: list[list[int]], *, color: tuple[int, int, int] = (255, 0, 0)) -> Image.Image:
    image = rgb_array_to_image(rgb).copy()
    draw = ImageDraw.Draw(image)
    for bbox in bboxes:
        x, y, width, height = bbox
        draw.rectangle([x, y, x + width - 1, y + height - 1], outline=color, width=1)
    return image


def mask_overlay(rgb: np.ndarray[Any, Any], mask: np.ndarray[Any, Any], *, color: tuple[int, int, int] = (255, 0, 0), opacity: int = 96) -> Image.Image:
    if not 0 <= opacity <= 255:
        raise ValueError("opacity must be in 0..255")
    image = rgb_array_to_image(rgb).convert("RGBA")
    bool_mask = ensure_bool_mask(mask)
    if image.size != (bool_mask.shape[1], bool_mask.shape[0]):
        raise ValueError("mask dimensions must match image")
    overlay = Image.new("RGBA", image.size, color + (0,))
    alpha = np.where(bool_mask, opacity, 0).astype(np.uint8)
    overlay.putalpha(Image.fromarray(alpha, mode="L"))
    return Image.alpha_composite(image, overlay)


def image_png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
