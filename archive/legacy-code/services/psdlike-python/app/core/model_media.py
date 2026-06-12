from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np

from .candidates import is_full_page_backing, nms_candidates
from .components import component_bbox, connected_components
from .evidence import bbox_scores, bbox_tile_slice, text_mask_ratio
from .model_evidence import MEDIA_CLASSES, ModelDetection
from .schema import BBox, Candidate, OCRBlock, clamp_box, intersection_area, ioa, iou


MEDIA_TRIGGER_CONFIDENCE = 0.50
MEDIA_HIGH_CONFIDENCE = 0.72
MAX_MEDIA_WINDOW_AREA_RATIO = 0.20


@dataclass(frozen=True)
class ModelMediaResult:
    rasters: list[Candidate]
    decisions: list[dict[str, Any]]
    diagnostics: dict[str, Any]


def refine_model_assisted_media(
    detections: list[ModelDetection],
    raster_candidates: list[Candidate],
    control_shapes: list[Candidate],
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    ocr_blocks: list[OCRBlock],
    width: int,
    height: int,
    tile_size: int,
) -> ModelMediaResult:
    page_area = max(1, width * height)
    kept_by_id = {item.id: item for item in raster_candidates}
    consumed_ids: set[str] = set()
    additions: list[Candidate] = []
    decisions: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    search_count = 0
    high_confidence_count = 0
    merged_raster_count = 0
    limited_raster_count = 0
    added_raster_count = 0

    for det in detections:
        if det.class_name not in MEDIA_CLASSES:
            continue
        if det.confidence < MEDIA_TRIGGER_CONFIDENCE:
            reason = "below_media_trigger_confidence"
            reason_counts[reason] += 1
            decisions.append(rejected_decision(det, reason))
            continue

        search_count += 1
        if det.confidence >= MEDIA_HIGH_CONFIDENCE:
            high_confidence_count += 1

        window = expanded_media_window(det.bbox, width, height, det.class_name)
        if window is None:
            reason = "empty_media_search_window"
            reason_counts[reason] += 1
            decisions.append(rejected_decision(det, reason))
            continue

        active_rasters = [item for item in kept_by_id.values() if item.id not in consumed_ids]
        strong_existing = best_existing_media_match(det, window, active_rasters, maps, text_mask, tile_size, width, height)
        if window.area > page_area * MAX_MEDIA_WINDOW_AREA_RATIO and strong_existing is None:
            reason = "media_search_window_too_large"
            reason_counts[reason] += 1
            decisions.append(rejected_decision(det, reason, search_window=window))
            continue

        control_overlap = best_control_overlap(window, control_shapes)
        if control_overlap is not None:
            reason = "overlaps_accepted_control"
            reason_counts[reason] += 1
            decisions.append(rejected_decision(det, reason, search_window=window, control=control_overlap))
            continue

        if strong_existing is not None:
            decisions.append(accepted_existing_decision(det, strong_existing, window))
            continue

        merge_candidate, consumed = merged_fragment_candidate(
            det=det,
            window=window,
            rasters=active_rasters,
            control_shapes=control_shapes,
            maps=maps,
            text_mask=text_mask,
            width=width,
            height=height,
            tile_size=tile_size,
        )
        if merge_candidate is not None:
            additions.append(merge_candidate)
            consumed_ids.update(consumed)
            merged_raster_count += len(consumed)
            decisions.append(accepted_added_decision(det, merge_candidate, window, "accepted_model_media_refinement"))
            continue

        component_candidate, rejected_reason = local_component_candidate(
            det=det,
            window=window,
            existing_rasters=active_rasters,
            control_shapes=control_shapes,
            maps=maps,
            text_mask=text_mask,
            ocr_blocks=ocr_blocks,
            width=width,
            height=height,
            tile_size=tile_size,
        )
        if component_candidate is None:
            reason = rejected_reason or "missing_local_media_component"
            reason_counts[reason] += 1
            decisions.append(rejected_decision(det, reason, search_window=window))
            continue

        overlarge = overlarge_existing_owner(component_candidate, active_rasters)
        if overlarge is not None:
            consumed_ids.add(overlarge.id)
            limited_raster_count += 1

        additions.append(component_candidate)
        added_raster_count += 1
        decisions.append(accepted_added_decision(det, component_candidate, window, "accepted_model_media_refinement"))

    remaining = [item for item in kept_by_id.values() if item.id not in consumed_ids]
    rasters = nms_candidates(remaining + additions, overlap_threshold=0.48)
    diagnostics = {
        "modelMediaSearchWindowCount": search_count,
        "modelMediaAcceptedCount": sum(1 for item in decisions if str(item.get("decision", "")).startswith("accepted_")),
        "modelMediaRejectedCount": sum(1 for item in decisions if str(item.get("decision", "")).startswith("rejected_")),
        "modelMediaHighConfidenceCount": high_confidence_count,
        "modelMediaMergedRasterCount": merged_raster_count,
        "modelMediaLimitedRasterCount": limited_raster_count,
        "modelMediaAddedRasterCount": added_raster_count,
        "modelMediaOwnedTextSuppressedCount": 0,
        "modelMediaRejectedReasons": dict(sorted(reason_counts.items())),
    }
    return ModelMediaResult(rasters=rasters, decisions=decisions, diagnostics=diagnostics)


def expanded_media_window(box: BBox, width: int, height: int, class_name: str) -> BBox | None:
    pad = min(16, max(2, round(min(box.width, box.height) * 0.10)))
    expanded = clamp_box(BBox(box.x - pad, box.y - pad, box.width + pad * 2, box.height + pad * 2), width, height)
    if expanded is None:
        return None
    if class_name == "Icon":
        max_width = max(box.width, int(round(box.width * 1.8)))
        max_height = max(box.height, int(round(box.height * 1.8)))
        if expanded.width > max_width or expanded.height > max_height:
            center_x = box.x + box.width / 2
            center_y = box.y + box.height / 2
            expanded = clamp_box(
                BBox(
                    int(round(center_x - min(expanded.width, max_width) / 2)),
                    int(round(center_y - min(expanded.height, max_height) / 2)),
                    min(expanded.width, max_width),
                    min(expanded.height, max_height),
                ),
                width,
                height,
            )
    return expanded


def best_existing_media_match(
    det: ModelDetection,
    window: BBox,
    rasters: list[Candidate],
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    tile_size: int,
    width: int,
    height: int,
) -> Candidate | None:
    best: tuple[float, Candidate] | None = None
    for raster in rasters:
        overlap_score = max(iou(det.bbox, raster.bbox), ioa(det.bbox, raster.bbox) * 0.80, ioa(raster.bbox, window) * 0.68)
        if overlap_score < 0.32:
            continue
        ok, _, _ = score_media_box(det.class_name, raster.bbox, maps, text_mask, tile_size, width, height)
        if not ok:
            continue
        score = overlap_score + media_score(raster.scores) * 0.20
        if best is None or score > best[0]:
            best = (score, raster)
    return best[1] if best is not None else None


def merged_fragment_candidate(
    det: ModelDetection,
    window: BBox,
    rasters: list[Candidate],
    control_shapes: list[Candidate],
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    width: int,
    height: int,
    tile_size: int,
) -> tuple[Candidate | None, list[str]]:
    fragments = [
        raster
        for raster in rasters
        if ioa(raster.bbox, window) >= 0.72
        and raster.bbox.area <= max(window.area * 0.72, 1600)
        and best_control_overlap(raster.bbox, control_shapes) is None
    ]
    if len(fragments) < 2:
        return None, []
    box = union_box([item.bbox for item in fragments])
    if box is None or ioa(box, window) < 0.70:
        return None, []
    ok, scores, reason = score_media_box(det.class_name, box, maps, text_mask, tile_size, width, height)
    if not ok:
        return None, []
    scores = dict(scores)
    scores["modelMedia"] = 1.0
    scores["modelConfidence"] = round(float(det.confidence), 4)
    scores["mergedRasterCount"] = float(len(fragments))
    return (
        Candidate(
            id=f"model_media_{det.id}_merged",
            kind="raster",
            bbox=box,
            score=max(0.68, media_score(scores)),
            scores=scores,
            reason="model_assisted_media_merge",
        ),
        [item.id for item in fragments],
    )


def local_component_candidate(
    det: ModelDetection,
    window: BBox,
    existing_rasters: list[Candidate],
    control_shapes: list[Candidate],
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    ocr_blocks: list[OCRBlock],
    width: int,
    height: int,
    tile_size: int,
) -> tuple[Candidate | None, str]:
    tile_rows, tile_cols = maps["raster"].shape
    row_slice, col_slice = bbox_tile_slice(window, tile_size, (tile_rows, tile_cols))
    raster = maps["raster"][row_slice, col_slice]
    texture = maps["texture"][row_slice, col_slice]
    edge = maps["edge"][row_slice, col_slice]
    entropy = maps["entropy"][row_slice, col_slice]
    unique = maps["unique"][row_slice, col_slice]
    text_coverage = maps["textCoverage"][row_slice, col_slice]
    local_mask = (
        ((raster >= 0.30) | ((texture >= 0.28) & (edge >= 0.16)) | ((edge >= 0.28) & (entropy >= 0.16)) | ((unique >= 0.34) & (edge >= 0.14)))
        & (text_coverage <= 0.60)
    )
    if det.class_name == "Icon":
        local_mask |= ((edge >= 0.22) & (entropy >= 0.12) & (text_coverage <= 0.45))

    best: tuple[float, Candidate] | None = None
    rejected: Counter[str] = Counter()
    for component_index, component in enumerate(connected_components(local_mask), start=1):
        absolute_component = [(row + row_slice.start, col + col_slice.start) for row, col in component]
        box = clamp_box(component_bbox(absolute_component, tile_size, width, height), width, height)
        if box is None:
            continue
        if ioa(box, window) < 0.70:
            rejected["component_outside_window"] += 1
            continue
        if best_control_overlap(box, control_shapes) is not None:
            rejected["overlaps_accepted_control"] += 1
            continue
        if existing_similar(box, existing_rasters):
            rejected["existing_raster_already_covers_component"] += 1
            continue
        ok, scores, reason = score_media_box(det.class_name, box, maps, text_mask, tile_size, width, height)
        if not ok:
            rejected[reason] += 1
            continue
        covered_text_count = sum(1 for block in ocr_blocks if intersection_area(block.bbox, box) > 0)
        scores = dict(scores)
        scores["modelMedia"] = 1.0
        scores["modelConfidence"] = round(float(det.confidence), 4)
        scores["coveredTextBlockCount"] = float(covered_text_count)
        candidate = Candidate(
            id=f"model_media_{det.id}_{component_index:04d}",
            kind="raster",
            bbox=box,
            score=max(0.66, media_score(scores)),
            scores=scores,
            reason="model_assisted_media_refinement",
        )
        rank = media_score(scores) + max(iou(det.bbox, box), ioa(box, det.bbox) * 0.55) - box.area / max(1, window.area) * 0.08
        if best is None or rank > best[0]:
            best = (rank, candidate)
    if best is not None:
        return best[1], ""
    return None, rejected.most_common(1)[0][0] if rejected else "missing_local_media_component"


def score_media_box(
    class_name: str,
    box: BBox,
    maps: dict[str, np.ndarray],
    text_mask: np.ndarray,
    tile_size: int,
    width: int,
    height: int,
) -> tuple[bool, dict[str, float], str]:
    page_area = max(1, width * height)
    if box.area <= 0:
        return False, {}, "empty"
    if is_full_page_backing(box, width, height):
        return False, {}, "full_page_backing"
    min_area = 400 if class_name == "Icon" else 512
    if box.area < min_area or box.width < 8 or box.height < 8:
        return False, {}, "too_small"
    if box.area > page_area * MAX_MEDIA_WINDOW_AREA_RATIO:
        return False, {}, "too_large"
    scores = bbox_scores(box, maps, text_mask, tile_size)
    text_ratio = text_mask_ratio(box, text_mask)
    if box.area < 8_000 and text_ratio > 0.015:
        return False, {}, "ocr_overlap_too_high"
    if class_name == "Icon" and text_ratio > 0.08:
        return False, {}, "ocr_overlap_too_high"
    if box.area < 18_000 and text_ratio > 0.08:
        return False, {}, "ocr_overlap_too_high"
    if text_ratio > 0.38:
        return False, {}, "ocr_overlap_too_high"

    score = media_score(scores)
    if score < (0.30 if class_name == "Icon" else 0.36):
        return False, {}, "weak_texture_edge_component"
    if (
        float(scores.get("texture", 0.0)) < 0.12
        and float(scores.get("edge", 0.0)) < 0.12
        and float(scores.get("entropy", 0.0)) < 0.14
        and float(scores.get("raster", 0.0)) < 0.22
    ):
        return False, {}, "weak_texture_edge_component"
    aspect = box.width / max(1, box.height)
    if aspect < 0.08 or aspect > 20.0:
        return False, {}, "bad_aspect"
    if class_name != "Icon" and max(box.width, box.height) < 24:
        return False, {}, "too_small"

    scores = dict(scores)
    scores["mediaScore"] = round(float(score), 4)
    scores["textMaskRatio"] = round(float(text_ratio), 4)
    return True, scores, ""


def media_score(scores: dict[str, float]) -> float:
    texture = float(scores.get("texture", 0.0))
    edge = float(scores.get("edge", 0.0))
    entropy = float(scores.get("entropy", 0.0))
    unique = float(scores.get("unique", 0.0))
    raster = float(scores.get("raster", 0.0))
    return max(raster, texture, edge * 1.10, entropy * 0.85, unique * 0.70)


def best_control_overlap(box: BBox, control_shapes: list[Candidate]) -> Candidate | None:
    best: tuple[float, Candidate] | None = None
    for control in control_shapes:
        score = max(iou(box, control.bbox), ioa(box, control.bbox), ioa(control.bbox, box) * 0.72)
        if score < 0.58:
            continue
        if best is None or score > best[0]:
            best = (score, control)
    return best[1] if best is not None else None


def existing_similar(box: BBox, rasters: list[Candidate]) -> bool:
    for raster in rasters:
        if iou(box, raster.bbox) >= 0.54 or ioa(box, raster.bbox) >= 0.86:
            return True
    return False


def overlarge_existing_owner(candidate: Candidate, rasters: list[Candidate]) -> Candidate | None:
    for raster in rasters:
        if ioa(candidate.bbox, raster.bbox) >= 0.92 and raster.bbox.area >= candidate.bbox.area * 1.80:
            return raster
    return None


def union_box(boxes: list[BBox]) -> BBox | None:
    boxes = [box for box in boxes if box.area > 0]
    if not boxes:
        return None
    x1 = min(box.x for box in boxes)
    y1 = min(box.y for box in boxes)
    x2 = max(box.x2 for box in boxes)
    y2 = max(box.y2 for box in boxes)
    return BBox(x1, y1, x2 - x1, y2 - y1)


def accepted_existing_decision(det: ModelDetection, raster: Candidate, search_window: BBox) -> dict[str, Any]:
    return {
        "kind": "model_media_ownership_decision",
        "detectionId": det.id,
        "className": det.class_name,
        "confidence": round(float(det.confidence), 4),
        "decision": "accepted_existing_model_media",
        "candidateId": raster.id,
        "bbox": raster.bbox.to_dict(),
        "searchWindow": search_window.to_dict(),
        "reason": "existing_raster_texture_edge_component_passed",
        "sourceRefs": [f"model_evidence:{det.id}", f"raster_candidate:{raster.id}", "pixel:local_media_gate"],
    }


def accepted_added_decision(det: ModelDetection, raster: Candidate, search_window: BBox, decision: str) -> dict[str, Any]:
    return {
        "kind": "model_media_ownership_decision",
        "detectionId": det.id,
        "className": det.class_name,
        "confidence": round(float(det.confidence), 4),
        "decision": decision,
        "candidateId": raster.id,
        "bbox": raster.bbox.to_dict(),
        "searchWindow": search_window.to_dict(),
        "reason": "local_texture_edge_component_passed",
        "sourceRefs": [f"model_evidence:{det.id}", "pixel:local_media_gate"],
    }


def rejected_decision(
    det: ModelDetection,
    reason: str,
    search_window: BBox | None = None,
    control: Candidate | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "model_media_ownership_decision",
        "detectionId": det.id,
        "className": det.class_name,
        "confidence": round(float(det.confidence), 4),
        "decision": "rejected_model_media",
        "reason": reason,
        "sourceRefs": [f"model_evidence:{det.id}"],
    }
    if search_window is not None:
        payload["searchWindow"] = search_window.to_dict()
    if control is not None:
        payload["controlSurfaceId"] = control.id
        payload["controlSurfaceBBox"] = control.bbox.to_dict()
        payload["sourceRefs"].append(f"control_surface:{control.id}")
    return payload
