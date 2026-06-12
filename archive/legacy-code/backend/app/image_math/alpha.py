from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from .arrays import UInt8Array, crop_array, rgba_array_to_image
from .masks import ensure_bool_mask


def alpha_from_mask(mask: np.ndarray[Any, Any], *, foreground_alpha: int = 255, background_alpha: int = 0) -> UInt8Array:
    if not 0 <= foreground_alpha <= 255 or not 0 <= background_alpha <= 255:
        raise ValueError("alpha values must be in 0..255")
    bool_mask = ensure_bool_mask(mask)
    return np.where(bool_mask, foreground_alpha, background_alpha).astype(np.uint8)


def soft_alpha(alpha: np.ndarray[Any, Any], radius: int = 1) -> UInt8Array:
    if alpha.ndim != 2:
        raise ValueError("alpha must be 2D")
    if alpha.dtype != np.uint8:
        raise ValueError("alpha must use uint8 dtype")
    if radius < 1:
        raise ValueError("radius must be positive")
    image = Image.fromarray(alpha, mode="L")
    return np.asarray(image.filter(ImageFilter.BoxBlur(radius=radius)), dtype=np.uint8)


def apply_alpha(rgb: np.ndarray[Any, Any], alpha: np.ndarray[Any, Any]) -> UInt8Array:
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("rgb must have shape height x width x 3")
    if alpha.ndim != 2:
        raise ValueError("alpha must be 2D")
    if rgb.shape[:2] != alpha.shape:
        raise ValueError("rgb and alpha dimensions must match")
    if rgb.dtype != np.uint8 or alpha.dtype != np.uint8:
        raise ValueError("rgb and alpha must use uint8 dtype")
    return np.dstack([rgb, alpha]).astype(np.uint8, copy=False)


def crop_apply_alpha(rgb: np.ndarray[Any, Any], alpha: np.ndarray[Any, Any], bbox: list[int] | tuple[int, int, int, int]) -> UInt8Array:
    rgb_crop = crop_array(rgb, bbox)
    alpha_crop = crop_array(alpha, bbox)
    return apply_alpha(rgb_crop, alpha_crop)


def rgba_png_bytes(rgba: np.ndarray[Any, Any]) -> bytes:
    image = rgba_array_to_image(rgba)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def alpha_coverage(alpha: np.ndarray[Any, Any], *, threshold: int = 0) -> float:
    if alpha.ndim != 2:
        raise ValueError("alpha must be 2D")
    if alpha.size == 0:
        return 0.0
    return float(np.count_nonzero(alpha > threshold) / alpha.size)


def alpha_bbox(alpha: np.ndarray[Any, Any], *, threshold: int = 0) -> list[int] | None:
    if alpha.ndim != 2:
        raise ValueError("alpha must be 2D")
    ys, xs = np.nonzero(alpha > threshold)
    if len(xs) == 0:
        return None
    left = int(xs.min())
    top = int(ys.min())
    right = int(xs.max()) + 1
    bottom = int(ys.max()) + 1
    return [left, top, right - left, bottom - top]
