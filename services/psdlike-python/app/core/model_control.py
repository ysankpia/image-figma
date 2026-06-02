from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np

from .controls import (
    control_surface_fill,
    control_surface_local_complexity,
    control_surface_outer_ring_delta,
    control_text_contrast,
    merge_control_surfaces,
    score_ocr_anchored_control_surface,
)
from .model_evidence import CONTROL_CLASSES, ModelDetection
from .schema import BBox, Candidate, OCRBlock, clamp_box, intersection_area, ioa
from .style import relative_luminance


CONTROL_TRIGGER_CONFIDENCE = 0.55
CONTROL_HIGH_CONFIDENCE = 0.75
MAX_CONTROL_WINDOW_AREA_RATIO = 0.08


@dataclass(frozen=True)
class ModelControlResult:
    candidates: list[Candidate]
    decisions: list[dict[str, Any]]
    diagnostics: dict[str, Any]


def detect_model_assisted_control_surfaces(
    detections: list[ModelDetection],
    rgb: np.ndarray,
    ocr_blocks: list[OCRBlock],
    text_mask: np.ndarray,
) -> ModelControlResult:
    height, width, _ = rgb.shape
    page_area = max(1, width * height)
    accepted: list[Candidate] = []
    decisions: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    search_count = 0
    high_confidence_count = 0

    for det in detections:
        if det.class_name not in CONTROL_CLASSES:
            continue
        if det.confidence < CONTROL_TRIGGER_CONFIDENCE:
            reason = "below_control_trigger_confidence"
            reason_counts[reason] += 1
            decisions.append(rejected_decision(det, reason))
            continue

        search_count += 1
        if det.confidence >= CONTROL_HIGH_CONFIDENCE:
            high_confidence_count += 1
        window = expanded_control_window(det.bbox, width, height)
        if window is None:
            reason = "empty_control_search_window"
            reason_counts[reason] += 1
            decisions.append(rejected_decision(det, reason))
            continue
        if window.area > page_area * MAX_CONTROL_WINDOW_AREA_RATIO:
            reason = "control_search_window_too_large"
            reason_counts[reason] += 1
            decisions.append(rejected_decision(det, reason, search_window=window))
            continue

        blocks = control_ocr_blocks(det, window, ocr_blocks)
        if not blocks:
            reason = "missing_ocr_containment_or_adjacency"
            reason_counts[reason] += 1
            decisions.append(rejected_decision(det, reason, search_window=window))
            continue

        best_candidate: Candidate | None = None
        best_scores: dict[str, float] = {}
        best_block: OCRBlock | None = None
        rejected_reasons: Counter[str] = Counter()
        for block in blocks:
            for box in model_control_search_boxes(block.bbox, window, width, height, det.confidence):
                candidate = Candidate(
                    id=f"model_control_{det.id}_{block.id}",
                    kind="shape",
                    bbox=box,
                    score=0.78,
                    scores={},
                    reason="model_assisted_control_surface",
                )
                ok, scores, reason = score_ocr_anchored_control_surface(
                    rgb=rgb,
                    candidate=candidate,
                    block=block,
                    text_mask=text_mask,
                    page_area=page_area,
                )
                if not ok:
                    ok, scores, reason = score_model_window_control_surface(
                        rgb=rgb,
                        candidate=candidate,
                        block=block,
                        text_mask=text_mask,
                        page_area=page_area,
                    )
                if not ok:
                    rejected_reasons[reason] += 1
                    continue
                scored = Candidate(
                    id=f"model_control_{det.id}_{block.id}",
                    kind="shape",
                    bbox=box,
                    score=max(float(scores["score"]), 0.76),
                    scores={
                        **scores,
                        "modelControlSurface": 1.0,
                        "modelConfidence": round(float(det.confidence), 4),
                    },
                    reason="model_assisted_control_surface",
                )
                rank = scored.score + ioa(block.bbox, box) * 0.04 - box.area / page_area * 0.20
                current_rank = (
                    best_candidate.score + ioa(best_block.bbox, best_candidate.bbox) * 0.04 - best_candidate.bbox.area / page_area * 0.20
                    if best_candidate is not None and best_block is not None
                    else -1.0
                )
                if best_candidate is None or rank > current_rank:
                    best_candidate = scored
                    best_scores = scores
                    best_block = block

        if best_candidate is None or best_block is None:
            reason = most_common_reason(rejected_reasons) or "failed_control_physical_gate"
            reason_counts[reason] += 1
            decisions.append(rejected_decision(det, reason, search_window=window, source_blocks=blocks))
            continue

        accepted.append(best_candidate)
        decisions.append(
            {
                "kind": "model_control_ownership_decision",
                "detectionId": det.id,
                "className": det.class_name,
                "confidence": round(float(det.confidence), 4),
                "decision": "accepted_model_control_surface",
                "candidateId": best_candidate.id,
                "bbox": best_candidate.bbox.to_dict(),
                "searchWindow": window.to_dict(),
                "reason": "ocr_containment_fill_ring_padding_passed",
                "sourceRefs": [f"model_evidence:{det.id}", f"ocr:{best_block.id}", "pixel:local_control_gate"],
                "sourceTextBlockIds": [best_block.id],
                "scores": {key: round(float(value), 4) for key, value in best_scores.items()},
            }
        )

    merged = merge_control_surfaces(accepted)
    diagnostics = {
        "modelControlSearchWindowCount": search_count,
        "modelControlAcceptedCount": len(merged),
        "modelControlRejectedCount": sum(1 for item in decisions if str(item.get("decision", "")).startswith("rejected_")),
        "modelControlHighConfidenceCount": high_confidence_count,
        "modelControlRejectedReasons": dict(sorted(reason_counts.items())),
    }
    return ModelControlResult(candidates=merged, decisions=decisions, diagnostics=diagnostics)


def expanded_control_window(box: BBox, width: int, height: int) -> BBox | None:
    pad = min(12, max(2, round(min(box.width, box.height) * 0.12)))
    return clamp_box(BBox(box.x - pad, box.y - pad, box.width + pad * 2, box.height + pad * 2), width, height)


def control_ocr_blocks(det: ModelDetection, window: BBox, ocr_blocks: list[OCRBlock]) -> list[OCRBlock]:
    blocks: list[OCRBlock] = []
    for block in ocr_blocks:
        if block.bbox.area <= 0:
            continue
        coverage_in_window = intersection_area(block.bbox, window) / block.bbox.area
        coverage_in_detection = intersection_area(block.bbox, det.bbox) / block.bbox.area
        adjacent = coverage_in_window >= 0.35 and near_detection_center(block.bbox, det.bbox)
        if coverage_in_detection >= 0.55 or coverage_in_window >= 0.65 or adjacent:
            blocks.append(block)
    return sorted(blocks, key=lambda item: (item.bbox.y, item.bbox.x, item.id))[:8]


def near_detection_center(text_box: BBox, det_box: BBox) -> bool:
    text_cx = text_box.x + text_box.width / 2
    text_cy = text_box.y + text_box.height / 2
    det_cx = det_box.x + det_box.width / 2
    det_cy = det_box.y + det_box.height / 2
    return abs(text_cx - det_cx) <= max(det_box.width * 0.42, text_box.width) and abs(text_cy - det_cy) <= max(det_box.height * 0.42, text_box.height)


def model_control_search_boxes(
    text_box: BBox,
    window: BBox,
    width: int,
    height: int,
    confidence: float,
) -> list[BBox]:
    high = confidence >= CONTROL_HIGH_CONFIDENCE
    pad_x_values = {
        max(6, round(text_box.height * 0.65)),
        max(8, round(text_box.height * 1.0)),
        max(10, round(text_box.width * 0.24)),
        max(12, round(text_box.width * 0.45)),
    }
    pad_y_values = {
        max(4, round(text_box.height * 0.35)),
        max(5, round(text_box.height * 0.55)),
        max(6, round(text_box.height * 0.85)),
    }
    if high:
        pad_x_values.update({max(14, round(text_box.width * 0.75)), max(18, round(text_box.width * 1.10))})
        pad_y_values.add(max(7, round(text_box.height * 1.05)))

    boxes: list[BBox] = []
    seen: set[tuple[int, int, int, int]] = set()

    def add_box(box: BBox | None) -> None:
        if box is None:
            return
        clamped = clamp_box(box, width, height)
        if clamped is None:
            return
        clipped = intersection_box(clamped, window)
        if clipped is None:
            return
        key = (clipped.x, clipped.y, clipped.width, clipped.height)
        if key in seen:
            return
        seen.add(key)
        boxes.append(clipped)

    for pad_x in sorted(pad_x_values):
        for pad_y in sorted(pad_y_values):
            add_box(
                BBox(
                    text_box.x - pad_x,
                    text_box.y - pad_y,
                    text_box.width + pad_x * 2,
                    text_box.height + pad_y * 2,
                )
            )

    for inset in (0, 2, 3, 4, 6):
        add_box(BBox(window.x + inset, window.y + inset, window.width - inset * 2, window.height - inset * 2))

    center_x = text_box.x + text_box.width / 2
    center_y = text_box.y + text_box.height / 2
    for width_ratio in (0.72, 0.82, 0.92, 1.0):
        for height_ratio in (0.72, 0.84, 0.96, 1.0):
            target_width = max(text_box.width + 16, int(round(window.width * width_ratio)))
            target_height = max(text_box.height + 10, int(round(window.height * height_ratio)))
            target_width = min(window.width, target_width)
            target_height = min(window.height, target_height)
            add_box(
                BBox(
                    int(round(center_x - target_width / 2)),
                    int(round(center_y - target_height / 2)),
                    target_width,
                    target_height,
                )
            )
    return sorted(boxes, key=lambda item: (item.area, item.y, item.x))


def score_model_window_control_surface(
    rgb: np.ndarray,
    candidate: Candidate,
    block: OCRBlock,
    text_mask: np.ndarray,
    page_area: int,
) -> tuple[bool, dict[str, float], str]:
    box = candidate.bbox
    if block.bbox.area <= 0 or box.area <= 0:
        return False, {}, "empty"
    if intersection_area(box, block.bbox) / block.bbox.area < 0.90:
        return False, {}, "text_not_contained"
    if box.area > max(12_000, page_area * MAX_CONTROL_WINDOW_AREA_RATIO) or box.width < 24 or box.height < 14:
        return False, {}, "bad_size"
    aspect = box.width / max(1, box.height)
    if aspect < 1.10 or aspect > 14.0:
        return False, {}, "bad_aspect"
    if box.height > max(112, block.bbox.height * 7):
        return False, {}, "too_tall"

    left_pad = block.bbox.x - box.x
    right_pad = box.x2 - block.bbox.x2
    top_pad = block.bbox.y - box.y
    bottom_pad = box.y2 - block.bbox.y2
    if min(left_pad, right_pad, top_pad, bottom_pad) < -1:
        return False, {}, "not_enough_padding"
    if left_pad + right_pad < max(10, int(box.width * 0.16)):
        return False, {}, "not_enough_padding"
    if top_pad + bottom_pad < max(6, int(box.height * 0.16)):
        return False, {}, "not_enough_padding"

    fill, fill_coverage, close_coverage = control_surface_fill(
        rgb,
        candidate,
        text_mask,
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
        0.40
        + min(0.22, close_coverage * 0.18)
        + min(0.16, ring_support_delta / 260.0)
        + min(0.14, text_contrast / 520.0)
        + min(0.08, aspect / 140.0)
        - min(0.12, texture / 800.0)
    )
    return True, {
        "score": round(float(max(0.72, min(0.94, score))), 4),
        "controlSurface": 1.0,
        "modelWindowControlSurface": 1.0,
        "textContainment": round(float(intersection_area(box, block.bbox) / block.bbox.area), 4),
        "areaRatio": round(float(box.area / block.bbox.area), 4),
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
    }, ""


def intersection_box(a: BBox, b: BBox) -> BBox | None:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return BBox(x1, y1, x2 - x1, y2 - y1)


def rejected_decision(
    det: ModelDetection,
    reason: str,
    search_window: BBox | None = None,
    source_blocks: list[OCRBlock] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "model_control_ownership_decision",
        "detectionId": det.id,
        "className": det.class_name,
        "confidence": round(float(det.confidence), 4),
        "decision": "rejected_model_control",
        "reason": reason,
        "sourceRefs": [f"model_evidence:{det.id}"],
    }
    if search_window is not None:
        payload["searchWindow"] = search_window.to_dict()
    if source_blocks:
        payload["sourceTextBlockIds"] = [block.id for block in source_blocks]
        payload["sourceRefs"].extend(f"ocr:{block.id}" for block in source_blocks[:4])
    return payload


def most_common_reason(reasons: Counter[str]) -> str:
    if not reasons:
        return ""
    return reasons.most_common(1)[0][0]
