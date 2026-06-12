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


def crop_raster_assets(
    image: Image.Image,
    candidates: list[Candidate],
    output_dir: Path,
    text_mask: np.ndarray | None = None,
    ocr_blocks: list[OCRBlock] | None = None,
    rgb: np.ndarray | None = None,
) -> dict[str, str]:
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    asset_refs: dict[str, str] = {}
    for index, candidate in enumerate(candidates, start=1):
        layer_id = f"raster_{index:04d}"
        filename = f"{layer_id}.png"
        crop = image.crop((candidate.bbox.x, candidate.bbox.y, candidate.bbox.x2, candidate.bbox.y2)).convert("RGBA")
        crop = inpaint_text_pixels_in_raster(
            crop,
            candidate,
            rgb=rgb,
            ocr_blocks=ocr_blocks or [],
            text_mask=text_mask,
        )
        crop.save(assets_dir / filename)
        asset_refs[candidate.id] = f"assets/{filename}"
    return asset_refs


def inpaint_text_pixels_in_raster(
    crop: Image.Image,
    candidate: Candidate,
    rgb: np.ndarray | None,
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray | None,
) -> Image.Image:
    if rgb is None or text_mask is None or not text_mask.size:
        return crop
    rgba = np.asarray(crop).copy()
    changed = False
    image_height, image_width, _ = rgb.shape

    for block in ocr_blocks:
        if intersection_area(candidate.bbox, block.bbox) <= 0:
            continue
        block_box = clamp_box(block.bbox, image_width, image_height)
        if block_box is None:
            continue
        x1 = max(candidate.bbox.x, block_box.x)
        y1 = max(candidate.bbox.y, block_box.y)
        x2 = min(candidate.bbox.x2, block_box.x2)
        y2 = min(candidate.bbox.y2, block_box.y2)
        if x2 <= x1 or y2 <= y1:
            continue

        fill = estimate_inpaint_fill_for_candidate_text(
            rgb=rgb,
            candidate=candidate,
            block_box=block_box,
            text_mask=text_mask,
        )
        button_like = is_button_like_text_span(rgb, fill, candidate, block_box, x1, y1, x2, y2)
        if button_like:
            x1 = max(candidate.bbox.x, block_box.x - 2)
            y1 = max(candidate.bbox.y, block_box.y - 2)
            x2 = min(candidate.bbox.x2, block_box.x2 + 2)
            y2 = min(candidate.bbox.y2, block_box.y2 + 2)
        local_mask = build_candidate_local_text_mask(
            rgb=rgb,
            fill=fill,
            candidate=candidate,
            block_box=block_box,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            fallback_mask=text_mask,
            force_button_text=button_like,
        )
        if local_mask.shape != (y2 - y1, x2 - x1) or not local_mask.any():
            continue
        lx1 = x1 - candidate.bbox.x
        ly1 = y1 - candidate.bbox.y
        lx2 = lx1 + (x2 - x1)
        ly2 = ly1 + (y2 - y1)
        region = rgba[ly1:ly2, lx1:lx2]
        if button_like:
            region[local_mask, 0:3] = np.asarray(fill, dtype=np.uint8)
        else:
            region[local_mask, 0:3] = smooth_inpaint_fill(region[:, :, 0:3], local_mask, fill)
        region[local_mask, 3] = 255
        changed = True

    if not changed:
        return crop
    return Image.fromarray(rgba, mode="RGBA")


def smooth_inpaint_fill(region_rgb: np.ndarray, local_mask: np.ndarray, fill: np.ndarray) -> np.ndarray:
    output = np.zeros((int(local_mask.sum()), 3), dtype=np.uint8)
    if output.size == 0:
        return output
    background = np.asarray(fill, dtype=np.float32)
    padded_region = np.pad(region_rgb.astype(np.float32), ((1, 1), (1, 1), (0, 0)), mode="edge")
    padded_mask = np.pad(local_mask.astype(bool), 1, mode="constant", constant_values=False)
    values: list[np.ndarray] = []
    ys, xs = np.where(local_mask)
    for y, x in zip(ys, xs):
        window = padded_region[y : y + 3, x : x + 3]
        mask_window = padded_mask[y : y + 3, x : x + 3]
        neighbors = window[~mask_window]
        if neighbors.size:
            close = neighbors[np.linalg.norm(neighbors - background.reshape(1, 3), axis=1) <= 42.0]
            if close.size:
                values.append(np.median(close, axis=0))
                continue
        values.append(background)
    return np.clip(np.stack(values), 0, 255).astype(np.uint8)


def build_candidate_local_text_mask(
    rgb: np.ndarray,
    fill: np.ndarray,
    candidate: Candidate,
    block_box: BBox,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    fallback_mask: np.ndarray,
    force_button_text: bool = False,
) -> np.ndarray:
    region = rgb[y1:y2, x1:x2]
    if region.size == 0:
        return np.zeros((max(0, y2 - y1), max(0, x2 - x1)), dtype=bool)
    diff = np.linalg.norm(region.astype(np.float32) - fill.reshape(1, 1, 3).astype(np.float32), axis=2)
    strong_button_text = force_button_text or is_button_like_text_region(candidate, block_box, diff)
    if strong_button_text:
        threshold = max(18.0, min(58.0, float(np.percentile(diff, 52)) * 0.62))
    else:
        threshold = max(34.0, min(96.0, float(np.percentile(diff, 68)) * 0.72))
    local = diff >= threshold
    if local.size and float(local.mean()) > 0.58:
        threshold = max(42.0, float(np.percentile(diff, 82)))
        local = diff >= threshold
    if local.size and float(local.mean()) < 0.015 and diff.max(initial=0.0) >= 40.0:
        threshold = max(28.0, float(np.percentile(diff, 88)) * 0.66)
        local = diff >= threshold

    fallback = fallback_mask[y1:y2, x1:x2]
    if fallback.shape == local.shape and fallback.any():
        local |= fallback

    block_area = max(1, block_box.area)
    coverage = float(local.mean()) if local.size else 0.0
    if coverage > 0.62:
        local = diff >= max(50.0, float(np.percentile(diff, 90)))
    elif strong_button_text:
        local = binary_close(binary_dilate(local, iterations=1), iterations=1)
    elif coverage < 0.42 and block_area <= max(2400, candidate.bbox.area * 0.45):
        local = binary_dilate(local, iterations=1)
    return local


def is_button_like_text_span(
    rgb: np.ndarray,
    fill: np.ndarray,
    candidate: Candidate,
    block_box: BBox,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> bool:
    region = rgb[y1:y2, x1:x2]
    if region.size == 0:
        return False
    diff = np.linalg.norm(region.astype(np.float32) - fill.reshape(1, 1, 3).astype(np.float32), axis=2)
    return is_button_like_text_region(candidate, block_box, diff)


def is_button_like_text_region(candidate: Candidate, block_box: BBox, diff: np.ndarray) -> bool:
    if candidate.bbox.area <= 0 or block_box.area <= 0 or diff.size == 0:
        return False
    text_ratio = block_box.area / candidate.bbox.area
    candidate_aspect = candidate.bbox.width / max(1, candidate.bbox.height)
    high_contrast = float(np.percentile(diff, 90)) >= 92.0 and float(np.percentile(diff, 50)) >= 24.0
    compact_surface = (
        candidate.bbox.height <= 72
        and candidate.bbox.width <= 360
        and candidate_aspect >= 1.6
        and 0.16 <= text_ratio <= 0.78
    )
    return compact_surface and high_contrast


def estimate_inpaint_fill_for_candidate_text(
    rgb: np.ndarray,
    candidate: Candidate,
    block_box: BBox,
    text_mask: np.ndarray,
) -> np.ndarray:
    crop = rgb[candidate.bbox.y : candidate.bbox.y2, candidate.bbox.x : candidate.bbox.x2]
    if crop.size == 0:
        return estimate_text_background_for_box(rgb, block_box)

    local_text = text_mask[candidate.bbox.y : candidate.bbox.y2, candidate.bbox.x : candidate.bbox.x2]
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)

    lx1 = max(0, block_box.x - candidate.bbox.x)
    ly1 = max(0, block_box.y - candidate.bbox.y)
    lx2 = min(candidate.bbox.width, block_box.x2 - candidate.bbox.x)
    ly2 = min(candidate.bbox.height, block_box.y2 - candidate.bbox.y)
    if lx2 <= lx1 or ly2 <= ly1:
        return candidate_non_text_dominant_color(crop, local_text, rgb, block_box)

    pad = max(2, min(8, block_box.height // 2))
    rx1 = max(0, lx1 - pad)
    ry1 = max(0, ly1 - pad)
    rx2 = min(candidate.bbox.width, lx2 + pad)
    ry2 = min(candidate.bbox.height, ly2 + pad)
    ring = np.zeros(crop.shape[:2], dtype=bool)
    ring[ry1:ry2, rx1:rx2] = True
    ring[ly1:ly2, lx1:lx2] = False
    ring &= ~local_text
    ring_pixels = crop[ring]
    if ring_pixels.shape[0] >= max(8, block_box.area // 12):
        return dominant_cluster_color(ring_pixels.astype(np.uint8), bucket_size=20)

    block_region_mask = np.zeros(crop.shape[:2], dtype=bool)
    block_region_mask[ly1:ly2, lx1:lx2] = True
    block_region_mask &= ~local_text
    block_pixels = crop[block_region_mask]
    if block_pixels.shape[0] >= max(4, block_box.area // 20):
        return dominant_cluster_color(block_pixels.astype(np.uint8), bucket_size=20)

    return candidate_non_text_dominant_color(crop, local_text, rgb, block_box)


def candidate_non_text_dominant_color(
    crop: np.ndarray,
    local_text: np.ndarray,
    rgb: np.ndarray,
    block_box: BBox,
) -> np.ndarray:
    non_text = ~local_text if local_text.shape == crop.shape[:2] else np.ones(crop.shape[:2], dtype=bool)
    pixels = crop[non_text]
    if pixels.shape[0] >= 16:
        return dominant_cluster_color(pixels.astype(np.uint8), bucket_size=20)
    return estimate_text_background_for_box(rgb, block_box)


def median_fill(rgb: np.ndarray, box: BBox) -> str:
    region = rgb[box.y : box.y2, box.x : box.x2]
    if region.size == 0:
        return "#ffffff"
    color = np.median(region.reshape(-1, 3), axis=0).astype(np.uint8)
    return f"#{int(color[0]):02x}{int(color[1]):02x}{int(color[2]):02x}"
