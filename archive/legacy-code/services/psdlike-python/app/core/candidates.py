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

from .schema import BBox, Candidate, OCRBlock, intersection_area, ioa, iou

# Mechanical migration from PSD-like V1 oracle. Keep behavior changes out of this stage.


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


def split_vertical_media_stack_rasters(
    rgb: np.ndarray,
    raster_candidates: list[Candidate],
    text_mask: np.ndarray,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    split_parents: set[str] = set()
    split_children: list[Candidate] = []
    parent_decisions: list[dict[str, Any]] = []
    for raster in raster_candidates:
        children = vertical_media_stack_children(rgb, raster, text_mask)
        if len(children) < 2:
            continue
        split_parents.add(raster.id)
        split_children.extend(children)
        parent_decisions.append(
            {
                "kind": "vertical_media_stack_parent_suppressed",
                "id": raster.id,
                "bbox": raster.bbox.to_dict(),
                "reason": "vertical_media_stack_split",
                "childCount": len(children),
                "childBBoxes": [child.bbox.to_dict() for child in children],
            }
        )
    if not split_children:
        return raster_candidates, []

    next_candidates: list[Candidate] = []
    for raster in raster_candidates:
        if raster.id in split_parents:
            continue
        if vertical_children_cover_raster(raster.bbox, split_children):
            parent_decisions.append(
                {
                    "kind": "vertical_media_stack_child_duplicate_suppressed",
                    "id": raster.id,
                    "bbox": raster.bbox.to_dict(),
                    "reason": "covered_by_vertical_media_stack_item",
                }
            )
            continue
        next_candidates.append(raster)
    next_candidates.extend(split_children)
    return nms_candidates(next_candidates, overlap_threshold=0.52), parent_decisions


def vertical_children_cover_raster(box: BBox, children: list[Candidate]) -> bool:
    if box.area <= 0:
        return False
    overlap_area = sum(intersection_area(box, child.bbox) for child in children)
    return overlap_area / box.area >= 0.86


def vertical_media_stack_children(rgb: np.ndarray, raster: Candidate, text_mask: np.ndarray) -> list[Candidate]:
    if raster.reason not in {"foreground_object_on_surface", "high_texture_low_text_overlap", "high_texture_with_internal_text"}:
        return []
    box = raster.bbox
    if box.width < 72 or box.height < 180:
        return []
    if box.height / max(1, box.width) < 2.35:
        return []
    if box.area < 24_000:
        return []
    if raster.scores.get("textOverlap", 0.0) > 0.12:
        return []
    crop = rgb[box.y : box.y2, box.x : box.x2]
    if crop.shape[0] != box.height or crop.shape[1] != box.width or crop.size == 0:
        return []
    local_text = text_mask[box.y : box.y2, box.x : box.x2]
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)

    visual_rows = vertical_media_visual_rows(crop, local_text)
    spans = vertical_media_spans_from_gutters(crop, local_text, visual_rows, min_height=max(56, int(box.width * 0.48)))
    if len(spans) < 2:
        return []
    accepted: list[tuple[int, int, dict[str, float]]] = []
    for start, end in spans:
        child_box = tighten_media_child_box(crop, local_text, box, start, end)
        if child_box is None:
            continue
        scores = media_child_scores(rgb, text_mask, child_box)
        if not accept_vertical_media_child(child_box, box, scores):
            continue
        accepted.append((child_box.y - box.y, child_box.y2 - box.y, scores))
    if len(accepted) < 2:
        return []
    coverage = sum(end - start for start, end, _scores in accepted) / max(1, box.height)
    if coverage < 0.36:
        return []
    x_centers = [tighten_media_child_box(crop, local_text, box, start, end) for start, end, _scores in accepted]
    if any(child is None for child in x_centers):
        return []
    child_boxes = [child for child in x_centers if child is not None]
    median_width = float(np.median([child.width for child in child_boxes]))
    if median_width < box.width * 0.58:
        return []
    if max(abs(child.width - median_width) for child in child_boxes) > max(32, median_width * 0.34):
        return []

    children: list[Candidate] = []
    for index, child_box in enumerate(child_boxes, start=1):
        scores = media_child_scores(rgb, text_mask, child_box)
        scores.update(
            {
                "verticalMediaStackItem": 1.0,
                "parentAreaRatio": round(child_box.area / max(1, box.area), 4),
                "parentRasterKey": float(abs(hash(raster.id)) % 1_000_000),
            }
        )
        children.append(
            Candidate(
                id=f"{raster.id}_vsplit_{index:02d}",
                kind="raster",
                bbox=child_box,
                score=max(raster.score, float(scores.get("raster", 0.0)), 0.62),
                scores=scores,
                reason="vertical_media_stack_item",
            )
        )
    return children


def vertical_media_visual_rows(crop: np.ndarray, local_text: np.ndarray) -> np.ndarray:
    arr = crop.astype(np.float32)
    height, width = arr.shape[:2]
    if height <= 0 or width <= 0:
        return np.zeros(height, dtype=bool)
    row_texture = np.zeros(height, dtype=np.float32)
    row_edge = np.zeros(height, dtype=np.float32)
    if width > 1:
        row_texture = np.mean(np.abs(np.diff(arr, axis=1)), axis=(1, 2)) / 255.0
    if height > 1:
        edge_values = np.mean(np.abs(np.diff(arr, axis=0)), axis=(1, 2)) / 255.0
        row_edge[:-1] = np.maximum(row_edge[:-1], edge_values)
        row_edge[1:] = np.maximum(row_edge[1:], edge_values)
    row_text = np.mean(local_text.astype(np.float32), axis=1) if local_text.size else np.zeros(height, dtype=np.float32)
    row_score = row_texture * 0.68 + row_edge * 0.32
    threshold = max(0.030, float(np.percentile(row_score, 54)) * 0.78)
    visual = (row_score >= threshold) & (row_text <= 0.34)
    visual = close_boolean_runs(visual, max_gap=max(3, width // 40))
    return visual


def media_row_spans(rows: np.ndarray, width: int, min_height: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(rows.tolist() + [False]):
        if value and start is None:
            start = index
        if not value and start is not None:
            end = index
            if end - start >= min_height:
                spans.append((start, end))
            start = None
    return spans


def vertical_media_spans_from_gutters(
    crop: np.ndarray,
    local_text: np.ndarray,
    visual_rows: np.ndarray,
    min_height: int,
) -> list[tuple[int, int]]:
    height, width = crop.shape[:2]
    if height <= 0:
        return []
    arr = crop.astype(np.float32)
    row_texture = np.zeros(height, dtype=np.float32)
    if width > 1:
        row_texture = np.mean(np.abs(np.diff(arr, axis=1)), axis=(1, 2)) / 255.0
    row_std = np.mean(np.std(arr, axis=1), axis=1) / 255.0
    row_luma = np.mean(arr, axis=(1, 2)) / 255.0
    row_text = np.mean(local_text.astype(np.float32), axis=1) if local_text.size else np.zeros(height, dtype=np.float32)
    low_threshold = max(0.018, float(np.percentile(row_texture, 28)) * 1.10)
    std_threshold = max(0.018, float(np.percentile(row_std, 8)) * 1.80)
    light_threshold = max(0.82, float(np.percentile(row_luma, 84)))
    gutter_rows = (
        (row_texture <= low_threshold)
        & (row_std <= std_threshold)
        & (row_luma >= light_threshold)
        & (row_text <= 0.08)
        & ~visual_rows
    )
    gutter_runs: list[tuple[int, int]] = []
    start: int | None = None
    min_gutter = max(8, min(14, width // 18))
    for index, value in enumerate(gutter_rows.tolist() + [False]):
        if value and start is None:
            start = index
        if not value and start is not None:
            if index - start >= min_gutter:
                gutter_runs.append((start, index))
            start = None
    boundaries = [0]
    for start, end in gutter_runs:
        mid = (start + end) // 2
        if mid - boundaries[-1] >= max(12, min_height // 3):
            boundaries.append(mid)
    if height - boundaries[-1] >= max(12, min_height // 3):
        boundaries.append(height)
    spans: list[tuple[int, int]] = []
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        if end - start < min_height:
            continue
        visual_ratio = float(np.mean(visual_rows[start:end])) if end > start else 0.0
        segment = crop[start:end]
        unique_ratio = sampled_unique_ratio(segment)
        if visual_ratio < 0.045 and unique_ratio < 0.42:
            continue
        spans.append((start, end))
    if len(spans) >= 2:
        return spans
    return media_row_spans(visual_rows, width, min_height)


def merge_close_media_spans(spans: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    if not spans:
        return []
    merged = [spans[0]]
    for start, end in spans[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= max_gap:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def close_boolean_runs(values: np.ndarray, max_gap: int) -> np.ndarray:
    if values.size == 0 or max_gap <= 0:
        return values
    result = values.copy()
    false_start: int | None = None
    for index, value in enumerate(values.tolist() + [True]):
        if not value and false_start is None:
            false_start = index
        if value and false_start is not None:
            if index - false_start <= max_gap:
                result[false_start:index] = True
            false_start = None
    return result


def tighten_media_child_box(crop: np.ndarray, local_text: np.ndarray, parent: BBox, start: int, end: int) -> BBox | None:
    segment = crop[start:end]
    if segment.size == 0:
        return None
    x1, x2 = 0, parent.width
    y1 = parent.y + max(0, start)
    y2 = parent.y + min(parent.height, end)
    if y2 - y1 < 24:
        return None
    return BBox(parent.x + x1, y1, x2 - x1, y2 - y1)


def media_child_scores(rgb: np.ndarray, text_mask: np.ndarray, box: BBox) -> dict[str, float]:
    crop = rgb[box.y : box.y2, box.x : box.x2]
    if crop.size == 0:
        return {"texture": 0.0, "edge": 0.0, "textOverlap": 0.0, "raster": 0.0}
    arr = crop.astype(np.float32)
    texture = float(np.mean(np.abs(np.diff(arr, axis=1))) / 255.0) if box.width > 1 else 0.0
    edge = float(np.mean(np.abs(np.diff(arr, axis=0))) / 255.0) if box.height > 1 else 0.0
    unique = float(len(np.unique(crop.reshape(-1, 3)[:: max(1, crop.reshape(-1, 3).shape[0] // 512)], axis=0)) / 512.0)
    local_text = text_mask[box.y : box.y2, box.x : box.x2]
    text_overlap = float(np.mean(local_text)) if local_text.shape == crop.shape[:2] and local_text.size else 0.0
    raster = min(1.0, texture * 0.55 + edge * 0.45 + unique * 0.12)
    return {
        "texture": round(texture, 4),
        "edge": round(edge, 4),
        "unique": round(unique, 4),
        "textOverlap": round(text_overlap, 4),
        "raster": round(raster, 4),
    }


def accept_vertical_media_child(child: BBox, parent: BBox, scores: dict[str, float]) -> bool:
    if child.area < 5_000:
        return False
    if child.width < parent.width * 0.52:
        return False
    if child.height < max(48, parent.width * 0.38):
        return False
    if child.height > parent.height * 0.72:
        return False
    if scores.get("textOverlap", 0.0) > 0.18:
        return False
    if scores.get("texture", 0.0) < 0.018 and scores.get("edge", 0.0) < 0.018 and scores.get("unique", 0.0) < 0.42:
        return False
    return True


def sampled_unique_ratio(crop: np.ndarray) -> float:
    if crop.size == 0:
        return 0.0
    pixels = crop.reshape(-1, 3)
    sample = pixels[:: max(1, pixels.shape[0] // 512)]
    return float(min(1.0, len(np.unique(sample, axis=0)) / 512.0))


def promote_complex_shape_regions(
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
) -> tuple[list[Candidate], list[Candidate], list[dict[str, Any]]]:
    promoted: list[Candidate] = []
    remaining_shapes: list[Candidate] = []
    consumed_raster_ids: set[str] = set()
    decisions: list[dict[str, Any]] = []

    for shape in shape_candidates:
        if shape.reason in {"background_surface_band", "ocr_anchored_control_surface", "editable_control_surface_from_raster"}:
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
