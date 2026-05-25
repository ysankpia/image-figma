from __future__ import annotations

from typing import Any

import numpy as np
from skimage.morphology import binary_closing, binary_dilation, binary_erosion, binary_opening, disk, remove_small_holes, remove_small_objects

from .masks import ensure_bool_mask


def remove_small(mask: np.ndarray[Any, Any], min_size: int) -> np.ndarray[Any, np.dtype[np.bool_]]:
    if min_size < 1:
        raise ValueError("min_size must be positive")
    return remove_small_objects(ensure_bool_mask(mask), min_size=min_size)


def fill_holes(mask: np.ndarray[Any, Any], max_hole_size: int) -> np.ndarray[Any, np.dtype[np.bool_]]:
    if max_hole_size < 1:
        raise ValueError("max_hole_size must be positive")
    return remove_small_holes(ensure_bool_mask(mask), area_threshold=max_hole_size)


def open_mask(mask: np.ndarray[Any, Any], radius: int = 1) -> np.ndarray[Any, np.dtype[np.bool_]]:
    return binary_opening(ensure_bool_mask(mask), footprint_for(radius))


def close_mask(mask: np.ndarray[Any, Any], radius: int = 1) -> np.ndarray[Any, np.dtype[np.bool_]]:
    return binary_closing(ensure_bool_mask(mask), footprint_for(radius))


def dilate_mask(mask: np.ndarray[Any, Any], radius: int = 1) -> np.ndarray[Any, np.dtype[np.bool_]]:
    return binary_dilation(ensure_bool_mask(mask), footprint_for(radius))


def erode_mask(mask: np.ndarray[Any, Any], radius: int = 1) -> np.ndarray[Any, np.dtype[np.bool_]]:
    return binary_erosion(ensure_bool_mask(mask), footprint_for(radius))


def footprint_for(radius: int) -> np.ndarray[Any, np.dtype[np.uint8]]:
    if radius < 1:
        raise ValueError("radius must be positive")
    return disk(radius)
