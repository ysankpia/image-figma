from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from .arrays import UInt8Array, crop_array, rgb_array_to_image
from .metrics import color_distance_array


def edge_samples(rgb: np.ndarray[Any, Any]) -> np.ndarray[Any, np.dtype[np.uint8]]:
    validate_rgb_array(rgb)
    height, width, _channels = rgb.shape
    if width == 1 and height == 1:
        return rgb.reshape(1, 3)
    top = rgb[0, :, :]
    bottom = rgb[-1, :, :] if height > 1 else np.empty((0, 3), dtype=np.uint8)
    left = rgb[1:-1, 0, :] if height > 2 else np.empty((0, 3), dtype=np.uint8)
    right = rgb[1:-1, -1, :] if width > 1 and height > 2 else np.empty((0, 3), dtype=np.uint8)
    return np.vstack([top, bottom, left, right]).astype(np.uint8, copy=False)


def median_rgb(samples: np.ndarray[Any, Any]) -> tuple[int, int, int]:
    if samples.size == 0:
        return (0, 0, 0)
    if samples.ndim != 2 or samples.shape[1] != 3:
        raise ValueError("samples must have shape n x 3")
    values = np.median(samples.astype(np.float32), axis=0)
    return tuple(int(round(float(item))) for item in values)


def rgb_mean_distance(samples: np.ndarray[Any, Any], reference_rgb: tuple[int, int, int]) -> float:
    if samples.size == 0:
        return 0.0
    reference = np.asarray(reference_rgb, dtype=np.int16)
    return float(np.abs(samples.astype(np.int16) - reference).sum(axis=1).mean())


def crop_edge_background(rgb: np.ndarray[Any, Any], bbox: list[int] | tuple[int, int, int, int]) -> dict[str, object]:
    crop = crop_array(rgb, bbox)
    samples = edge_samples(crop)
    background = median_rgb(samples)
    return {
        "rgb": list(background),
        "meanDistance": round(rgb_mean_distance(samples, background), 4),
        "sampleCount": int(len(samples)),
    }


def blur_background_map(rgb: np.ndarray[Any, Any], radius: int) -> UInt8Array:
    validate_rgb_array(rgb)
    if radius < 1:
        raise ValueError("radius must be positive")
    image = rgb_array_to_image(rgb)
    blurred = image.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.asarray(blurred.convert("RGB"), dtype=np.uint8)


def foreground_distance_map(rgb: np.ndarray[Any, Any], background_rgb: tuple[int, int, int] | np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    validate_rgb_array(rgb)
    if isinstance(background_rgb, tuple):
        return color_distance_array(rgb, background_rgb)
    validate_rgb_array(background_rgb)
    if rgb.shape != background_rgb.shape:
        raise ValueError("background map must match rgb shape")
    return np.abs(rgb.astype(np.int16) - background_rgb.astype(np.int16)).sum(axis=2).astype(np.int16)


def validate_rgb_array(array: np.ndarray[Any, Any]) -> None:
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("array must have shape height x width x 3")
