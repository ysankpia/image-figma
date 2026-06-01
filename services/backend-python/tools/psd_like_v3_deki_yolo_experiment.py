#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
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
    bbox_scores,
    build_draft_runtime_dsl,
    build_foreground_object_candidates,
    build_layer_stack,
    build_raster_candidates,
    build_raster_ownership,
    build_shape_candidates,
    build_surface_candidates,
    build_text_knockout_mask,
    build_text_mask,
    clamp_box,
    compute_tile_maps,
    contained_text_blocks,
    control_surface_fill,
    control_text_contrast,
    crop_raster_assets,
    draw_overlay,
    draw_reconstructed_preview,
    estimate_background_color,
    heatmap_image,
    infer_control_corner_radius,
    infer_background_plate_candidates,
    intersection_area,
    iou,
    ioa,
    is_full_page_backing,
    load_ocr_blocks,
    merge_surface_and_shape_candidates,
    nms_candidates,
    promote_complex_shape_regions,
    promote_control_surfaces,
    write_draft_preview_png,
    write_preview_html,
    write_preview_report,
)


KNOWN_DEKI_CLASSES = {"View", "ImageView", "Text", "Line"}


@dataclass(frozen=True)
class DekiYoloCandidate:
    id: str
    class_id: int
    class_name: str
    bbox: BBox
    confidence: float


def load_deki_yolo_candidates(path: Path | None, width: int, height: int) -> tuple[list[DekiYoloCandidate], list[dict[str, Any]], dict[str, Any]]:
    if path is None:
        return [], [], {
            "version": "deki_yolo_candidates.v1",
            "modelPath": "",
            "sourceImage": "",
            "canvas": {"width": width, "height": height},
            "candidates": [],
        }

    data = json.loads(path.read_text(encoding="utf-8"))
    candidates: list[DekiYoloCandidate] = []
    diagnostics: list[dict[str, Any]] = []
    raw_candidates = data.get("candidates", [])
    if data.get("version") != "deki_yolo_candidates.v1":
        diagnostics.append({"kind": "deki_yolo", "reason": "unexpected_version", "version": data.get("version", "")})

    for index, item in enumerate(raw_candidates, start=1):
        class_name = str(item.get("className", "")).strip()
        class_id = int(item.get("classId", -1))
        if class_name not in KNOWN_DEKI_CLASSES:
            diagnostics.append(
                {
                    "kind": "deki_yolo",
                    "reason": "unknown_class",
                    "id": item.get("id") or f"yolo_{index:04d}",
                    "classId": class_id,
                    "className": class_name,
                }
            )
            continue
        raw_box = item.get("bbox", {})
        box = BBox(
            int(round(float(raw_box.get("x", 0)))),
            int(round(float(raw_box.get("y", 0)))),
            int(round(float(raw_box.get("width", 0)))),
            int(round(float(raw_box.get("height", 0)))),
        )
        clamped = clamp_box(box, width, height)
        if clamped is None:
            diagnostics.append(
                {
                    "kind": "deki_yolo",
                    "reason": "invalid_bbox",
                    "id": item.get("id") or f"yolo_{index:04d}",
                    "bbox": box.to_dict(),
                }
            )
            continue
        candidates.append(
            DekiYoloCandidate(
                id=str(item.get("id") or f"yolo_{index:04d}"),
                class_id=class_id,
                class_name=class_name,
                bbox=clamped,
                confidence=float(item.get("confidence", 0.0)),
            )
        )
    return candidates, diagnostics, data


def deki_imageview_to_raster_candidates(
    yolo_candidates: list[DekiYoloCandidate],
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    ocr_blocks: list[OCRBlock],
    width: int,
    height: int,
    tile_size: int,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    candidates: list[Candidate] = []
    rejected: list[dict[str, Any]] = []
    page_area = width * height

    for index, item in enumerate(yolo_candidates, start=1):
        if item.class_name != "ImageView":
            continue
        box = item.bbox
        scores = bbox_scores(box, maps, text_mask, tile_size)
        scores.update({"dekiConfidence": round(item.confidence, 4), "dekiClassId": float(item.class_id)})

        reason = reject_deki_imageview(box, scores, ocr_blocks, width, height, page_area, item.confidence)
        if reason:
            rejected.append(
                {
                    "kind": "deki_yolo_imageview",
                    "id": item.id,
                    "bbox": box.to_dict(),
                    "reason": reason,
                    "confidence": round(item.confidence, 4),
                    "scores": scores,
                }
            )
            continue
        candidates.append(
            Candidate(
                id=f"deki_raster_{index:04d}_{item.id}",
                kind="raster",
                bbox=box,
                score=max(0.58, min(0.96, item.confidence)),
                scores=scores,
                reason="deki_yolo_imageview",
            )
        )
    return candidates, rejected


def reject_deki_imageview(
    box: BBox,
    scores: dict[str, float],
    ocr_blocks: list[OCRBlock],
    width: int,
    height: int,
    page_area: int,
    confidence: float,
) -> str:
    if confidence < 0.58:
        return "low_confidence"
    if box.area < 360 or box.width < 12 or box.height < 12:
        return "too_small"
    if is_full_page_backing(box, width, height):
        return "full_page_backing"
    if page_area > 0 and box.area / page_area > 0.28:
        return "too_large_for_imageview"
    text_overlap = sum(intersection_area(box, block.bbox) for block in ocr_blocks)
    if text_overlap / max(1, box.area) > 0.14:
        return "covers_ocr_text"
    covered_blocks = sum(1 for block in ocr_blocks if block.bbox.area > 0 and intersection_area(box, block.bbox) / block.bbox.area >= 0.45)
    if covered_blocks >= 2:
        return "contains_multiple_ocr_blocks"
    if scores.get("textOverlap", 0.0) > 0.22:
        return "text_overlap_score"
    aspect = box.width / max(1, box.height)
    if aspect > 8.0 or aspect < 0.12:
        return "line_like_imageview"
    if scores.get("texture", 0.0) < 0.04 and scores.get("edge", 0.0) < 0.04 and scores.get("dominant", 0.0) > 0.92:
        return "flat_background_fragment"
    return ""


def merge_deki_rasters(v1_rasters: list[Candidate], deki_rasters: list[Candidate]) -> tuple[list[Candidate], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    for deki in deki_rasters:
        decisions.append(
            {
                "dekiId": deki.id,
                "kind": "deki_raster_diagnostic_only",
                "dekiBbox": deki.bbox.to_dict(),
                "reason": "imageview_not_allowed_to_expand_or_replace_v1_raster_in_v3_p0",
            }
        )
    return v1_rasters, decisions


def choose_better_raster_bbox(v1: Candidate, deki: Candidate) -> Candidate:
    if deki.score >= v1.score + 0.08:
        return deki
    if deki.bbox.area < v1.bbox.area * 0.55 and deki.score >= 0.62:
        return deki
    return v1


def deki_view_to_shape_candidates(
    yolo_candidates: list[DekiYoloCandidate],
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    ocr_blocks: list[OCRBlock],
    rgb: np.ndarray,
    width: int,
    height: int,
    tile_size: int,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    page_area = width * height
    candidates: list[Candidate] = []
    rejected: list[dict[str, Any]] = []

    for index, item in enumerate(yolo_candidates, start=1):
        if item.class_name != "View":
            continue
        box = item.bbox
        base_candidate = Candidate(
            id=f"deki_view_{index:04d}_{item.id}",
            kind="shape",
            bbox=box,
            score=max(0.58, min(0.96, item.confidence)),
            scores=bbox_scores(box, maps, text_mask, tile_size),
            reason="deki_yolo_view_shape",
        )
        blocks = contained_text_blocks(base_candidate, ocr_blocks)
        fill, fill_coverage, close_coverage = control_surface_fill(rgb, base_candidate, text_mask)
        text_contrast = control_text_contrast(rgb, blocks, fill)
        rejection = reject_deki_view_shape(
            candidate=base_candidate,
            blocks=blocks,
            fill_coverage=fill_coverage,
            close_coverage=close_coverage,
            text_contrast=text_contrast,
            page_area=page_area,
            width=width,
            height=height,
            confidence=item.confidence,
        )
        scores = dict(base_candidate.scores)
        scores.update(
            {
                "controlSurface": 1.0,
                "dekiConfidence": round(item.confidence, 4),
                "dekiClassId": float(item.class_id),
                "fillCoverage": round(float(fill_coverage), 4),
                "closeFillCoverage": round(float(close_coverage), 4),
                "textContrast": round(float(text_contrast), 4),
                "fillR": float(fill[0]),
                "fillG": float(fill[1]),
                "fillB": float(fill[2]),
            }
        )
        if rejection:
            rejected.append(
                {
                    "kind": "deki_yolo_view",
                    "id": item.id,
                    "bbox": box.to_dict(),
                    "reason": rejection,
                    "confidence": round(item.confidence, 4),
                    "containedTextBlockIds": [block.id for block in blocks],
                    "scores": scores,
                }
            )
            continue
        candidates.append(
            Candidate(
                id=base_candidate.id,
                kind="shape",
                bbox=box,
                score=max(base_candidate.score, 0.76),
                scores=scores,
                reason="deki_yolo_view_control_surface",
            )
        )
    return nms_deki_view_shapes(candidates), rejected


def reject_deki_view_shape(
    candidate: Candidate,
    blocks: list[OCRBlock],
    fill_coverage: float,
    close_coverage: float,
    text_contrast: float,
    page_area: int,
    width: int,
    height: int,
    confidence: float,
) -> str:
    if confidence < 0.35:
        return "low_confidence"
    if is_full_page_backing(candidate.bbox, width, height):
        return "full_page_backing"
    if candidate.bbox.area > page_area * 0.22:
        return "too_large_for_control_shape"
    if candidate.bbox.width > width * 0.72 and candidate.bbox.height > 56:
        return "wide_bar_not_p0_control"
    if not is_deki_editable_control_surface(candidate, blocks, fill_coverage, close_coverage, text_contrast):
        return "not_editable_control_surface"
    return ""


def is_deki_editable_control_surface(
    candidate: Candidate,
    blocks: list[OCRBlock],
    fill_coverage: float,
    close_coverage: float,
    text_contrast: float,
) -> bool:
    if not blocks or len(blocks) > 2:
        return False
    if candidate.bbox.area < 480:
        return False
    if candidate.bbox.width < 24 or candidate.bbox.height < 14:
        return False
    if candidate.bbox.height > 96:
        return False
    aspect = candidate.bbox.width / max(1, candidate.bbox.height)
    if aspect < 1.05 or aspect > 12.0:
        return False
    if candidate.scores.get("texture", 1.0) > 0.88:
        return False
    if candidate.scores.get("entropy", 1.0) > 0.66:
        return False
    if fill_coverage < 0.30 and candidate.scores.get("dominant", 0.0) < 0.38:
        return False
    if close_coverage < 0.91:
        return False

    union_x1 = min(block.bbox.x for block in blocks)
    union_y1 = min(block.bbox.y for block in blocks)
    union_x2 = max(block.bbox.x2 for block in blocks)
    union_y2 = max(block.bbox.y2 for block in blocks)
    text_box = BBox(union_x1, union_y1, union_x2 - union_x1, union_y2 - union_y1)
    if text_box.area <= 0:
        return False
    if text_box.area / max(1, candidate.bbox.area) > 0.58:
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
    return text_contrast >= 38.0


def nms_deki_view_shapes(candidates: list[Candidate]) -> list[Candidate]:
    accepted: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.score, -item.bbox.area), reverse=True):
        if any(iou(candidate.bbox, kept.bbox) >= 0.72 or contained_overlap(candidate.bbox, kept.bbox) >= 0.86 for kept in accepted):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda item: (item.bbox.y, item.bbox.x, item.id))


def contained_overlap(a: BBox, b: BBox) -> float:
    return intersection_area(a, b) / max(1, min(a.area, b.area))


def filter_deki_shapes_by_problem_raster(
    deki_shapes: list[Candidate],
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
    raster_ownership: dict[str, dict[str, Any]],
    rgb: np.ndarray,
    text_mask: np.ndarray,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    accepted: list[Candidate] = []
    decisions: list[dict[str, Any]] = []
    for shape in deki_shapes:
        mean_delta, p90_delta = vector_surface_error(rgb, shape, text_mask)
        scores = dict(shape.scores)
        scores.update(
            {
                "vectorSurfaceMeanDelta": round(float(mean_delta), 4),
                "vectorSurfaceP90Delta": round(float(p90_delta), 4),
            }
        )
        shape = Candidate(shape.id, shape.kind, shape.bbox, shape.score, scores, shape.reason)

        duplicate = duplicate_existing_shape(shape, shape_candidates)
        if duplicate:
            decisions.append(
                {
                    "kind": "deki_view_shape_rejected",
                    "shapeId": shape.id,
                    "bbox": shape.bbox.to_dict(),
                    "reason": "duplicate_existing_shape",
                    "existingShapeId": duplicate.id,
                    "existingBbox": duplicate.bbox.to_dict(),
                }
            )
            continue
        if mean_delta > 36.0 or p90_delta > 82.0:
            decisions.append(
                {
                    "kind": "deki_view_shape_rejected",
                    "shapeId": shape.id,
                    "bbox": shape.bbox.to_dict(),
                    "reason": "vector_surface_error_too_high",
                    "vectorSurfaceMeanDelta": round(float(mean_delta), 4),
                    "vectorSurfaceP90Delta": round(float(p90_delta), 4),
                }
            )
            continue

        blockers: list[Candidate] = []
        owned_rasters: list[Candidate] = []
        for raster in raster_candidates:
            shape_coverage = intersection_area(shape.bbox, raster.bbox) / max(1, shape.bbox.area)
            if shape_coverage <= 0.10:
                continue
            if raster_can_yield_to_deki_shape(raster, shape, raster_ownership.get(raster.id, {})):
                owned_rasters.append(raster)
                continue
            blockers.append(raster)

        if not owned_rasters:
            decisions.append(
                {
                    "kind": "deki_view_shape_rejected",
                    "shapeId": shape.id,
                    "bbox": shape.bbox.to_dict(),
                    "reason": "no_text_knockout_raster_to_replace",
                    "vectorSurfaceMeanDelta": round(float(mean_delta), 4),
                    "vectorSurfaceP90Delta": round(float(p90_delta), 4),
                }
            )
            continue

        if blockers:
            decisions.append(
                {
                    "kind": "deki_view_shape_rejected",
                    "shapeId": shape.id,
                    "bbox": shape.bbox.to_dict(),
                    "reason": "covered_by_noneditable_raster",
                    "blockingRasterIds": [item.id for item in blockers[:8]],
                    "blockingRasterCount": len(blockers),
                    "vectorSurfaceMeanDelta": round(float(mean_delta), 4),
                    "vectorSurfaceP90Delta": round(float(p90_delta), 4),
                }
            )
            continue

        decisions.append(
            {
                "kind": "deki_view_shape_accepted",
                "shapeId": shape.id,
                "shapeBbox": shape.bbox.to_dict(),
                "ownedRasterIds": [item.id for item in owned_rasters],
                "reason": "local_vector_surface_gate_passed",
                "vectorSurfaceMeanDelta": round(float(mean_delta), 4),
                "vectorSurfaceP90Delta": round(float(p90_delta), 4),
            }
        )
        accepted.append(shape)
    return accepted, decisions


def vector_surface_error(rgb: np.ndarray, shape: Candidate, text_mask: np.ndarray) -> tuple[float, float]:
    box = shape.bbox
    crop = rgb[box.y : box.y2, box.x : box.x2]
    if crop.size == 0:
        return 999.0, 999.0
    local_text = text_mask[box.y : box.y2, box.x : box.x2]
    if local_text.shape != crop.shape[:2]:
        local_text = np.zeros(crop.shape[:2], dtype=bool)
    pixels = crop[~local_text]
    if pixels.shape[0] < max(16, box.area // 10):
        pixels = crop.reshape(-1, 3)
    fill = np.array(
        [
            shape.scores.get("fillR", 255.0),
            shape.scores.get("fillG", 255.0),
            shape.scores.get("fillB", 255.0),
        ],
        dtype=np.float32,
    )
    deltas = np.mean(np.abs(pixels.astype(np.float32) - fill.reshape(1, 3)), axis=1)
    if deltas.size == 0:
        return 999.0, 999.0
    return float(np.mean(deltas)), float(np.percentile(deltas, 90))


def duplicate_existing_shape(shape: Candidate, shape_candidates: list[Candidate]) -> Candidate | None:
    for existing in shape_candidates:
        if existing.bbox.area <= 0:
            continue
        area_ratio = shape.bbox.area / max(1, existing.bbox.area)
        comparable_area = 0.62 <= area_ratio <= 1.62
        if comparable_area and (iou(shape.bbox, existing.bbox) >= 0.72 or contained_overlap(shape.bbox, existing.bbox) >= 0.90):
            return existing
    return None


def raster_can_yield_to_deki_shape(raster: Candidate, shape: Candidate, ownership: dict[str, Any]) -> bool:
    if not ownership.get("textKnockout"):
        return False
    if same_region_for_deki_shape_replacement(raster.bbox, shape.bbox):
        return True
    if int(ownership.get("coveredTextBlockCount", 0)) > 2:
        return False
    if ioa(shape.bbox, raster.bbox) < 0.96:
        return False
    if shape.bbox.area / max(1, raster.bbox.area) > 0.46:
        return False
    return True


def same_region_for_deki_shape_replacement(raster: BBox, shape: BBox) -> bool:
    if raster.area <= 0 or shape.area <= 0:
        return False
    area_ratio = raster.area / max(1, shape.area)
    if area_ratio < 0.55 or area_ratio > 1.85:
        return False
    if iou(raster, shape) >= 0.54:
        return True
    return contained_overlap(raster, shape) >= 0.86


def apply_deki_view_ownership(
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
    deki_shapes: list[Candidate],
    raster_ownership: dict[str, dict[str, Any]],
) -> tuple[list[Candidate], list[Candidate], list[dict[str, Any]]]:
    if not deki_shapes:
        return raster_candidates, shape_candidates, []

    decisions: list[dict[str, Any]] = []
    filtered_rasters: list[Candidate] = []
    for raster in raster_candidates:
        owning_shapes = [
            shape
            for shape in deki_shapes
            if raster_can_yield_to_deki_shape(raster, shape, raster_ownership.get(raster.id, {}))
        ]
        if not owning_shapes:
            filtered_rasters.append(raster)
            continue

        same_region_owner = next((shape for shape in owning_shapes if same_region_for_deki_shape_replacement(raster.bbox, shape.bbox)), None)
        if same_region_owner is not None:
            decisions.append(
                {
                    "kind": "raster_suppressed_by_deki_view_shape",
                    "rasterId": raster.id,
                    "shapeId": same_region_owner.id,
                    "rasterBbox": raster.bbox.to_dict(),
                    "shapeBbox": same_region_owner.bbox.to_dict(),
                    "rasterOwnership": raster_ownership.get(raster.id, {}),
                }
            )
            continue

        pieces = split_raster_around_deki_shapes(raster, owning_shapes)
        if pieces:
            filtered_rasters.extend(pieces)
            decisions.append(
                {
                    "kind": "raster_split_around_deki_view_shape",
                    "rasterId": raster.id,
                    "shapeIds": [shape.id for shape in owning_shapes],
                    "rasterBbox": raster.bbox.to_dict(),
                    "pieceCount": len(pieces),
                    "rasterOwnership": raster_ownership.get(raster.id, {}),
                }
            )
            continue

        decisions.append(
            {
                "kind": "raster_suppressed_by_deki_view_shape",
                "rasterId": raster.id,
                "shapeId": owning_shapes[0].id,
                "rasterBbox": raster.bbox.to_dict(),
                "shapeBbox": owning_shapes[0].bbox.to_dict(),
                "rasterOwnership": raster_ownership.get(raster.id, {}),
                "reason": "split_removed_all_visible_raster_area",
            }
        )

    merged_shapes: list[Candidate] = []
    ordered_shapes = sorted(deki_shapes, key=lambda item: (item.bbox.y, item.bbox.x, -item.score, item.id))
    ordered_shapes.extend(sorted(shape_candidates, key=lambda item: (item.bbox.y, item.bbox.x, -item.score, item.id)))
    for candidate in ordered_shapes:
        if any(iou(candidate.bbox, kept.bbox) >= 0.82 or contained_overlap(candidate.bbox, kept.bbox) >= 0.90 for kept in merged_shapes):
            if candidate.reason == "deki_yolo_view_control_surface":
                decisions.append({"kind": "deki_view_shape_duplicate_suppressed", "shapeId": candidate.id, "bbox": candidate.bbox.to_dict()})
            continue
        merged_shapes.append(candidate)
    return filtered_rasters, merged_shapes, decisions


def split_raster_around_deki_shapes(raster: Candidate, shapes: list[Candidate]) -> list[Candidate]:
    pieces = [raster]
    for shape in sorted(shapes, key=lambda item: (-intersection_area(raster.bbox, item.bbox), item.id)):
        next_pieces: list[Candidate] = []
        for piece in pieces:
            next_pieces.extend(split_candidate_around_box(piece, shape.bbox, shape.id))
        pieces = next_pieces
        if not pieces:
            break
    return pieces


def split_candidate_around_box(candidate: Candidate, cut: BBox, owner_id: str) -> list[Candidate]:
    inter = intersection_box(candidate.bbox, cut)
    if inter is None:
        return [candidate]

    boxes = [
        BBox(candidate.bbox.x, candidate.bbox.y, candidate.bbox.width, inter.y - candidate.bbox.y),
        BBox(candidate.bbox.x, inter.y2, candidate.bbox.width, candidate.bbox.y2 - inter.y2),
        BBox(candidate.bbox.x, inter.y, inter.x - candidate.bbox.x, inter.height),
        BBox(inter.x2, inter.y, candidate.bbox.x2 - inter.x2, inter.height),
    ]
    pieces: list[Candidate] = []
    for index, box in enumerate(boxes, start=1):
        if box.width < 4 or box.height < 4 or box.area < 96:
            continue
        scores = dict(candidate.scores)
        scores["splitAroundDekiView"] = 1.0
        pieces.append(
            Candidate(
                id=f"{candidate.id}_split_{owner_id}_{index:02d}",
                kind=candidate.kind,
                bbox=box,
                score=candidate.score,
                scores=scores,
                reason="raster_split_around_deki_view_shape",
            )
        )
    return pieces


def intersection_box(a: BBox, b: BBox) -> BBox | None:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return BBox(x1, y1, x2 - x1, y2 - y1)


def copy_deki_artifact(source: Path | None, artifact: dict[str, Any], output_dir: Path) -> None:
    target = output_dir / "deki_yolo_candidates.v1.json"
    if source is not None and source.exists():
        shutil.copyfile(source, target)
        return
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def draw_deki_yolo_overlay(image: Image.Image, candidates: list[DekiYoloCandidate], diagnostics: list[dict[str, Any]], output_path: Path) -> None:
    overlay = image.convert("RGBA")
    draw = ImageDraw.Draw(overlay, "RGBA")
    colors = {
        "View": (30, 190, 90, 255),
        "ImageView": (230, 80, 60, 255),
        "Text": (60, 120, 255, 220),
        "Line": (160, 80, 220, 255),
    }
    for item in candidates:
        color = colors.get(item.class_name, (255, 180, 0, 255))
        box = item.bbox
        draw.rectangle((box.x, box.y, box.x2, box.y2), outline=color, width=2)
        draw.text((box.x + 2, box.y + 2), f"{item.class_name}:{item.confidence:.2f}", fill=color)
    if diagnostics:
        draw.rectangle((0, 0, min(520, image.width), 18), fill=(0, 0, 0, 150))
        draw.text((4, 2), f"diagnostics: {len(diagnostics)}", fill=(255, 255, 255, 255))
    overlay.convert("RGB").save(output_path)


def write_v3_diagnostics(output_path: Path, layer_stack: dict[str, Any]) -> None:
    diagnostics = layer_stack["diagnostics"]
    lines = [
        "# PSD-like V3 Deki YOLO Diagnostics",
        "",
        f"- source: `{layer_stack['sourceImage']}`",
        f"- ocr: `{layer_stack.get('ocr', '')}`",
        f"- canvas: {layer_stack['canvas']['width']}x{layer_stack['canvas']['height']}",
        f"- layers: {diagnostics['layerCount']}",
        f"- text layers: {diagnostics['textLayerCount']}",
        f"- raster layers: {diagnostics['rasterLayerCount']}",
        f"- shape layers: {diagnostics['shapeLayerCount']}",
        f"- deki candidates: {diagnostics.get('dekiCandidateCount', 0)}",
        f"- deki views accepted: {diagnostics.get('dekiViewShapeAcceptedCount', 0)}",
        f"- deki imageviews accepted: {diagnostics.get('dekiImageViewRasterAcceptedCount', 0)}",
        f"- deki text diagnostic count: {diagnostics.get('dekiTextDiagnosticCount', 0)}",
        f"- full page visible raster: {diagnostics['fullPageVisibleRaster']}",
        f"- tiny raster fragments: {diagnostics['tinyRasterFragments']}",
        f"- raw text overlap raster: {diagnostics['rawTextOverlapRaster']}",
        f"- raster text knockout: {diagnostics['rasterTextKnockoutCount']}",
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


def write_v3_ownership_report(output_path: Path, layer_stack: dict[str, Any]) -> None:
    raster_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "raster"]
    shape_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "shape"]
    text_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "text"]
    report = {
        "version": "psd_like_v3_ownership_report.v1",
        "diagnostics": layer_stack["diagnostics"],
        "dekiShapeLayers": [
            {
                "id": layer["id"],
                "bbox": layer["bbox"],
                "reason": layer.get("reason", ""),
                "style": layer.get("style", {}),
                "scores": layer.get("scores", {}),
            }
            for layer in shape_layers
            if str(layer.get("reason", "")).startswith("deki_yolo")
        ],
        "rasterOwnership": [
            {
                "id": layer["id"],
                "bbox": layer["bbox"],
                "asset": layer.get("asset", ""),
                "reason": layer.get("reason", ""),
                "ownership": layer.get("ownership", {}),
            }
            for layer in raster_layers
        ],
        "zOrder": {
            "maxShapeZ": max([layer["z"] for layer in shape_layers], default=0),
            "minRasterZ": min([layer["z"] for layer in raster_layers], default=0),
            "maxRasterZ": max([layer["z"] for layer in raster_layers], default=0),
            "minTextZ": min([layer["z"] for layer in text_layers], default=0),
        },
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_v3_preview_report(output_path: Path, dsl: dict[str, Any], layer_stack: dict[str, Any]) -> None:
    write_preview_report(output_path, dsl, layer_stack)


def rewrite_dsl_v3(dsl: dict[str, Any]) -> dict[str, Any]:
    dsl["taskId"] = "psd_like_v3_deki_yolo_experiment"
    dsl["page"]["name"] = "PSD-like V3 Deki YOLO Draft Experiment"
    dsl["root"]["name"] = "PSD-like V3 Draft"
    dsl.setdefault("meta", {})["pipeline"] = "psd_like_v3_deki_yolo_experiment.v1"
    return dsl


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

    deki_path: Path | None = None
    if args.deki_json:
        candidate = Path(args.deki_json).expanduser().resolve()
        if candidate.exists():
            deki_path = candidate
        elif not args.allow_missing_deki:
            raise FileNotFoundError(f"Deki YOLO artifact not found: {candidate}")

    image = Image.open(image_path).convert("RGB")
    rgb = np.asarray(image)
    ocr_blocks = load_ocr_blocks(ocr_path, image.width, image.height, args.ocr_min_confidence)
    text_mask = build_text_mask(image.width, image.height, ocr_blocks, args.text_padding)
    text_knockout_mask = build_text_knockout_mask(rgb, ocr_blocks)
    maps = compute_tile_maps(rgb, text_mask, args.tile_size)
    deki_candidates, deki_diagnostics, deki_artifact = load_deki_yolo_candidates(deki_path, image.width, image.height)
    copy_deki_artifact(deki_path, deki_artifact, output_dir)
    draw_deki_yolo_overlay(image, deki_candidates, deki_diagnostics, output_dir / "deki_yolo_overlay.png")

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
    deki_rasters, deki_raster_rejected = deki_imageview_to_raster_candidates(
        yolo_candidates=deki_candidates,
        maps=maps,
        text_mask=text_mask,
        ocr_blocks=ocr_blocks,
        width=image.width,
        height=image.height,
        tile_size=args.tile_size,
    )
    raster_candidates, deki_raster_merge_decisions = merge_deki_rasters(raster_candidates, deki_rasters)

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
    deki_shape_candidates, deki_shape_rejected = deki_view_to_shape_candidates(
        yolo_candidates=deki_candidates,
        maps=maps,
        text_mask=text_knockout_mask,
        ocr_blocks=ocr_blocks,
        rgb=rgb,
        width=image.width,
        height=image.height,
        tile_size=args.tile_size,
    )
    deki_shapes: list[Candidate] = []
    deki_shape_filter_decisions: list[dict[str, Any]] = []
    deki_shape_ownership_decisions: list[dict[str, Any]] = []
    if getattr(args, "enable_deki_view_shapes", False):
        provisional_ownership = build_raster_ownership(raster_candidates, ocr_blocks, text_knockout_mask)
        deki_shapes, deki_shape_filter_decisions = filter_deki_shapes_by_problem_raster(
            deki_shapes=deki_shape_candidates,
            raster_candidates=raster_candidates,
            shape_candidates=shape_candidates,
            raster_ownership=provisional_ownership,
            rgb=rgb,
            text_mask=text_knockout_mask,
        )
        raster_candidates, shape_candidates, deki_shape_ownership_decisions = apply_deki_view_ownership(
            raster_candidates=raster_candidates,
            shape_candidates=shape_candidates,
            deki_shapes=deki_shapes,
            raster_ownership=provisional_ownership,
        )
    else:
        deki_shape_filter_decisions = [
            {
                "kind": "deki_view_shape_diagnostic_only",
                "shapeId": shape.id,
                "bbox": shape.bbox.to_dict(),
                "reason": "enable_deki_view_shapes_not_set",
            }
            for shape in deki_shape_candidates
        ]
    promotion_decisions.extend(control_decisions)
    promotion_decisions.extend(deki_raster_merge_decisions)
    promotion_decisions.extend(deki_shape_filter_decisions)
    promotion_decisions.extend(deki_shape_ownership_decisions)
    promotion_decisions.extend(deki_diagnostics)

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
        "dekiImageViewMinConfidence": 0.42,
        "dekiViewMinConfidence": 0.35,
        "dekiViewCloseFillCoverageMin": 0.91,
    }
    rejected = (
        raster_rejected
        + deki_raster_rejected
        + shape_rejected
        + surface_rejected
        + foreground_rejected
        + deki_shape_rejected
        + promotion_decisions
    )
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
        rejected=rejected,
        thresholds=thresholds,
    )
    layer_stack["version"] = "layer_stack.v3"
    apply_v3_shape_styles(layer_stack, rgb)
    layer_stack["diagnostics"].update(
        {
            "dekiCandidateCount": len(deki_candidates),
            "dekiViewCandidateCount": sum(1 for item in deki_candidates if item.class_name == "View"),
            "dekiImageViewCandidateCount": sum(1 for item in deki_candidates if item.class_name == "ImageView"),
            "dekiTextDiagnosticCount": sum(1 for item in deki_candidates if item.class_name == "Text"),
            "dekiLineDiagnosticCount": sum(1 for item in deki_candidates if item.class_name == "Line"),
            "dekiViewShapePassCount": len(deki_shape_candidates),
            "dekiViewShapeAcceptedCount": len(deki_shapes),
            "dekiImageViewRasterPassCount": len(deki_rasters),
            "dekiImageViewRasterAcceptedCount": sum(1 for item in raster_candidates if item.reason == "deki_yolo_imageview"),
        }
    )

    (output_dir / "layer_stack.v3.json").write_text(
        json.dumps(layer_stack, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    draft_runtime = rewrite_dsl_v3(build_draft_runtime_dsl(layer_stack, rgb))
    (output_dir / "draft_runtime.v3.dsl.v1_0.json").write_text(
        json.dumps(draft_runtime, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_preview_html(output_dir / "preview.v3.html", draft_runtime)
    write_v3_preview_report(output_dir / "preview_report.v3.md", draft_runtime, layer_stack)
    write_draft_preview_png(output_dir / "draft_preview.v3.png", draft_runtime, output_dir)
    heatmap_image(maps["raster"], image.width, image.height, args.tile_size, (255, 80, 80)).save(output_dir / "raster_heatmap.v3.png")
    heatmap_image(maps["shape"], image.width, image.height, args.tile_size, (80, 220, 120)).save(output_dir / "shape_heatmap.v3.png")
    draw_overlay(image, ocr_blocks, raster_candidates, shape_candidates, output_dir / "overlay.v3.png")
    draw_reconstructed_preview(image, rgb, ocr_blocks, raster_candidates, shape_candidates, text_knockout_mask, output_dir / "reconstructed_preview.v3.png")
    write_v3_diagnostics(output_dir / "diagnostics.v3.md", layer_stack)
    write_v3_ownership_report(output_dir / "ownership_report.v3.json", layer_stack)
    return layer_stack


def apply_v3_shape_styles(layer_stack: dict[str, Any], rgb: np.ndarray) -> None:
    for layer in layer_stack.get("layers", []):
        if layer.get("type") != "shape" or layer.get("reason") != "deki_yolo_view_control_surface":
            continue
        bbox = layer.get("bbox", {})
        scores = layer.get("scores", {})
        shape = Candidate(
            id=str(layer.get("id", "deki_shape")),
            kind="shape",
            bbox=BBox(int(bbox.get("x", 0)), int(bbox.get("y", 0)), int(bbox.get("width", 0)), int(bbox.get("height", 0))),
            score=float(scores.get("dekiConfidence", 0.0)),
            scores=scores,
            reason="editable_control_surface_from_raster",
        )
        style = {
            "fill": color_from_scores(scores),
        }
        radius = infer_control_corner_radius(rgb, shape)
        if radius > 0:
            style["cornerRadius"] = radius
        layer["style"] = style


def color_from_scores(scores: dict[str, Any]) -> str:
    r = max(0, min(255, int(round(float(scores.get("fillR", 255.0))))))
    g = max(0, min(255, int(round(float(scores.get("fillG", 255.0))))))
    b = max(0, min(255, int(round(float(scores.get("fillB", 255.0))))))
    return f"#{r:02x}{g:02x}{b:02x}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PSD-like V3 deterministic layer decomposition with Deki YOLO candidates.")
    parser.add_argument("--image", required=True, help="Source PNG path.")
    parser.add_argument("--ocr", default="", help="OCR artifact path with blocks[].")
    parser.add_argument("--deki-json", default="", help="Deki YOLO candidate artifact path.")
    parser.add_argument("--out", required=True, help="Output directory.")
    parser.add_argument("--allow-missing-ocr", action="store_true", help="Run without OCR when the artifact is missing.")
    parser.add_argument("--allow-missing-deki", action="store_true", help="Run without Deki YOLO when the artifact is missing.")
    parser.add_argument("--tile-size", type=int, default=8)
    parser.add_argument("--text-padding", type=int, default=3)
    parser.add_argument("--ocr-min-confidence", type=float, default=0.70)
    parser.add_argument("--raster-threshold", type=float, default=0.42)
    parser.add_argument("--shape-threshold", type=float, default=0.62)
    parser.add_argument("--raster-min-area", type=int, default=512)
    parser.add_argument("--shape-min-area", type=int, default=1200)
    parser.add_argument("--surface-min-area", type=int, default=2400)
    parser.add_argument("--max-text-overlap", type=float, default=0.24)
    parser.set_defaults(enable_deki_view_shapes=False)
    parser.add_argument("--enable-deki-view-shapes", dest="enable_deki_view_shapes", action="store_true", help="Allow Deki View candidates to change final shape/raster ownership.")
    parser.add_argument("--disable-deki-view-shapes", dest="enable_deki_view_shapes", action="store_false", help="Keep Deki View candidates diagnostic-only.")
    return parser.parse_args()


def main() -> None:
    layer_stack = run(parse_args())
    diagnostics = layer_stack["diagnostics"]
    print(
        "PSD-like V3 experiment: "
        f"text={diagnostics['textLayerCount']} "
        f"raster={diagnostics['rasterLayerCount']} "
        f"shape={diagnostics['shapeLayerCount']} "
        f"deki={diagnostics.get('dekiCandidateCount', 0)} "
        f"deki_view_shapes={diagnostics.get('dekiViewShapeAcceptedCount', 0)} "
        f"missing_assets={diagnostics['missingAssetCount']} "
        f"out={Path(layer_stack['sourceImage']).name}"
    )


if __name__ == "__main__":
    main()
