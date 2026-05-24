from __future__ import annotations

from typing import Any

from ..visual_evidence_normalization import parse_bbox
from ..visual_primitive_graph import bbox_in_bounds
from .overlap import overlap_with_text_union, overlapping_text_boxes
from .types import M2907Options, OwnershipDecision, OwnershipDecisionKind, OwnershipKind


def valid_text_boxes(m2902_document: dict[str, Any], width: int, height: int, options: M2907Options) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for raw in m2902_document.get("textBoxes", []):
        if not isinstance(raw, dict):
            continue
        bbox = parse_bbox(raw.get("bbox"))
        source_id = str(raw.get("id") or "")
        if bbox is None or not source_id or not bbox_in_bounds(bbox, width, height):
            continue
        text = str(raw.get("text") or "").strip()
        boxes.append(
            {
                "id": source_id,
                "bbox": bbox,
                "text": text,
                "textPreview": truncate_text(text, options.text_preview_max_chars),
                "confidence": float(raw.get("confidence", 1.0)),
            }
        )
    return boxes

def build_ownership_decisions(
    m2903_document: dict[str, Any],
    text_boxes: list[dict[str, Any]],
    width: int,
    height: int,
    options: M2907Options,
) -> list[OwnershipDecision]:
    decisions: list[OwnershipDecision] = []
    for raw in m2903_document.get("items", []):
        if not isinstance(raw, dict):
            continue
        bbox = parse_bbox(raw.get("bbox"))
        source_id = str(raw.get("sourceEvidenceId") or "")
        item_id = str(raw.get("id") or "")
        if bbox is None or not item_id or not source_id or not bbox_in_bounds(bbox, width, height):
            continue
        decisions.append(decide_visual_item(f"own_{len(decisions) + 1:04d}", raw, bbox, text_boxes, options))
    for text_box in text_boxes:
        decisions.append(decide_text_box(f"own_{len(decisions) + 1:04d}", text_box, options))
    return decisions

def decide_text_box(id: str, text_box: dict[str, Any], options: M2907Options) -> OwnershipDecision:
    confidence = float(text_box.get("confidence", 1.0))
    return OwnershipDecision(
        id=id,
        source="m2902_text_box",
        source_evidence_id=str(text_box["id"]),
        source_visual_evidence_item_id=None,
        source_text_box_id=str(text_box["id"]),
        source_visual_kind=None,
        bbox=list(text_box["bbox"]),
        ownership="text_owned",
        decision="accepted" if confidence >= options.ocr_confidence_min else "candidate",
        ownership_reason_kind="high_ocr_overlap_text_noise" if confidence >= options.ocr_confidence_min else "low_ocr_confidence",
        matched_text_box_ids=[str(text_box["id"])],
        text_overlap_ratio=1.0,
        ocr_overlap_ratio=1.0,
        text_preview=str(text_box.get("textPreview") or ""),
        ocr_confidence=confidence,
        suppressed_as_visual=False,
        allowed_for_object_forming_visual_side=False,
        allowed_for_text_side=True,
        allowed_for_audit_only=True,
        risks=[] if confidence >= options.ocr_confidence_min else ["low_ocr_confidence"],
        reasons=["m2902_text_box", "text_owned_source"],
    )

def decide_visual_item(id: str, raw: dict[str, Any], bbox: list[int], text_boxes: list[dict[str, Any]], options: M2907Options) -> OwnershipDecision:
    visual_kind = str(raw.get("visualKind") or "")
    source_lineage = raw.get("sourceLineage") if isinstance(raw.get("sourceLineage"), dict) else None
    matched = overlapping_text_boxes(bbox, text_boxes)
    matched_ids = [str(item["id"]) for item in matched]
    ocr_overlap = overlap_with_text_union(bbox, matched, denominator="bbox")
    text_covered = overlap_with_text_union(bbox, matched, denominator="text")
    best_text = max(matched, key=lambda item: float(item.get("confidence", 0.0)), default=None)
    confidence = float(best_text.get("confidence", 0.0)) if best_text else None
    raw_text_overlap = float(raw.get("textOverlapRatio", 0.0))
    text_preview = truncate_text(" ".join(str(item.get("text") or "").strip() for item in matched if str(item.get("text") or "").strip()), options.text_preview_max_chars) if matched else None
    has_good_ocr = confidence is not None and confidence >= options.ocr_confidence_min
    has_text_ownership_overlap = ocr_overlap >= options.text_owned_overlap_min and text_covered >= options.text_owned_text_covered_min

    if has_source_support_contract(raw):
        return make_visual_decision(
            id,
            raw,
            bbox,
            ownership="shape_owned",
            decision="candidate",
            reason_kind="source_support_shape",
            matched_ids=matched_ids,
            raw_text_overlap=raw_text_overlap,
            ocr_overlap=ocr_overlap,
            text_preview=text_preview,
            ocr_confidence=confidence,
            suppressed=False,
            allow_visual=True,
            allow_text=False,
            risks=[],
            reasons=["source_support_shape_retained"],
        )

    if visual_kind == "mixed_symbol_text_candidate":
        return make_visual_decision(
            id,
            raw,
            bbox,
            ownership="mixed_or_uncertain",
            decision="uncertain",
            reason_kind="symbol_text_ownership_conflict",
            matched_ids=matched_ids,
            raw_text_overlap=raw_text_overlap,
            ocr_overlap=ocr_overlap,
            text_preview=text_preview,
            ocr_confidence=confidence,
            suppressed=False,
            allow_visual=False,
            allow_text=False,
            risks=["pre_ocr_symbol_lineage_conflict"],
            reasons=["mixed_symbol_text_candidate_audit_only", "pre_ocr_symbol_lineage_preserved"],
        )

    if visual_kind == "text_noise":
        text_noise_risks: list[str] = []
        text_noise_reasons = ["text_noise_owned_by_ocr", "high_ocr_overlap"]
        if lineage_is_text_owned_rejected(source_lineage):
            text_noise_risks.append("text_contamination_possible")
            text_noise_reasons.append("text_owned_rejected_lineage")
        if has_good_ocr and has_text_ownership_overlap:
            return make_visual_decision(
                id,
                raw,
                bbox,
                ownership="text_owned",
                decision="accepted",
                reason_kind="high_ocr_overlap_text_noise",
                matched_ids=matched_ids,
                raw_text_overlap=raw_text_overlap,
                ocr_overlap=ocr_overlap,
                text_preview=text_preview,
                ocr_confidence=confidence,
                suppressed=True,
                allow_visual=False,
                allow_text=True,
                risks=text_noise_risks,
                reasons=text_noise_reasons,
            )
        return make_visual_decision(
            id,
            raw,
            bbox,
            ownership="audit_only" if not matched else "mixed_or_uncertain",
            decision="uncertain",
            reason_kind="low_ocr_confidence" if matched else "missing_text_match",
            matched_ids=matched_ids,
            raw_text_overlap=raw_text_overlap,
            ocr_overlap=ocr_overlap,
            text_preview=text_preview,
            ocr_confidence=confidence,
            suppressed=True,
            allow_visual=False,
            allow_text=False,
            risks=["low_ocr_confidence"] if matched else ["missing_text_match"],
            reasons=["text_noise_not_allowed_as_visual_side"],
        )

    if visual_kind == "icon_candidate":
        if matched and ocr_overlap >= options.visual_candidate_high_text_overlap:
            return make_visual_decision(
                id,
                raw,
                bbox,
                ownership="mixed_or_uncertain",
                decision="uncertain",
                reason_kind="conflicting_ownership",
                matched_ids=matched_ids,
                raw_text_overlap=raw_text_overlap,
                ocr_overlap=ocr_overlap,
                text_preview=text_preview,
                ocr_confidence=confidence,
                suppressed=False,
                allow_visual=True,
                allow_text=False,
                risks=["ocr_overlap_on_visual_candidate"],
                reasons=["icon_candidate_kept_for_visual_review"],
            )
        return visual_owned_decision(id, raw, bbox, matched_ids, raw_text_overlap, ocr_overlap, text_preview, confidence)

    if visual_kind in {"media_candidate", "accepted_image"}:
        risks = ["text_overlay_on_visual"] if matched and ocr_overlap > 0 else []
        return make_visual_decision(
            id,
            raw,
            bbox,
            ownership="visual_owned",
            decision="accepted" if visual_kind == "accepted_image" else "candidate",
            reason_kind="image_with_text_overlay" if risks else "visual_candidate_kept",
            matched_ids=matched_ids,
            raw_text_overlap=raw_text_overlap,
            ocr_overlap=ocr_overlap,
            text_preview=text_preview,
            ocr_confidence=confidence,
            suppressed=False,
            allow_visual=True,
            allow_text=False,
            risks=risks,
            reasons=["visual_image_kept", "text_overlay_recorded"] if risks else ["visual_image_kept"],
        )

    if matched and ocr_overlap >= options.visual_candidate_high_text_overlap:
        return make_visual_decision(
            id,
            raw,
            bbox,
            ownership="mixed_or_uncertain",
            decision="uncertain",
            reason_kind="conflicting_ownership",
            matched_ids=matched_ids,
            raw_text_overlap=raw_text_overlap,
            ocr_overlap=ocr_overlap,
            text_preview=text_preview,
            ocr_confidence=confidence,
            suppressed=False,
            allow_visual=True,
            allow_text=False,
            risks=["ocr_overlap_on_visual_candidate"],
            reasons=["visual_candidate_kept_with_ownership_conflict"],
        )
    return visual_owned_decision(id, raw, bbox, matched_ids, raw_text_overlap, ocr_overlap, text_preview, confidence)

def visual_owned_decision(
    id: str,
    raw: dict[str, Any],
    bbox: list[int],
    matched_ids: list[str],
    raw_text_overlap: float,
    ocr_overlap: float,
    text_preview: str | None,
    confidence: float | None,
) -> OwnershipDecision:
    return make_visual_decision(
        id,
        raw,
        bbox,
        ownership="visual_owned",
        decision="candidate",
        reason_kind="visual_candidate_kept",
        matched_ids=matched_ids,
        raw_text_overlap=raw_text_overlap,
        ocr_overlap=ocr_overlap,
        text_preview=text_preview,
        ocr_confidence=confidence,
        suppressed=False,
        allow_visual=True,
        allow_text=False,
        risks=[],
        reasons=["visual_candidate_kept"],
    )

def make_visual_decision(
    id: str,
    raw: dict[str, Any],
    bbox: list[int],
    *,
    ownership: OwnershipKind,
    decision: OwnershipDecisionKind,
    reason_kind: str,
    matched_ids: list[str],
    raw_text_overlap: float,
    ocr_overlap: float,
    text_preview: str | None,
    ocr_confidence: float | None,
    suppressed: bool,
    allow_visual: bool,
    allow_text: bool,
    risks: list[str],
    reasons: list[str],
) -> OwnershipDecision:
    source_lineage = raw.get("sourceLineage") if isinstance(raw.get("sourceLineage"), dict) else None
    return OwnershipDecision(
        id=id,
        source="m2903_visual_evidence",
        source_evidence_id=str(raw.get("sourceEvidenceId") or ""),
        source_visual_evidence_item_id=str(raw.get("id") or ""),
        source_text_box_id=None,
        source_visual_kind=str(raw.get("visualKind") or ""),
        bbox=bbox,
        ownership=ownership,
        decision=decision,
        ownership_reason_kind=reason_kind,
        matched_text_box_ids=matched_ids,
        text_overlap_ratio=raw_text_overlap,
        ocr_overlap_ratio=ocr_overlap,
        text_preview=text_preview,
        ocr_confidence=ocr_confidence,
        suppressed_as_visual=suppressed,
        allowed_for_object_forming_visual_side=allow_visual,
        allowed_for_text_side=allow_text,
        allowed_for_audit_only=True,
        risks=dedupe_strings(risks),
        reasons=dedupe_strings([*reasons, *[str(reason) for reason in raw.get("reasons", []) if isinstance(reason, str)], f"source_visual_kind_{str(raw.get('visualKind') or 'unknown')}"]),
        source_lineage=dict(source_lineage) if source_lineage is not None else None,
    )

def has_source_support_contract(raw: dict[str, Any]) -> bool:
    subtype = str(raw.get("sourceSubtype") or raw.get("sourceM29Subtype") or raw.get("subtype") or "")
    for reason in raw.get("reasons", []):
        if not subtype and isinstance(reason, str) and reason.startswith("sourceSubtype:"):
            subtype = reason.split(":", 1)[1]
            break
    reasons = {str(reason) for reason in raw.get("reasons", []) if isinstance(reason, str)}
    return subtype in {"low_contrast_support", "text_support_background"} or bool(
        reasons & {"low_contrast_support_region", "text_support_background_region"}
    )

def truncate_text(text: str | None, max_chars: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= max_chars else text[:max_chars] + "..."

def dedupe_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result

def lineage_is_text_owned_rejected(source_lineage: dict[str, Any] | None) -> bool:
    if not isinstance(source_lineage, dict):
        return False
    return (
        source_lineage.get("conflictClass") == "text_owned_rejected_lineage"
        or source_lineage.get("rejectedLineageReason") == "text_owned_rejected_lineage"
    )
