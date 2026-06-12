#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tools.psd_like_layer_decomposition_experiment import (
    BBox,
    Candidate,
    OCRBlock,
    binary_close,
    binary_dilate,
    build_raster_candidates,
    build_raster_ownership,
    build_draft_runtime_dsl,
    build_text_mask,
    build_text_knockout_mask,
    clamp,
    clamp_box,
    color_distance,
    color_hex,
    compute_tile_maps,
    component_bbox,
    connected_components,
    count_text_blocks,
    crop_raster_assets,
    dominant_cluster_stats,
    draw_overlay,
    estimate_background_color,
    intersection_area,
    ioa,
    iou,
    load_ocr_blocks,
    nms_candidates,
    relative_luminance,
    sample_text_color,
    write_draft_preview_png,
    write_ownership_report,
    write_preview_html,
    write_preview_report,
)


@dataclass(frozen=True)
class VectorSurfaceCandidate:
    id: str
    bbox: BBox
    fill: tuple[int, int, int]
    corner_radius: int
    confidence: float
    contained_text_ids: list[str]
    reason: str
    scores: dict[str, float]


@dataclass(frozen=True)
class RasterFallbackCandidate:
    id: str
    bbox: BBox
    score: float
    reason: str
    scores: dict[str, float]


def candidate_from_surface(surface: VectorSurfaceCandidate, index: int) -> Candidate:
    role = str(surface.scores.get("role", ""))
    scores = dict(surface.scores)
    scores.update(
        {
            "fillR": float(surface.fill[0]),
            "fillG": float(surface.fill[1]),
            "fillB": float(surface.fill[2]),
            "cornerRadius": float(surface.corner_radius),
            "vectorSurface": 1.0,
            "confidence": float(surface.confidence),
            "containedTextIds": list(surface.contained_text_ids),
            **({"role": role} if role else {}),
        }
    )
    return Candidate(
        id=f"vector_surface_{index:04d}_{surface.id}",
        kind="shape",
        bbox=surface.bbox,
        score=surface.confidence,
        scores=scores,
        reason="vector_surface",
    )


def contained_text_blocks(box: BBox, blocks: list[OCRBlock], min_coverage: float = 0.82) -> list[OCRBlock]:
    contained: list[OCRBlock] = []
    for block in blocks:
        if block.bbox.area <= 0:
            continue
        if intersection_area(box, block.bbox) / block.bbox.area >= min_coverage:
            contained.append(block)
    return contained


def text_union(blocks: list[OCRBlock]) -> BBox | None:
    if not blocks:
        return None
    x1 = min(block.bbox.x for block in blocks)
    y1 = min(block.bbox.y for block in blocks)
    x2 = max(block.bbox.x2 for block in blocks)
    y2 = max(block.bbox.y2 for block in blocks)
    return BBox(x1, y1, x2 - x1, y2 - y1)


def stable_fill_stats(rgb: np.ndarray, box: BBox, text_mask: np.ndarray) -> tuple[np.ndarray, float, float, float]:
    crop = rgb[box.y : box.y2, box.x : box.x2]
    if crop.size == 0:
        return np.array([255, 255, 255], dtype=np.uint8), 0.0, 0.0, 1.0
    local_text = text_mask[box.y : box.y2, box.x : box.x2]
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)
    pixels = crop[~local_text]
    if pixels.shape[0] < max(16, crop.shape[0] * crop.shape[1] // 8):
        pixels = crop.reshape(-1, 3)
    fill, bucket_coverage = dominant_cluster_stats(pixels.astype(np.uint8), bucket_size=20)
    distances = np.linalg.norm(pixels.astype(np.float32) - fill.reshape(1, 3).astype(np.float32), axis=1)
    close_coverage = float((distances <= 64.0).mean()) if distances.size else 0.0
    texture = float(np.sqrt(np.mean(np.var(pixels.astype(np.float32), axis=0)))) if pixels.size else 255.0
    return fill, bucket_coverage, close_coverage, texture


def text_contrast(rgb: np.ndarray, blocks: list[OCRBlock], fill: np.ndarray) -> float:
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


def infer_corner_radius(rgb: np.ndarray, box: BBox, fill: np.ndarray) -> int:
    max_radius = max(0, min(box.width, box.height) // 2 - 1)
    if max_radius <= 0:
        return 0
    crop = rgb[box.y : box.y2, box.x : box.x2].astype(np.float32)
    if crop.size == 0:
        return 0
    close = np.linalg.norm(crop - fill.reshape(1, 1, 3).astype(np.float32), axis=2) <= 64.0
    runs: list[int] = []
    for corner in ("tl", "tr", "bl", "br"):
        run = corner_background_run(close, corner, max_radius)
        if run > 0:
            runs.append(run)
    if not runs:
        return 0
    return max(0, min(max_radius, int(round(float(np.median(runs)) * 3.4))))


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


def is_full_page_backing(box: BBox, width: int, height: int) -> bool:
    page_area = width * height
    if page_area <= 0:
        return False
    return box.area / page_area >= 0.62 or (box.width >= width * 0.94 and box.height >= height * 0.70)


def is_vector_surface_physical_match(
    box: BBox,
    blocks: list[OCRBlock],
    fill: np.ndarray,
    bucket_coverage: float,
    close_coverage: float,
    texture: float,
    contrast: float,
    width: int,
    height: int,
) -> bool:
    if not blocks or len(blocks) > 6:
        return False
    if box.area < 480 or is_full_page_backing(box, width, height):
        return False
    if box.width < 24 or box.height < 14:
        return False
    area_ratio = box.area / max(1, width * height)
    if area_ratio > 0.35:
        return False
    if bucket_coverage < 0.24 and close_coverage < 0.52:
        return False
    if texture > 88.0 and close_coverage < 0.70:
        return False
    if contrast < 38.0:
        return False
    text_box = text_union(blocks)
    if text_box is None:
        return False
    if text_box.area / max(1, box.area) > 0.62:
        return False
    left_pad = text_box.x - box.x
    right_pad = box.x2 - text_box.x2
    top_pad = text_box.y - box.y
    bottom_pad = box.y2 - text_box.y2
    if min(left_pad, right_pad, top_pad, bottom_pad) < -1:
        return False
    if left_pad + right_pad < max(6, int(box.width * 0.08)):
        return False
    if top_pad + bottom_pad < max(4, int(box.height * 0.08)):
        return False
    if relative_luminance(fill) < 20 and close_coverage < 0.72:
        return False
    return True


def expanded_box(box: BBox, width: int, height: int, x_pad: int, y_pad: int) -> BBox | None:
    return clamp_box(
        BBox(box.x - x_pad, box.y - y_pad, box.width + x_pad * 2, box.height + y_pad * 2),
        width,
        height,
    )


def estimate_surface_fill_near_text(rgb: np.ndarray, text_mask: np.ndarray, block: OCRBlock) -> tuple[np.ndarray, float]:
    height, width, _ = rgb.shape
    outer_pad_x = max(8, min(80, int(round(block.bbox.width * 0.55))))
    outer_pad_y = max(6, min(48, int(round(block.bbox.height * 1.35))))
    outer = expanded_box(block.bbox, width, height, outer_pad_x, outer_pad_y)
    inner = expanded_box(block.bbox, width, height, 1, 1)
    if outer is None:
        return np.array([255, 255, 255], dtype=np.uint8), 0.0

    crop = rgb[outer.y : outer.y2, outer.x : outer.x2]
    local_text = text_mask[outer.y : outer.y2, outer.x : outer.x2].copy()
    if inner is not None:
        local_text[
            max(0, inner.y - outer.y) : max(0, inner.y2 - outer.y),
            max(0, inner.x - outer.x) : max(0, inner.x2 - outer.x),
        ] = True

    pixels = crop[~local_text]
    if pixels.shape[0] < 16:
        pixels = crop.reshape(-1, 3)
    return dominant_cluster_stats(pixels.astype(np.uint8), bucket_size=20)


def candidate_window_for_block(box: BBox, width: int, height: int) -> BBox | None:
    x_pad = max(32, min(220, int(round(box.width * 2.2))))
    y_pad = max(22, min(150, int(round(box.height * 4.2))))
    return expanded_box(box, width, height, x_pad, y_pad)


def component_touching_seed(
    mask: np.ndarray,
    seed_box: BBox,
    origin_x: int,
    origin_y: int,
) -> list[tuple[int, int]] | None:
    local_seed = BBox(seed_box.x - origin_x, seed_box.y - origin_y, seed_box.width, seed_box.height)
    seed_mask = np.zeros_like(mask, dtype=bool)
    x1 = max(0, local_seed.x)
    y1 = max(0, local_seed.y)
    x2 = min(mask.shape[1], local_seed.x2)
    y2 = min(mask.shape[0], local_seed.y2)
    if x2 <= x1 or y2 <= y1:
        return None
    seed_mask[y1:y2, x1:x2] = True

    best: list[tuple[int, int]] | None = None
    best_overlap = 0
    for component in connected_components(mask):
        overlap = sum(1 for row, col in component if seed_mask[row, col])
        if overlap > best_overlap:
            best = component
            best_overlap = overlap
    return best if best_overlap > 0 else None


def extract_surface_from_text_seed(
    rgb: np.ndarray,
    text_mask: np.ndarray,
    block: OCRBlock,
    page_background: tuple[int, int, int],
) -> tuple[BBox, np.ndarray, dict[str, float]] | None:
    height, width, _ = rgb.shape
    window = candidate_window_for_block(block.bbox, width, height)
    if window is None:
        return None

    fill, seed_coverage = estimate_surface_fill_near_text(rgb, text_mask, block)
    page_distance = color_distance(fill, page_background)
    crop = rgb[window.y : window.y2, window.x : window.x2]
    local_text = text_mask[window.y : window.y2, window.x : window.x2]
    if crop.size == 0:
        return None

    distances = np.linalg.norm(crop.astype(np.float32) - fill.reshape(1, 1, 3).astype(np.float32), axis=2)
    close_threshold = 58.0 if page_distance >= 20.0 else 42.0
    close = distances <= close_threshold
    if local_text.shape == close.shape:
        close |= local_text
    close = binary_close(close, iterations=2)

    component = component_touching_seed(close, block.bbox, window.x, window.y)
    if component is None:
        return None
    local_box = component_bbox(component, 1, window.width, window.height)
    global_box = clamp_box(BBox(window.x + local_box.x, window.y + local_box.y, local_box.width, local_box.height), width, height)
    if global_box is None:
        return None

    return (
        global_box,
        fill,
        {
            "seedFillCoverage": round(float(seed_coverage), 4),
            "seedPageDistance": round(float(page_distance), 4),
            "seedCloseThreshold": round(float(close_threshold), 4),
        },
    )


def extract_vector_surfaces(
    rgb: np.ndarray,
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray,
    min_area: int = 480,
) -> list[VectorSurfaceCandidate]:
    height, width, _ = rgb.shape
    page_background = estimate_background_color(rgb)
    candidates: list[VectorSurfaceCandidate] = []

    for index, block in enumerate(ocr_blocks, start=1):
        extracted = extract_surface_from_text_seed(rgb, text_mask, block, page_background)
        if extracted is None:
            continue
        box, seed_fill, seed_scores = extracted
        if box.area < min_area:
            continue
        blocks = contained_text_blocks(box, ocr_blocks)
        fill, bucket_coverage, close_coverage, texture = stable_fill_stats(rgb, box, text_mask)
        contrast = text_contrast(rgb, blocks, fill)
        if not is_vector_surface_physical_match(box, blocks, fill, bucket_coverage, close_coverage, texture, contrast, width, height):
            continue
        radius = infer_corner_radius(rgb, box, fill)
        confidence = clamp(0.35 + close_coverage * 0.30 + bucket_coverage * 0.20 + min(1.0, contrast / 160.0) * 0.15)
        seed_distance = color_distance(seed_fill, fill)
        candidates.append(
            VectorSurfaceCandidate(
                id=f"surface_{index:04d}",
                bbox=box,
                fill=(int(fill[0]), int(fill[1]), int(fill[2])),
                corner_radius=radius,
                confidence=round(confidence, 4),
                contained_text_ids=[block.id for block in blocks],
                reason="vector_surface_contains_ocr",
                scores={
                    **seed_scores,
                    "seedToFinalFillDistance": round(float(seed_distance), 4),
                    "bucketCoverage": round(float(bucket_coverage), 4),
                    "closeCoverage": round(float(close_coverage), 4),
                    "texture": round(float(texture), 4),
                    "textContrast": round(float(contrast), 4),
                },
            )
        )

    return dedupe_vector_surfaces(candidates)


def dedupe_vector_surfaces(candidates: list[VectorSurfaceCandidate]) -> list[VectorSurfaceCandidate]:
    accepted: list[VectorSurfaceCandidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.confidence, item.bbox.area), reverse=True):
        duplicate = False
        for kept in accepted:
            if intersection_area(candidate.bbox, kept.bbox) / max(1, min(candidate.bbox.area, kept.bbox.area)) >= 0.82:
                duplicate = True
                break
        if not duplicate:
            accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def surface_to_dict(surface: VectorSurfaceCandidate) -> dict[str, Any]:
    return {
        "id": surface.id,
        "bbox": surface.bbox.to_dict(),
        "fill": color_hex(np.array(surface.fill, dtype=np.uint8)),
        "cornerRadius": surface.corner_radius,
        "confidence": surface.confidence,
        "containedTextIds": surface.contained_text_ids,
        "reason": surface.reason,
        "scores": surface.scores,
    }


def write_surface_overlay(
    image: Image.Image,
    surfaces: list[VectorSurfaceCandidate],
    ocr_blocks: list[OCRBlock],
    output_path: Path,
) -> None:
    overlay = image.convert("RGBA")
    draw = ImageDraw.Draw(overlay, "RGBA")
    for index, surface in enumerate(surfaces, start=1):
        box = surface.bbox
        draw.rounded_rectangle(
            (box.x, box.y, box.x2, box.y2),
            radius=max(0, surface.corner_radius),
            outline=(40, 180, 90, 255),
            width=3,
        )
        draw.text((box.x + 2, box.y + 2), f"V{index}", fill=(40, 180, 90, 255))
    for block in ocr_blocks:
        box = block.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=(60, 120, 255, 220), width=2)
    overlay.convert("RGB").save(output_path)


def write_surface_diagnostics(path: Path, surfaces: list[VectorSurfaceCandidate], image: Image.Image, ocr_blocks: list[OCRBlock]) -> None:
    lines = [
        "# PSD-like v2 Vector Surface Diagnostics",
        "",
        f"- canvas: {image.width}x{image.height}",
        f"- OCR blocks: {len(ocr_blocks)}",
        f"- vector surfaces: {len(surfaces)}",
        "",
        "| id | bbox | fill | radius | confidence | text ids | reason |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for surface in surfaces:
        box = surface.bbox
        lines.append(
            f"|{surface.id}|{box.x},{box.y},{box.width},{box.height}|{color_hex(np.array(surface.fill, dtype=np.uint8))}|"
            f"{surface.corner_radius}|{surface.confidence}|{','.join(surface.contained_text_ids)}|{surface.reason}|"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def vector_surface_role(surface: VectorSurfaceCandidate, width: int, height: int) -> str:
    area_ratio = surface.bbox.area / max(1, width * height)
    aspect = surface.bbox.width / max(1, surface.bbox.height)
    text_count = len(surface.contained_text_ids)
    if text_count <= 2 and area_ratio <= 0.20 and 1.05 <= aspect <= 14.0:
        return "control_surface"
    return "container_surface"


def select_vector_surfaces(surfaces: list[VectorSurfaceCandidate], width: int, height: int) -> list[VectorSurfaceCandidate]:
    accepted: list[VectorSurfaceCandidate] = []

    def sort_key(surface: VectorSurfaceCandidate) -> tuple[int, float, int]:
        role_rank = 1 if vector_surface_role(surface, width, height) == "control_surface" else 0
        return (role_rank, surface.confidence, -surface.bbox.area)

    for surface in sorted(surfaces, key=sort_key, reverse=True):
        text_ids = set(surface.contained_text_ids)
        keep = True
        for kept in accepted:
            overlap = intersection_area(surface.bbox, kept.bbox)
            if overlap <= 0:
                continue
            min_overlap = overlap / max(1, min(surface.bbox.area, kept.bbox.area))
            fill_distance = color_distance(surface.fill, kept.fill)
            shared_text = text_ids & set(kept.contained_text_ids)
            if min_overlap >= 0.82 and fill_distance <= 18.0:
                keep = False
                break
            if shared_text and min_overlap >= 0.45 and surface.bbox.area >= kept.bbox.area:
                keep = False
                break
        if keep:
            scores = dict(surface.scores)
            scores["role"] = vector_surface_role(surface, width, height)
            accepted.append(
                VectorSurfaceCandidate(
                    id=surface.id,
                    bbox=surface.bbox,
                    fill=surface.fill,
                    corner_radius=surface.corner_radius,
                    confidence=surface.confidence,
                    contained_text_ids=surface.contained_text_ids,
                    reason=surface.reason,
                    scores=scores,
                )
            )

    return sorted(accepted, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def filter_raster_fallbacks(
    raster_candidates: list[Candidate],
    vector_shapes: list[Candidate],
    text_mask: np.ndarray,
    width: int,
    height: int,
    max_text_overlap: float,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    accepted: list[Candidate] = []
    rejected: list[dict[str, Any]] = []
    control_shapes = [shape for shape in vector_shapes if shape.scores.get("role") == "control_surface"]

    for raster in raster_candidates:
        reason = ""
        if is_full_page_backing(raster.bbox, width, height):
            reason = "full_page_backing"
        elif raster_text_overlap(raster.bbox, text_mask) > max_text_overlap:
            reason = "text_overlap"
        else:
            for shape in control_shapes:
                control_overlap = intersection_area(raster.bbox, shape.bbox)
                control_min_overlap = control_overlap / max(1, min(raster.bbox.area, shape.bbox.area))
                control_edge_distance = raster_edge_distance(raster.bbox, shape.bbox)
                if ioa(raster.bbox, shape.bbox) >= 0.18:
                    reason = "vector_control_owned_background"
                    break
                if control_min_overlap >= 0.18 and control_edge_distance <= max(8, min(shape.bbox.width, shape.bbox.height) // 6):
                    reason = "vector_control_edge_residual"
                    break
                if is_surface_edge_residual(raster.bbox, shape.bbox):
                    reason = "vector_control_edge_residual"
                    break
        if not reason:
            for shape in vector_shapes:
                overlap = intersection_area(raster.bbox, shape.bbox)
                if overlap <= 0:
                    continue
                min_overlap = overlap / max(1, min(raster.bbox.area, shape.bbox.area))
                close_to_shape_edge = raster_edge_distance(raster.bbox, shape.bbox) <= max(6, min(shape.bbox.width, shape.bbox.height) // 8)
                if ioa(raster.bbox, shape.bbox) >= 0.86 and raster.bbox.area <= shape.bbox.area * 1.20:
                    reason = "duplicate_vector_surface"
                    break
                if min_overlap >= 0.22 and close_to_shape_edge:
                    reason = "vector_surface_edge_residual"
                    break
                if is_surface_edge_residual(raster.bbox, shape.bbox):
                    reason = "vector_surface_edge_residual"
                    break
        if reason:
            rejected.append(
                {
                    "kind": "raster_fallback",
                    "bbox": raster.bbox.to_dict(),
                    "reason": reason,
                    "scores": raster.scores,
                }
            )
            continue
        accepted.append(raster)

    return nms_candidates(accepted, overlap_threshold=0.50), rejected


def raster_edge_distance(box: BBox, owner: BBox) -> int:
    return min(
        abs(box.x - owner.x),
        abs(box.y - owner.y),
        abs(box.x2 - owner.x2),
        abs(box.y2 - owner.y2),
    )


def is_surface_edge_residual(box: BBox, owner: BBox) -> bool:
    thin_limit = max(8, min(owner.width, owner.height) // 5)
    if min(box.width, box.height) > thin_limit:
        return False
    edge_limit = max(8, min(owner.width, owner.height) // 5)
    if raster_edge_distance(box, owner) > edge_limit:
        return False
    x_overlap = max(0, min(box.x2, owner.x2) - max(box.x, owner.x))
    y_overlap = max(0, min(box.y2, owner.y2) - max(box.y, owner.y))
    horizontal_projection = x_overlap / max(1, min(box.width, owner.width))
    vertical_projection = y_overlap / max(1, min(box.height, owner.height))
    return horizontal_projection >= 0.35 or vertical_projection >= 0.35


def raster_text_overlap(box: BBox, text_mask: np.ndarray) -> float:
    if box.area <= 0 or not text_mask.size:
        return 0.0
    region = text_mask[box.y : box.y2, box.x : box.x2]
    return float(region.mean()) if region.size else 0.0


def crop_v2_raster_assets(image: Image.Image, candidates: list[Candidate], output_dir: Path) -> dict[str, str]:
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    asset_refs: dict[str, str] = {}
    for index, candidate in enumerate(candidates, start=1):
        layer_id = f"raster_{index:04d}"
        filename = f"{layer_id}.png"
        crop = image.crop((candidate.bbox.x, candidate.bbox.y, candidate.bbox.x2, candidate.bbox.y2)).convert("RGBA")
        crop.save(assets_dir / filename)
        asset_refs[candidate.id] = f"assets/{filename}"
    return asset_refs


def build_v2_layer_stack(
    image_path: Path,
    ocr_path: Path | None,
    image: Image.Image,
    rgb: np.ndarray,
    ocr_blocks: list[OCRBlock],
    surfaces: list[VectorSurfaceCandidate],
    raster_candidates: list[Candidate],
    asset_refs: dict[str, str],
    ownership: dict[str, dict[str, Any]],
    rejected: list[dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    layers: list[dict[str, Any]] = []
    vector_shapes = [candidate_from_surface(surface, index) for index, surface in enumerate(surfaces, start=1)]

    for index, shape in enumerate(vector_shapes, start=1):
        radius = int(shape.scores.get("cornerRadius", 0))
        role = str(shape.scores.get("role", ""))
        layers.append(
            {
                "id": f"shape_{index:04d}",
                "type": "shape",
                "bbox": shape.bbox.to_dict(),
                "z": (1200 if role == "container_surface" else 1600) + index,
                "style": {
                    "fill": color_hex(
                        np.array(
                            [
                                shape.scores.get("fillR", 255.0),
                                shape.scores.get("fillG", 255.0),
                                shape.scores.get("fillB", 255.0),
                            ],
                            dtype=np.uint8,
                        )
                    ),
                    **({"cornerRadius": radius} if radius > 0 else {}),
                },
                "scores": shape.scores,
                "reason": shape.reason,
                "sourceIds": [shape.id, *[str(item) for item in shape.scores.get("containedTextIds", [])]],
            }
        )

    for index, raster in enumerate(raster_candidates, start=1):
        layers.append(
            {
                "id": f"raster_{index:04d}",
                "type": "raster",
                "bbox": raster.bbox.to_dict(),
                "z": 2200 + index,
                "asset": asset_refs.get(raster.id, ""),
                "scores": raster.scores,
                "ownership": ownership.get(raster.id, {}),
                "reason": raster.reason,
                "sourceIds": [raster.id],
            }
        )

    for index, block in enumerate(ocr_blocks, start=1):
        layers.append(
            {
                "id": block.id or f"text_{index:04d}",
                "type": "text",
                "bbox": block.bbox.to_dict(),
                "z": 3200 + index,
                "text": block.text,
                "confidence": round(block.confidence, 4),
                "reason": "ocr_authority",
                "sourceIds": [block.id],
            }
        )

    page_area = image.width * image.height
    raw_text_overlap_raster = sum(
        1 for item in raster_candidates if item.scores.get("textOverlap", 0.0) > thresholds["maxTextOverlap"]
    )
    raster_text_knockout = sum(1 for item in raster_candidates if ownership.get(item.id, {}).get("textKnockout"))
    covered_text_blocks = sum(int(ownership.get(item.id, {}).get("coveredTextBlockCount", 0)) for item in raster_candidates)
    missing_assets = sum(1 for item in raster_candidates if not asset_refs.get(item.id))
    page_background = color_hex(estimate_background_color(rgb))

    return {
        "version": "layer_stack.v2",
        "sourceImage": str(image_path),
        "ocr": str(ocr_path) if ocr_path else "",
        "canvas": {"width": image.width, "height": image.height},
        "pageBackground": page_background,
        "layers": sorted(layers, key=lambda item: item["z"]),
        "diagnostics": {
            "layerCount": len(layers),
            "textLayerCount": len(ocr_blocks),
            "rasterLayerCount": len(raster_candidates),
            "shapeLayerCount": len(vector_shapes),
            "surfaceShapeLayerCount": len(vector_shapes),
            "vectorSurfaceShapeLayerCount": len(vector_shapes),
            "controlSurfaceShapeLayerCount": sum(1 for item in vector_shapes if item.scores.get("role") == "control_surface"),
            "containerSurfaceShapeLayerCount": sum(1 for item in vector_shapes if item.scores.get("role") == "container_surface"),
            "pageBackground": page_background,
            "rejectedCandidateCount": len(rejected),
            "fullPageVisibleRaster": sum(1 for item in raster_candidates if is_full_page_backing(item.bbox, image.width, image.height)),
            "tinyRasterFragments": sum(1 for item in raster_candidates if item.bbox.area < 400),
            "textOverlapRaster": sum(1 for item in raster_candidates if ownership.get(item.id, {}).get("visibleTextOwnershipConflict")),
            "rawTextOverlapRaster": raw_text_overlap_raster,
            "rasterTextKnockoutCount": raster_text_knockout,
            "rasterCoveredTextBlockCount": covered_text_blocks,
            "missingAssetCount": missing_assets,
            "pageArea": page_area,
        },
        "thresholds": thresholds,
        "rejected": rejected[:300],
    }


def build_v2_draft_runtime_dsl(layer_stack: dict[str, Any], rgb: np.ndarray) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []

    for layer in sorted(layer_stack["layers"], key=lambda item: (item["z"], item["bbox"]["y"], item["bbox"]["x"], item["id"])):
        bbox = layer["bbox"]
        layer_type = layer["type"]
        node: dict[str, Any] = {
            "id": layer["id"],
            "type": "image" if layer_type == "raster" else layer_type,
            "name": v2_layer_name(layer),
            "bbox": bbox,
            "z": layer["z"],
            "meta": {
                "source": "psd_like_v2_vector_surface",
                "reason": layer.get("reason", ""),
                "sourceIds": layer.get("sourceIds", []),
                "role": layer.get("scores", {}).get("role", ""),
                "confidence": layer.get("scores", {}).get("confidence", layer.get("confidence", 1.0)),
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
            node["meta"]["containedTextIds"] = layer.get("scores", {}).get("containedTextIds", [])
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
    return {
        "version": "1.0",
        "kind": "draft_runtime",
        "taskId": "psd_like_v2_experiment",
        "page": {
            "name": "PSD-like v2 Draft Experiment",
            "width": canvas["width"],
            "height": canvas["height"],
            "background": str(layer_stack.get("pageBackground") or color_hex(estimate_background_color(rgb))),
        },
        "root": {
            "id": "root",
            "type": "frame",
            "name": "PSD-like v2 Draft",
            "bbox": {"x": 0, "y": 0, "width": canvas["width"], "height": canvas["height"]},
            "children": children,
        },
        "assets": assets,
        "meta": {
            "pipeline": "psd_like_v2_vector_surface_experiment",
            "sourceImage": layer_stack.get("sourceImage", ""),
            "diagnostics": layer_stack.get("diagnostics", {}),
        },
    }


def v2_layer_name(layer: dict[str, Any]) -> str:
    if layer["type"] == "text":
        text = str(layer.get("text", "")).strip()
        return text[:32] if text else layer["id"]
    if layer["type"] == "raster":
        return f"Raster {layer['id']}"
    role = str(layer.get("scores", {}).get("role", "surface"))
    return f"Vector {role} {layer['id']}"


def write_v2_ownership_report(path: Path, layer_stack: dict[str, Any]) -> None:
    raster_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "raster"]
    shape_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "shape"]
    report = {
        "version": "psd_like_v2_ownership_report.v1",
        "diagnostics": layer_stack["diagnostics"],
        "vectorShapes": [
            {
                "id": layer["id"],
                "bbox": layer["bbox"],
                "role": layer.get("scores", {}).get("role", ""),
                "containedTextIds": layer.get("scores", {}).get("containedTextIds", []),
                "reason": layer.get("reason", ""),
            }
            for layer in shape_layers
        ],
        "rasterOwnership": [
            {
                "id": layer["id"],
                "bbox": layer["bbox"],
                "asset": layer.get("asset", ""),
                "ownership": layer.get("ownership", {}),
                "reason": layer.get("reason", ""),
            }
            for layer in raster_layers
        ],
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    surfaces = extract_vector_surfaces(rgb, ocr_blocks, text_mask, min_area=args.vector_min_area)
    accepted_surfaces = select_vector_surfaces(surfaces, image.width, image.height)
    vector_shapes = [candidate_from_surface(surface, index) for index, surface in enumerate(accepted_surfaces, start=1)]

    maps = compute_tile_maps(rgb, text_mask, args.tile_size)
    raw_raster_candidates, raster_rejected = build_raster_candidates(
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
    raster_candidates, ownership_rejected = filter_raster_fallbacks(
        raw_raster_candidates,
        vector_shapes,
        text_knockout_mask,
        image.width,
        image.height,
        args.max_text_overlap,
    )
    ownership = build_raster_ownership(raster_candidates, ocr_blocks, text_knockout_mask)
    asset_refs = crop_v2_raster_assets(image, raster_candidates, output_dir)
    thresholds = {
        "tileSize": args.tile_size,
        "rasterThreshold": args.raster_threshold,
        "rasterMinArea": args.raster_min_area,
        "vectorMinArea": args.vector_min_area,
        "maxTextOverlap": args.max_text_overlap,
        "ocrMinConfidence": args.ocr_min_confidence,
    }
    layer_stack = build_v2_layer_stack(
        image_path=image_path,
        ocr_path=ocr_path,
        image=image,
        rgb=rgb,
        ocr_blocks=ocr_blocks,
        surfaces=accepted_surfaces,
        raster_candidates=raster_candidates,
        asset_refs=asset_refs,
        ownership=ownership,
        rejected=raster_rejected + ownership_rejected,
        thresholds=thresholds,
    )
    draft_runtime = build_v2_draft_runtime_dsl(layer_stack, rgb)

    artifact = {
        "version": "vector_surfaces.v1",
        "sourceImage": str(image_path),
        "ocr": str(ocr_path) if ocr_path else "",
        "canvas": {"width": image.width, "height": image.height},
        "surfaces": [surface_to_dict(surface) for surface in surfaces],
        "acceptedSurfaceIds": [surface.id for surface in accepted_surfaces],
    }
    (output_dir / "vector_surfaces.v1.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_surface_overlay(image, surfaces, ocr_blocks, output_dir / "surface_overlay.png")
    write_surface_diagnostics(output_dir / "surface_diagnostics.md", surfaces, image, ocr_blocks)
    (output_dir / "layer_stack.v2.json").write_text(json.dumps(layer_stack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "draft_runtime.v2.dsl.v1_0.json").write_text(
        json.dumps(draft_runtime, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_preview_html(output_dir / "preview.v2.html", draft_runtime)
    write_preview_report(output_dir / "preview_report.v2.md", draft_runtime, layer_stack)
    write_draft_preview_png(output_dir / "draft_preview.v2.png", draft_runtime, output_dir)
    draw_overlay(image, ocr_blocks, raster_candidates, vector_shapes, output_dir / "overlay.v2.png")
    write_v2_ownership_report(output_dir / "ownership_report.v2.json", layer_stack)
    return layer_stack


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PSD-like v2 vector surface extraction experiment.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--ocr", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--allow-missing-ocr", action="store_true")
    parser.add_argument("--text-padding", type=int, default=3)
    parser.add_argument("--ocr-min-confidence", type=float, default=0.70)
    parser.add_argument("--vector-min-area", type=int, default=480)
    parser.add_argument("--tile-size", type=int, default=8)
    parser.add_argument("--raster-threshold", type=float, default=0.42)
    parser.add_argument("--raster-min-area", type=int, default=512)
    parser.add_argument("--max-text-overlap", type=float, default=0.04)
    return parser.parse_args()


def main() -> None:
    layer_stack = run(parse_args())
    diagnostics = layer_stack["diagnostics"]
    print(
        "PSD-like v2 vector surface: "
        f"text={diagnostics['textLayerCount']} "
        f"shape={diagnostics['shapeLayerCount']} "
        f"raster={diagnostics['rasterLayerCount']} "
        f"rejected={diagnostics['rejectedCandidateCount']} "
        f"out={Path(layer_stack.get('sourceImage', '')).name}"
    )


if __name__ == "__main__":
    main()
