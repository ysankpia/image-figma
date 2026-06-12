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


def compute_tile_maps(rgb: np.ndarray, text_mask: np.ndarray, tile_size: int) -> dict[str, np.ndarray]:
    height, width, _ = rgb.shape
    rows = math.ceil(height / tile_size)
    cols = math.ceil(width / tile_size)

    texture = np.zeros((rows, cols), dtype=np.float32)
    edge = np.zeros((rows, cols), dtype=np.float32)
    entropy = np.zeros((rows, cols), dtype=np.float32)
    unique = np.zeros((rows, cols), dtype=np.float32)
    dominant = np.zeros((rows, cols), dtype=np.float32)
    text_coverage = np.zeros((rows, cols), dtype=np.float32)
    mean_color = np.zeros((rows, cols, 3), dtype=np.float32)

    gray = (
        rgb[:, :, 0].astype(np.float32) * 0.299
        + rgb[:, :, 1].astype(np.float32) * 0.587
        + rgb[:, :, 2].astype(np.float32) * 0.114
    )

    for row in range(rows):
        y1 = row * tile_size
        y2 = min(height, y1 + tile_size)
        for col in range(cols):
            x1 = col * tile_size
            x2 = min(width, x1 + tile_size)
            tile = rgb[y1:y2, x1:x2]
            tile_gray = gray[y1:y2, x1:x2]
            pixels = tile.reshape(-1, 3)
            pixel_count = max(1, pixels.shape[0])

            sqrt_var = float(np.sqrt(np.mean(np.var(pixels.astype(np.float32), axis=0))))
            texture[row, col] = clamp((sqrt_var - 6.0) / 44.0)

            gx = np.abs(np.diff(tile_gray, axis=1)).mean() if tile_gray.shape[1] > 1 else 0.0
            gy = np.abs(np.diff(tile_gray, axis=0)).mean() if tile_gray.shape[0] > 1 else 0.0
            edge[row, col] = clamp((float(gx) + float(gy)) / 48.0)

            hist, _ = np.histogram(tile_gray, bins=16, range=(0, 256))
            prob = hist[hist > 0].astype(np.float32) / pixel_count
            ent = float(-(prob * np.log2(prob)).sum()) if prob.size else 0.0
            entropy[row, col] = clamp(ent / 4.0)

            quantized = (pixels // 32).astype(np.int16)
            codes = quantized[:, 0] * 64 + quantized[:, 1] * 8 + quantized[:, 2]
            _, counts = np.unique(codes, return_counts=True)
            unique_count = int(counts.size)
            unique[row, col] = clamp((unique_count - 1) / 24.0)
            dominant[row, col] = float(counts.max()) / pixel_count if counts.size else 1.0

            text_coverage[row, col] = float(text_mask[y1:y2, x1:x2].mean()) if text_mask.size else 0.0
            mean_color[row, col] = pixels.mean(axis=0)

    raster = (0.32 * texture + 0.28 * edge + 0.25 * entropy + 0.15 * unique) * (1.0 - 0.75 * text_coverage)

    bg = np.array(estimate_background_color(rgb), dtype=np.float32)
    color_distance = np.linalg.norm(mean_color - bg.reshape(1, 1, 3), axis=2)
    color_distance_score = np.clip(color_distance / 64.0, 0.0, 1.0).astype(np.float32)
    shape_base = 0.40 * dominant + 0.25 * (1.0 - edge) + 0.25 * (1.0 - entropy) + 0.10 * (1.0 - texture)
    shape = shape_base * (0.55 + 0.45 * color_distance_score) * (1.0 - 0.85 * text_coverage)
    shape = np.where((texture < 0.45) & (edge < 0.45) & (entropy < 0.72), shape, 0.0)

    return {
        "texture": texture,
        "edge": edge,
        "entropy": entropy,
        "unique": unique,
        "dominant": dominant,
        "textCoverage": text_coverage,
        "raster": raster.astype(np.float32),
        "shape": shape.astype(np.float32),
        "meanColor": mean_color,
    }


def bbox_tile_slice(box: BBox, tile_size: int, shape: tuple[int, int]) -> tuple[slice, slice]:
    rows, cols = shape
    row1 = max(0, min(rows, box.y // tile_size))
    col1 = max(0, min(cols, box.x // tile_size))
    row2 = max(row1 + 1, min(rows, math.ceil(box.y2 / tile_size)))
    col2 = max(col1 + 1, min(cols, math.ceil(box.x2 / tile_size)))
    return slice(row1, row2), slice(col1, col2)


def count_text_blocks(box: BBox, blocks: list[OCRBlock]) -> int:
    return sum(1 for block in blocks if intersection_area(box, block.bbox) > 0)


def bbox_scores(box: BBox, maps: dict[str, np.ndarray], text_mask: np.ndarray, tile_size: int) -> dict[str, float]:
    tile_rows, tile_cols = maps["raster"].shape
    row_slice, col_slice = bbox_tile_slice(box, tile_size, (tile_rows, tile_cols))
    text_overlap = float(text_mask[box.y : box.y2, box.x : box.x2].mean()) if box.area > 0 else 0.0

    return {
        "texture": round(float(maps["texture"][row_slice, col_slice].mean()), 4),
        "edge": round(float(maps["edge"][row_slice, col_slice].mean()), 4),
        "entropy": round(float(maps["entropy"][row_slice, col_slice].mean()), 4),
        "unique": round(float(maps["unique"][row_slice, col_slice].mean()), 4),
        "dominant": round(float(maps["dominant"][row_slice, col_slice].mean()), 4),
        "textOverlap": round(text_overlap, 4),
        "raster": round(float(maps["raster"][row_slice, col_slice].mean()), 4),
        "shape": round(float(maps["shape"][row_slice, col_slice].mean()), 4),
    }


def text_mask_ratio(box: BBox, text_mask: np.ndarray) -> float:
    if not text_mask.size or box.area <= 0:
        return 0.0
    height, width = text_mask.shape
    clamped = clamp_box(box, width, height)
    if clamped is None or clamped.area <= 0:
        return 0.0
    return float(text_mask[clamped.y : clamped.y2, clamped.x : clamped.x2].mean())


def text_mask_score_for_box(box: BBox, text_mask: np.ndarray) -> float:
    if not text_mask.size or box.area <= 0:
        return 0.0
    height, width = text_mask.shape
    clamped = clamp_box(box, width, height)
    if clamped is None or clamped.area <= 0:
        return 0.0
    local = text_mask[clamped.y : clamped.y2, clamped.x : clamped.x2]
    if local.size == 0:
        return 0.0
    if local.any():
        return max(float(local.mean()), 0.24)
    padded = clamp_box(BBox(clamped.x - 2, clamped.y - 2, clamped.width + 4, clamped.height + 4), width, height)
    if padded is None:
        return 0.0
    expanded = text_mask[padded.y : padded.y2, padded.x : padded.x2]
    if not expanded.any():
        return 0.0
    return min(0.34, 0.18 + float(expanded.mean()) * 0.50)
