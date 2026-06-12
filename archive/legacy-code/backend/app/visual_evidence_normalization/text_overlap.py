from __future__ import annotations

import string
from typing import Any

from ..visual_primitive_graph import M29PrimitiveMetrics, bbox_in_bounds
from .parsing import parse_bbox
from .types import TEXT_REJECTED_LINEAGE_ASPECT_MIN, TEXT_REJECTED_LINEAGE_FULL_OCR_COVERAGE_MIN, VisualEvidenceOptions


def text_lineage_counter_evidence(
    *,
    bbox: list[int],
    metrics: M29PrimitiveMetrics,
    source_lineage: dict[str, Any],
    text_overlap: float,
    matched_text_boxes: list[dict[str, Any]],
    options: VisualEvidenceOptions,
) -> list[str]:
    reasons: list[str] = []
    if text_overlap >= TEXT_REJECTED_LINEAGE_FULL_OCR_COVERAGE_MIN:
        reasons.append("full_ocr_coverage")
    if bbox[2] / max(1, bbox[3]) >= TEXT_REJECTED_LINEAGE_ASPECT_MIN or metrics.aspect_ratio >= TEXT_REJECTED_LINEAGE_ASPECT_MIN:
        reasons.append("text_like_aspect")
    text_preview = "".join(str(item.get("text") or "") for item in matched_text_boxes).strip()
    if is_single_text_like_token(text_preview):
        reasons.append("single_text_like_token")
    if has_glyph_sequence_risk(source_lineage, bbox):
        reasons.append("glyph_sequence_risk")
    if source_lineage.get("lineageStrength") == "weak" and source_lineage.get("lineageSource") == "eligible_blocked" and text_overlap >= options.text_noise_overlap_threshold:
        reasons.append("weak_eligible_blocked_high_ocr_overlap")
    return dedupe_strings(reasons)

def has_glyph_sequence_risk(source_lineage: dict[str, Any], bbox: list[int]) -> bool:
    risks = {str(item) for item in source_lineage.get("risks", [])}
    reasons = {str(item) for item in source_lineage.get("reasons", [])}
    if "text_like_sequence_risk" in risks or "text_like_sequence" in reasons:
        return True
    candidate_bboxes = [parse_bbox(value) for value in source_lineage.get("m291CandidateBboxes", []) if isinstance(value, list)]
    candidate_bboxes = [value for value in candidate_bboxes if value is not None]
    if len(candidate_bboxes) < 3:
        return False
    centers = [value[1] + value[3] / 2 for value in candidate_bboxes]
    return max(centers) - min(centers) <= max(3, bbox[3] * 0.35) and bbox[2] / max(1, bbox[3]) >= 2.8

def collect_text_boxes(m2902_document: dict[str, Any], width: int, height: int) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for raw in m2902_document.get("textBoxes", []):
        if not isinstance(raw, dict):
            continue
        bbox = parse_bbox(raw.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        boxes.append(
            {
                "id": str(raw.get("id") or ""),
                "bbox": bbox,
                "text": str(raw.get("text") or ""),
                "confidence": float(raw.get("confidence", 1.0)),
            }
        )
    return boxes

def overlapping_text_boxes(bbox: list[int], text_boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in text_boxes if intersection_area(bbox, item["bbox"]) > 0]

def intersection_area(left: list[int], right: list[int]) -> int:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    return max(0, x2 - x1) * max(0, y2 - y1)

def is_single_text_like_token(text: str) -> bool:
    value = text.strip()
    if not value:
        return False
    compact = "".join(value.split())
    if len(compact) <= 1:
        return True
    return all(char.isdigit() or char in string.punctuation or char in "￥¥$%元人课分秒时天月年" for char in compact)

def dedupe_strings(items: list[str]) -> list[str]:
    output: list[str] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output
