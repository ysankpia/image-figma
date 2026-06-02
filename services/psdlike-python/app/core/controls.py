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


def detect_ocr_anchored_control_surfaces(
    rgb: np.ndarray,
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    height, width, _ = rgb.shape
    page_area = width * height
    candidates: list[Candidate] = []
    rejected: list[dict[str, Any]] = []

    for index, block in enumerate(ocr_blocks, start=1):
        if block.bbox.area <= 0 or block.bbox.width < 4 or block.bbox.height < 6:
            continue
        best: tuple[float, Candidate] | None = None
        for box in control_surface_search_boxes(block.bbox, width, height):
            candidate = Candidate(
                id=f"ocr_control_{index:04d}",
                kind="shape",
                bbox=box,
                score=0.78,
                scores={},
                reason="ocr_anchored_control_surface",
            )
            accepted, scores, reason = score_ocr_anchored_control_surface(
                rgb=rgb,
                candidate=candidate,
                block=block,
                text_mask=text_mask,
                page_area=page_area,
            )
            if not accepted:
                if reason in {"high_texture", "missing_outer_ring", "not_enough_padding"}:
                    rejected.append(
                        {
                            "kind": "ocr_control_surface",
                            "id": candidate.id,
                            "bbox": box.to_dict(),
                            "reason": reason,
                            "sourceTextBlockId": block.id,
                        }
                    )
                continue
            scored = Candidate(
                id=candidate.id,
                kind="shape",
                bbox=box,
                score=float(scores["score"]),
                scores=scores,
                reason="ocr_anchored_control_surface",
            )
            rank = float(scores["score"]) - (box.area / max(1, page_area)) * 0.20
            if best is None or rank > best[0] or (rank == best[0] and box.area < best[1].bbox.area):
                best = (rank, scored)
        if best is not None:
            candidates.append(best[1])

    return merge_control_surfaces(candidates), rejected[:80]


def control_surface_search_boxes(text_box: BBox, width: int, height: int) -> list[BBox]:
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
    pad_y_values = sorted(
        {
            max(4, round(text_box.height * 0.35)),
            max(4, round(text_box.height * 0.45)),
            max(5, round(text_box.height * 0.55)),
            max(6, round(text_box.height * 0.85)),
        }
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
    text_mask: np.ndarray,
    page_area: int,
) -> tuple[bool, dict[str, float], str]:
    box = candidate.bbox
    if block.bbox.area <= 0 or box.area <= 0:
        return False, {}, "empty"
    text_containment = intersection_area(box, block.bbox) / block.bbox.area
    if text_containment < 0.90:
        return False, {}, "text_not_contained"
    area_ratio = box.area / block.bbox.area
    if area_ratio < 1.18 or area_ratio > 12.0:
        return False, {}, "bad_area_ratio"
    if box.area > max(12_000, page_area * 0.08) or box.width < 24 or box.height < 14:
        return False, {}, "bad_size"
    aspect = box.width / max(1, box.height)
    if aspect < 1.10 or aspect > 14.0:
        return False, {}, "bad_aspect"
    if box.height > max(96, block.bbox.height * 5):
        return False, {}, "too_tall"

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

    ring_min_delta, ring_support_delta = control_surface_outer_ring_delta(rgb, box, fill)
    if ring_min_delta is None or ring_support_delta is None:
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
    if ring_support_delta < ring_threshold:
        return False, {}, "weak_outer_boundary"

    text_contrast = control_text_contrast(rgb, [block], fill)
    if text_contrast < 34.0:
        return False, {}, "low_text_contrast"

    score = (
        0.42
        + min(0.22, close_coverage * 0.18)
        + min(0.16, ring_support_delta / 260.0)
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
        "outerRingDelta": round(float(ring_min_delta), 4),
        "outerRingSupportDelta": round(float(ring_support_delta), 4),
        "outerRingThreshold": round(float(ring_threshold), 4),
        "textContrast": round(float(text_contrast), 4),
        "fillLuminance": round(float(fill_luminance), 4),
        "darkControlSurface": 1.0 if dark_surface else 0.0,
        "texture": round(float(texture / 255.0), 4),
        "entropy": round(float(entropy), 4),
        "edge": round(float(edge_density), 4),
        "fillR": float(fill[0]),
        "fillG": float(fill[1]),
        "fillB": float(fill[2]),
    }
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
    height, width, _ = rgb.shape
    pad = max(2, min(5, box.height // 8))
    if box.x - pad < 0 or box.y - pad < 0 or box.x2 + pad > width or box.y2 + pad > height:
        return None, None
    strips = [
        rgb[box.y - pad : box.y, box.x : box.x2],
        rgb[box.y2 : box.y2 + pad, box.x : box.x2],
        rgb[box.y : box.y2, box.x - pad : box.x],
        rgb[box.y : box.y2, box.x2 : box.x2 + pad],
    ]
    deltas: list[float] = []
    for strip in strips:
        if strip.size == 0:
            return None, None
        color = dominant_cluster_color(strip.reshape(-1, 3).astype(np.uint8), bucket_size=24)
        deltas.append(color_distance(color, fill))
    sorted_deltas = sorted(deltas)
    return float(sorted_deltas[0]), float(sorted_deltas[1])


def merge_control_surfaces(candidates: list[Candidate]) -> list[Candidate]:
    accepted: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda item: (-item.score, item.bbox.area, item.bbox.y, item.bbox.x)):
        if any(iou(candidate.bbox, kept.bbox) >= 0.66 or ioa(candidate.bbox, kept.bbox) >= 0.92 for kept in accepted):
            continue
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
        if item.reason in {"ocr_anchored_control_surface", "editable_control_surface_from_raster", "model_assisted_control_surface"}
    ]


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
