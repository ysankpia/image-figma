from __future__ import annotations

from typing import Any

import numpy as np
from skimage.filters import sobel


def luma_array(rgb: np.ndarray[Any, Any]) -> np.ndarray[Any, np.dtype[np.float32]]:
    validate_rgb_array(rgb)
    values = rgb.astype(np.float32)
    return values[:, :, 0] * 0.299 + values[:, :, 1] * 0.587 + values[:, :, 2] * 0.114


def color_distance_array(rgb: np.ndarray[Any, Any], reference_rgb: tuple[int, int, int]) -> np.ndarray[Any, np.dtype[np.int16]]:
    validate_rgb_array(rgb)
    reference = np.asarray(reference_rgb, dtype=np.int16)
    return np.abs(rgb.astype(np.int16) - reference).sum(axis=2).astype(np.int16)


def mean_color_distance(samples: np.ndarray[Any, Any], reference_rgb: tuple[int, int, int]) -> float:
    if samples.size == 0:
        return 0.0
    if samples.ndim != 2 or samples.shape[1] != 3:
        raise ValueError("samples must have shape n x 3")
    reference = np.asarray(reference_rgb, dtype=np.float32)
    return float(np.abs(samples.astype(np.float32) - reference).sum(axis=1).mean())


def rgb_variance(samples: np.ndarray[Any, Any]) -> float:
    if samples.size == 0:
        return 0.0
    if samples.ndim != 2 or samples.shape[1] != 3:
        raise ValueError("samples must have shape n x 3")
    return float(np.mean(np.var(samples.astype(np.float32), axis=0)))


def edge_strength(luma: np.ndarray[Any, Any]) -> np.ndarray[Any, np.dtype[np.float32]]:
    if luma.ndim != 2:
        raise ValueError("luma must be 2D")
    return sobel(luma.astype(np.float32)).astype(np.float32)


def texture_score(rgb: np.ndarray[Any, Any]) -> float:
    luma = luma_array(rgb)
    if luma.size == 0:
        return 0.0
    return float(edge_strength(luma).mean())


def pixel_abs_difference(left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]) -> float:
    if left.shape != right.shape:
        raise ValueError("arrays must have the same shape")
    if left.size == 0:
        return 0.0
    return float(np.abs(left.astype(np.int16) - right.astype(np.int16)).mean())


def validate_rgb_array(array: np.ndarray[Any, Any]) -> None:
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("array must have shape height x width x 3")
