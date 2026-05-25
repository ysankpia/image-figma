from __future__ import annotations

from typing import Any

import numpy as np


BoolMask = np.ndarray[Any, np.dtype[np.bool_]]


def empty_mask(width: int, height: int) -> BoolMask:
    if width <= 0 or height <= 0:
        raise ValueError("mask dimensions must be positive")
    return np.zeros((height, width), dtype=bool)


def mask_from_bbox(width: int, height: int, bbox: list[int] | tuple[int, int, int, int]) -> BoolMask:
    mask = empty_mask(width, height)
    x, y, box_width, box_height = clamp_bbox(bbox, width, height)
    if box_width <= 0 or box_height <= 0:
        return mask
    mask[y : y + box_height, x : x + box_width] = True
    return mask


def ensure_bool_mask(mask: np.ndarray[Any, Any], name: str = "mask") -> BoolMask:
    if mask.ndim != 2:
        raise ValueError(f"{name} must be a 2D mask")
    return mask.astype(bool, copy=False)


def mask_and(left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]) -> BoolMask:
    return np.logical_and(ensure_bool_mask(left, "left"), ensure_bool_mask(right, "right"))


def mask_or(left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]) -> BoolMask:
    return np.logical_or(ensure_bool_mask(left, "left"), ensure_bool_mask(right, "right"))


def mask_subtract(left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]) -> BoolMask:
    return np.logical_and(ensure_bool_mask(left, "left"), np.logical_not(ensure_bool_mask(right, "right")))


def mask_area(mask: np.ndarray[Any, Any]) -> int:
    return int(np.count_nonzero(ensure_bool_mask(mask)))


def mask_bbox(mask: np.ndarray[Any, Any]) -> list[int] | None:
    bool_mask = ensure_bool_mask(mask)
    ys, xs = np.nonzero(bool_mask)
    if len(xs) == 0:
        return None
    left = int(xs.min())
    top = int(ys.min())
    right = int(xs.max()) + 1
    bottom = int(ys.max()) + 1
    return [left, top, right - left, bottom - top]


def mask_overlap_area(left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]) -> int:
    return mask_area(mask_and(left, right))


def mask_iou(left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]) -> float:
    union = mask_area(mask_or(left, right))
    if union == 0:
        return 0.0
    return mask_overlap_area(left, right) / union


def mask_containment(inner: np.ndarray[Any, Any], outer: np.ndarray[Any, Any]) -> float:
    inner_area = mask_area(inner)
    if inner_area == 0:
        return 0.0
    return mask_overlap_area(inner, outer) / inner_area


def expand_mask(mask: np.ndarray[Any, Any], pad_x: int, pad_y: int) -> BoolMask:
    bool_mask = ensure_bool_mask(mask)
    if pad_x < 0 or pad_y < 0:
        raise ValueError("mask padding must be non-negative")
    if pad_x == 0 and pad_y == 0:
        return bool_mask.copy()
    ys, xs = np.nonzero(bool_mask)
    expanded = np.zeros_like(bool_mask)
    height, width = bool_mask.shape
    for x, y in zip(xs, ys, strict=True):
        left = max(0, int(x) - pad_x)
        top = max(0, int(y) - pad_y)
        right = min(width, int(x) + pad_x + 1)
        bottom = min(height, int(y) + pad_y + 1)
        expanded[top:bottom, left:right] = True
    return expanded


def expand_bbox(bbox: list[int] | tuple[int, int, int, int], pad_x: int, pad_y: int, width: int, height: int) -> list[int]:
    x, y, box_width, box_height = normalize_bbox(bbox, "bbox")
    return clamp_bbox([x - pad_x, y - pad_y, box_width + pad_x * 2, box_height + pad_y * 2], width, height)


def clamp_bbox(bbox: list[int] | tuple[int, int, int, int], width: int, height: int) -> list[int]:
    x, y, box_width, box_height = normalize_bbox(bbox, "bbox")
    left = max(0, min(width, x))
    top = max(0, min(height, y))
    right = max(left, min(width, x + box_width))
    bottom = max(top, min(height, y + box_height))
    return [left, top, right - left, bottom - top]


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
