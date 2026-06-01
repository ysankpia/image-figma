#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def to_dict(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class OCRBlock:
    id: str
    text: str
    bbox: BBox
    confidence: float


@dataclass(frozen=True)
class Candidate:
    id: str
    kind: str
    bbox: BBox
    score: float
    scores: dict[str, float]
    reason: str


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def clamp_box(box: BBox, width: int, height: int) -> BBox | None:
    x1 = max(0, min(width, box.x))
    y1 = max(0, min(height, box.y))
    x2 = max(0, min(width, box.x2))
    y2 = max(0, min(height, box.y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return BBox(x1, y1, x2 - x1, y2 - y1)


def intersection_area(a: BBox, b: BBox) -> int:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    return max(0, x2 - x1) * max(0, y2 - y1)


def iou(a: BBox, b: BBox) -> float:
    inter = intersection_area(a, b)
    union = a.area + b.area - inter
    if union <= 0:
        return 0.0
    return inter / union


def ioa(inner: BBox, outer: BBox) -> float:
    if inner.area <= 0:
        return 0.0
    return intersection_area(inner, outer) / inner.area


def load_ocr_blocks(path: Path | None, image_width: int, image_height: int, min_confidence: float) -> list[OCRBlock]:
    if path is None:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_blocks = data.get("blocks", data if isinstance(data, list) else [])

    blocks: list[OCRBlock] = []
    for index, item in enumerate(raw_blocks, start=1):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        confidence = float(item.get("confidence", 1.0))
        if confidence < min_confidence:
            continue
        raw_box = item.get("bbox", {})
        if isinstance(raw_box, list):
            if len(raw_box) < 4:
                continue
            box = BBox(int(raw_box[0]), int(raw_box[1]), int(raw_box[2]), int(raw_box[3]))
        else:
            box = BBox(
                int(raw_box.get("x", 0)),
                int(raw_box.get("y", 0)),
                int(raw_box.get("width", 0)),
                int(raw_box.get("height", 0)),
            )
        clamped = clamp_box(box, image_width, image_height)
        if clamped is None or clamped.width <= 1 or clamped.height < 6:
            continue
        blocks.append(
            OCRBlock(
                id=str(item.get("id") or f"text_{index:04d}"),
                text=text,
                bbox=clamped,
                confidence=confidence,
            )
        )
    return blocks


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


def estimate_background_color(rgb: np.ndarray) -> tuple[int, int, int]:
    height, width, _ = rgb.shape
    edge = max(8, min(width, height) // 30)
    samples = np.concatenate(
        [
            rgb[:edge, :, :].reshape(-1, 3),
            rgb[height - edge :, :, :].reshape(-1, 3),
            rgb[:, :edge, :].reshape(-1, 3),
            rgb[:, width - edge :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    color, _ = dominant_cluster_stats(samples, bucket_size=16)
    return int(color[0]), int(color[1]), int(color[2])


def dominant_cluster_color(pixels: np.ndarray, bucket_size: int = 24) -> np.ndarray:
    color, _ = dominant_cluster_stats(pixels, bucket_size)
    return color


def dominant_cluster_stats(pixels: np.ndarray, bucket_size: int = 24) -> tuple[np.ndarray, float]:
    if pixels.size == 0:
        return np.array([255, 255, 255], dtype=np.uint8), 1.0
    buckets = np.clip(pixels.astype(np.int16) // bucket_size, 0, 255 // bucket_size)
    codes = buckets[:, 0] * 1024 + buckets[:, 1] * 32 + buckets[:, 2]
    values, counts = np.unique(codes, return_counts=True)
    dominant_index = int(np.argmax(counts))
    dominant_code = values[dominant_index]
    cluster = pixels[codes == dominant_code]
    if cluster.size == 0:
        color = np.median(pixels, axis=0)
    else:
        color = np.median(cluster, axis=0)
    return np.clip(color, 0, 255).astype(np.uint8), float(counts[dominant_index]) / max(1, int(counts.sum()))


def color_hex(color: tuple[int, int, int] | np.ndarray) -> str:
    r, g, b = [int(item) for item in color]
    return f"#{r:02x}{g:02x}{b:02x}"


def color_distance(a: tuple[int, int, int] | np.ndarray, b: tuple[int, int, int] | np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=np.float32) - np.asarray(b, dtype=np.float32)))


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


def connected_components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    rows, cols = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[list[tuple[int, int]]] = []

    for row in range(rows):
        for col in range(cols):
            if not mask[row, col] or visited[row, col]:
                continue
            stack = [(row, col)]
            visited[row, col] = True
            component: list[tuple[int, int]] = []
            while stack:
                cur_row, cur_col = stack.pop()
                component.append((cur_row, cur_col))
                for next_row, next_col in (
                    (cur_row - 1, cur_col),
                    (cur_row + 1, cur_col),
                    (cur_row, cur_col - 1),
                    (cur_row, cur_col + 1),
                ):
                    if (
                        0 <= next_row < rows
                        and 0 <= next_col < cols
                        and mask[next_row, next_col]
                        and not visited[next_row, next_col]
                    ):
                        visited[next_row, next_col] = True
                        stack.append((next_row, next_col))
            components.append(component)
    return components


def component_bbox(component: list[tuple[int, int]], tile_size: int, width: int, height: int) -> BBox:
    rows = [item[0] for item in component]
    cols = [item[1] for item in component]
    x1 = min(cols) * tile_size
    y1 = min(rows) * tile_size
    x2 = min(width, (max(cols) + 1) * tile_size)
    y2 = min(height, (max(rows) + 1) * tile_size)
    return BBox(x1, y1, x2 - x1, y2 - y1)


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


def is_full_page_backing(box: BBox, width: int, height: int) -> bool:
    page_area = width * height
    if page_area <= 0:
        return False
    area_ratio = box.area / page_area
    return area_ratio >= 0.62 or (box.width >= width * 0.94 and box.height >= height * 0.70)


def reject_raster(
    box: BBox,
    scores: dict[str, float],
    width: int,
    height: int,
    min_area: int,
    max_text_overlap: float,
) -> str:
    if box.area < min_area:
        return "too_small"
    if is_full_page_backing(box, width, height):
        return "full_page_backing"
    if box.width < 6 or box.height < 6:
        return "too_thin"
    aspect = max(box.width / max(1, box.height), box.height / max(1, box.width))
    if aspect > 18:
        return "extreme_aspect"
    if scores["textOverlap"] > max_text_overlap and scores["texture"] < 0.68:
        return "text_overlap"
    return ""


def reject_shape(box: BBox, scores: dict[str, float], width: int, height: int, min_area: int) -> str:
    if box.area < min_area:
        return "too_small"
    if is_full_page_backing(box, width, height):
        return "full_page_backing"
    page_area = width * height
    if page_area > 0 and box.area / page_area >= 0.22 and scores.get("textOverlap", 0.0) >= 0.12:
        return "body_scale_text_backing"
    if box.width < 12 or box.height < 6:
        return "too_thin"
    return ""


def nms_candidates(candidates: list[Candidate], overlap_threshold: float) -> list[Candidate]:
    accepted: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.score, item.bbox.area), reverse=True):
        duplicate = False
        for kept in accepted:
            if iou(candidate.bbox, kept.bbox) >= overlap_threshold or ioa(candidate.bbox, kept.bbox) >= 0.82:
                duplicate = True
                break
        if not duplicate:
            accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def build_raster_candidates(
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    ocr_blocks: list[OCRBlock],
    width: int,
    height: int,
    tile_size: int,
    threshold: float,
    min_area: int,
    max_text_overlap: float,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    raw_mask = (maps["raster"] >= threshold) & (maps["textCoverage"] <= 0.65)
    closed = binary_close(raw_mask, iterations=1)
    candidates: list[Candidate] = []
    rejected: list[dict[str, Any]] = []

    for index, component in enumerate(connected_components(closed), start=1):
        box = component_bbox(component, tile_size, width, height)
        scores = bbox_scores(box, maps, text_mask, tile_size)
        reason = reject_raster(box, scores, width, height, min_area, max_text_overlap)
        if reason:
            rejected.append(
                {
                    "kind": "raster",
                    "bbox": box.to_dict(),
                    "reason": reason,
                    "scores": scores,
                }
            )
            continue
        text_count = count_text_blocks(box, ocr_blocks)
        candidate_reason = "high_texture_low_text_overlap"
        if text_count:
            candidate_reason = "high_texture_with_internal_text"
        score = float(scores["raster"])
        candidates.append(Candidate(f"raster_{index:04d}", "raster", box, score, scores, candidate_reason))

    return nms_candidates(candidates, overlap_threshold=0.52), rejected


def build_shape_candidates(
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    raster_candidates: list[Candidate],
    width: int,
    height: int,
    tile_size: int,
    threshold: float,
    min_area: int,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    shape_mask = (maps["shape"] >= threshold) & (maps["textCoverage"] <= 0.35)
    raster_tile_mask = np.zeros_like(shape_mask, dtype=bool)
    for raster in raster_candidates:
        row_slice, col_slice = bbox_tile_slice(raster.bbox, tile_size, shape_mask.shape)
        raster_tile_mask[row_slice, col_slice] = True
    shape_mask &= ~binary_dilate(raster_tile_mask, iterations=1)
    closed = binary_close(shape_mask, iterations=1)

    candidates: list[Candidate] = []
    rejected: list[dict[str, Any]] = []
    for index, component in enumerate(connected_components(closed), start=1):
        box = component_bbox(component, tile_size, width, height)
        scores = bbox_scores(box, maps, text_mask, tile_size)
        reason = reject_shape(box, scores, width, height, min_area)
        if reason:
            rejected.append(
                {
                    "kind": "shape",
                    "bbox": box.to_dict(),
                    "reason": reason,
                    "scores": scores,
                }
            )
            continue
        candidates.append(Candidate(f"shape_{index:04d}", "shape", box, float(scores["shape"]), scores, "low_texture_solid_region"))
    return nms_candidates(candidates, overlap_threshold=0.62), rejected


def build_surface_candidates(
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    width: int,
    height: int,
    tile_size: int,
    min_area: int,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    tile_rows, tile_cols = maps["shape"].shape
    eligible = (
        (maps["texture"] <= 0.42)
        & (maps["edge"] <= 0.42)
        & (maps["entropy"] <= 0.76)
        & (maps["dominant"] >= 0.34)
        & (maps["textCoverage"] <= 0.55)
    )
    row_segments: list[dict[str, Any]] = []
    for row in range(tile_rows):
        cols = np.flatnonzero(eligible[row])
        if len(cols) < max(3, math.ceil(tile_cols * 0.28)):
            continue
        row_colors = maps["meanColor"][row, cols].reshape(-1, 3)
        color, ratio = dominant_cluster_stats(row_colors.astype(np.uint8), bucket_size=32)
        close_cols = [
            int(col)
            for col in cols
            if color_distance(maps["meanColor"][row, int(col)], color) <= 46.0
        ]
        if len(close_cols) < max(3, math.ceil(tile_cols * 0.25)):
            continue
        for start_col, end_col in contiguous_ranges(close_cols):
            segment_width = end_col - start_col + 1
            if segment_width < max(3, math.ceil(tile_cols * 0.20)):
                continue
            row_segments.append(
                {
                    "row1": row,
                    "row2": row,
                    "col1": start_col,
                    "col2": end_col,
                    "colors": [color.astype(np.float32)],
                    "ratio": ratio,
                }
            )

    bands: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for segment in row_segments:
        next_active = [band for band in active if band["row2"] >= segment["row1"] - 1]
        match: dict[str, Any] | None = None
        for band in next_active:
            if not bands_overlap_horizontally(band, segment):
                continue
            band_color = np.mean(np.stack(band["colors"]), axis=0)
            segment_color = np.mean(np.stack(segment["colors"]), axis=0)
            if color_distance(band_color, segment_color) <= 52.0:
                match = band
                break
        if match is None:
            bands.append(segment)
            next_active.append(segment)
        else:
            match["row2"] = segment["row2"]
            match["col1"] = min(match["col1"], segment["col1"])
            match["col2"] = max(match["col2"], segment["col2"])
            match["colors"].extend(segment["colors"])
            match["ratio"] = min(float(match["ratio"]), float(segment["ratio"]))
        active = next_active

    candidates: list[Candidate] = []
    rejected: list[dict[str, Any]] = []
    page_bg = estimate_background_color(maps_color_proxy(maps, width, height, tile_size))
    page_area = width * height
    for index, band in enumerate(bands, start=1):
        box = BBox(
            x=int(band["col1"]) * tile_size,
            y=int(band["row1"]) * tile_size,
            width=min(width, (int(band["col2"]) + 1) * tile_size) - int(band["col1"]) * tile_size,
            height=min(height, (int(band["row2"]) + 1) * tile_size) - int(band["row1"]) * tile_size,
        )
        scores = bbox_scores(box, maps, text_mask, tile_size)
        band_color = np.mean(np.stack(band["colors"]), axis=0)
        scores.update(
            {
                "surface": round(float(scores["dominant"]) * 0.45 + (1.0 - float(scores["texture"])) * 0.30 + (1.0 - float(scores["edge"])) * 0.25, 4),
                "fillR": round(float(band_color[0]), 2),
                "fillG": round(float(band_color[1]), 2),
                "fillB": round(float(band_color[2]), 2),
                "rowDominantRatio": round(float(band["ratio"]), 4),
            }
        )
        reason = reject_surface(box, scores, width, height, min_area, page_area, page_bg)
        if reason:
            rejected.append(
                {
                    "kind": "surface",
                    "bbox": box.to_dict(),
                    "reason": reason,
                    "scores": scores,
                }
            )
            continue
        candidates.append(Candidate(f"surface_{index:04d}", "shape", box, float(scores["surface"]), scores, "background_surface_band"))

    return nms_surface_candidates(candidates), rejected


def contiguous_ranges(values: list[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    ranges: list[tuple[int, int]] = []
    start = values[0]
    previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append((start, previous))
        start = value
        previous = value
    ranges.append((start, previous))
    return ranges


def bands_overlap_horizontally(a: dict[str, Any], b: dict[str, Any]) -> bool:
    left = max(int(a["col1"]), int(b["col1"]))
    right = min(int(a["col2"]), int(b["col2"]))
    overlap = max(0, right - left + 1)
    if overlap <= 0:
        return False
    a_width = int(a["col2"]) - int(a["col1"]) + 1
    b_width = int(b["col2"]) - int(b["col1"]) + 1
    return overlap / max(1, min(a_width, b_width)) >= 0.35


def maps_color_proxy(maps: dict[str, np.ndarray], width: int, height: int, tile_size: int) -> np.ndarray:
    proxy = np.zeros((height, width, 3), dtype=np.uint8)
    mean_color = maps["meanColor"]
    rows, cols, _ = mean_color.shape
    for row in range(rows):
        y1 = row * tile_size
        y2 = min(height, y1 + tile_size)
        for col in range(cols):
            x1 = col * tile_size
            x2 = min(width, x1 + tile_size)
            proxy[y1:y2, x1:x2] = np.clip(mean_color[row, col], 0, 255).astype(np.uint8)
    return proxy


def reject_surface(
    box: BBox,
    scores: dict[str, float],
    width: int,
    height: int,
    min_area: int,
    page_area: int,
    page_bg: tuple[int, int, int],
) -> str:
    if box.area < min_area:
        return "too_small"
    if box.width < max(48, width * 0.12) or box.height < 16:
        return "too_thin"
    if box.area >= page_area * 0.82:
        return "page_background"
    fill = np.array([scores.get("fillR", 255.0), scores.get("fillG", 255.0), scores.get("fillB", 255.0)], dtype=np.float32)
    if box.area >= page_area * 0.55 and color_distance(fill, page_bg) <= 28.0:
        return "same_as_page_background"
    if scores.get("texture", 1.0) > 0.46 or scores.get("edge", 1.0) > 0.46:
        return "not_stable_surface"
    return ""


def nms_surface_candidates(candidates: list[Candidate]) -> list[Candidate]:
    accepted: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.bbox.area, item.score), reverse=True):
        duplicate = False
        for kept in accepted:
            if iou(candidate.bbox, kept.bbox) >= 0.78 or ioa(candidate.bbox, kept.bbox) >= 0.88:
                duplicate = True
                break
        if not duplicate:
            accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def merge_surface_and_shape_candidates(surface_candidates: list[Candidate], shape_candidates: list[Candidate]) -> list[Candidate]:
    merged = nms_surface_candidates(surface_candidates) + shape_candidates
    accepted: list[Candidate] = []
    for candidate in sorted(merged, key=lambda item: (item.bbox.y, item.bbox.x, -item.bbox.area, item.id)):
        duplicate = False
        for kept in accepted:
            if iou(candidate.bbox, kept.bbox) >= 0.82:
                duplicate = True
                break
        if not duplicate:
            accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def control_surface_fill(rgb: np.ndarray, candidate: Candidate, text_mask: np.ndarray) -> tuple[np.ndarray, float, float]:
    crop = rgb[candidate.bbox.y : candidate.bbox.y2, candidate.bbox.x : candidate.bbox.x2]
    if crop.size == 0:
        return np.array([255, 255, 255], dtype=np.uint8), 0.0, 0.0
    local_text = text_mask[candidate.bbox.y : candidate.bbox.y2, candidate.bbox.x : candidate.bbox.x2]
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)
    pixels = crop[~local_text]
    if pixels.shape[0] < max(16, crop.shape[0] * crop.shape[1] // 8):
        pixels = crop.reshape(-1, 3)
    fill, coverage = dominant_cluster_stats(pixels.astype(np.uint8), bucket_size=20)
    distances = np.linalg.norm(pixels.astype(np.float32) - fill.reshape(1, 3).astype(np.float32), axis=1)
    close_coverage = float((distances <= 64.0).mean()) if distances.size else 0.0
    return fill, coverage, close_coverage


def contained_text_blocks(candidate: Candidate, ocr_blocks: list[OCRBlock]) -> list[OCRBlock]:
    blocks: list[OCRBlock] = []
    for block in ocr_blocks:
        if block.bbox.area <= 0:
            continue
        coverage = intersection_area(candidate.bbox, block.bbox) / block.bbox.area
        if coverage >= 0.82:
            blocks.append(block)
    return blocks


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
            best = max(best, float(np.percentile(distances, 92)))
    return best


def is_editable_control_surface(
    candidate: Candidate,
    blocks: list[OCRBlock],
    fill_coverage: float,
    close_coverage: float,
    text_contrast: float,
    page_area: int,
) -> bool:
    if not blocks or len(blocks) > 2:
        return False
    if candidate.bbox.area < 480 or candidate.bbox.area > page_area * 0.08:
        return False
    if candidate.bbox.width < 24 or candidate.bbox.height < 14:
        return False
    aspect = candidate.bbox.width / max(1, candidate.bbox.height)
    if aspect < 1.15 or aspect > 12.0:
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
) -> tuple[list[Candidate], list[Candidate], list[dict[str, Any]]]:
    page_area = int(rgb.shape[0] * rgb.shape[1])
    promoted_shapes: list[Candidate] = []
    residual_rasters: list[Candidate] = []
    consumed_raster_ids: set[str] = set()
    decisions: list[dict[str, Any]] = []

    for index, raster in enumerate(raster_candidates, start=1):
        blocks = contained_text_blocks(raster, ocr_blocks)
        fill, fill_coverage, close_coverage = control_surface_fill(rgb, raster, text_mask)
        text_contrast = control_text_contrast(rgb, blocks, fill)
        if not is_editable_control_surface(raster, blocks, fill_coverage, close_coverage, text_contrast, page_area):
            continue

        scores = dict(raster.scores)
        scores.update(
            {
                "controlSurface": 1.0,
                "fillCoverage": round(float(fill_coverage), 4),
                "closeFillCoverage": round(float(close_coverage), 4),
                "textContrast": round(float(text_contrast), 4),
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
                "residualRasterCount": len(residuals),
            }
        )

    remaining_rasters = [item for item in raster_candidates if item.id not in consumed_raster_ids]
    merged_rasters = nms_candidates(remaining_rasters + residual_rasters, overlap_threshold=0.52)
    merged_shapes: list[Candidate] = []
    for candidate in sorted(shape_candidates + promoted_shapes, key=lambda item: (item.bbox.y, item.bbox.x, -item.bbox.area, item.id)):
        if any(iou(candidate.bbox, kept.bbox) >= 0.82 for kept in merged_shapes):
            continue
        merged_shapes.append(candidate)
    return merged_rasters, merged_shapes, decisions


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


def infer_background_plate_candidates(
    surface_candidates: list[Candidate],
    width: int,
    height: int,
    page_background: tuple[int, int, int],
) -> list[Candidate]:
    surfaces = [
        item
        for item in surface_candidates
        if item.reason == "background_surface_band"
        and item.bbox.width >= max(120, width * 0.18)
        and item.bbox.height >= 16
        and surface_fill_distance(item, page_background) >= 36.0
    ]
    clusters: list[dict[str, Any]] = []
    for surface in sorted(surfaces, key=lambda item: item.bbox.area, reverse=True):
        color = surface_fill_rgb(surface)
        match: dict[str, Any] | None = None
        for cluster in clusters:
            if color_distance(cluster["color"], color) <= 40.0:
                match = cluster
                break
        if match is None:
            clusters.append({"color": color.astype(np.float32), "surfaces": [surface]})
        else:
            match["surfaces"].append(surface)
            colors = np.stack([surface_fill_rgb(item).astype(np.float32) for item in match["surfaces"]])
            match["color"] = np.mean(colors, axis=0)

    plates: list[Candidate] = []
    page_area = width * height
    for index, cluster in enumerate(clusters, start=1):
        members: list[Candidate] = cluster["surfaces"]
        if len(members) < 3:
            continue
        x1 = min(item.bbox.x for item in members)
        y1 = min(item.bbox.y for item in members)
        x2 = max(item.bbox.x2 for item in members)
        y2 = max(item.bbox.y2 for item in members)
        box = BBox(x1, y1, x2 - x1, y2 - y1)
        if box.width < width * 0.50 or box.height < height * 0.42:
            continue
        wide_member_count = sum(1 for item in members if item.bbox.width >= width * 0.45)
        if wide_member_count < 3:
            continue
        member_area = sum(item.bbox.area for item in members)
        if box.area <= 0 or member_area / box.area < 0.16:
            continue
        if page_area > 0 and box.area / page_area < 0.18:
            continue
        color = np.clip(cluster["color"], 0, 255).astype(np.uint8)
        scores = {
            "fillR": round(float(color[0]), 2),
            "fillG": round(float(color[1]), 2),
            "fillB": round(float(color[2]), 2),
            "sourceSurfaceCount": float(len(members)),
            "wideSurfaceCount": float(wide_member_count),
            "sourceSurfaceAreaRatio": round(float(member_area / max(1, box.area)), 4),
            "pageBackgroundDistance": round(float(color_distance(color, page_background)), 4),
        }
        plates.append(
            Candidate(
                id=f"background_plate_{index:04d}",
                kind="shape",
                bbox=box,
                score=0.99,
                scores=scores,
                reason="inferred_background_plate_from_surface_bands",
            )
        )

    return nms_surface_candidates(plates)


def surface_fill_rgb(surface: Candidate) -> np.ndarray:
    return np.array(
        [
            surface.scores.get("fillR", 255.0),
            surface.scores.get("fillG", 255.0),
            surface.scores.get("fillB", 255.0),
        ],
        dtype=np.float32,
    )


def surface_fill_distance(surface: Candidate, color: tuple[int, int, int] | np.ndarray) -> float:
    return color_distance(surface_fill_rgb(surface), color)


def build_foreground_object_candidates(
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    ocr_blocks: list[OCRBlock],
    surface_candidates: list[Candidate],
    width: int,
    height: int,
    tile_size: int,
    min_area: int,
    max_text_overlap: float,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    candidates: list[Candidate] = []
    rejected: list[dict[str, Any]] = []
    tile_rows, tile_cols = maps["raster"].shape
    analysis_regions = list(surface_candidates)
    analysis_regions.append(
        Candidate(
            "analysis_page_background",
            "shape",
            BBox(0, 0, width, height),
            1.0,
            {},
            "analysis_only_page_background",
        )
    )

    for surface_index, surface in enumerate(analysis_regions, start=1):
        if surface.bbox.area < max(min_area * 3, width * height * 0.015):
            continue
        row_slice, col_slice = bbox_tile_slice(surface.bbox, tile_size, (tile_rows, tile_cols))
        local_colors = maps["meanColor"][row_slice, col_slice].reshape(-1, 3).astype(np.uint8)
        bg_color = dominant_cluster_color(local_colors, bucket_size=28)
        local_mask = np.zeros((row_slice.stop - row_slice.start, col_slice.stop - col_slice.start), dtype=bool)
        for local_row, row in enumerate(range(row_slice.start, row_slice.stop)):
            for local_col, col in enumerate(range(col_slice.start, col_slice.stop)):
                mean = maps["meanColor"][row, col]
                distance = color_distance(mean, bg_color)
                text_coverage = float(maps["textCoverage"][row, col])
                if text_coverage > 0.50:
                    continue
                distinct_color = distance >= 52.0 and maps["dominant"][row, col] >= 0.12
                distinct_edge = distance >= 34.0 and maps["edge"][row, col] >= 0.20 and maps["entropy"][row, col] >= 0.18
                if distinct_color or distinct_edge:
                    local_mask[local_row, local_col] = True

        local_mask = binary_close(local_mask, iterations=1)
        for component_index, component in enumerate(connected_components(local_mask), start=1):
            absolute_component = [(row + row_slice.start, col + col_slice.start) for row, col in component]
            box = component_bbox(absolute_component, tile_size, width, height)
            box = clamp_box(box, width, height)
            if box is None:
                continue
            scores = bbox_scores(box, maps, text_mask, tile_size)
            reason = reject_raster(box, scores, width, height, min_area, max_text_overlap)
            if not reason and count_text_blocks(box, ocr_blocks) >= 3 and scores["texture"] < 0.22:
                reason = "text_cluster"
            if reason:
                rejected.append(
                    {
                        "kind": "foreground_object",
                        "bbox": box.to_dict(),
                        "reason": reason,
                        "scores": scores,
                    }
                )
                continue
            object_score = max(float(scores["raster"]), min(0.92, 0.45 + float(scores["edge"]) * 0.25 + float(scores["entropy"]) * 0.20 + float(scores["unique"]) * 0.10))
            scores = dict(scores)
            scores["foregroundObject"] = round(object_score, 4)
            candidates.append(
                Candidate(
                    f"foreground_{surface_index:04d}_{component_index:04d}",
                    "raster",
                    box,
                    object_score,
                    scores,
                    "foreground_object_on_surface",
                )
            )

    return nms_candidates(candidates, overlap_threshold=0.48), rejected


def promote_complex_shape_regions(
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
) -> tuple[list[Candidate], list[Candidate], list[dict[str, Any]]]:
    promoted: list[Candidate] = []
    remaining_shapes: list[Candidate] = []
    consumed_raster_ids: set[str] = set()
    decisions: list[dict[str, Any]] = []

    for shape in shape_candidates:
        if shape.reason == "background_surface_band":
            remaining_shapes.append(shape)
            continue
        contained = [item for item in raster_candidates if ioa(item.bbox, shape.bbox) >= 0.92]
        is_complex_region = (
            shape.bbox.area >= 24_000
            and len(contained) >= 3
            and shape.scores.get("dominant", 1.0) <= 0.76
            and shape.scores.get("textOverlap", 1.0) <= 0.12
            and (shape.scores.get("texture", 0.0) >= 0.10 or shape.scores.get("edge", 0.0) >= 0.12)
        )
        if not is_complex_region:
            remaining_shapes.append(shape)
            continue

        consumed_raster_ids.update(item.id for item in contained)
        scores = dict(shape.scores)
        scores["promotedFromShape"] = 1.0
        promoted.append(
            Candidate(
                id=f"promoted_{shape.id}",
                kind="raster",
                bbox=shape.bbox,
                score=max(shape.score, 0.65),
                scores=scores,
                reason="complex_visual_region_promoted_from_shape",
            )
        )
        decisions.append(
            {
                "kind": "shape_to_raster",
                "bbox": shape.bbox.to_dict(),
                "reason": "complex_region_contains_multiple_raster_fragments",
                "consumedRasterCount": len(contained),
            }
        )

    remaining_rasters = [item for item in raster_candidates if item.id not in consumed_raster_ids]
    return nms_candidates(remaining_rasters + promoted, overlap_threshold=0.52), remaining_shapes, decisions


def raster_ownership(candidate: Candidate, ocr_blocks: list[OCRBlock], text_mask: np.ndarray) -> dict[str, Any]:
    covered_blocks: list[dict[str, Any]] = []
    for block in ocr_blocks:
        overlap = intersection_area(candidate.bbox, block.bbox)
        if overlap <= 0 or block.bbox.area <= 0:
            continue
        block_coverage = overlap / block.bbox.area
        if block_coverage < 0.25:
            continue
        covered_blocks.append(
            {
                "id": block.id,
                "coverage": round(block_coverage, 4),
                "textLength": len(block.text),
            }
        )

    knockout_pixel_ratio = 0.0
    if candidate.bbox.area > 0 and text_mask.size:
        knockout_pixel_ratio = float(text_mask[candidate.bbox.y : candidate.bbox.y2, candidate.bbox.x : candidate.bbox.x2].mean())

    return {
        "textKnockout": bool(covered_blocks),
        "knockoutPixelRatio": round(knockout_pixel_ratio, 4),
        "coveredTextBlockCount": len(covered_blocks),
        "coveredTextBlocks": covered_blocks,
        "visibleTextOwnershipConflict": False,
    }


def build_raster_ownership(candidates: list[Candidate], ocr_blocks: list[OCRBlock], text_mask: np.ndarray) -> dict[str, dict[str, Any]]:
    return {candidate.id: raster_ownership(candidate, ocr_blocks, text_mask) for candidate in candidates}


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


def shape_fill(rgb: np.ndarray, shape: Candidate) -> str:
    if shape.reason in {"background_surface_band", "inferred_background_plate_from_surface_bands", "editable_control_surface_from_raster"}:
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
    if shape.reason == "editable_control_surface_from_raster":
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


def build_layer_stack(
    image_path: Path,
    ocr_path: Path | None,
    image: Image.Image,
    rgb: np.ndarray,
    ocr_blocks: list[OCRBlock],
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
    asset_refs: dict[str, str],
    ownership: dict[str, dict[str, Any]],
    rejected: list[dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    layers: list[dict[str, Any]] = []

    for index, shape in enumerate(shape_candidates, start=1):
        if shape.reason == "inferred_background_plate_from_surface_bands":
            z = 50 + index
        elif shape.reason == "background_surface_band":
            z = 100 + index
        else:
            z = 1000 + index
        layers.append(
            {
                "id": f"shape_{index:04d}",
                "type": "shape",
                "bbox": shape.bbox.to_dict(),
                "z": z,
                "style": shape_style(rgb, shape),
                "scores": shape.scores,
                "reason": shape.reason,
            }
        )

    for index, raster in enumerate(raster_candidates, start=1):
        layers.append(
            {
                "id": f"raster_{index:04d}",
                "type": "raster",
                "bbox": raster.bbox.to_dict(),
                "z": 2000 + index,
                "asset": asset_refs.get(raster.id, ""),
                "scores": raster.scores,
                "ownership": ownership.get(raster.id, {}),
                "reason": raster.reason,
            }
        )

    for index, block in enumerate(ocr_blocks, start=1):
        layers.append(
            {
                "id": block.id or f"text_{index:04d}",
                "type": "text",
                "bbox": block.bbox.to_dict(),
                "z": 3000 + index,
                "text": block.text,
                "confidence": round(block.confidence, 4),
                "reason": "ocr_authority",
            }
        )

    page_area = image.width * image.height
    full_page_raster = sum(1 for item in raster_candidates if is_full_page_backing(item.bbox, image.width, image.height))
    tiny_raster = sum(1 for item in raster_candidates if item.bbox.area < 400)
    raw_text_overlap_raster = sum(1 for item in raster_candidates if item.scores.get("textOverlap", 0.0) > thresholds["maxTextOverlap"])
    raster_text_knockout = sum(1 for item in raster_candidates if ownership.get(item.id, {}).get("textKnockout"))
    covered_text_blocks = sum(int(ownership.get(item.id, {}).get("coveredTextBlockCount", 0)) for item in raster_candidates)
    visible_text_overlap = sum(1 for item in raster_candidates if ownership.get(item.id, {}).get("visibleTextOwnershipConflict"))
    missing_assets = sum(1 for item in layers if item["type"] == "raster" and not item.get("asset"))
    surface_shapes = sum(1 for item in shape_candidates if item.reason == "background_surface_band")
    background_plates = sum(1 for item in shape_candidates if item.reason == "inferred_background_plate_from_surface_bands")
    control_surfaces = sum(1 for item in shape_candidates if item.reason == "editable_control_surface_from_raster")
    page_background = color_hex(estimate_background_color(rgb))

    return {
        "version": "layer_stack.v1",
        "sourceImage": str(image_path),
        "ocr": str(ocr_path) if ocr_path else "",
        "canvas": {"width": image.width, "height": image.height},
        "pageBackground": page_background,
        "layers": sorted(layers, key=lambda item: item["z"]),
        "diagnostics": {
            "layerCount": len(layers),
            "textLayerCount": len(ocr_blocks),
            "rasterLayerCount": len(raster_candidates),
            "shapeLayerCount": len(shape_candidates),
            "surfaceShapeLayerCount": surface_shapes,
            "backgroundPlateLayerCount": background_plates,
            "controlSurfaceShapeLayerCount": control_surfaces,
            "pageBackground": page_background,
            "rejectedCandidateCount": len(rejected),
            "fullPageVisibleRaster": full_page_raster,
            "tinyRasterFragments": tiny_raster,
            "textOverlapRaster": visible_text_overlap,
            "rawTextOverlapRaster": raw_text_overlap_raster,
            "rasterTextKnockoutCount": raster_text_knockout,
            "rasterCoveredTextBlockCount": covered_text_blocks,
            "missingAssetCount": missing_assets,
            "pageArea": page_area,
        },
        "thresholds": thresholds,
        "rejected": rejected[:200],
    }


def build_draft_runtime_dsl(layer_stack: dict[str, Any], rgb: np.ndarray) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []

    for layer in sorted(layer_stack["layers"], key=lambda item: (item["z"], item["bbox"]["y"], item["bbox"]["x"], item["id"])):
        layer_type = layer["type"]
        bbox = layer["bbox"]
        node: dict[str, Any] = {
            "id": layer["id"],
            "type": "image" if layer_type == "raster" else layer_type,
            "name": layer_name(layer),
            "bbox": bbox,
            "z": layer["z"],
            "meta": {
                "source": "psd_like_layer_stack",
                "reason": layer.get("reason", ""),
            },
        }

        if layer_type == "raster":
            asset_id = f"asset_{layer['id']}"
            node["image"] = {"assetId": asset_id, "mode": "fill"}
            node["meta"]["ownership"] = layer.get("ownership", {})
            assets.append(
                {
                    "assetId": asset_id,
                    "type": "image",
                    "url": layer.get("asset", ""),
                    "path": layer.get("asset", ""),
                    "format": "png",
                    "width": bbox["width"],
                    "height": bbox["height"],
                    "meta": {"sourceLayerId": layer["id"]},
                }
            )
        elif layer_type == "shape":
            node["style"] = layer.get("style", {})
        elif layer_type == "text":
            text = str(layer.get("text", ""))
            if not text.strip():
                continue
            node["text"] = {"characters": text}
            box = BBox(int(bbox["x"]), int(bbox["y"]), int(bbox["width"]), int(bbox["height"]))
            node["style"] = {
                "fontSize": max(8, min(96, round(box.height * 0.8))),
                "fontWeight": 400,
                "color": sample_text_color(rgb, box),
            }

        children.append(node)

    canvas = layer_stack["canvas"]
    background = str(layer_stack.get("pageBackground") or color_hex(estimate_background_color(rgb)))
    return {
        "version": "1.0",
        "kind": "draft_runtime",
        "taskId": "psd_like_experiment",
        "page": {
            "name": "PSD-like Draft Experiment",
            "width": canvas["width"],
            "height": canvas["height"],
            "background": background,
        },
        "root": {
            "id": "root",
            "type": "frame",
            "name": "PSD-like Draft",
            "bbox": {"x": 0, "y": 0, "width": canvas["width"], "height": canvas["height"]},
            "children": children,
        },
        "assets": assets,
        "meta": {
            "pipeline": "psd_like_layer_decomposition_experiment.v1",
            "sourceImage": layer_stack.get("sourceImage", ""),
            "diagnostics": layer_stack.get("diagnostics", {}),
        },
    }


def layer_name(layer: dict[str, Any]) -> str:
    if layer["type"] == "text":
        text = str(layer.get("text", "")).strip()
        return text[:32] if text else layer["id"]
    if layer["type"] == "raster":
        return f"Raster {layer['id']}"
    return f"Shape {layer['id']}"


def write_preview_html(output_path: Path, dsl: dict[str, Any]) -> None:
    page = dsl["page"]
    width = int(page["width"])
    height = int(page["height"])
    background = str(page.get("background") or "#ffffff")
    children = sorted(dsl["root"].get("children", []), key=lambda item: (item.get("z", 0), item["id"]))
    asset_urls = {asset["assetId"]: asset.get("url", "") for asset in dsl.get("assets", [])}

    nodes = "\n".join(render_preview_node(node, asset_urls) for node in children)
    output_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PSD-like Draft Preview</title>
<style>
  html, body {{
    margin: 0;
    padding: 0;
    background: #1f2328;
    font-family: Arial, Helvetica, sans-serif;
  }}
  .page {{
    position: relative;
    width: {width}px;
    height: {height}px;
    margin: 24px auto;
    overflow: hidden;
    background: {html.escape(background)};
    box-shadow: 0 0 0 1px rgba(255,255,255,.12), 0 18px 60px rgba(0,0,0,.35);
  }}
  .node {{
    position: absolute;
    box-sizing: border-box;
  }}
  .shape {{
    pointer-events: none;
  }}
  .raster {{
    object-fit: fill;
    display: block;
  }}
  .text {{
    overflow: hidden;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
  }}
</style>
</head>
<body>
<main class="page" data-width="{width}" data-height="{height}">
{nodes}
</main>
</body>
</html>
""",
        encoding="utf-8",
    )


def render_preview_node(node: dict[str, Any], asset_urls: dict[str, str]) -> str:
    bbox = node["bbox"]
    base_style = (
        f"left:{int(bbox['x'])}px;top:{int(bbox['y'])}px;"
        f"width:{int(bbox['width'])}px;height:{int(bbox['height'])}px;"
        f"z-index:{int(node.get('z', 0))};"
    )
    node_id = html.escape(str(node["id"]))
    title = html.escape(str(node.get("name") or node["id"]))
    node_type = node["type"]

    if node_type == "image":
        asset_id = str(node.get("image", {}).get("assetId", ""))
        src = html.escape(asset_urls.get(asset_id, ""))
        return f'<img class="node raster" data-node-id="{node_id}" title="{title}" src="{src}" style="{base_style}" alt="">'

    if node_type == "shape":
        style = node.get("style", {})
        fill = html.escape(str(style.get("fill") or "transparent"))
        radius = int(style.get("cornerRadius") or style.get("radius") or 0)
        return (
            f'<div class="node shape" data-node-id="{node_id}" title="{title}" '
            f'style="{base_style}background:{fill};border-radius:{radius}px;"></div>'
        )

    if node_type == "text":
        style = node.get("style", {})
        text = html.escape(str(node.get("text", {}).get("characters", "")))
        font_size = int(style.get("fontSize") or max(8, round(float(bbox["height"]) * 0.8)))
        color = html.escape(str(style.get("color") or "#111111"))
        font_weight = int(style.get("fontWeight") or 400)
        line_height = max(font_size, int(bbox["height"]))
        return (
            f'<div class="node text" data-node-id="{node_id}" title="{title}" '
            f'style="{base_style}font-size:{font_size}px;line-height:{line_height}px;'
            f'font-weight:{font_weight};color:{color};">{text}</div>'
        )

    return f'<div class="node" data-node-id="{node_id}" title="{title}" style="{base_style}"></div>'


def write_preview_report(output_path: Path, dsl: dict[str, Any], layer_stack: dict[str, Any]) -> None:
    children = dsl["root"].get("children", [])
    image_nodes = [node for node in children if node.get("type") == "image"]
    text_nodes = [node for node in children if node.get("type") == "text"]
    shape_nodes = [node for node in children if node.get("type") == "shape"]
    asset_ids = {asset["assetId"] for asset in dsl.get("assets", [])}
    missing_image_refs = [
        node["id"]
        for node in image_nodes
        if node.get("image", {}).get("assetId") not in asset_ids
    ]
    diagnostics = layer_stack["diagnostics"]
    lines = [
        "# PSD-like Draft Preview Report",
        "",
        f"- nodes: {len(children)}",
        f"- text nodes: {len(text_nodes)}",
        f"- image nodes: {len(image_nodes)}",
        f"- shape nodes: {len(shape_nodes)}",
        f"- surface shape nodes: {diagnostics.get('surfaceShapeLayerCount', 0)}",
        f"- control surface shape nodes: {diagnostics.get('controlSurfaceShapeLayerCount', 0)}",
        f"- page background: {diagnostics.get('pageBackground', dsl.get('page', {}).get('background', ''))}",
        f"- assets: {len(dsl.get('assets', []))}",
        f"- missing image refs: {len(missing_image_refs)}",
        f"- visible text overlap: {diagnostics['textOverlapRaster']}",
        f"- raw text overlap: {diagnostics['rawTextOverlapRaster']}",
        f"- raster text knockout: {diagnostics['rasterTextKnockoutCount']}",
        f"- full page visible raster: {diagnostics['fullPageVisibleRaster']}",
        f"- tiny raster fragments: {diagnostics['tinyRasterFragments']}",
        "",
    ]
    if missing_image_refs:
        lines.append("## Missing Image Refs")
        lines.extend(f"- `{item}`" for item in missing_image_refs)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_draft_preview_png(output_path: Path, dsl: dict[str, Any], output_dir: Path) -> None:
    page = dsl["page"]
    width = int(page["width"])
    height = int(page["height"])
    image = Image.new("RGBA", (width, height), css_color_to_rgba(str(page.get("background") or "#ffffff")))
    draw = ImageDraw.Draw(image)
    assets = {asset["assetId"]: asset.get("url", "") for asset in dsl.get("assets", [])}

    for node in sorted(dsl["root"].get("children", []), key=lambda item: (item.get("z", 0), item["id"])):
        bbox = node["bbox"]
        box = (
            int(bbox["x"]),
            int(bbox["y"]),
            int(bbox["x"] + bbox["width"]),
            int(bbox["y"] + bbox["height"]),
        )
        if node["type"] == "shape":
            style = node.get("style", {})
            fill = css_color_to_rgba(str(style.get("fill") or "#ffffff"))
            radius = int(style.get("cornerRadius") or style.get("radius") or 0)
            if radius > 0:
                draw.rounded_rectangle(box, radius=radius, fill=fill)
            else:
                draw.rectangle(box, fill=fill)
        elif node["type"] == "image":
            asset_id = str(node.get("image", {}).get("assetId", ""))
            asset_url = assets.get(asset_id, "")
            asset_path = output_dir / asset_url
            if asset_path.exists():
                crop = Image.open(asset_path).convert("RGBA").resize((int(bbox["width"]), int(bbox["height"])))
                image.paste(crop, (int(bbox["x"]), int(bbox["y"])), crop)
        elif node["type"] == "text":
            style = node.get("style", {})
            color = css_color_to_rgba(str(style.get("color") or "#111111"))
            text = str(node.get("text", {}).get("characters", ""))
            font_size = int(style.get("fontSize") or max(8, round(float(bbox["height"]) * 0.8)))
            draw.text((int(bbox["x"]), int(bbox["y"])), text, fill=color, font=load_preview_font(font_size))

    image.convert("RGB").save(output_path)


def css_color_to_rgba(value: str) -> tuple[int, int, int, int]:
    value = value.strip()
    if value.startswith("#") and len(value) in {4, 7}:
        if len(value) == 4:
            r = int(value[1] * 2, 16)
            g = int(value[2] * 2, 16)
            b = int(value[3] * 2, 16)
        else:
            r = int(value[1:3], 16)
            g = int(value[3:5], 16)
            b = int(value[5:7], 16)
        return (r, g, b, 255)
    return (255, 255, 255, 255)


def load_preview_font(size: int) -> ImageFont.ImageFont:
    for path in [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def heatmap_image(values: np.ndarray, width: int, height: int, tile_size: int, color: tuple[int, int, int]) -> Image.Image:
    clipped = np.clip(values, 0.0, 1.0)
    small = (clipped * 255).astype(np.uint8)
    image = Image.fromarray(small, mode="L").resize((width, height), Image.Resampling.NEAREST)
    rgb = Image.new("RGB", (width, height), (0, 0, 0))
    alpha = np.asarray(image).astype(np.float32) / 255.0
    out = np.zeros((height, width, 3), dtype=np.uint8)
    out[:, :, 0] = (alpha * color[0]).astype(np.uint8)
    out[:, :, 1] = (alpha * color[1]).astype(np.uint8)
    out[:, :, 2] = (alpha * color[2]).astype(np.uint8)
    return Image.fromarray(out, mode="RGB")


def draw_overlay(
    image: Image.Image,
    ocr_blocks: list[OCRBlock],
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
    output_path: Path,
) -> None:
    overlay = image.convert("RGBA")
    draw = ImageDraw.Draw(overlay, "RGBA")

    for index, shape in enumerate(shape_candidates, start=1):
        box = shape.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=(40, 180, 90, 255), width=3)
        draw.text((box.x + 2, box.y + 2), f"S{index}", fill=(40, 180, 90, 255))

    for index, raster in enumerate(raster_candidates, start=1):
        box = raster.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=(230, 70, 70, 255), width=3)
        draw.text((box.x + 2, box.y + 2), f"R{index}", fill=(230, 70, 70, 255))

    for block in ocr_blocks:
        box = block.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=(60, 120, 255, 230), width=2)

    overlay.convert("RGB").save(output_path)


def draw_reconstructed_preview(
    image: Image.Image,
    rgb: np.ndarray,
    ocr_blocks: list[OCRBlock],
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
    text_mask: np.ndarray,
    output_path: Path,
) -> None:
    bg = estimate_background_color(rgb)
    preview = Image.new("RGB", image.size, bg)
    draw = ImageDraw.Draw(preview)

    for shape in shape_candidates:
        fill = median_fill(rgb, shape.bbox)
        box = shape.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), fill=fill)

    for raster in raster_candidates:
        crop = image.crop((raster.bbox.x, raster.bbox.y, raster.bbox.x2, raster.bbox.y2)).convert("RGBA")
        crop = inpaint_text_pixels_in_raster(crop, raster, rgb=rgb, ocr_blocks=ocr_blocks, text_mask=text_mask)
        preview.paste(crop, (raster.bbox.x, raster.bbox.y), crop)

    for block in ocr_blocks:
        box = block.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=(20, 80, 220), width=1)
        draw.text((box.x, box.y), block.text[:32], fill=(20, 20, 20))

    preview.save(output_path)


def write_diagnostics(output_path: Path, layer_stack: dict[str, Any]) -> None:
    diagnostics = layer_stack["diagnostics"]
    lines = [
        "# PSD-like Layer Decomposition Diagnostics",
        "",
        f"- source: `{layer_stack['sourceImage']}`",
        f"- ocr: `{layer_stack.get('ocr', '')}`",
        f"- canvas: {layer_stack['canvas']['width']}x{layer_stack['canvas']['height']}",
        f"- layers: {diagnostics['layerCount']}",
        f"- text layers: {diagnostics['textLayerCount']}",
        f"- raster layers: {diagnostics['rasterLayerCount']}",
        f"- shape layers: {diagnostics['shapeLayerCount']}",
        f"- surface shape layers: {diagnostics.get('surfaceShapeLayerCount', 0)}",
        f"- control surface shape layers: {diagnostics.get('controlSurfaceShapeLayerCount', 0)}",
        f"- page background: {diagnostics.get('pageBackground', '')}",
        f"- rejected candidates: {diagnostics['rejectedCandidateCount']}",
        f"- full page visible raster: {diagnostics['fullPageVisibleRaster']}",
        f"- tiny raster fragments: {diagnostics['tinyRasterFragments']}",
        f"- text overlap raster: {diagnostics['textOverlapRaster']}",
        f"- raw text overlap raster: {diagnostics['rawTextOverlapRaster']}",
        f"- raster text knockout: {diagnostics['rasterTextKnockoutCount']}",
        f"- raster covered text blocks: {diagnostics['rasterCoveredTextBlockCount']}",
        f"- missing assets: {diagnostics['missingAssetCount']}",
        "",
        "## Rejection Reasons",
        "",
    ]
    counts: dict[str, int] = {}
    for item in layer_stack.get("rejected", []):
        key = f"{item.get('kind')}:{item.get('reason')}"
        counts[key] = counts.get(key, 0) + 1
    if counts:
        for key, count in sorted(counts.items()):
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- none")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ownership_report(output_path: Path, layer_stack: dict[str, Any]) -> None:
    raster_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "raster"]
    text_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "text"]
    coverage_by_text: dict[str, list[dict[str, Any]]] = {layer["id"]: [] for layer in text_layers}

    for raster in raster_layers:
        ownership = raster.get("ownership", {})
        for block in ownership.get("coveredTextBlocks", []):
            text_id = str(block.get("id", ""))
            if text_id in coverage_by_text:
                coverage_by_text[text_id].append(
                    {
                        "rasterId": raster["id"],
                        "coverage": block.get("coverage", 0),
                    }
                )

    report = {
        "version": "psd_like_ownership_report.v1",
        "diagnostics": {
            "rasterLayerCount": len(raster_layers),
            "textLayerCount": len(text_layers),
            "visibleTextOwnershipConflict": layer_stack["diagnostics"]["textOverlapRaster"],
            "rasterTextKnockoutCount": layer_stack["diagnostics"]["rasterTextKnockoutCount"],
            "rasterCoveredTextBlockCount": layer_stack["diagnostics"]["rasterCoveredTextBlockCount"],
        },
        "rasterOwnership": [
            {
                "id": layer["id"],
                "bbox": layer["bbox"],
                "asset": layer.get("asset", ""),
                "ownership": layer.get("ownership", {}),
            }
            for layer in raster_layers
        ],
        "textCoverage": coverage_by_text,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    image_path = Path(args.image).expanduser().resolve()
    output_dir = Path(args.out).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr_path: Path | None = None
    if args.ocr:
        candidate = Path(args.ocr).expanduser().resolve()
        if candidate.exists():
            ocr_path = candidate
        elif not args.allow_missing_ocr:
            raise FileNotFoundError(f"OCR artifact not found: {candidate}")

    image = Image.open(image_path).convert("RGB")
    rgb = np.asarray(image)
    ocr_blocks = load_ocr_blocks(ocr_path, image.width, image.height, args.ocr_min_confidence)
    text_mask = build_text_mask(image.width, image.height, ocr_blocks, args.text_padding)
    text_knockout_mask = build_text_knockout_mask(rgb, ocr_blocks)
    maps = compute_tile_maps(rgb, text_mask, args.tile_size)

    raster_candidates, raster_rejected = build_raster_candidates(
        maps=maps,
        text_mask=text_mask,
        ocr_blocks=ocr_blocks,
        width=image.width,
        height=image.height,
        tile_size=args.tile_size,
        threshold=args.raster_threshold,
        min_area=args.raster_min_area,
        max_text_overlap=args.max_text_overlap,
    )
    shape_candidates, shape_rejected = build_shape_candidates(
        maps=maps,
        text_mask=text_mask,
        raster_candidates=raster_candidates,
        width=image.width,
        height=image.height,
        tile_size=args.tile_size,
        threshold=args.shape_threshold,
        min_area=args.shape_min_area,
    )
    surface_candidates, surface_rejected = build_surface_candidates(
        maps=maps,
        text_mask=text_mask,
        width=image.width,
        height=image.height,
        tile_size=args.tile_size,
        min_area=args.surface_min_area,
    )
    background_plate_candidates = infer_background_plate_candidates(
        surface_candidates,
        width=image.width,
        height=image.height,
        page_background=estimate_background_color(rgb),
    )
    foreground_candidates, foreground_rejected = build_foreground_object_candidates(
        maps=maps,
        text_mask=text_mask,
        ocr_blocks=ocr_blocks,
        surface_candidates=surface_candidates,
        width=image.width,
        height=image.height,
        tile_size=args.tile_size,
        min_area=args.raster_min_area,
        max_text_overlap=args.max_text_overlap,
    )
    raster_candidates = nms_candidates(raster_candidates + foreground_candidates, overlap_threshold=0.48)
    shape_candidates = merge_surface_and_shape_candidates(background_plate_candidates + surface_candidates, shape_candidates)
    raster_candidates, shape_candidates, promotion_decisions = promote_complex_shape_regions(
        raster_candidates,
        shape_candidates,
    )
    raster_candidates, shape_candidates, control_decisions = promote_control_surfaces(
        raster_candidates,
        shape_candidates,
        ocr_blocks=ocr_blocks,
        text_mask=text_knockout_mask,
        rgb=rgb,
    )
    promotion_decisions.extend(control_decisions)

    ownership = build_raster_ownership(raster_candidates, ocr_blocks, text_knockout_mask)
    asset_refs = crop_raster_assets(
        image,
        raster_candidates,
        output_dir,
        text_mask=text_knockout_mask,
        ocr_blocks=ocr_blocks,
        rgb=rgb,
    )
    thresholds = {
        "tileSize": args.tile_size,
        "rasterThreshold": args.raster_threshold,
        "shapeThreshold": args.shape_threshold,
        "rasterMinArea": args.raster_min_area,
        "shapeMinArea": args.shape_min_area,
        "surfaceMinArea": args.surface_min_area,
        "maxTextOverlap": args.max_text_overlap,
        "ocrMinConfidence": args.ocr_min_confidence,
    }
    layer_stack = build_layer_stack(
        image_path=image_path,
        ocr_path=ocr_path,
        image=image,
        rgb=rgb,
        ocr_blocks=ocr_blocks,
        raster_candidates=raster_candidates,
        shape_candidates=shape_candidates,
        asset_refs=asset_refs,
        ownership=ownership,
        rejected=raster_rejected + shape_rejected + surface_rejected + foreground_rejected + promotion_decisions,
        thresholds=thresholds,
    )

    (output_dir / "layer_stack.v1.json").write_text(
        json.dumps(layer_stack, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    draft_runtime = build_draft_runtime_dsl(layer_stack, rgb)
    (output_dir / "draft_runtime.dsl.v1_0.json").write_text(
        json.dumps(draft_runtime, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_preview_html(output_dir / "preview.html", draft_runtime)
    write_preview_report(output_dir / "preview_report.md", draft_runtime, layer_stack)
    write_draft_preview_png(output_dir / "draft_preview.png", draft_runtime, output_dir)
    heatmap_image(maps["raster"], image.width, image.height, args.tile_size, (255, 80, 80)).save(output_dir / "raster_heatmap.png")
    heatmap_image(maps["shape"], image.width, image.height, args.tile_size, (80, 220, 120)).save(output_dir / "shape_heatmap.png")
    draw_overlay(image, ocr_blocks, raster_candidates, shape_candidates, output_dir / "overlay.png")
    draw_reconstructed_preview(image, rgb, ocr_blocks, raster_candidates, shape_candidates, text_knockout_mask, output_dir / "reconstructed_preview.png")
    write_diagnostics(output_dir / "diagnostics.md", layer_stack)
    write_ownership_report(output_dir / "ownership_report.v1.json", layer_stack)
    return layer_stack


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PSD-like deterministic layer decomposition experiment.")
    parser.add_argument("--image", required=True, help="Source PNG path.")
    parser.add_argument("--ocr", default="", help="OCR artifact path with blocks[].")
    parser.add_argument("--out", required=True, help="Output directory.")
    parser.add_argument("--allow-missing-ocr", action="store_true", help="Run without OCR when the artifact is missing.")
    parser.add_argument("--tile-size", type=int, default=8)
    parser.add_argument("--text-padding", type=int, default=3)
    parser.add_argument("--ocr-min-confidence", type=float, default=0.70)
    parser.add_argument("--raster-threshold", type=float, default=0.42)
    parser.add_argument("--shape-threshold", type=float, default=0.62)
    parser.add_argument("--raster-min-area", type=int, default=512)
    parser.add_argument("--shape-min-area", type=int, default=1200)
    parser.add_argument("--surface-min-area", type=int, default=2400)
    parser.add_argument("--max-text-overlap", type=float, default=0.24)
    return parser.parse_args()


def main() -> None:
    layer_stack = run(parse_args())
    diagnostics = layer_stack["diagnostics"]
    print(
        "PSD-like experiment: "
        f"text={diagnostics['textLayerCount']} "
        f"raster={diagnostics['rasterLayerCount']} "
        f"shape={diagnostics['shapeLayerCount']} "
        f"rejected={diagnostics['rejectedCandidateCount']} "
        f"missing_assets={diagnostics['missingAssetCount']} "
        f"out={Path(layer_stack['sourceImage']).name}"
    )


if __name__ == "__main__":
    main()
