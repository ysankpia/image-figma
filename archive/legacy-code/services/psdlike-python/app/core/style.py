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

from .colors import (
    color_distance,
    color_hex,
    dominant_cluster_color,
    dominant_cluster_stats,
)
from .schema import BBox, Candidate, clamp_box

# Mechanical migration from PSD-like V1 oracle. Keep behavior changes out of this stage.


@dataclass(frozen=True)
class TextStyleContext:
    owner_bbox: BBox | None = None
    owner_fill: tuple[int, int, int] | None = None
    owner_reason: str = ""
    owner_role: str = "unknown"
    owner_id: str = ""


@dataclass(frozen=True)
class TextColorSample:
    color: str
    source: str
    background: str
    score: float


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
    if all(key in shape.scores for key in ("strokeR", "strokeG", "strokeB")):
        stroke = np.array(
            [
                shape.scores.get("strokeR", 0.0),
                shape.scores.get("strokeG", 0.0),
                shape.scores.get("strokeB", 0.0),
            ],
            dtype=np.uint8,
        )
        style["stroke"] = {
            "color": color_hex(stroke),
            "width": max(1, int(round(shape.scores.get("strokeWidth", 1.0)))),
        }
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


def sample_text_color(rgb: np.ndarray, box: BBox, context: TextStyleContext | None = None) -> str:
    return sample_text_color_with_diagnostics(rgb, box, context).color


def sample_text_color_with_diagnostics(
    rgb: np.ndarray,
    box: BBox,
    context: TextStyleContext | None = None,
) -> TextColorSample:
    region = rgb[box.y : box.y2, box.x : box.x2]
    if region.size == 0:
        return TextColorSample("#111111", "fallback_contrast", "#ffffff", 0.0)
    pixels = region.reshape(-1, 3).astype(np.uint8)
    if context and context.owner_fill is not None:
        bg = np.asarray(context.owner_fill, dtype=np.uint8)
        source = "owner_surface_contrast_sample"
    else:
        bg = estimate_text_background_for_box(rgb, box)
        source = "local_contrast_sample"
    box_fill, box_fill_ratio = dominant_cluster_stats(pixels, bucket_size=16)
    if color_distance(box_fill, bg) > 72.0 and box_fill_ratio >= 0.24:
        bg = box_fill.astype(np.uint8)
        source = "ocr_box_dominant_background_contrast_sample"
    bucket_count = 16
    buckets = np.clip(pixels.astype(np.int16) // 16, 0, bucket_count - 1)
    codes = buckets[:, 0] * bucket_count * bucket_count + buckets[:, 1] * bucket_count + buckets[:, 2]
    values, counts = np.unique(codes, return_counts=True)
    best_color = np.array([17, 17, 17], dtype=np.uint8)
    best_score = -1.0
    bg_luma = relative_luminance(bg)
    for value, count in zip(values, counts):
        cluster = pixels[codes == value]
        if len(cluster) < max(1, len(pixels) // 120):
            continue
        color = np.median(cluster, axis=0)
        distance = color_distance(color, bg)
        if distance < 42.0:
            continue
        color_luma = relative_luminance(color)
        luma_delta = abs(color_luma - bg_luma)
        if luma_delta < 24.0 and distance < 80.0:
            continue
        polarity_factor = 1.15 if (bg_luma >= 128 and color_luma < bg_luma) or (bg_luma < 128 and color_luma > bg_luma) else 0.82
        score = min(math.sqrt(float(count)), 6.0) * (distance / 441.7) * polarity_factor * (luma_delta / 255.0)
        if score > best_score:
            best_score = score
            best_color = np.clip(color, 0, 255).astype(np.uint8)
    if best_score < 0:
        best_color = np.array([17, 17, 17], dtype=np.uint8) if bg_luma > 150 else np.array([255, 255, 255], dtype=np.uint8)
        source = "fallback_contrast"
        best_score = 0.0
    return TextColorSample(color_hex(best_color), source, color_hex(bg), round(float(best_score), 4))


def estimate_text_style(
    rgb: np.ndarray,
    box: BBox,
    text: str,
    context: TextStyleContext | None = None,
) -> dict[str, Any]:
    raw_size = max(8, min(96, round(box.height * 0.8)))
    fitted_size, measured = fit_text_font_size(text, box, raw_size, context)
    line_height_factor = 1.0 if is_owner_bounded_label_context(context, box, text) else 1.12
    line_height = max(8, min(120, math.ceil(fitted_size * line_height_factor)))
    color_sample = sample_text_color_with_diagnostics(rgb, box, context)
    font_family = infer_font_family(text)
    font_weight = infer_font_weight(rgb, box, text, context)
    return {
        "style": {
            "fontSize": fitted_size,
            "fontFamily": font_family,
            "fontWeight": font_weight,
            "lineHeight": line_height,
            "color": color_sample.color,
            "textAlign": "center" if is_owner_bounded_label_context(context, box, text) else "left",
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
            "textColorSource": color_sample.source,
            "textColorBackground": color_sample.background,
            "textForegroundScore": color_sample.score,
            "fontFamily": font_family,
            "fontWeight": font_weight,
            "textOwnerRole": context.owner_role if context else "unknown",
            "textOwnerReason": context.owner_reason if context else "",
            "textOwnerId": context.owner_id if context else "",
            "ownerAwareFit": 1 if is_owner_bounded_label_context(context, box, text) else 0,
        },
    }


def fit_text_font_size(
    text: str,
    box: BBox,
    raw_size: int,
    context: TextStyleContext | None = None,
) -> tuple[int, dict[str, int]]:
    value = text.strip()
    if not value or box.width <= 0 or box.height <= 0:
        return max(8, min(96, raw_size)), {"width": 0, "height": 0}
    max_size = max(8, min(96, raw_size))
    min_size = 8
    target_width = max(1, int(box.width * 0.98))
    target_height = max(1, int(box.height * 0.98))
    if is_owner_bounded_label_context(context, box, text) and context and context.owner_bbox is not None:
        horizontal_padding = max(4, int(round(context.owner_bbox.height * 0.28)))
        vertical_padding = max(3, int(round(context.owner_bbox.height * 0.18)))
        available_width = max(1, context.owner_bbox.width - horizontal_padding * 2)
        available_height = max(1, context.owner_bbox.height - vertical_padding * 2)
        if box.width >= context.owner_bbox.width * 0.30:
            target_width = min(max(target_width, int(available_width * 0.96)), max(1, int(context.owner_bbox.width * 0.88)))
        target_height = min(target_height, int(available_height * 0.92))
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


def infer_font_family(text: str) -> str:
    cjk = sum(1 for char in text if "\u3400" <= char <= "\u9fff")
    if cjk > 0:
        return "PingFang SC"
    return "Inter"


def is_owner_bounded_label_context(context: TextStyleContext | None, box: BBox, text: str) -> bool:
    if context is None or context.owner_bbox is None:
        return False
    if context.owner_role == "control_surface":
        return True
    if context.owner_role != "container_surface":
        return False
    owner = context.owner_bbox
    if owner.area <= 0 or owner.area > 18000:
        return False
    if owner.width > box.width * 3.6 or owner.height > box.height * 3.2:
        return False
    if len(text.strip()) > 8:
        return False
    return bbox_center_inside_for_style(box, owner)


def bbox_center_inside_for_style(inner: BBox, outer: BBox) -> bool:
    cx = inner.x + inner.width / 2
    cy = inner.y + inner.height / 2
    return outer.x <= cx <= outer.x2 and outer.y <= cy <= outer.y2


def infer_font_weight(
    rgb: np.ndarray,
    box: BBox,
    text: str,
    context: TextStyleContext | None = None,
) -> int:
    if context and context.owner_role == "control_surface" and len(text.strip()) >= 2:
        return 500
    if (
        context
        and context.owner_role == "container_surface"
        and context.owner_bbox is not None
        and text_centered_in_owner(box, context.owner_bbox)
        and has_cjk_text(text)
        and len(text.strip()) <= 10
    ):
        return 500
    if box.height >= 34 and len(text.strip()) <= 8:
        return 500
    return 400


def has_cjk_text(text: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" for char in text)


def text_centered_in_owner(text_box: BBox, owner_box: BBox) -> bool:
    if owner_box.width <= 0 or owner_box.height <= 0:
        return False
    text_cx = text_box.x + text_box.width / 2
    text_cy = text_box.y + text_box.height / 2
    owner_cx = owner_box.x + owner_box.width / 2
    owner_cy = owner_box.y + owner_box.height / 2
    return abs(text_cy - owner_cy) <= owner_box.height * 0.22 and abs(text_cx - owner_cx) <= owner_box.width * 0.38


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
    from .previews import load_preview_font
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
