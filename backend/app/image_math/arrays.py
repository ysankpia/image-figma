from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image


UInt8Array = np.ndarray[Any, np.dtype[np.uint8]]


def image_to_rgb_array(image: Image.Image) -> UInt8Array:
    return np.asarray(image.convert("RGB"), dtype=np.uint8)


def image_to_rgba_array(image: Image.Image) -> UInt8Array:
    return np.asarray(image.convert("RGBA"), dtype=np.uint8)


def png_bytes_to_rgb_array(data: bytes) -> UInt8Array:
    with Image.open(BytesIO(data)) as image:
        return image_to_rgb_array(image)


def png_bytes_to_rgba_array(data: bytes) -> UInt8Array:
    with Image.open(BytesIO(data)) as image:
        return image_to_rgba_array(image)


def rgb_array_to_image(array: UInt8Array) -> Image.Image:
    validate_uint8_channels(array, (3,), "rgb array")
    return Image.fromarray(array, mode="RGB")


def rgba_array_to_image(array: UInt8Array) -> Image.Image:
    validate_uint8_channels(array, (4,), "rgba array")
    return Image.fromarray(array, mode="RGBA")


def validate_uint8_channels(array: np.ndarray[Any, Any], channels: tuple[int, ...], name: str) -> None:
    if array.dtype != np.uint8:
        raise ValueError(f"{name} must use uint8 dtype")
    if array.ndim != 3 or array.shape[2] not in channels:
        allowed = ", ".join(str(item) for item in channels)
        raise ValueError(f"{name} must have shape height x width x channels, channels in {{{allowed}}}")


def image_size(array: np.ndarray[Any, Any]) -> tuple[int, int]:
    if array.ndim < 2:
        raise ValueError("array must have at least two dimensions")
    return int(array.shape[1]), int(array.shape[0])


def clamp_bbox_to_array(bbox: list[int] | tuple[int, int, int, int], array: np.ndarray[Any, Any]) -> list[int]:
    width, height = image_size(array)
    x, y, box_width, box_height = normalize_bbox(bbox, "bbox")
    left = max(0, min(width, x))
    top = max(0, min(height, y))
    right = max(left, min(width, x + box_width))
    bottom = max(top, min(height, y + box_height))
    return [left, top, right - left, bottom - top]


def crop_array(array: np.ndarray[Any, Any], bbox: list[int] | tuple[int, int, int, int]) -> np.ndarray[Any, Any]:
    x, y, width, height = clamp_bbox_to_array(bbox, array)
    if width <= 0 or height <= 0:
        raise ValueError("clamped bbox is empty")
    return array[y : y + height, x : x + width].copy()


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
