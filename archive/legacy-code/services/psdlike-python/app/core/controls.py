from __future__ import annotations

import argparse
import html
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .schema import BBox, Candidate, OCRBlock, intersection_area, ioa, iou

# Mechanical migration from PSD-like V1 oracle. Keep behavior changes out of this stage.


@dataclass(frozen=True)
class ControlProfile:
    kind: str
    max_area: int
    max_aspect: float
    min_height: int
    min_area: int = 480
    max_container_area_ratio: float = 0.08
    max_local_window_area_ratio: float = 0.10
    search_x_scale: float = 2.2
    search_y_scale: float = 4.2
    search_x_cap: int = 220
    search_y_cap: int = 150


@dataclass(frozen=True)
class RingEvidence:
    min_delta: float
    support_delta: float
    median_delta: float
    max_delta: float
    strong_side_count: int
    fill_to_local_delta: float
    fill_to_page_delta: float
    side_deltas: tuple[float, float, float, float]
    stroke_color: tuple[int, int, int] | None = None
    stroke_delta: float = 0.0


@dataclass(frozen=True)
class LocalSurfaceCandidate:
    id: str
    bbox: BBox
    fill: tuple[int, int, int]
    seed_text_id: str
    contained_text_ids: list[str]
    score: float
    scores: dict[str, float]
    extraction_reason: str


@dataclass(frozen=True)
class SurfaceRoleDecision:
    surface_id: str
    role: str
    decision: str
    reason: str
    source_refs: list[str]


NUMERIC_METRIC_PATTERN = re.compile(r"^[+\-≈~￥¥$€£\s]*\d[\d,.\s]*(万|亿|k|K|m|M|g|G)?$")
CURRENCY_PERCENT_PATTERN = re.compile(r"^[+\-≈~￥¥$€£\s]*\d[\d,.\s]*(%|％|万|亿|k|K|m|M)?$")
DATE_TIME_PATTERN = re.compile(r"^(\d{1,4}[-/:]\d{1,2}([-/:\s]\d{1,4})?|\d{1,2}:\d{2})$")


def build_control_profile(width: int, height: int) -> ControlProfile:
    page_area = max(1, width * height)
    aspect = width / max(1, height)
    if aspect < 0.85:
        return ControlProfile(
            kind="mobile",
            max_area=int(min(24_000, max(6_000, page_area * 0.04))),
            max_aspect=14.0,
            min_height=14,
            max_container_area_ratio=0.08,
            max_local_window_area_ratio=0.10,
            search_x_scale=2.2,
            search_y_scale=4.2,
            search_x_cap=220,
            search_y_cap=150,
        )
    return ControlProfile(
        kind="web_like",
        max_area=int(min(48_000, max(6_000, page_area * 0.04))),
        max_aspect=36.0,
        min_height=12,
        max_container_area_ratio=0.14,
        max_local_window_area_ratio=0.18,
        search_x_scale=10.0,
        search_y_scale=4.0,
        search_x_cap=640,
        search_y_cap=180,
    )


def control_profile_diagnostics(profile: ControlProfile) -> dict[str, Any]:
    return {
        "controlProfileKind": profile.kind,
        "controlMaxArea": profile.max_area,
        "controlMaxAspect": profile.max_aspect,
        "controlMaxContainerAreaRatio": profile.max_container_area_ratio,
        "controlMaxLocalWindowAreaRatio": profile.max_local_window_area_ratio,
    }


def ocr_text_role(text: str) -> str:
    normalized = "".join(text.strip().split())
    if not normalized:
        return "short_symbol"
    if DATE_TIME_PATTERN.match(normalized):
        return "date_or_time"
    if "%" in normalized or "％" in normalized or normalized[:1] in {"￥", "¥", "$", "€", "£"}:
        if CURRENCY_PERCENT_PATTERN.match(normalized):
            return "currency_or_percent"
    digit_count = sum(ch.isdigit() for ch in normalized)
    if digit_count > 0 and digit_count / max(1, len(normalized)) >= 0.55 and NUMERIC_METRIC_PATTERN.match(normalized):
        return "numeric_metric"
    if len(normalized) <= 2 and not any(ch.isalnum() for ch in normalized):
        return "short_symbol"
    return "normal_label"


def role_requires_strong_boundary(role: str) -> bool:
    return role in {"numeric_metric", "currency_or_percent", "date_or_time", "short_symbol"}


def stable_text_block_key(block_id: str) -> float:
    return float(sum((index + 1) * ord(char) for index, char in enumerate(block_id)))


def control_surface_fill(
    rgb: np.ndarray,
    candidate: Candidate,
    text_mask: np.ndarray,
    support_box: BBox | None = None,
    text_box: BBox | None = None,
) -> tuple[np.ndarray, float, float]:
    crop = rgb[candidate.bbox.y : candidate.bbox.y2, candidate.bbox.x : candidate.bbox.x2]
    if crop.size == 0:
        return np.array([255, 255, 255], dtype=np.uint8), 0.0, 0.0
    local_text = text_mask[candidate.bbox.y : candidate.bbox.y2, candidate.bbox.x : candidate.bbox.x2]
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)

    fill_pixels = None
    if text_box is not None:
        support_pixels = control_surface_text_support_pixels(rgb, candidate.bbox, text_box, text_mask)
        if support_pixels.shape[0] >= max(12, crop.shape[0] * crop.shape[1] // 36):
            fill_pixels = support_pixels
    if fill_pixels is None and support_box is not None:
        support_mask = support_surface_mask(candidate.bbox, support_box, crop.shape[1], crop.shape[0])
        support_pixels = crop[support_mask & ~local_text]
        if support_pixels.shape[0] >= max(12, crop.shape[0] * crop.shape[1] // 24):
            fill_pixels = support_pixels
    if fill_pixels is None:
        fill_pixels = crop[~local_text]
    if fill_pixels.shape[0] < max(16, crop.shape[0] * crop.shape[1] // 8):
        fill_pixels = crop.reshape(-1, 3)

    fill, _ = dominant_cluster_stats(fill_pixels.astype(np.uint8), bucket_size=20)
    measure_pixels = crop[~binary_dilate(local_text, iterations=1)]
    if measure_pixels.shape[0] < max(16, crop.shape[0] * crop.shape[1] // 8):
        measure_pixels = fill_pixels
    distances = np.linalg.norm(measure_pixels.astype(np.float32) - fill.reshape(1, 3).astype(np.float32), axis=1)
    coverage = float((distances <= 32.0).mean()) if distances.size else 0.0
    close_coverage = float((distances <= 64.0).mean()) if distances.size else 0.0
    return fill, coverage, close_coverage


def control_surface_text_support_pixels(
    rgb: np.ndarray,
    candidate_box: BBox,
    text_box: BBox,
    text_mask: np.ndarray,
) -> np.ndarray:
    height, width, _ = rgb.shape
    candidate = clamp_box(candidate_box, width, height)
    if candidate is None:
        return np.empty((0, 3), dtype=np.uint8)
    y_pad = max(2, min(10, round(text_box.height * 0.24)))
    x_pad = max(3, min(16, round(text_box.height * 0.42)))
    vertical_band = (
        max(candidate.y, text_box.y - y_pad),
        min(candidate.y2, text_box.y2 + y_pad),
    )
    horizontal_band = (
        max(candidate.x, text_box.x - x_pad),
        min(candidate.x2, text_box.x2 + x_pad),
    )

    side_regions = [
        BBox(candidate.x, vertical_band[0], max(0, text_box.x - candidate.x), max(0, vertical_band[1] - vertical_band[0])),
        BBox(text_box.x2, vertical_band[0], max(0, candidate.x2 - text_box.x2), max(0, vertical_band[1] - vertical_band[0])),
    ]
    side_pixels = sample_regions_excluding_text(rgb, text_mask, side_regions)
    if side_pixels.shape[0] >= max(12, candidate.area // 48):
        return side_pixels

    vertical_regions = [
        BBox(horizontal_band[0], candidate.y, max(0, horizontal_band[1] - horizontal_band[0]), max(0, text_box.y - candidate.y)),
        BBox(horizontal_band[0], text_box.y2, max(0, horizontal_band[1] - horizontal_band[0]), max(0, candidate.y2 - text_box.y2)),
    ]
    return sample_regions_excluding_text(rgb, text_mask, side_regions + vertical_regions)


def sample_regions_excluding_text(rgb: np.ndarray, text_mask: np.ndarray, regions: list[BBox]) -> np.ndarray:
    height, width, _ = rgb.shape
    samples: list[np.ndarray] = []
    for region in regions:
        box = clamp_box(region, width, height)
        if box is None or box.area <= 0:
            continue
        crop = rgb[box.y : box.y2, box.x : box.x2]
        local_text = text_mask[box.y : box.y2, box.x : box.x2]
        if local_text.shape != crop.shape[:2]:
            local_text = np.zeros(crop.shape[:2], dtype=bool)
        pixels = crop[~local_text]
        if pixels.size:
            samples.append(pixels.reshape(-1, 3))
    if not samples:
        return np.empty((0, 3), dtype=np.uint8)
    return np.concatenate(samples, axis=0).astype(np.uint8)


def support_surface_mask(candidate_box: BBox, support_box: BBox, width: int, height: int) -> np.ndarray:
    x1 = max(0, min(width, support_box.x - candidate_box.x))
    y1 = max(0, min(height, support_box.y - candidate_box.y))
    x2 = max(0, min(width, support_box.x2 - candidate_box.x))
    y2 = max(0, min(height, support_box.y2 - candidate_box.y))
    mask = np.zeros((height, width), dtype=bool)
    if x2 <= x1 or y2 <= y1:
        return mask
    mask[y1:y2, x1:x2] = True
    return mask


def ocr_support_box(text_box: BBox, candidate_box: BBox) -> BBox:
    pad_x = max(4, min(18, round(text_box.height * 0.45)))
    pad_y = max(3, min(12, round(text_box.height * 0.28)))
    return BBox(
        max(candidate_box.x, text_box.x - pad_x),
        max(candidate_box.y, text_box.y - pad_y),
        min(candidate_box.x2, text_box.x2 + pad_x) - max(candidate_box.x, text_box.x - pad_x),
        min(candidate_box.y2, text_box.y2 + pad_y) - max(candidate_box.y, text_box.y - pad_y),
    )


def contained_text_blocks(candidate: Candidate, ocr_blocks: list[OCRBlock]) -> list[OCRBlock]:
    blocks: list[OCRBlock] = []
    for block in ocr_blocks:
        if block.bbox.area <= 0:
            continue
        coverage = intersection_area(candidate.bbox, block.bbox) / block.bbox.area
        if coverage >= 0.82:
            blocks.append(block)
    return blocks


def related_control_text_blocks(anchor: OCRBlock, contained: list[OCRBlock]) -> list[OCRBlock]:
    related: list[OCRBlock] = []
    for block in contained:
        if block.id == anchor.id:
            related.append(block)
            continue
        same_baseline = abs((block.bbox.y + block.bbox.height / 2) - (anchor.bbox.y + anchor.bbox.height / 2)) <= max(
            4, min(block.bbox.height, anchor.bbox.height) * 0.42
        )
        vertical_overlap = intersection_1d(block.bbox.y, block.bbox.y2, anchor.bbox.y, anchor.bbox.y2) / max(
            1, min(block.bbox.height, anchor.bbox.height)
        )
        compact_gap = horizontal_gap(block.bbox, anchor.bbox) <= max(12, min(block.bbox.height, anchor.bbox.height) * 0.85)
        if same_baseline and vertical_overlap >= 0.55 and compact_gap:
            related.append(block)
    return sorted(related, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def intersection_1d(a1: int, a2: int, b1: int, b2: int) -> int:
    return max(0, min(a2, b2) - max(a1, b1))


def horizontal_gap(a: BBox, b: BBox) -> int:
    if a.x2 < b.x:
        return b.x - a.x2
    if b.x2 < a.x:
        return a.x - b.x2
    return 0


def chart_tick_like_block(anchor: OCRBlock, ocr_blocks: list[OCRBlock]) -> bool:
    role = ocr_text_role(anchor.text)
    if role not in {"numeric_metric", "currency_or_percent", "date_or_time"}:
        return False
    peers = [
        block
        for block in ocr_blocks
        if block.bbox.area > 0
        and ocr_text_role(block.text) in {"numeric_metric", "currency_or_percent", "date_or_time"}
        and nearby_axis_peer(anchor.bbox, block.bbox)
    ]
    if len(peers) < 3:
        return False
    return aligned_tick_group(peers, axis="x") or aligned_tick_group(peers, axis="y")


def nearby_axis_peer(anchor: BBox, peer: BBox) -> bool:
    x_close = abs(center_x(anchor) - center_x(peer)) <= max(anchor.width, peer.width, 48)
    y_close = abs(center_y(anchor) - center_y(peer)) <= max(anchor.height, peer.height, 48)
    vertical_zone = abs(center_x(anchor) - center_x(peer)) <= max(anchor.width, peer.width) * 1.8
    horizontal_zone = abs(center_y(anchor) - center_y(peer)) <= max(anchor.height, peer.height) * 1.8
    return x_close or y_close or vertical_zone or horizontal_zone


def aligned_tick_group(blocks: list[OCRBlock], axis: str) -> bool:
    if len(blocks) < 3:
        return False
    if axis == "x":
        aligned_values = [center_x(block.bbox) for block in blocks]
        spread_values = [center_y(block.bbox) for block in blocks]
        tolerance = max(12.0, float(np.median([block.bbox.width for block in blocks])) * 0.75)
    else:
        aligned_values = [center_y(block.bbox) for block in blocks]
        spread_values = [center_x(block.bbox) for block in blocks]
        tolerance = max(12.0, float(np.median([block.bbox.height for block in blocks])) * 0.75)
    if max(aligned_values) - min(aligned_values) > tolerance:
        return False
    ordered = sorted(spread_values)
    gaps = [ordered[index + 1] - ordered[index] for index in range(len(ordered) - 1) if ordered[index + 1] - ordered[index] > 1]
    if len(gaps) < 2:
        return False
    median_gap = float(np.median(gaps))
    if median_gap <= 0:
        return False
    stable_gaps = sum(1 for gap in gaps if abs(gap - median_gap) <= max(8.0, median_gap * 0.45))
    return stable_gaps >= max(2, len(gaps) - 1)


def center_x(box: BBox) -> float:
    return box.x + box.width / 2


def center_y(box: BBox) -> float:
    return box.y + box.height / 2


def control_text_contrast(rgb: np.ndarray, blocks: list[OCRBlock], fill: np.ndarray) -> float:
    best = 0.0
    height, width, _ = rgb.shape
    for block in blocks:
        box = clamp_box(block.bbox, width, height)
        if box is None:
            continue
        region = rgb[box.y : box.y2, box.x : box.x2]
        if region.size == 0:
            continue
        pixels = region.reshape(-1, 3).astype(np.float32)
        distances = np.linalg.norm(pixels - fill.reshape(1, 3).astype(np.float32), axis=1)
        if distances.size:
            best = max(best, float(np.percentile(distances, 98)))
    return best


def expanded_box(box: BBox, width: int, height: int, x_pad: int, y_pad: int) -> BBox | None:
    return clamp_box(
        BBox(box.x - x_pad, box.y - y_pad, box.width + x_pad * 2, box.height + y_pad * 2),
        width,
        height,
    )


def intersection_box(a: BBox, b: BBox) -> BBox | None:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return BBox(x1, y1, x2 - x1, y2 - y1)


def local_surface_window_for_text(
    box: BBox,
    width: int,
    height: int,
    profile: ControlProfile | None = None,
    limit_window: BBox | None = None,
) -> BBox | None:
    profile = profile or build_control_profile(width, height)
    x_pad = max(32, min(profile.search_x_cap, int(round(box.width * profile.search_x_scale))))
    y_pad = max(22, min(profile.search_y_cap, int(round(box.height * profile.search_y_scale))))
    window = expanded_box(box, width, height, x_pad, y_pad)
    if window is None or limit_window is None:
        return clamp_local_surface_window(window, box, width, height, profile)
    return clamp_local_surface_window(intersection_box(window, limit_window), box, width, height, profile)


def clamp_local_surface_window(
    window: BBox | None,
    seed: BBox,
    width: int,
    height: int,
    profile: ControlProfile,
) -> BBox | None:
    if window is None:
        return None
    max_area = max(profile.max_area * 2, int(width * height * profile.max_local_window_area_ratio))
    if window.area <= max_area:
        return window
    aspect = window.width / max(1, window.height)
    target_height = max(seed.height + 44, int(round(math.sqrt(max_area / max(1.0, aspect)))))
    target_width = max(seed.width + 64, int(round(target_height * aspect)))
    if target_width * target_height > max_area:
        scale = math.sqrt(max_area / max(1, target_width * target_height))
        target_width = max(seed.width + 64, int(round(target_width * scale)))
        target_height = max(seed.height + 44, int(round(target_height * scale)))
    center_x_value = seed.x + seed.width / 2
    center_y_value = seed.y + seed.height / 2
    return clamp_box(
        BBox(
            int(round(center_x_value - target_width / 2)),
            int(round(center_y_value - target_height / 2)),
            min(width, target_width),
            min(height, target_height),
        ),
        width,
        height,
    )


def estimate_local_surface_fill_near_text(
    rgb: np.ndarray,
    text_mask: np.ndarray,
    block: OCRBlock,
    page_background: tuple[int, int, int] | np.ndarray,
    limit_window: BBox | None = None,
) -> tuple[np.ndarray, float]:
    height, width, _ = rgb.shape
    outer_pad_x = max(8, min(80, int(round(block.bbox.width * 0.55))))
    outer_pad_y = max(6, min(48, int(round(block.bbox.height * 1.35))))
    outer = expanded_box(block.bbox, width, height, outer_pad_x, outer_pad_y)
    inner = expanded_box(block.bbox, width, height, 1, 1)
    if outer is None:
        return np.array([255, 255, 255], dtype=np.uint8), 0.0
    if limit_window is not None:
        outer = intersection_box(outer, limit_window)
        if outer is None:
            return np.array([255, 255, 255], dtype=np.uint8), 0.0

    crop = rgb[outer.y : outer.y2, outer.x : outer.x2]
    local_text = text_mask[outer.y : outer.y2, outer.x : outer.x2].copy()
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)
    if inner is not None:
        local_text[
            max(0, inner.y - outer.y) : max(0, inner.y2 - outer.y),
            max(0, inner.x - outer.x) : max(0, inner.x2 - outer.x),
        ] = True

    pixels = crop[~local_text]
    if pixels.shape[0] < 16:
        pixels = crop.reshape(-1, 3)
    local_fill, local_coverage = dominant_cluster_stats(pixels.astype(np.uint8), bucket_size=20)

    text_crop = rgb[block.bbox.y : block.bbox.y2, block.bbox.x : block.bbox.x2]
    if text_crop.size == 0:
        return local_fill, local_coverage
    box_fill, box_coverage = dominant_cluster_stats(text_crop.reshape(-1, 3).astype(np.uint8), bucket_size=16)
    box_page_distance = color_distance(box_fill, page_background)
    local_page_distance = color_distance(local_fill, page_background)
    if box_coverage >= 0.18 and box_page_distance >= max(48.0, local_page_distance + 28.0):
        return box_fill.astype(np.uint8), box_coverage
    return local_fill, local_coverage


def local_surface_component_touching_seed(
    mask: np.ndarray,
    seed_box: BBox,
    origin_x: int,
    origin_y: int,
) -> list[tuple[int, int]] | None:
    local_seed = BBox(seed_box.x - origin_x, seed_box.y - origin_y, seed_box.width, seed_box.height)
    x1 = max(0, local_seed.x)
    y1 = max(0, local_seed.y)
    x2 = min(mask.shape[1], local_seed.x2)
    y2 = min(mask.shape[0], local_seed.y2)
    if x2 <= x1 or y2 <= y1:
        return None

    best: list[tuple[int, int]] | None = None
    best_overlap = 0
    for component in connected_components(mask):
        overlap = sum(1 for row, col in component if y1 <= row < y2 and x1 <= col < x2)
        if overlap > best_overlap:
            best = component
            best_overlap = overlap
    return best if best_overlap > 0 else None


def extract_local_surface_from_text_seed(
    rgb: np.ndarray,
    text_mask: np.ndarray,
    block: OCRBlock,
    ocr_blocks: list[OCRBlock],
    page_background: tuple[int, int, int],
    surface_id: str,
    profile: ControlProfile | None = None,
    limit_window: BBox | None = None,
) -> LocalSurfaceCandidate | None:
    height, width, _ = rgb.shape
    profile = profile or build_control_profile(width, height)
    window = local_surface_window_for_text(block.bbox, width, height, profile=profile, limit_window=limit_window)
    if window is None or window.area <= 0:
        return None

    fill_seed, seed_coverage = estimate_local_surface_fill_near_text(rgb, text_mask, block, page_background, limit_window=window)
    page_distance = color_distance(fill_seed, page_background)
    crop = rgb[window.y : window.y2, window.x : window.x2]
    if crop.size == 0:
        return None
    local_text = text_mask[window.y : window.y2, window.x : window.x2]
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)

    distances = np.linalg.norm(crop.astype(np.float32) - fill_seed.reshape(1, 1, 3).astype(np.float32), axis=2)
    if page_distance >= 80.0:
        close_threshold = 58.0
    elif page_distance >= 32.0:
        close_threshold = max(20.0, page_distance * 0.70)
    else:
        close_threshold = max(10.0, page_distance * 0.55)
    close = distances <= close_threshold
    close |= local_text
    close = binary_close(close, iterations=2)

    seed_support = ocr_support_box(block.bbox, window)
    component = local_surface_component_touching_seed(close, seed_support, window.x, window.y)
    if component is None:
        component = local_surface_component_touching_seed(close, block.bbox, window.x, window.y)
    if component is None:
        return None

    local_box = component_bbox(component, 1, window.width, window.height)
    global_box = clamp_box(BBox(window.x + local_box.x, window.y + local_box.y, local_box.width, local_box.height), width, height)
    if global_box is None or global_box.area <= 0:
        return None

    candidate = Candidate(surface_id, "shape", global_box, 0.0, {}, "local_surface_candidate")
    contained = contained_text_blocks(candidate, ocr_blocks)
    fill, fill_coverage, close_coverage = control_surface_fill(
        rgb,
        candidate,
        text_mask,
        support_box=ocr_support_box(block.bbox, global_box),
        text_box=block.bbox,
    )
    texture, entropy, edge_density = control_surface_local_complexity(rgb, global_box, text_mask, fill=fill)
    text_contrast = control_text_contrast(rgb, contained or [block], fill)
    touches_edges = local_surface_touches_window_edges(global_box, window)
    score = (
        0.34
        + min(0.24, close_coverage * 0.22)
        + min(0.18, fill_coverage * 0.20)
        + min(0.14, text_contrast / 480.0)
        - min(0.14, texture / 700.0)
    )
    scores = {
        "score": round(float(max(0.0, min(0.95, score))), 4),
        "localSurface": 1.0,
        "seedFillCoverage": round(float(seed_coverage), 4),
        "seedPageDistance": round(float(page_distance), 4),
        "seedCloseThreshold": round(float(close_threshold), 4),
        "fillCoverage": round(float(fill_coverage), 4),
        "closeFillCoverage": round(float(close_coverage), 4),
        "textContrast": round(float(text_contrast), 4),
        "texture": round(float(texture / 255.0), 4),
        "entropy": round(float(entropy), 4),
        "edge": round(float(edge_density), 4),
        "containedTextBlockCount": float(len(contained)),
        "touchesWindowEdgeCount": float(touches_edges),
        "windowAreaRatio": round(float(global_box.area / max(1, window.area)), 4),
        "canvasAreaRatio": round(float(global_box.area / max(1, width * height)), 4),
        "sourceTextBlockKey": stable_text_block_key(block.id),
        "fillR": float(fill[0]),
        "fillG": float(fill[1]),
        "fillB": float(fill[2]),
    }
    return LocalSurfaceCandidate(
        id=surface_id,
        bbox=global_box,
        fill=(int(fill[0]), int(fill[1]), int(fill[2])),
        seed_text_id=block.id,
        contained_text_ids=[item.id for item in contained],
        score=float(scores["score"]),
        scores=scores,
        extraction_reason="ocr_text_seed_connected_surface",
    )


def local_surface_touches_window_edges(surface: BBox, window: BBox) -> int:
    margin = 2
    return int(surface.x <= window.x + margin) + int(surface.y <= window.y + margin) + int(surface.x2 >= window.x2 - margin) + int(
        surface.y2 >= window.y2 - margin
    )


def classify_local_surface_role(
    surface: LocalSurfaceCandidate,
    seed_block: OCRBlock,
    ocr_blocks: list[OCRBlock],
    rgb: np.ndarray,
    text_mask: np.ndarray,
    profile: ControlProfile,
    page_background: tuple[int, int, int],
    source_refs: list[str],
) -> tuple[SurfaceRoleDecision, dict[str, float]]:
    height, width, _ = rgb.shape
    page_area = max(1, width * height)
    candidate = Candidate(surface.id, "shape", surface.bbox, surface.score, surface.scores, "local_surface_candidate")
    contained = contained_text_blocks(candidate, ocr_blocks)
    related = related_control_text_blocks(seed_block, contained)
    related_ids = {item.id for item in related}
    unrelated = [item for item in contained if item.id not in related_ids]
    area_ratio = surface.bbox.area / page_area
    aspect = surface.bbox.width / max(1, surface.bbox.height)
    scores = dict(surface.scores)
    scores.update(
        {
            "surfaceAspect": round(float(aspect), 4),
            "surfaceCanvasAreaRatio": round(float(area_ratio), 4),
            "relatedTextBlockCount": float(len(related)),
            "unrelatedTextBlockCount": float(len(unrelated)),
        }
    )

    def decision(role: str, state: str, reason: str) -> SurfaceRoleDecision:
        return SurfaceRoleDecision(surface.id, role, state, reason, source_refs)

    chart_tick_like = chart_tick_like_block(seed_block, ocr_blocks)
    if chart_tick_like and not numeric_seed_inside_labeled_surface(seed_block, contained):
        scores["surfaceRoleChartInternal"] = 1.0
        return decision("chart_or_media_internal", "metadata_only", "chart_tick_like_surface_not_control"), scores
    if area_ratio > 0.20:
        scores["surfaceRoleContainer"] = 1.0
        return decision("container_surface", "metadata_only", "surface_area_too_large_for_control"), scores
    if surface.bbox.area > profile.max_area:
        scores["surfaceRoleContainer"] = 1.0
        return decision("container_surface", "metadata_only", "container_surface_area_exceeds_control_profile"), scores
    if unrelated:
        scores["surfaceRoleContainer"] = 1.0
        return decision("container_surface", "metadata_only", "single_control_contains_unrelated_text"), scores

    scored_candidate = Candidate(surface.id, "shape", surface.bbox, surface.score, scores, "ocr_anchored_control_surface")
    accepted, control_scores, reason = score_ocr_anchored_control_surface(
        rgb=rgb,
        candidate=scored_candidate,
        block=seed_block,
        ocr_blocks=ocr_blocks,
        text_mask=text_mask,
        page_area=page_area,
        profile=profile,
        page_background=page_background,
    )
    scores.update(control_scores)
    if accepted:
        scores.update(
            {
                "confirmedControlSurface": 1.0,
                "surfaceRoleControl": 1.0,
                "controlSurface": 1.0,
            }
        )
        return decision("control_surface", "accepted", "connected_surface_control_gate_passed"), scores
    if scores.get("touchesWindowEdgeCount", 0.0) >= 2.0 and scores.get("windowAreaRatio", 0.0) >= 0.72:
        scores["surfaceRoleContainer"] = 1.0
        return decision("container_surface", "metadata_only", "parent_surface_slice_not_control"), scores
    if reason in {"high_texture", "one_sided_graphic_edge", "weak_boundary_closure"} and role_requires_strong_boundary(ocr_text_role(seed_block.text)):
        scores["surfaceRoleChartInternal"] = 1.0
        return decision("chart_or_media_internal", "metadata_only", "chart_or_media_internal"), scores
    scores["surfaceRoleAuditOnly"] = 1.0
    return decision("audit_only", "rejected", reason or "failed_connected_surface_control_gate"), scores


def local_surface_to_control_candidate(
    surface: LocalSurfaceCandidate,
    scores: dict[str, float],
    reason: str,
) -> Candidate:
    return Candidate(
        id=surface.id,
        kind="shape",
        bbox=surface.bbox,
        score=max(0.72, float(scores.get("score", surface.score))),
        scores=scores,
        reason=reason,
    )


def local_surface_to_container_candidate(
    surface: LocalSurfaceCandidate,
    scores: dict[str, float],
) -> Candidate:
    output_scores = dict(scores)
    output_scores["surfaceRoleContainer"] = 1.0
    output_scores["confirmedControlSurface"] = 0.0
    return Candidate(
        id=surface.id,
        kind="shape",
        bbox=surface.bbox,
        score=max(0.66, float(scores.get("score", surface.score))),
        scores=output_scores,
        reason="local_container_surface",
    )


def numeric_seed_inside_labeled_surface(seed_block: OCRBlock, contained: list[OCRBlock]) -> bool:
    if ocr_text_role(seed_block.text) not in {"numeric_metric", "currency_or_percent", "date_or_time"}:
        return False
    non_numeric = [
        block
        for block in contained
        if block.id != seed_block.id and ocr_text_role(block.text) not in {"numeric_metric", "currency_or_percent", "date_or_time"}
    ]
    return bool(non_numeric)


def is_visible_container_surface(
    surface: LocalSurfaceCandidate,
    scores: dict[str, float],
    width: int,
    height: int,
    profile: ControlProfile | None = None,
    ocr_blocks: list[OCRBlock] | None = None,
) -> bool:
    profile = profile or build_control_profile(width, height)
    page_area = max(1, width * height)
    area_ratio = surface.bbox.area / page_area
    if surface.bbox.area < 1800:
        return False
    if area_ratio > profile.max_container_area_ratio:
        return False
    if surface.bbox.width < 48 or surface.bbox.height < 32:
        return False
    if profile.kind == "web_like" and web_table_or_list_row_like_surface(surface.bbox, ocr_blocks or [], width, height):
        return False
    if scores.get("containedTextBlockCount", 0.0) < 2.0:
        return False
    if scores.get("touchesWindowEdgeCount", 0.0) > 1.0:
        return False
    if scores.get("fillCoverage", 0.0) < 0.58 or scores.get("closeFillCoverage", 0.0) < 0.68:
        return False
    if scores.get("texture", 1.0) > 0.34 or scores.get("edge", 1.0) > 0.28 or scores.get("entropy", 1.0) > 0.56:
        return False
    if scores.get("surfaceRoleChartInternal", 0.0) >= 1.0 or scores.get("surfaceRoleControl", 0.0) >= 1.0:
        return False
    return True


def web_table_or_list_row_like_surface(box: BBox, ocr_blocks: list[OCRBlock], width: int, height: int) -> bool:
    if box.area <= 0 or not ocr_blocks:
        return False
    page_area = max(1, width * height)
    aspect = box.width / max(1, box.height)
    if aspect < 6.0 or box.width < width * 0.42 or box.area > page_area * 0.09:
        return False
    contained = [
        block
        for block in ocr_blocks
        if block.bbox.area > 0 and intersection_area(block.bbox, box) / block.bbox.area >= 0.76
    ]
    if len(contained) < 3:
        return False
    peer_rows = table_like_peer_rows(box, ocr_blocks, width)
    return len(peer_rows) >= 2


def table_like_peer_rows(box: BBox, ocr_blocks: list[OCRBlock], width: int) -> list[BBox]:
    centers = sorted({round(center_y(block.bbox)) for block in ocr_blocks if block.bbox.area > 0})
    row_height = max(18, min(64, int(round(box.height * 0.72))))
    rows: list[BBox] = []
    for center in centers:
        row = BBox(box.x, int(round(center - row_height / 2)), box.width, row_height)
        if row.y < 0:
            continue
        contained = [
            block
            for block in ocr_blocks
            if block.bbox.area > 0 and intersection_area(block.bbox, row) / block.bbox.area >= 0.58
        ]
        if len(contained) < 3:
            continue
        span_x1 = min(block.bbox.x for block in contained)
        span_x2 = max(block.bbox.x2 for block in contained)
        if span_x2 - span_x1 < min(box.width * 0.36, width * 0.24):
            continue
        if abs(center_y(row) - center_y(box)) <= max(8, box.height * 0.55):
            continue
        if abs(row.width - box.width) / max(1, box.width) <= 0.12 and abs(row.x - box.x) <= max(18, box.width * 0.05):
            rows.append(row)
    return rows


def surface_role_decision_payload(
    role: SurfaceRoleDecision,
    surface: LocalSurfaceCandidate,
    seed_block: OCRBlock,
    scores: dict[str, float],
    kind: str,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": surface.id,
        "bbox": surface.bbox.to_dict(),
        "decision": role.decision,
        "role": role.role,
        "reason": role.reason,
        "sourceTextBlockId": seed_block.id,
        "sourceTextRole": ocr_text_role(seed_block.text),
        "containedTextBlockIds": surface.contained_text_ids,
        "sourceRefs": role.source_refs,
        "scores": {key: round(float(value), 4) for key, value in scores.items() if isinstance(value, int | float)},
    }


def is_editable_control_surface(
    candidate: Candidate,
    blocks: list[OCRBlock],
    fill_coverage: float,
    close_coverage: float,
    text_contrast: float,
    profile: ControlProfile,
) -> bool:
    if not blocks or len(blocks) > 2:
        return False
    if candidate.bbox.area < profile.min_area or candidate.bbox.area > profile.max_area:
        return False
    if candidate.bbox.width < 24 or candidate.bbox.height < profile.min_height:
        return False
    aspect = candidate.bbox.width / max(1, candidate.bbox.height)
    if aspect < 1.15 or aspect > profile.max_aspect:
        return False
    if candidate.scores.get("texture", 1.0) > 0.86:
        return False
    if candidate.scores.get("entropy", 1.0) > 0.62:
        return False
    if fill_coverage < 0.34 and candidate.scores.get("dominant", 0.0) < 0.42:
        return False
    if close_coverage < 0.56:
        return False

    union_x1 = min(block.bbox.x for block in blocks)
    union_y1 = min(block.bbox.y for block in blocks)
    union_x2 = max(block.bbox.x2 for block in blocks)
    union_y2 = max(block.bbox.y2 for block in blocks)
    text_box = BBox(union_x1, union_y1, union_x2 - union_x1, union_y2 - union_y1)
    if text_box.area <= 0:
        return False
    if text_box.area / max(1, candidate.bbox.area) > 0.55:
        return False

    left_pad = text_box.x - candidate.bbox.x
    right_pad = candidate.bbox.x2 - text_box.x2
    top_pad = text_box.y - candidate.bbox.y
    bottom_pad = candidate.bbox.y2 - text_box.y2
    if min(left_pad, right_pad, top_pad, bottom_pad) < -1:
        return False
    if left_pad + right_pad < max(6, int(candidate.bbox.width * 0.10)):
        return False
    if top_pad + bottom_pad < max(4, int(candidate.bbox.height * 0.10)):
        return False
    return text_contrast >= 42.0


def promote_control_surfaces(
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray,
    rgb: np.ndarray,
    profile: ControlProfile | None = None,
    page_background: tuple[int, int, int] | None = None,
) -> tuple[list[Candidate], list[Candidate], list[dict[str, Any]]]:
    height, width, _ = rgb.shape
    profile = profile or build_control_profile(width, height)
    page_background = page_background or estimate_background_color(rgb)
    promoted_shapes: list[Candidate] = []
    residual_rasters: list[Candidate] = []
    consumed_raster_ids: set[str] = set()
    decisions: list[dict[str, Any]] = []

    for index, raster in enumerate(raster_candidates, start=1):
        blocks = contained_text_blocks(raster, ocr_blocks)
        fill, fill_coverage, close_coverage = control_surface_fill(rgb, raster, text_mask)
        text_contrast = control_text_contrast(rgb, blocks, fill)
        if not is_editable_control_surface(raster, blocks, fill_coverage, close_coverage, text_contrast, profile):
            continue
        ring = control_surface_ring_evidence(rgb, raster.bbox, fill, page_background)
        if ring is None:
            continue
        ok, reason = passes_boundary_gate(
            ring=ring,
            ring_threshold=8.0 if relative_luminance(fill) <= 96.0 else 18.0,
            strong_boundary_required=False,
        )
        if not ok:
            continue

        scores = dict(raster.scores)
        scores.update(
            {
                "controlSurface": 1.0,
                "confirmedControlSurface": 1.0,
                "surfaceRoleControl": 1.0,
                "fillCoverage": round(float(fill_coverage), 4),
                "closeFillCoverage": round(float(close_coverage), 4),
                "textContrast": round(float(text_contrast), 4),
                "boundaryStrongSideCount": float(ring.strong_side_count),
                "fillToLocalDelta": round(float(ring.fill_to_local_delta), 4),
                "fillToPageDelta": round(float(ring.fill_to_page_delta), 4),
                "fillR": float(fill[0]),
                "fillG": float(fill[1]),
                "fillB": float(fill[2]),
            }
        )
        promoted_shapes.append(
            Candidate(
                id=f"control_{index:04d}_{raster.id}",
                kind="shape",
                bbox=raster.bbox,
                score=max(raster.score, 0.72),
                scores=scores,
                reason="editable_control_surface_from_raster",
            )
        )
        consumed_raster_ids.add(raster.id)
        residuals = extract_control_foreground_residuals(
            rgb=rgb,
            candidate=raster,
            fill=fill,
            text_mask=text_mask,
            source_index=index,
        )
        residual_rasters.extend(residuals)
        decisions.append(
            {
                "kind": "raster_to_shape",
                "bbox": raster.bbox.to_dict(),
                "reason": "editable_control_surface_contains_ocr_text",
                "sourceRasterId": raster.id,
                "coveredTextBlockIds": [block.id for block in blocks],
                "fill": color_hex(fill),
                "fillCoverage": round(float(fill_coverage), 4),
                "closeFillCoverage": round(float(close_coverage), 4),
                "textContrast": round(float(text_contrast), 4),
                "boundaryReason": reason,
                "residualRasterCount": len(residuals),
            }
        )

    remaining_rasters = [item for item in raster_candidates if item.id not in consumed_raster_ids]
    merged_rasters = nms_candidates(remaining_rasters + residual_rasters, overlap_threshold=0.52)
    merged_shapes: list[Candidate] = []
    for candidate in sorted(
        shape_candidates + promoted_shapes,
        key=lambda item: (-shape_merge_priority(item), item.bbox.y, item.bbox.x, -item.bbox.area, item.id),
    ):
        if any(is_duplicate_control_shape(candidate, kept) for kept in merged_shapes):
            decisions.append(
                {
                    "kind": "control_duplicate_shape_suppressed",
                    "id": candidate.id,
                    "bbox": candidate.bbox.to_dict(),
                    "reason": "cross_source_control_duplicate",
                    "keptShapeId": next(
                        kept.id for kept in merged_shapes if is_duplicate_control_shape(candidate, kept)
                    ),
                }
            )
            continue
        merged_shapes.append(candidate)
    return merged_rasters, merged_shapes, decisions


def shape_merge_priority(candidate: Candidate) -> int:
    if candidate.scores.get("confirmedControlSurface", 0.0) >= 1.0:
        return 3
    if candidate.reason == "local_container_surface":
        return 2
    if candidate.reason in {"background_surface_band", "inferred_background_plate_from_surface_bands"}:
        return 0
    return 1


def detect_ocr_anchored_control_surfaces(
    rgb: np.ndarray,
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray,
    profile: ControlProfile | None = None,
    page_background: tuple[int, int, int] | None = None,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    height, width, _ = rgb.shape
    profile = profile or build_control_profile(width, height)
    page_background = page_background or estimate_background_color(rgb)
    candidates: list[Candidate] = []
    decisions: list[dict[str, Any]] = []

    for index, block in enumerate(ocr_blocks, start=1):
        if block.bbox.area <= 0 or block.bbox.width < 4 or block.bbox.height < 6:
            continue
        surface = extract_local_surface_from_text_seed(
            rgb=rgb,
            text_mask=text_mask,
            block=block,
            ocr_blocks=ocr_blocks,
            page_background=page_background,
            surface_id=f"ocr_control_{index:04d}",
            profile=profile,
        )
        if surface is None:
            decisions.append(
                {
                    "kind": "ocr_control_surface",
                    "id": f"ocr_control_{index:04d}",
                    "bbox": block.bbox.to_dict(),
                    "decision": "rejected",
                    "role": "audit_only",
                    "reason": "missing_local_surface",
                    "sourceTextBlockId": block.id,
                    "sourceTextRole": ocr_text_role(block.text),
                    "sourceRefs": [f"ocr:{block.id}", "pixel:local_surface_gate"],
                }
            )
            continue

        role, scores = classify_local_surface_role(
            surface=surface,
            seed_block=block,
            ocr_blocks=ocr_blocks,
            rgb=rgb,
            text_mask=text_mask,
            profile=profile,
            page_background=page_background,
            source_refs=[f"ocr:{block.id}", "pixel:local_surface_gate"],
        )
        decisions.append(surface_role_decision_payload(role, surface, block, scores, "ocr_control_surface"))
        if role.role == "container_surface" and is_visible_container_surface(surface, scores, width, height, profile, ocr_blocks):
            candidates.append(local_surface_to_container_candidate(surface, scores))
            continue
        if role.role != "control_surface" or role.decision != "accepted":
            continue
        candidates.append(local_surface_to_control_candidate(surface, scores, "ocr_anchored_control_surface"))

    return merge_local_surface_candidates(candidates), decisions[:160]


def control_surface_search_boxes(
    text_box: BBox,
    width: int,
    height: int,
    profile: ControlProfile | None = None,
) -> list[BBox]:
    profile = profile or build_control_profile(width, height)
    pad_x_values = sorted(
        {
            max(6, round(text_box.height * 0.65)),
            max(8, round(text_box.height * 1.00)),
            max(10, round(text_box.width * 0.18)),
            max(12, round(text_box.width * 0.30)),
            max(14, round(text_box.width * 0.55)),
            max(14, round(text_box.width * 0.65)),
            max(16, round(text_box.width * 0.80)),
            max(18, round(text_box.width * 1.10)),
            max(20, round(text_box.width * 1.55)),
            max(22, round(text_box.width * 2.00)),
        }
    )
    if text_box.width <= text_box.height * 2.4:
        pad_x_values.extend(
            sorted(
                {
                    max(26, round(text_box.width * 2.80)),
                    max(32, round(text_box.width * 3.60)),
                }
            )
        )
    if profile.kind == "web_like":
        pad_x_values.extend(
            sorted(
                {
                    max(32, round(text_box.width * 2.50)),
                    max(44, round(text_box.width * 3.50)),
                    max(56, round(text_box.width * 4.80)),
                }
            )
        )
    pad_y_values = sorted(
        {
            max(4, round(text_box.height * 0.35)),
            max(4, round(text_box.height * 0.45)),
            max(5, round(text_box.height * 0.55)),
            max(6, round(text_box.height * 0.85)),
        }
    )
    if text_box.width <= text_box.height * 2.4:
        pad_y_values.extend(
            sorted(
                {
                    max(8, round(text_box.height * 1.15)),
                    max(12, round(text_box.height * 1.65)),
                }
            )
        )
    boxes: list[BBox] = []
    seen: set[tuple[int, int, int, int]] = set()
    for pad_x in pad_x_values:
        for pad_y in pad_y_values:
            box = clamp_box(
                BBox(
                    text_box.x - pad_x,
                    text_box.y - pad_y,
                    text_box.width + pad_x * 2,
                    text_box.height + pad_y * 2,
                ),
                width,
                height,
            )
            if box is None:
                continue
            if box.area > max(profile.max_area * 2, int(width * height * profile.max_local_window_area_ratio)):
                continue
            key = (box.x, box.y, box.width, box.height)
            if key in seen:
                continue
            seen.add(key)
            boxes.append(box)
    return boxes


def score_ocr_anchored_control_surface(
    rgb: np.ndarray,
    candidate: Candidate,
    block: OCRBlock,
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray,
    page_area: int,
    profile: ControlProfile | None = None,
    page_background: tuple[int, int, int] | None = None,
) -> tuple[bool, dict[str, float], str]:
    height, width, _ = rgb.shape
    profile = profile or build_control_profile(width, height)
    page_background = page_background or estimate_background_color(rgb)
    _ = page_area
    box = candidate.bbox
    if block.bbox.area <= 0 or box.area <= 0:
        return False, {}, "empty"
    text_containment = intersection_area(box, block.bbox) / block.bbox.area
    if text_containment < 0.90:
        return False, {}, "text_not_contained"
    area_ratio = box.area / block.bbox.area
    text_role = ocr_text_role(block.text)
    max_area_ratio = 30.0 if block.bbox.width <= block.bbox.height * 2.4 else 12.0
    if profile.kind == "web_like":
        candidate_aspect = box.width / max(1, box.height)
        if candidate_aspect >= 4.5:
            max_area_ratio = max(max_area_ratio, 48.0)
    if area_ratio < 1.18 or area_ratio > max_area_ratio:
        return False, {}, "bad_area_ratio"
    if box.area > profile.max_area or box.width < 24 or box.height < profile.min_height:
        return False, {}, "bad_size"
    aspect = box.width / max(1, box.height)
    if aspect < 1.10 or aspect > profile.max_aspect:
        return False, {}, "bad_aspect"
    if box.height > max(96, block.bbox.height * 5):
        return False, {}, "too_tall"
    contained = contained_text_blocks(candidate, ocr_blocks)
    related = related_control_text_blocks(block, contained)
    related_ids = {item.id for item in related}
    unrelated = [item for item in contained if item.id not in related_ids]
    if unrelated:
        return False, {}, "single_control_contains_unrelated_text"
    chart_tick_like = chart_tick_like_block(block, ocr_blocks)

    left_pad = block.bbox.x - box.x
    right_pad = box.x2 - block.bbox.x2
    top_pad = block.bbox.y - box.y
    bottom_pad = box.y2 - block.bbox.y2
    if min(left_pad, right_pad, top_pad, bottom_pad) < -1:
        return False, {}, "not_enough_padding"
    if left_pad + right_pad < max(8, int(box.width * 0.10)):
        return False, {}, "not_enough_padding"
    if top_pad + bottom_pad < max(5, int(box.height * 0.10)):
        return False, {}, "not_enough_padding"

    support_box = ocr_support_box(block.bbox, box)
    fill, fill_coverage, close_coverage = control_surface_fill(
        rgb,
        candidate,
        text_mask,
        support_box=support_box,
        text_box=block.bbox,
    )
    texture, entropy, edge_density = control_surface_local_complexity(rgb, box, text_mask, fill=fill)
    if texture > 42.0 or entropy > 0.70 or edge_density > 0.20:
        return False, {}, "high_texture"
    if fill_coverage < 0.30 and close_coverage < 0.58:
        return False, {}, "unstable_fill"

    ring = control_surface_ring_evidence(rgb, box, fill, page_background)
    if ring is None:
        return False, {}, "missing_outer_ring"
    fill_luminance = relative_luminance(fill)
    dark_surface = (
        fill_luminance <= 96.0
        and close_coverage >= 0.62
        and fill_coverage >= 0.26
        and texture <= 38.0
        and entropy <= 0.68
        and edge_density <= 0.22
    )
    ring_threshold = 8.0 if dark_surface else 18.0
    if chart_tick_like:
        return False, {}, "chart_tick_like_control_rejected"
    boundary_ok, boundary_reason = passes_boundary_gate(
        ring=ring,
        ring_threshold=ring_threshold,
        strong_boundary_required=role_requires_strong_boundary(text_role),
        allow_low_contrast_stroke=profile.kind == "web_like" and not role_requires_strong_boundary(text_role),
    )
    if not boundary_ok:
        return False, {}, boundary_reason

    text_contrast = control_text_contrast(rgb, [block], fill)
    if text_contrast < 34.0:
        return False, {}, "low_text_contrast"

    score = (
        0.42
        + min(0.22, close_coverage * 0.18)
        + min(0.16, ring.support_delta / 260.0)
        + min(0.14, text_contrast / 520.0)
        + min(0.08, aspect / 140.0)
        - min(0.12, texture / 800.0)
    )
    scores = {
        "score": round(float(max(0.72, min(0.94, score))), 4),
        "controlSurface": 1.0,
        "ocrAnchoredControlSurface": 1.0,
        "textContainment": round(float(text_containment), 4),
        "areaRatio": round(float(area_ratio), 4),
        "aspect": round(float(aspect), 4),
        "fillCoverage": round(float(fill_coverage), 4),
        "closeFillCoverage": round(float(close_coverage), 4),
        "outerRingDelta": round(float(ring.min_delta), 4),
        "outerRingSupportDelta": round(float(ring.support_delta), 4),
        "outerRingMedianDelta": round(float(ring.median_delta), 4),
        "outerRingMaxDelta": round(float(ring.max_delta), 4),
        "outerRingThreshold": round(float(ring_threshold), 4),
        "boundaryStrongSideCount": float(ring.strong_side_count),
        "fillToLocalDelta": round(float(ring.fill_to_local_delta), 4),
        "fillToPageDelta": round(float(ring.fill_to_page_delta), 4),
        "textContrast": round(float(text_contrast), 4),
        "fillLuminance": round(float(fill_luminance), 4),
        "darkControlSurface": 1.0 if dark_surface else 0.0,
        "textRoleRisk": 1.0 if role_requires_strong_boundary(text_role) else 0.0,
        "containedTextBlockCount": float(len(contained)),
        "sourceTextBlockKey": stable_text_block_key(block.id),
        "texture": round(float(texture / 255.0), 4),
        "entropy": round(float(entropy), 4),
        "edge": round(float(edge_density), 4),
        "fillR": float(fill[0]),
        "fillG": float(fill[1]),
        "fillB": float(fill[2]),
    }
    if ring.stroke_color is not None and ring.stroke_delta >= 10.0:
        scores.update(
            {
                "strokeR": float(ring.stroke_color[0]),
                "strokeG": float(ring.stroke_color[1]),
                "strokeB": float(ring.stroke_color[2]),
                "strokeWidth": 1.0,
                "strokeDelta": round(float(ring.stroke_delta), 4),
            }
        )
    return True, scores, ""


def control_surface_local_complexity(
    rgb: np.ndarray,
    box: BBox,
    text_mask: np.ndarray,
    fill: np.ndarray | None = None,
) -> tuple[float, float, float]:
    crop = rgb[box.y : box.y2, box.x : box.x2]
    if crop.size == 0:
        return 999.0, 1.0, 1.0
    local_text = text_mask[box.y : box.y2, box.x : box.x2]
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)
    usable = ~binary_dilate(local_text, iterations=1)
    if fill is not None:
        distances = np.linalg.norm(crop.astype(np.float32) - fill.reshape(1, 1, 3).astype(np.float32), axis=2)
        close_fill = distances <= 64.0
        if int((usable & close_fill).sum()) >= max(12, crop.shape[0] * crop.shape[1] // 10):
            usable &= close_fill
    pixels = crop[usable]
    if pixels.shape[0] < max(12, crop.shape[0] * crop.shape[1] // 8):
        pixels = crop.reshape(-1, 3)
    texture = float(np.mean(np.std(pixels.astype(np.float32), axis=0))) if pixels.size else 999.0
    quantized = np.clip(pixels.astype(np.int16) // 24, 0, 10)
    codes = quantized[:, 0] * 121 + quantized[:, 1] * 11 + quantized[:, 2]
    _, counts = np.unique(codes, return_counts=True)
    prob = counts.astype(np.float32) / max(1, int(counts.sum()))
    entropy = float(-(prob * np.log2(prob)).sum() / max(1.0, math.log2(max(2, len(counts)))))

    gray = crop.mean(axis=2).astype(np.float32)
    gx = np.abs(np.diff(gray, axis=1)).mean() if gray.shape[1] > 1 else 0.0
    gy = np.abs(np.diff(gray, axis=0)).mean() if gray.shape[0] > 1 else 0.0
    edge_density = float((gx + gy) / 255.0)
    return texture, entropy, edge_density


def control_surface_outer_ring_delta(rgb: np.ndarray, box: BBox, fill: np.ndarray) -> tuple[float | None, float | None]:
    evidence = control_surface_ring_evidence(rgb, box, fill, estimate_background_color(rgb))
    if evidence is None:
        return None, None
    return evidence.min_delta, evidence.support_delta


def control_surface_ring_evidence(
    rgb: np.ndarray,
    box: BBox,
    fill: np.ndarray,
    page_background: tuple[int, int, int] | np.ndarray,
) -> RingEvidence | None:
    height, width, _ = rgb.shape
    pad = max(2, min(5, box.height // 8))
    if box.x - pad < 0 or box.y - pad < 0 or box.x2 + pad > width or box.y2 + pad > height:
        return None
    strips = {
        "top": rgb[box.y - pad : box.y, box.x : box.x2],
        "bottom": rgb[box.y2 : box.y2 + pad, box.x : box.x2],
        "left": rgb[box.y : box.y2, box.x - pad : box.x],
        "right": rgb[box.y : box.y2, box.x2 : box.x2 + pad],
    }
    colors: list[np.ndarray] = []
    deltas: list[float] = []
    for strip in strips.values():
        if strip.size == 0:
            return None
        color = dominant_cluster_color(strip.reshape(-1, 3).astype(np.uint8), bucket_size=24)
        colors.append(color)
        deltas.append(color_distance(color, fill))
    sorted_deltas = sorted(deltas)
    ring_pixels = np.concatenate([strip.reshape(-1, 3) for strip in strips.values()], axis=0).astype(np.uint8)
    local_pixels = np.concatenate([color.reshape(1, 3) for color in colors], axis=0).astype(np.uint8)
    local_color = dominant_cluster_color(local_pixels, bucket_size=24)
    fill_to_page = color_distance(fill, page_background)
    stroke_color: tuple[int, int, int] | None = None
    stroke_delta = 0.0
    if fill_to_page <= 36.0 and ring_pixels.size:
        stroke_distances = np.linalg.norm(ring_pixels.astype(np.float32) - fill.reshape(1, 3).astype(np.float32), axis=1)
        stroke_threshold = max(18.0, fill_to_page + 8.0)
        stroke_pixels = ring_pixels[(stroke_distances >= stroke_threshold) & (stroke_distances <= 128.0)]
        if stroke_pixels.shape[0] >= max(8, int(ring_pixels.shape[0] * 0.012)):
            stroke_sample = dominant_cluster_color(stroke_pixels.astype(np.uint8), bucket_size=16)
            stroke_color = tuple(int(v) for v in stroke_sample.tolist())
            stroke_delta = color_distance(stroke_sample, fill)
    threshold = max(10.0, min(18.0, float(np.median(sorted_deltas)) * 0.80))
    strong_side_count = sum(1 for delta in deltas if delta >= threshold)
    return RingEvidence(
        min_delta=float(sorted_deltas[0]),
        support_delta=float(sorted_deltas[1]),
        median_delta=float(np.median(sorted_deltas)),
        max_delta=float(sorted_deltas[-1]),
        strong_side_count=strong_side_count,
        fill_to_local_delta=color_distance(fill, local_color),
        fill_to_page_delta=fill_to_page,
        side_deltas=(float(deltas[0]), float(deltas[1]), float(deltas[2]), float(deltas[3])),
        stroke_color=stroke_color,
        stroke_delta=stroke_delta,
    )


def passes_boundary_gate(
    ring: RingEvidence,
    ring_threshold: float,
    strong_boundary_required: bool,
    allow_low_contrast_stroke: bool = False,
) -> tuple[bool, str]:
    required_sides = 3 if strong_boundary_required else 2
    if (
        allow_low_contrast_stroke
        and ring.stroke_color is not None
        and ring.strong_side_count >= required_sides
        and ring.stroke_delta >= 18.0
    ):
        return True, ""
    if ring.support_delta < ring_threshold or ring.median_delta < ring_threshold:
        return False, "weak_boundary_closure"
    if ring.strong_side_count < required_sides:
        return False, "one_sided_graphic_edge"
    if ring.fill_to_local_delta <= 14.0 and ring.fill_to_page_delta <= 18.0:
        return False, "invisible_background_like_control"
    return True, ""


def is_duplicate_control_shape(candidate: Candidate, kept: Candidate) -> bool:
    if not is_control_like_shape(candidate) or not is_control_like_shape(kept):
        return iou(candidate.bbox, kept.bbox) >= 0.82
    overlap = iou(candidate.bbox, kept.bbox)
    containment = max(ioa(candidate.bbox, kept.bbox), ioa(kept.bbox, candidate.bbox))
    if overlap < 0.65 and containment < 0.85:
        return False
    if distinct_adjacent_controls(candidate.bbox, kept.bbox):
        return False
    if control_shape_fill_distance(candidate, kept) <= 34.0:
        return True
    if same_control_source(candidate, kept):
        return True
    return containment >= 0.92


def is_control_like_shape(candidate: Candidate) -> bool:
    if candidate.scores.get("confirmedControlSurface", 0.0) >= 1.0:
        return True
    return candidate.reason in {"editable_control_surface_from_raster"} and candidate.scores.get("controlSurface", 0.0) >= 1.0


def control_shape_fill_distance(a: Candidate, b: Candidate) -> float:
    if not all(key in a.scores for key in ("fillR", "fillG", "fillB")):
        return 999.0
    if not all(key in b.scores for key in ("fillR", "fillG", "fillB")):
        return 999.0
    return color_distance(
        np.array([a.scores["fillR"], a.scores["fillG"], a.scores["fillB"]], dtype=np.float32),
        np.array([b.scores["fillR"], b.scores["fillG"], b.scores["fillB"]], dtype=np.float32),
    )


def same_control_source(a: Candidate, b: Candidate) -> bool:
    source_a = float(a.scores.get("sourceTextBlockKey", 0.0))
    source_b = float(b.scores.get("sourceTextBlockKey", 0.0))
    if source_a and source_b and source_a == source_b:
        return True
    return a.reason != b.reason


def distinct_adjacent_controls(a: BBox, b: BBox) -> bool:
    horizontal_overlap = intersection_1d(a.y, a.y2, b.y, b.y2) / max(1, min(a.height, b.height))
    vertical_overlap = intersection_1d(a.x, a.x2, b.x, b.x2) / max(1, min(a.width, b.width))
    if horizontal_overlap >= 0.60 and horizontal_gap(a, b) >= max(4, min(a.height, b.height) * 0.18):
        return True
    if vertical_overlap >= 0.60 and vertical_gap(a, b) >= max(4, min(a.width, b.width) * 0.12):
        return True
    return False


def vertical_gap(a: BBox, b: BBox) -> int:
    if a.y2 < b.y:
        return b.y - a.y2
    if b.y2 < a.y:
        return a.y - b.y2
    return 0


def merge_control_surfaces(candidates: list[Candidate]) -> list[Candidate]:
    accepted: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda item: (-item.score, item.bbox.area, item.bbox.y, item.bbox.x)):
        if any(iou(candidate.bbox, kept.bbox) >= 0.66 or ioa(candidate.bbox, kept.bbox) >= 0.92 for kept in accepted):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def merge_local_surface_candidates(candidates: list[Candidate]) -> list[Candidate]:
    controls = [item for item in candidates if item.scores.get("confirmedControlSurface", 0.0) >= 1.0]
    containers = [item for item in candidates if item.reason == "local_container_surface"]
    accepted: list[Candidate] = merge_control_surfaces(controls)
    for candidate in sorted(containers, key=lambda item: (-item.bbox.area, -item.score, item.bbox.y, item.bbox.x)):
        duplicate = False
        for kept in accepted:
            if kept.reason != "local_container_surface":
                continue
            if iou(candidate.bbox, kept.bbox) >= 0.70 or ioa(candidate.bbox, kept.bbox) >= 0.90 or ioa(kept.bbox, candidate.bbox) >= 0.90:
                duplicate = True
                break
        if not duplicate:
            accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def suppress_control_owned_rasters(raster_candidates: list[Candidate], control_shapes: list[Candidate]) -> ControlSuppressionResult:
    if not control_shapes:
        return ControlSuppressionResult(rasters=raster_candidates, suppressed=[], residual_suppressed_count=0)
    kept: list[Candidate] = []
    suppressed: list[dict[str, Any]] = []
    residual_suppressed_count = 0
    for raster in raster_candidates:
        owner = best_control_owner(raster, control_shapes)
        if owner is None:
            kept.append(raster)
            continue
        reason = classify_control_owned_raster(raster, owner)
        if reason == "":
            kept.append(raster)
            continue
        if raster.reason == "control_foreground_residual":
            residual_suppressed_count += 1
        suppressed.append(
            {
                "kind": "control_owned_raster_suppressed",
                "id": raster.id,
                "bbox": raster.bbox.to_dict(),
                "reason": reason,
                "controlSurfaceId": owner.id,
                "controlSurfaceReason": owner.reason,
                "controlSurfaceBBox": owner.bbox.to_dict(),
                "ioaRasterInControl": round(ioa(raster.bbox, owner.bbox), 4),
                "ioaControlInRaster": round(ioa(owner.bbox, raster.bbox), 4),
                "iou": round(iou(raster.bbox, owner.bbox), 4),
            }
        )
    return ControlSuppressionResult(rasters=kept, suppressed=suppressed, residual_suppressed_count=residual_suppressed_count)


def suppress_text_owned_raster_fragments(
    raster_candidates: list[Candidate],
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    kept: list[Candidate] = []
    suppressed: list[dict[str, Any]] = []
    for raster in raster_candidates:
        reason, block = classify_text_owned_raster_fragment(raster, ocr_blocks, text_mask)
        if reason == "":
            kept.append(raster)
            continue
        suppressed.append(
            {
                "kind": "text_owned_raster_suppressed",
                "id": raster.id,
                "bbox": raster.bbox.to_dict(),
                "reason": reason,
                "sourceTextBlockId": block.id if block else "",
                "sourceTextBBox": block.bbox.to_dict() if block else {},
                "textMaskRatio": round(text_mask_ratio(raster.bbox, text_mask), 4),
                "textOverlapScore": round(float(raster.scores.get("textOverlap", 0.0)), 4),
            }
        )
    return kept, suppressed


def best_control_owner(raster: Candidate, control_shapes: list[Candidate]) -> Candidate | None:
    best: tuple[float, Candidate] | None = None
    for shape in control_shapes:
        raster_in_control = ioa(raster.bbox, shape.bbox)
        control_in_raster = ioa(shape.bbox, raster.bbox)
        overlap = iou(raster.bbox, shape.bbox)
        score = max(raster_in_control, control_in_raster, overlap)
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, shape)
    return best[1] if best is not None else None


def classify_control_owned_raster(raster: Candidate, control: Candidate) -> str:
    raster_in_control = ioa(raster.bbox, control.bbox)
    control_in_raster = ioa(control.bbox, raster.bbox)
    overlap = iou(raster.bbox, control.bbox)
    if raster.reason == "control_foreground_residual":
        if raster_in_control >= 0.72 and is_edge_like_control_fragment(raster.bbox, control.bbox):
            return "control_residual_edge_fragment"
        if raster_in_control >= 0.90 and raster.bbox.area < max(96, control.bbox.area * 0.035):
            return "control_residual_tiny_fragment"
        return ""
    if overlap >= 0.55:
        return "control_surface_owned_background"
    if is_control_sized_background_raster(raster.bbox, control.bbox, raster_in_control, control_in_raster):
        return "control_surface_owned_background"
    if raster_in_control >= 0.72 and raster.bbox.area <= control.bbox.area * 0.20 and is_edge_like_control_fragment(raster.bbox, control.bbox):
        return "control_surface_edge_fragment"
    return ""


def is_control_sized_background_raster(
    raster: BBox,
    control: BBox,
    raster_in_control: float,
    control_in_raster: float,
) -> bool:
    if raster.area <= 0 or control.area <= 0:
        return False
    area_ratio = min(raster.area, control.area) / max(raster.area, control.area)
    width_ratio = min(raster.width, control.width) / max(raster.width, control.width)
    height_ratio = min(raster.height, control.height) / max(raster.height, control.height)
    comparable = area_ratio >= 0.38 and width_ratio >= 0.55 and height_ratio >= 0.55
    if control_in_raster >= 0.90 and comparable:
        return True
    if raster_in_control >= 0.90 and comparable and raster.area >= control.area * 0.28:
        return True
    return False


def is_edge_like_control_fragment(box: BBox, control: BBox) -> bool:
    margin = max(3, min(control.width, control.height) // 5)
    return box.x <= control.x + margin or box.y <= control.y + margin or box.x2 >= control.x2 - margin or box.y2 >= control.y2 - margin


def control_shape_candidates(shape_candidates: list[Candidate]) -> list[Candidate]:
    return [
        item
        for item in shape_candidates
        if item.scores.get("confirmedControlSurface", 0.0) >= 1.0
    ]


def suppress_control_owned_shapes(shape_candidates: list[Candidate]) -> tuple[list[Candidate], list[dict[str, Any]]]:
    controls = control_shape_candidates(shape_candidates)
    if not controls:
        return shape_candidates, []
    kept: list[Candidate] = []
    suppressed: list[dict[str, Any]] = []
    for shape in shape_candidates:
        if shape.scores.get("confirmedControlSurface", 0.0) >= 1.0:
            kept.append(shape)
            continue
        owner = best_shape_control_owner(shape, controls)
        if owner is None:
            kept.append(shape)
            continue
        reason = classify_control_owned_shape(shape, owner)
        if reason == "":
            kept.append(shape)
            continue
        suppressed.append(
            {
                "kind": "control_owned_shape_suppressed",
                "id": shape.id,
                "bbox": shape.bbox.to_dict(),
                "reason": reason,
                "controlSurfaceId": owner.id,
                "controlSurfaceReason": owner.reason,
                "controlSurfaceBBox": owner.bbox.to_dict(),
                "ioaShapeInControl": round(ioa(shape.bbox, owner.bbox), 4),
                "ioaControlInShape": round(ioa(owner.bbox, shape.bbox), 4),
                "iou": round(iou(shape.bbox, owner.bbox), 4),
            }
        )
    return kept, suppressed


def best_shape_control_owner(shape: Candidate, control_shapes: list[Candidate]) -> Candidate | None:
    best: tuple[float, Candidate] | None = None
    for control in control_shapes:
        shape_in_control = ioa(shape.bbox, control.bbox)
        control_in_shape = ioa(control.bbox, shape.bbox)
        overlap = iou(shape.bbox, control.bbox)
        edge_score = adjacent_control_edge_score(shape.bbox, control.bbox)
        score = max(shape_in_control, control_in_shape, overlap, edge_score)
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, control)
    return best[1] if best is not None else None


def adjacent_control_edge_score(shape: BBox, control: BBox) -> float:
    if shape.area <= 0 or control.area <= 0:
        return 0.0
    vertical_overlap = max(0, min(shape.y2, control.y2) - max(shape.y, control.y))
    horizontal_overlap = max(0, min(shape.x2, control.x2) - max(shape.x, control.x))
    vertical_ratio = vertical_overlap / max(1, min(shape.height, control.height))
    horizontal_ratio = horizontal_overlap / max(1, min(shape.width, control.width))
    margin = max(2, int(round(min(control.width, control.height) * 0.18)))
    horizontal_touch = (
        0 <= shape.x - control.x2 <= margin
        or 0 <= control.x - shape.x2 <= margin
        or intersection_area(shape, control) > 0
    )
    vertical_touch = (
        0 <= shape.y - control.y2 <= margin
        or 0 <= control.y - shape.y2 <= margin
        or intersection_area(shape, control) > 0
    )
    if horizontal_touch and vertical_ratio >= 0.55:
        return 0.36 + min(0.24, vertical_ratio * 0.24)
    if vertical_touch and horizontal_ratio >= 0.55:
        return 0.30 + min(0.20, horizontal_ratio * 0.20)
    return 0.0


def suppress_container_parent_shapes(shape_candidates: list[Candidate]) -> tuple[list[Candidate], list[dict[str, Any]]]:
    containers = [item for item in shape_candidates if item.reason == "local_container_surface"]
    if len(containers) < 2:
        return shape_candidates, []
    kept: list[Candidate] = []
    suppressed: list[dict[str, Any]] = []
    for shape in shape_candidates:
        reason, children = classify_container_parent_shape(shape, containers)
        if reason == "":
            kept.append(shape)
            continue
        suppressed.append(
            {
                "kind": "container_parent_shape_suppressed",
                "id": shape.id,
                "bbox": shape.bbox.to_dict(),
                "reason": reason,
                "childSurfaceIds": [child.id for child in children],
                "childSurfaceBBoxes": [child.bbox.to_dict() for child in children],
                "childSurfaceCount": len(children),
                "childAreaRatio": round(sum(child.bbox.area for child in children) / max(1, shape.bbox.area), 4),
            }
        )
    return kept, suppressed


def classify_container_parent_shape(shape: Candidate, containers: list[Candidate]) -> tuple[str, list[Candidate]]:
    if shape.reason != "low_texture_solid_region":
        return "", []
    if shape.scores.get("confirmedControlSurface", 0.0) >= 1.0:
        return "", []
    children = [child for child in containers if child.id != shape.id and ioa(child.bbox, shape.bbox) >= 0.82]
    if len(children) < 2:
        return "", []
    union = union_bbox([child.bbox for child in children])
    if union is None:
        return "", []
    if ioa(union, shape.bbox) < 0.78:
        return "", []
    child_area_ratio = sum(child.bbox.area for child in children) / max(1, shape.bbox.area)
    if child_area_ratio < 0.24:
        return "", []
    if shape.bbox.area > union.area * 3.2:
        return "", []
    if not sibling_surface_group(children):
        return "", []
    return "container_children_own_surface", children


def union_bbox(boxes: list[BBox]) -> BBox | None:
    if not boxes:
        return None
    x1 = min(box.x for box in boxes)
    y1 = min(box.y for box in boxes)
    x2 = max(box.x2 for box in boxes)
    y2 = max(box.y2 for box in boxes)
    return BBox(x1, y1, x2 - x1, y2 - y1)


def sibling_surface_group(children: list[Candidate]) -> bool:
    if len(children) < 2:
        return False
    boxes = sorted([child.bbox for child in children], key=lambda box: (box.y + box.height / 2, box.x))
    heights = [box.height for box in boxes]
    widths = [box.width for box in boxes]
    median_height = float(np.median(heights))
    median_width = float(np.median(widths))
    if median_height <= 0 or median_width <= 0:
        return False
    same_row = max(abs((box.y + box.height / 2) - (boxes[0].y + boxes[0].height / 2)) for box in boxes) <= median_height * 0.42
    similar_height = max(abs(box.height - median_height) for box in boxes) <= median_height * 0.48
    horizontal_gutters = [max(0, boxes[index + 1].x - boxes[index].x2) for index in range(len(boxes) - 1)]
    visible_horizontal_gutter = any(gap >= max(4, median_height * 0.04) for gap in horizontal_gutters)
    if same_row and similar_height and visible_horizontal_gutter:
        return True
    boxes = sorted([child.bbox for child in children], key=lambda box: (box.x + box.width / 2, box.y))
    same_col = max(abs((box.x + box.width / 2) - (boxes[0].x + boxes[0].width / 2)) for box in boxes) <= median_width * 0.42
    similar_width = max(abs(box.width - median_width) for box in boxes) <= median_width * 0.48
    vertical_gutters = [max(0, boxes[index + 1].y - boxes[index].y2) for index in range(len(boxes) - 1)]
    visible_vertical_gutter = any(gap >= max(4, median_width * 0.04) for gap in vertical_gutters)
    return same_col and similar_width and visible_vertical_gutter


def classify_control_owned_shape(shape: Candidate, control: Candidate) -> str:
    if shape.reason in {"background_surface_band", "inferred_background_plate_from_surface_bands"}:
        return ""
    shape_in_control = ioa(shape.bbox, control.bbox)
    control_in_shape = ioa(control.bbox, shape.bbox)
    overlap = iou(shape.bbox, control.bbox)
    area_ratio = shape.bbox.area / max(1, control.bbox.area)
    center_dx = abs((shape.bbox.x + shape.bbox.width / 2) - (control.bbox.x + control.bbox.width / 2))
    center_dy = abs((shape.bbox.y + shape.bbox.height / 2) - (control.bbox.y + control.bbox.height / 2))
    center_close = center_dx <= control.bbox.width * 0.45 and center_dy <= control.bbox.height * 0.55
    if control_in_shape >= 0.72 and control_shape_fill_distance(shape, control) <= 42.0:
        return "control_surface_owned_background_shape"
    if control_in_shape >= 0.72 and area_ratio <= 1.65 and center_close:
        return "control_surface_parent_shape_fragment"
    if control_in_shape >= 0.55 and shape_in_control >= 0.45 and area_ratio <= 1.80 and center_close:
        return "control_surface_overlapping_shape_fragment"
    if shape_in_control >= 0.72 and shape.bbox.area <= control.bbox.area * 0.35:
        return "control_surface_internal_shape_fragment"
    if overlap >= 0.52 and control_shape_fill_distance(shape, control) <= 48.0:
        return "control_surface_duplicate_shape_fragment"
    if is_control_adjacent_background_sliver(shape, control, shape_in_control, control_in_shape, overlap):
        return "control_adjacent_background_sliver"
    return ""


def is_control_adjacent_background_sliver(
    shape: Candidate,
    control: Candidate,
    shape_in_control: float,
    control_in_shape: float,
    overlap: float,
) -> bool:
    if shape.reason != "low_texture_solid_region":
        return False
    if shape.scores.get("confirmedControlSurface", 0.0) >= 1.0:
        return False
    if shape.scores.get("textOverlap", 0.0) > 0.05:
        return False
    if shape.bbox.area <= 0 or control.bbox.area <= 0:
        return False
    area_ratio = shape.bbox.area / max(1, control.bbox.area)
    if area_ratio > 0.55:
        return False
    if intersection_area(shape.bbox, control.bbox) <= 0:
        return False
    if shape_in_control < 0.10 and overlap < 0.06:
        return False
    if control_in_shape >= 0.36:
        return False
    if shape_like_independent_control(shape, control):
        return False
    if not is_background_sliver_like(shape, control):
        return False
    if max(shape_in_control, overlap, adjacent_control_edge_score(shape.bbox, control.bbox)) < 0.34:
        return False
    return True


def is_background_sliver_like(shape: Candidate, control: Candidate) -> bool:
    width_ratio = shape.bbox.width / max(1, control.bbox.width)
    height_ratio = shape.bbox.height / max(1, control.bbox.height)
    narrow = width_ratio <= 0.36 and height_ratio >= 0.55
    flat = height_ratio <= 0.36 and width_ratio >= 0.55
    small_residual = shape.bbox.area <= control.bbox.area * 0.32 and (width_ratio <= 0.45 or height_ratio <= 0.45)
    if not (narrow or flat or small_residual):
        return False
    dominant = float(shape.scores.get("dominant", 0.0))
    texture = float(shape.scores.get("texture", 1.0))
    entropy = float(shape.scores.get("entropy", 1.0))
    edge = float(shape.scores.get("edge", 1.0))
    if dominant < 0.72:
        return False
    if texture > 0.42 or entropy > 0.32 or edge > 0.34:
        return False
    return True


def shape_like_independent_control(shape: Candidate, control: Candidate) -> bool:
    if shape.scores.get("surfaceRoleControl", 0.0) >= 1.0 or shape.scores.get("controlSurface", 0.0) >= 1.0:
        return True
    if shape.reason in {"ocr_anchored_control_surface", "model_assisted_control_surface", "editable_control_surface_from_raster"}:
        return True
    width_ratio = shape.bbox.width / max(1, control.bbox.width)
    height_ratio = shape.bbox.height / max(1, control.bbox.height)
    aspect = shape.bbox.width / max(1, shape.bbox.height)
    comparable = 0.58 <= width_ratio <= 1.75 and 0.58 <= height_ratio <= 1.75
    control_like_aspect = 1.1 <= aspect <= 14.0
    has_control_evidence = (
        shape.scores.get("boundaryStrongSideCount", 0.0) >= 2.0
        or shape.scores.get("containedTextBlockCount", 0.0) >= 1.0
        or shape.scores.get("relatedTextBlockCount", 0.0) >= 1.0
    )
    return comparable and control_like_aspect and has_control_evidence


def extract_control_foreground_residuals(
    rgb: np.ndarray,
    candidate: Candidate,
    fill: np.ndarray,
    text_mask: np.ndarray,
    source_index: int,
) -> list[Candidate]:
    crop = rgb[candidate.bbox.y : candidate.bbox.y2, candidate.bbox.x : candidate.bbox.x2]
    if crop.size == 0:
        return []
    local_text = text_mask[candidate.bbox.y : candidate.bbox.y2, candidate.bbox.x : candidate.bbox.x2]
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)

    distances = np.linalg.norm(crop.astype(np.float32) - fill.reshape(1, 1, 3).astype(np.float32), axis=2)
    residual = (distances >= 72.0) & ~binary_dilate(local_text, iterations=1)
    margin = max(6, min(candidate.bbox.width, candidate.bbox.height) // 5)
    if residual.shape[0] <= margin * 2 or residual.shape[1] <= margin * 2:
        return []
    residual[:margin, :] = False
    residual[-margin:, :] = False
    residual[:, :margin] = False
    residual[:, -margin:] = False
    residual = binary_close(residual, iterations=2)

    residuals: list[Candidate] = []
    for component_index, component in enumerate(connected_components(residual), start=1):
        box = component_bbox(component, 1, candidate.bbox.width, candidate.bbox.height)
        if box.area < 48 or box.width < 5 or box.height < 5:
            continue
        if box.area > candidate.bbox.area * 0.28:
            continue
        global_box = BBox(candidate.bbox.x + box.x, candidate.bbox.y + box.y, box.width, box.height)
        if overlaps_text_zone(global_box, text_mask, padding=max(4, candidate.bbox.height // 4)):
            continue
        scores = {
            "texture": candidate.scores.get("texture", 0.0),
            "edge": candidate.scores.get("edge", 0.0),
            "entropy": candidate.scores.get("entropy", 0.0),
            "unique": candidate.scores.get("unique", 0.0),
            "dominant": candidate.scores.get("dominant", 0.0),
            "textOverlap": 0.0,
            "raster": max(0.55, candidate.scores.get("raster", 0.0)),
            "shape": 0.0,
            "controlResidual": 1.0,
        }
        residuals.append(
            Candidate(
                id=f"control_residual_{source_index:04d}_{component_index:04d}_{candidate.id}",
                kind="raster",
                bbox=global_box,
                score=max(0.55, candidate.score),
                scores=scores,
                reason="control_foreground_residual",
            )
        )
    return nms_candidates(residuals, overlap_threshold=0.52)


def overlaps_text_zone(box: BBox, text_mask: np.ndarray, padding: int) -> bool:
    if not text_mask.size:
        return False
    height, width = text_mask.shape
    padded = clamp_box(
        BBox(box.x - padding, box.y - padding, box.width + padding * 2, box.height + padding * 2),
        width,
        height,
    )
    if padded is None:
        return False
    return bool(text_mask[padded.y : padded.y2, padded.x : padded.x2].any())
