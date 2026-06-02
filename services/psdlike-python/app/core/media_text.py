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


def assign_media_owned_text_blocks(
    raster_candidates: list[Candidate],
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray,
    image_width: int,
    image_height: int,
) -> tuple[set[str], list[dict[str, Any]]]:
    page_area = max(1, image_width * image_height)
    best_by_text: dict[str, tuple[float, Candidate, OCRBlock, float, str]] = {}

    for raster in raster_candidates:
        reason = classify_media_text_owner_candidate(raster, page_area, image_width, image_height, text_mask)
        if not reason:
            continue
        small_media = is_small_embedded_media_candidate(raster)
        coverage_threshold = 0.68 if small_media else 0.72
        covered: list[tuple[OCRBlock, float]] = []
        for block in ocr_blocks:
            if block.bbox.area <= 0:
                continue
            coverage = intersection_area(raster.bbox, block.bbox) / block.bbox.area
            if coverage >= coverage_threshold:
                covered.append((block, coverage))
        if not covered:
            continue
        if len(covered) == 1 and raster.bbox.area < page_area * 0.035 and media_complexity_score(raster) < 0.52 and not small_media:
            continue
        text_area = sum(intersection_area(raster.bbox, block.bbox) for block, _ in covered)
        text_area_ratio = text_area / max(1, raster.bbox.area)
        max_text_area_ratio = 0.45 if small_media else 0.22
        if text_area_ratio > max_text_area_ratio:
            continue

        owner_score = (
            media_complexity_score(raster)
            + min(0.25, raster.bbox.area / page_area)
            + min(0.18, len(covered) * 0.035)
            - min(0.20, text_area_ratio)
        )
        for block, coverage in covered:
            previous = best_by_text.get(block.id)
            score = owner_score + coverage * 0.10
            if previous is None or score > previous[0]:
                best_by_text[block.id] = (score, raster, block, coverage, reason)

    decisions: list[dict[str, Any]] = []
    for text_id, (score, raster, block, coverage, reason) in sorted(best_by_text.items(), key=lambda item: item[0]):
        decisions.append(
            {
                "kind": "media_owned_text",
                "sourceTextBlockId": text_id,
                "sourceTextBBox": block.bbox.to_dict(),
                "ownerRasterId": raster.id,
                "ownerRasterBBox": raster.bbox.to_dict(),
                "reason": reason,
                "coverage": round(float(coverage), 4),
                "ownerScore": round(float(score), 4),
                "rasterReason": raster.reason,
                "rasterAreaRatio": round(float(raster.bbox.area / max(1, page_area)), 4),
                "mediaComplexity": round(float(media_complexity_score(raster)), 4),
                "textMaskRatio": round(float(text_mask_ratio(raster.bbox, text_mask)), 4),
            }
        )
    return set(best_by_text), decisions


def classify_media_text_owner_candidate(
    raster: Candidate,
    page_area: int,
    image_width: int,
    image_height: int,
    text_mask: np.ndarray,
) -> str:
    if raster.bbox.area <= 0:
        return ""
    if is_full_page_backing(raster.bbox, image_width, image_height):
        return ""
    if raster.reason in {"control_foreground_residual"}:
        return ""
    small_media = is_small_embedded_media_candidate(raster)
    if raster.bbox.area < max(18_000, int(page_area * 0.012)) and not small_media:
        return ""
    if (raster.bbox.width < 72 or raster.bbox.height < 56) and not small_media:
        return ""
    if text_mask_ratio(raster.bbox, text_mask) > 0.24:
        return ""

    complexity = media_complexity_score(raster)
    complex_reason = raster.reason in {
        "high_texture_region",
        "high_texture_with_internal_text",
        "high_texture_low_text_overlap",
        "complex_visual_region_promoted_from_shape",
        "foreground_object_on_surface",
    }
    if complexity < 0.42 and not complex_reason and not small_media:
        return ""

    aspect = raster.bbox.width / max(1, raster.bbox.height)
    compact_control_like = raster.bbox.height <= 80 and raster.bbox.width <= 360 and 1.15 <= aspect <= 12.0
    if compact_control_like and complexity < 0.58 and not small_media:
        return ""

    return "complex_media_raster_owns_internal_text"


def is_small_embedded_media_candidate(raster: Candidate) -> bool:
    if raster.reason not in {"foreground_object_on_surface", "high_texture_with_internal_text"}:
        return False
    if raster.bbox.area < 1_600 or raster.bbox.area > 38_000:
        return False
    if raster.bbox.width < 32 or raster.bbox.height < 32:
        return False
    aspect = raster.bbox.width / max(1, raster.bbox.height)
    if aspect < 0.35 or aspect > 2.10:
        return False
    return media_complexity_score(raster) >= 0.54


def media_complexity_score(raster: Candidate) -> float:
    texture = float(raster.scores.get("texture", 0.0))
    edge = float(raster.scores.get("edge", 0.0))
    entropy = float(raster.scores.get("entropy", 0.0))
    unique = float(raster.scores.get("unique", 0.0))
    promoted = 0.18 if raster.reason == "complex_visual_region_promoted_from_shape" else 0.0
    foreground = 0.08 if raster.reason == "foreground_object_on_surface" else 0.0
    return max(texture, edge * 1.15, entropy * 0.80, unique * 0.70) + promoted + foreground


def classify_text_owned_raster_fragment(
    raster: Candidate,
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray,
) -> tuple[str, OCRBlock | None]:
    if not text_mask.size or raster.bbox.area <= 0:
        return "", None
    if raster.reason not in {"foreground_object_on_surface", "high_texture_with_internal_text", "high_texture_low_text_overlap"}:
        return "", None
    longest_side = max(raster.bbox.width, raster.bbox.height)
    shortest_side = min(raster.bbox.width, raster.bbox.height)
    if raster.bbox.area > 4096 or longest_side > 160:
        return "", None

    mask_ratio = text_mask_ratio(raster.bbox, text_mask)
    score_overlap = float(raster.scores.get("textOverlap", 0.0))
    score_overlap = max(score_overlap, text_mask_score_for_box(raster.bbox, text_mask))
    thin_fragment = shortest_side <= 10 and longest_side <= 160 and score_overlap >= 0.24
    compact_text_chip = raster.bbox.area <= 2304 and mask_ratio >= 0.26
    if not thin_fragment and not compact_text_chip and score_overlap < 0.34:
        return "", None

    owner = best_text_owner(raster.bbox, ocr_blocks)
    if owner is None:
        return "", None
    owner_coverage = intersection_area(raster.bbox, owner.bbox) / max(1, owner.bbox.area)
    raster_coverage = ioa(raster.bbox, owner.bbox)
    if thin_fragment and (raster_coverage >= 0.25 or owner_coverage >= 0.20):
        return "text_owned_thin_fragment", owner
    if compact_text_chip and (raster_coverage >= 0.35 or owner_coverage >= 0.22):
        return "text_owned_compact_fragment", owner
    if score_overlap >= 0.45 and raster_coverage >= 0.28:
        return "text_owned_high_overlap_fragment", owner
    return "", None


def best_text_owner(box: BBox, ocr_blocks: list[OCRBlock]) -> OCRBlock | None:
    best: tuple[float, OCRBlock] | None = None
    for block in ocr_blocks:
        overlap = intersection_area(box, block.bbox)
        if overlap <= 0:
            continue
        score = max(overlap / max(1, box.area), overlap / max(1, block.bbox.area))
        if best is None or score > best[0]:
            best = (score, block)
    return best[1] if best is not None else None
