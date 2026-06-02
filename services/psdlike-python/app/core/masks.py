from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Mechanical migration from PSD-like V1 oracle. Keep behavior changes out of this stage.


def build_text_mask(width: int, height: int, blocks: list[OCRBlock], padding: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    for block in blocks:
        x1 = max(0, block.bbox.x - padding)
        y1 = max(0, block.bbox.y - padding)
        x2 = min(width, block.bbox.x2 + padding)
        y2 = min(height, block.bbox.y2 + padding)
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = True
    return mask


def build_text_knockout_mask(rgb: np.ndarray, blocks: list[OCRBlock]) -> np.ndarray:
    height, width, _ = rgb.shape
    mask = np.zeros((height, width), dtype=bool)
    for block in blocks:
        box = clamp_box(block.bbox, width, height)
        if box is None or box.area <= 0:
            continue
        region = rgb[box.y : box.y2, box.x : box.x2]
        if region.size == 0:
            continue
        bg = estimate_text_background_for_box(rgb, box)
        diff = np.linalg.norm(region.astype(np.float32) - bg.reshape(1, 1, 3).astype(np.float32), axis=2)
        threshold = max(30.0, float(np.percentile(diff, 72)) * 0.72)
        local = diff >= threshold
        coverage = float(local.mean()) if local.size else 0.0
        if coverage > 0.38:
            local = diff >= max(38.0, float(np.percentile(diff, 82)))
        elif coverage < 0.015 and diff.max(initial=0.0) >= 32.0:
            local = diff >= max(24.0, float(np.percentile(diff, 88)) * 0.70)
        if local.size and float(local.mean()) <= 0.32:
            local = binary_dilate(local, iterations=1)
        if local.size and float(local.mean()) > 0.42:
            local = diff >= max(42.0, float(np.percentile(diff, 90)))
        mask[box.y : box.y2, box.x : box.x2] |= local
    return mask


def binary_dilate(mask: np.ndarray, iterations: int) -> np.ndarray:
    result = mask.astype(bool)
    for _ in range(iterations):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        expanded = np.zeros_like(result)
        for dy in range(3):
            for dx in range(3):
                expanded |= padded[dy : dy + result.shape[0], dx : dx + result.shape[1]]
        result = expanded
    return result


def binary_erode(mask: np.ndarray, iterations: int) -> np.ndarray:
    result = mask.astype(bool)
    for _ in range(iterations):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        eroded = np.ones_like(result)
        for dy in range(3):
            for dx in range(3):
                eroded &= padded[dy : dy + result.shape[0], dx : dx + result.shape[1]]
        result = eroded
    return result


def binary_close(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    return binary_erode(binary_dilate(mask, iterations), iterations)
