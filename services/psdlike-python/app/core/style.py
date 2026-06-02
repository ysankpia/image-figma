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


def shape_fill(rgb: np.ndarray, shape: Candidate) -> str:
    if shape.reason in {
        "background_surface_band",
        "inferred_background_plate_from_surface_bands",
        "editable_control_surface_from_raster",
        "ocr_anchored_control_surface",
        "model_assisted_control_surface",
    }:
        return color_hex(
            np.array(
                [
                    shape.scores.get("fillR", 255.0),
                    shape.scores.get("fillG", 255.0),
                    shape.scores.get("fillB", 255.0),
                ],
                dtype=np.uint8,
            )
        )
    return median_fill(rgb, shape.bbox)


def shape_style(rgb: np.ndarray, shape: Candidate) -> dict[str, Any]:
    style: dict[str, Any] = {"fill": shape_fill(rgb, shape)}
    if shape.scores.get("confirmedControlSurface", 0.0) >= 1.0:
        radius = infer_control_corner_radius(rgb, shape)
        if radius > 0:
            style["cornerRadius"] = radius
    return style


def infer_control_corner_radius(rgb: np.ndarray, shape: Candidate) -> int:
    box = shape.bbox
    if box.width < 12 or box.height < 12:
        return 0
    fill = np.array(
        [
            shape.scores.get("fillR", 255.0),
            shape.scores.get("fillG", 255.0),
            shape.scores.get("fillB", 255.0),
        ],
        dtype=np.float32,
    )
    max_radius = max(0, min(box.width, box.height) // 2 - 1)
    if max_radius <= 0:
        return 0
    crop = rgb[box.y : box.y2, box.x : box.x2].astype(np.float32)
    if crop.size == 0:
        return 0
    close = np.linalg.norm(crop - fill.reshape(1, 1, 3), axis=2) <= 64.0
    radii: list[int] = []
    for corner in ("tl", "tr", "bl", "br"):
        radius = corner_background_run(close, corner, max_radius)
        if radius > 0:
            radii.append(radius)
    if not radii:
        return 0
    # Diagonal corner run is roughly radius * (1 - 1/sqrt(2)) for a quarter circle.
    radius = int(round(float(np.median(radii)) * 3.4))
    return max(0, min(max_radius, radius))


def corner_background_run(close_mask: np.ndarray, corner: str, max_radius: int) -> int:
    height, width = close_mask.shape
    limit = max(0, min(max_radius, height // 2, width // 2))
    run = 0
    for offset in range(limit):
        if corner == "tl":
            inside = bool(close_mask[offset, offset])
        elif corner == "tr":
            inside = bool(close_mask[offset, width - 1 - offset])
        elif corner == "bl":
            inside = bool(close_mask[height - 1 - offset, offset])
        else:
            inside = bool(close_mask[height - 1 - offset, width - 1 - offset])
        if inside:
            break
        run = offset + 1
    return run


def sample_text_color(rgb: np.ndarray, box: BBox) -> str:
    region = rgb[box.y : box.y2, box.x : box.x2]
    if region.size == 0:
        return "#111111"
    pixels = region.reshape(-1, 3).astype(np.uint8)
    bg = estimate_text_box_background(region)
    buckets = np.clip(pixels.astype(np.int16) // 24, 0, 10)
    codes = buckets[:, 0] * 121 + buckets[:, 1] * 11 + buckets[:, 2]
    values, counts = np.unique(codes, return_counts=True)
    best_color = np.array([17, 17, 17], dtype=np.uint8)
    best_score = -1.0
    for value, count in zip(values, counts):
        cluster = pixels[codes == value]
        if len(cluster) < max(2, len(pixels) // 80):
            continue
        color = np.median(cluster, axis=0)
        distance = color_distance(color, bg)
        coverage = float(count) / max(1, len(pixels))
        if distance < 36.0:
            continue
        score = distance * (1.0 - min(0.80, coverage))
        if score > best_score:
            best_score = score
            best_color = np.clip(color, 0, 255).astype(np.uint8)
    if best_score < 0:
        bg_luma = relative_luminance(bg)
        best_color = np.array([17, 17, 17], dtype=np.uint8) if bg_luma > 150 else np.array([255, 255, 255], dtype=np.uint8)
    return color_hex(best_color)


def estimate_text_style(rgb: np.ndarray, box: BBox, text: str) -> dict[str, Any]:
    raw_size = max(8, min(96, round(box.height * 0.8)))
    fitted_size, measured = fit_text_font_size(text, box, raw_size)
    line_height = max(8, min(120, math.ceil(fitted_size * 1.12)))
    return {
        "style": {
            "fontSize": fitted_size,
            "fontWeight": 400,
            "lineHeight": line_height,
            "color": sample_text_color(rgb, box),
        },
        "diagnostics": {
            "rawFontSize": raw_size,
            "fontSize": fitted_size,
            "lineHeight": line_height,
            "shrink": max(0, raw_size - fitted_size),
            "measuredWidth": measured["width"],
            "measuredHeight": measured["height"],
            "targetWidth": box.width,
            "targetHeight": box.height,
        },
    }


def fit_text_font_size(text: str, box: BBox, raw_size: int) -> tuple[int, dict[str, int]]:
    value = text.strip()
    if not value or box.width <= 0 or box.height <= 0:
        return max(8, min(96, raw_size)), {"width": 0, "height": 0}
    max_size = max(8, min(96, raw_size))
    min_size = 8
    target_width = max(1, int(box.width * 0.98))
    target_height = max(1, int(box.height * 0.98))
    best_size = min_size
    best_measured = measure_text_pixels(value, min_size)
    for size in range(max_size, min_size - 1, -1):
        measured = measure_text_pixels(value, size)
        if measured["width"] <= target_width and measured["height"] <= target_height:
            best_size = size
            best_measured = measured
            break
        best_measured = measured
    return best_size, best_measured


def measure_text_pixels(text: str, font_size: int) -> dict[str, int]:
    font = cached_preview_font(max(1, int(font_size)))
    lines = text.splitlines() or [text]
    widths: list[int] = []
    heights: list[int] = []
    for line in lines:
        content = line if line else " "
        try:
            left, top, right, bottom = font.getbbox(content)
            widths.append(max(0, int(math.ceil(right - left))))
            heights.append(max(1, int(math.ceil(bottom - top))))
        except AttributeError:
            width, height = font.getsize(content)
            widths.append(int(width))
            heights.append(int(height))
    line_height = max(max(heights), int(math.ceil(font_size * 1.08)))
    return {
        "width": max(widths) if widths else 0,
        "height": line_height * max(1, len(lines)),
    }


@lru_cache(maxsize=128)
def cached_preview_font(size: int) -> ImageFont.ImageFont:
    return load_preview_font(size)


def estimate_text_box_background(region: np.ndarray) -> np.ndarray:
    height, width, _ = region.shape
    edge = max(1, min(height, width, 3))
    samples = np.concatenate(
        [
            region[:edge, :, :].reshape(-1, 3),
            region[height - edge :, :, :].reshape(-1, 3),
            region[:, :edge, :].reshape(-1, 3),
            region[:, width - edge :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    return dominant_cluster_color(samples.astype(np.uint8), bucket_size=24)


def estimate_text_background_for_box(rgb: np.ndarray, box: BBox) -> np.ndarray:
    height, width, _ = rgb.shape
    padding = max(2, min(10, box.height // 2))
    padded = clamp_box(
        BBox(box.x - padding, box.y - padding, box.width + padding * 2, box.height + padding * 2),
        width,
        height,
    )
    if padded is None:
        return estimate_text_box_background(rgb[box.y : box.y2, box.x : box.x2])
    return estimate_text_box_background(rgb[padded.y : padded.y2, padded.x : padded.x2])


def relative_luminance(color: tuple[int, int, int] | np.ndarray) -> float:
    rgb = np.asarray(color, dtype=np.float32)
    return float(0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2])
