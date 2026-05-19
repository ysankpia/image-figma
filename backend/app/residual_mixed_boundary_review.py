from __future__ import annotations

import csv
import json
import string
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .mixed_symbol_text_conflict_audit import find_forbidden_contract_terms
from .png_tools import PngPixels, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_evidence_normalization import parse_bbox
from .visual_primitive_graph import bbox_area, bbox_in_bounds, bbox_iou, crop_pixels, draw_rect, measure_region


ReviewConclusion = Literal[
    "m2903_tightening_candidate",
    "m2913_classification_adjustment_candidate",
    "keep_residual_mixed_conflict",
    "candidate_for_future_uncertain_review",
    "insufficient_evidence",
]
RecommendedNextStage = Literal[
    "consider_m2903_text_counter_evidence",
    "consider_m2913_audit_adjustment",
    "keep_audit_only",
    "future_uncertain_review_only",
]
OcrCoverageKind = Literal["none", "partial_ocr_overlap", "full_ocr_coverage", "single_text_overlap", "multiple_text_overlap"]


@dataclass(frozen=True)
class M29032Options:
    full_ocr_coverage_min: float = 0.72
    partial_ocr_overlap_min: float = 0.08
    text_like_aspect_min: float = 3.5
    compact_max_edge: int = 128
    compact_max_area: int = 14000
    repeated_alignment_tolerance: int = 8
    label_adjacency_max_gap: int = 40
    duplicate_iou_min: float = 0.65
    max_examples_per_conclusion: int = 40

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResidualMixedSignals:
    lineage_strength: str
    lineage_source: str
    ocr_coverage_kind: OcrCoverageKind
    text_like_token: bool
    glyph_sequence_risk: bool
    text_like_aspect_risk: bool
    full_ocr_coverage: bool
    partial_ocr_overlap: bool
    label_adjacent_relation: bool
    repeated_compact_alignment: bool
    duplicate_topology_count: int
    visual_structure_hint: bool
    m2913_text_rejected: bool
    m2913_future_promotable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineageStrength": self.lineage_strength,
            "lineageSource": self.lineage_source,
            "ocrCoverageKind": self.ocr_coverage_kind,
            "textLikeToken": self.text_like_token,
            "glyphSequenceRisk": self.glyph_sequence_risk,
            "textLikeAspectRisk": self.text_like_aspect_risk,
            "fullOcrCoverage": self.full_ocr_coverage,
            "partialOcrOverlap": self.partial_ocr_overlap,
            "labelAdjacentRelation": self.label_adjacent_relation,
            "repeatedCompactAlignment": self.repeated_compact_alignment,
            "duplicateTopologyCount": self.duplicate_topology_count,
            "visualStructureHint": self.visual_structure_hint,
            "m2913TextRejected": self.m2913_text_rejected,
            "m2913FuturePromotable": self.m2913_future_promotable,
        }


@dataclass(frozen=True)
class ResidualMixedReviewItem:
    id: str
    source_image_id: str
    source_visual_evidence_item_id: str
    source_m2913_conflict_id: str | None
    source_m2907_ownership_decision_id: str | None
    bbox: list[int]
    m2913_classification: str | None
    review_conclusion: ReviewConclusion
    recommended_next_stage: RecommendedNextStage
    should_tighten_m2903: bool
    should_adjust_m2913: bool
    candidate_for_future_uncertain_review: bool
    allowed_for_promotion_now: bool
    allowed_for_visual_side_now: bool
    allowed_for_formal_asset_now: bool
    signals: ResidualMixedSignals
    reasons: list[str]
    risks: list[str]
    example_crop_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceImageId": self.source_image_id,
            "sourceVisualEvidenceItemId": self.source_visual_evidence_item_id,
            "sourceM2913ConflictId": self.source_m2913_conflict_id,
            "sourceM2907OwnershipDecisionId": self.source_m2907_ownership_decision_id,
            "bbox": self.bbox,
            "m2913Classification": self.m2913_classification,
            "reviewConclusion": self.review_conclusion,
            "recommendedNextStage": self.recommended_next_stage,
            "shouldTightenM2903": self.should_tighten_m2903,
            "shouldAdjustM2913": self.should_adjust_m2913,
            "candidateForFutureUncertainReview": self.candidate_for_future_uncertain_review,
            "allowedForPromotionNow": self.allowed_for_promotion_now,
            "allowedForVisualSideNow": self.allowed_for_visual_side_now,
            "allowedForFormalAssetNow": self.allowed_for_formal_asset_now,
            "signals": self.signals.to_dict(),
            "reasons": self.reasons,
            "risks": self.risks,
            "exampleCropPath": self.example_crop_path,
        }


@dataclass(frozen=True)
class M29032DebugArtifacts:
    review_sheet_remaining_mixed: str

    def to_dict(self) -> dict[str, str]:
        return {"reviewSheetRemainingMixed": self.review_sheet_remaining_mixed}


@dataclass(frozen=True)
class M29032Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_image_id: str
    source_m2903_visual_evidence_json: str
    source_m2913_conflict_audit_json: str | None
    source_m2907_ownership_json: str | None
    source_m2902_audit_json: str | None
    source_m291_group_nodes_json: str | None
    source_m2911_lineage_audit_json: str | None
    options: M29032Options
    reviews: list[ResidualMixedReviewItem]
    summary: dict[str, Any]
    debug: M29032DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceImageId": self.source_image_id,
            "sourceM2903VisualEvidenceJson": self.source_m2903_visual_evidence_json,
            "sourceM2913ConflictAuditJson": self.source_m2913_conflict_audit_json,
            "sourceM2907OwnershipJson": self.source_m2907_ownership_json,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "sourceM291GroupNodesJson": self.source_m291_group_nodes_json,
            "sourceM2911LineageAuditJson": self.source_m2911_lineage_audit_json,
            "options": self.options.to_dict(),
            "reviews": [review.to_dict() for review in self.reviews],
            "summary": self.summary,
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }


def extract_residual_mixed_boundary_review(
    *,
    png_data: bytes,
    source_image: str,
    source_image_id: str,
    m2903_document: dict[str, Any],
    m2903_visual_evidence_json_path: str,
    output_dir: Path,
    m2913_document: dict[str, Any] | None = None,
    m2913_conflict_audit_json_path: str | None = None,
    m2907_document: dict[str, Any] | None = None,
    m2907_ownership_json_path: str | None = None,
    m2902_document: dict[str, Any] | None = None,
    m2902_audit_json_path: str | None = None,
    m291_document: dict[str, Any] | None = None,
    m291_group_nodes_json_path: str | None = None,
    m2911_document: dict[str, Any] | None = None,
    m2911_lineage_audit_json_path: str | None = None,
    options: M29032Options | None = None,
    warnings: list[str] | None = None,
) -> M29032Document:
    options = options or M29032Options()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    mixed_items = [item for item in m2903_document.get("items", []) if isinstance(item, dict) and item.get("visualKind") == "mixed_symbol_text_candidate"]
    text_boxes = collect_text_boxes(m2902_document or {}, pixels.width, pixels.height)
    conflicts_by_item = index_m2913_conflicts(m2913_document or {})
    ownership_by_item = index_m2907_decisions(m2907_document or {})
    m291_candidates_by_id = {str(candidate.get("id")): candidate for candidate in (m291_document or {}).get("candidates", []) if isinstance(candidate, dict)}
    m2911_findings = [item for item in (m2911_document or {}).get("findings", []) if isinstance(item, dict)]
    reviews = build_reviews(
        source_image_id=source_image_id,
        mixed_items=mixed_items,
        text_boxes=text_boxes,
        conflicts_by_item=conflicts_by_item,
        ownership_by_item=ownership_by_item,
        m291_candidates_by_id=m291_candidates_by_id,
        m2911_findings=m2911_findings,
        pixels=pixels,
        options=options,
    )
    export_review_examples(pixels, output_dir, reviews, options)
    review_sheet = write_review_sheet(pixels, output_dir, reviews)
    document = M29032Document(
        schema_name="M29032ResidualMixedBoundaryReviewDocument",
        schema_version="0.1",
        source_image=source_image,
        source_image_id=source_image_id,
        source_m2903_visual_evidence_json=m2903_visual_evidence_json_path,
        source_m2913_conflict_audit_json=m2913_conflict_audit_json_path,
        source_m2907_ownership_json=m2907_ownership_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        source_m291_group_nodes_json=m291_group_nodes_json_path,
        source_m2911_lineage_audit_json=m2911_lineage_audit_json_path,
        options=options,
        reviews=reviews,
        summary=build_summary(reviews, m2907_document, m2902_document),
        debug=M29032DebugArtifacts(review_sheet_remaining_mixed=review_sheet),
        warnings=warnings or [],
        meta={"notes": "m29_0_3_2_residual_mixed_boundary_review", "reviewCount": len(reviews)},
    )
    validate_m29032_document(document, output_dir, pixels.width, pixels.height)
    write_outputs(document, output_dir)
    return document


def build_reviews(
    *,
    source_image_id: str,
    mixed_items: list[dict[str, Any]],
    text_boxes: list[dict[str, Any]],
    conflicts_by_item: dict[str, dict[str, Any]],
    ownership_by_item: dict[str, dict[str, Any]],
    m291_candidates_by_id: dict[str, dict[str, Any]],
    m2911_findings: list[dict[str, Any]],
    pixels: PngPixels,
    options: M29032Options,
) -> list[ResidualMixedReviewItem]:
    reviews: list[ResidualMixedReviewItem] = []
    all_mixed_bboxes = [bbox for item in mixed_items if (bbox := parse_bbox(item.get("bbox"))) is not None]
    for item in mixed_items:
        item_id = str(item.get("id") or "")
        bbox = parse_bbox(item.get("bbox"))
        if not item_id or bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
            continue
        conflict = conflicts_by_item.get(item_id)
        ownership = ownership_by_item.get(item_id)
        lineage = item.get("sourceLineage") if isinstance(item.get("sourceLineage"), dict) else {}
        candidate_ids = [str(value) for value in lineage.get("m291CandidateIds", []) if value]
        candidates = [m291_candidates_by_id[candidate_id] for candidate_id in candidate_ids if candidate_id in m291_candidates_by_id]
        matched_text = overlapping_text_boxes(bbox, text_boxes)
        matched_findings = matching_m2911_findings(item_id, bbox, m2911_findings)
        signals = build_signals(item, bbox, lineage, conflict, candidates, matched_text, text_boxes, matched_findings, all_mixed_bboxes, pixels, options)
        conclusion, next_stage, tighten, adjust, future, reasons, risks = classify_review(conflict, signals)
        reviews.append(
            ResidualMixedReviewItem(
                id=f"residual_mixed_review_{len(reviews) + 1:04d}",
                source_image_id=source_image_id,
                source_visual_evidence_item_id=item_id,
                source_m2913_conflict_id=str(conflict.get("id") or "") if conflict else None,
                source_m2907_ownership_decision_id=str(ownership.get("id") or "") if ownership else None,
                bbox=bbox,
                m2913_classification=str(conflict.get("classification") or "") if conflict else None,
                review_conclusion=conclusion,
                recommended_next_stage=next_stage,
                should_tighten_m2903=tighten,
                should_adjust_m2913=adjust,
                candidate_for_future_uncertain_review=future,
                allowed_for_promotion_now=False,
                allowed_for_visual_side_now=False,
                allowed_for_formal_asset_now=False,
                signals=signals,
                reasons=dedupe_strings(reasons),
                risks=dedupe_strings(risks),
                example_crop_path=None,
            )
        )
    return reviews


def build_signals(
    item: dict[str, Any],
    bbox: list[int],
    lineage: dict[str, Any],
    conflict: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    matched_text: list[dict[str, Any]],
    all_text_boxes: list[dict[str, Any]],
    matched_findings: list[dict[str, Any]],
    all_mixed_bboxes: list[list[int]],
    pixels: PngPixels,
    options: M29032Options,
) -> ResidualMixedSignals:
    text_overlap = overlap_with_text_union(bbox, matched_text, denominator="bbox")
    text_cover = overlap_with_text_union(bbox, matched_text, denominator="text")
    full_ocr_coverage = text_overlap >= options.full_ocr_coverage_min or text_cover >= options.full_ocr_coverage_min
    partial_ocr_overlap = text_overlap >= options.partial_ocr_overlap_min and not full_ocr_coverage
    if not matched_text:
        ocr_kind: OcrCoverageKind = "none"
    elif full_ocr_coverage:
        ocr_kind = "full_ocr_coverage"
    elif len(matched_text) > 1:
        ocr_kind = "multiple_text_overlap"
    elif partial_ocr_overlap:
        ocr_kind = "partial_ocr_overlap"
    else:
        ocr_kind = "single_text_overlap"
    text_preview = " ".join(str(text.get("text") or "") for text in matched_text).strip()
    aspect = bbox[2] / max(1, bbox[3])
    text_like_aspect = aspect >= options.text_like_aspect_min
    finding_kinds = {str(finding.get("findingKind") or "") for finding in matched_findings}
    conflict_signals = conflict.get("signals", {}) if isinstance(conflict, dict) else {}
    glyph_sequence = (
        bool(conflict_signals.get("glyphSequenceRisk"))
        or "text_like_glyph_sequence" in finding_kinds
        or text_like_aspect
        or is_single_text_like_token(text_preview)
        or has_baseline_stroke_pattern(candidates, bbox)
    )
    metrics = measure_region(pixels, bbox)
    compact = max(bbox[2], bbox[3]) <= options.compact_max_edge and bbox_area(bbox) <= options.compact_max_area
    visual_structure = metrics.edge_score >= 0.18 and metrics.fill_ratio >= 0.08 and compact and not text_like_aspect
    classification = str(conflict.get("classification") or "") if conflict else ""
    return ResidualMixedSignals(
        lineage_strength=str(lineage.get("lineageStrength") or conflict_signals.get("lineageStrength") or "weak"),
        lineage_source=str(lineage.get("lineageSource") or conflict_signals.get("lineageSource") or "unknown"),
        ocr_coverage_kind=ocr_kind,
        text_like_token=is_single_text_like_token(text_preview),
        glyph_sequence_risk=glyph_sequence,
        text_like_aspect_risk=text_like_aspect,
        full_ocr_coverage=full_ocr_coverage,
        partial_ocr_overlap=partial_ocr_overlap,
        label_adjacent_relation=has_label_adjacent_relation(bbox, all_text_boxes, options),
        repeated_compact_alignment=has_repeated_compact_alignment(bbox, all_mixed_bboxes, options),
        duplicate_topology_count=count_duplicate_topology(bbox, all_mixed_bboxes, options),
        visual_structure_hint=visual_structure,
        m2913_text_rejected=classification == "text_owned_rejected_lineage",
        m2913_future_promotable=classification == "future_promotable_uncertain_symbol_candidate",
    )


def classify_review(
    conflict: dict[str, Any] | None,
    signals: ResidualMixedSignals,
) -> tuple[ReviewConclusion, RecommendedNextStage, bool, bool, bool, list[str], list[str]]:
    reasons = ["residual_mixed_after_m29031"]
    risks = ["lineage_conflict"]
    if conflict is None:
        return "insufficient_evidence", "keep_audit_only", False, False, False, [*reasons, "missing_m2913_conflict"], [*risks, "insufficient_evidence"]
    text_counter_evidence = [
        signals.full_ocr_coverage,
        signals.text_like_token,
        signals.text_like_aspect_risk,
        signals.glyph_sequence_risk,
        signals.lineage_strength == "weak" and signals.lineage_source == "eligible_blocked",
    ]
    text_counter_count = sum(1 for value in text_counter_evidence if value)
    visual_review_signals = [
        signals.partial_ocr_overlap and not signals.full_ocr_coverage,
        not signals.glyph_sequence_risk,
        not signals.text_like_token,
        not signals.text_like_aspect_risk,
        signals.repeated_compact_alignment or signals.label_adjacent_relation,
        signals.duplicate_topology_count > 0 or signals.visual_structure_hint,
    ]
    visual_review_count = sum(1 for value in visual_review_signals if value)
    if signals.m2913_text_rejected:
        reasons.append("m2913_text_rejected_lineage")
        if text_counter_count:
            reasons.append("m2903_readable_text_counter_evidence")
            risks.append("text_contamination_possible")
            return "m2903_tightening_candidate", "consider_m2903_text_counter_evidence", True, False, False, reasons, risks
        reasons.append("m2913_text_rejected_without_m2903_readable_counter_evidence")
        return "m2913_classification_adjustment_candidate", "consider_m2913_audit_adjustment", False, True, False, reasons, risks
    if signals.m2913_future_promotable:
        reasons.append("m2913_future_review_candidate")
        if text_counter_count >= 2:
            reasons.append("future_candidate_has_text_like_risk")
            risks.append("text_contamination_possible")
            return "m2913_classification_adjustment_candidate", "consider_m2913_audit_adjustment", False, True, False, reasons, risks
        if visual_review_count >= 4:
            reasons.append("future_uncertain_review_candidate")
            return "candidate_for_future_uncertain_review", "future_uncertain_review_only", False, False, True, reasons, risks
    reasons.append("signals_remain_conflicted")
    if text_counter_count:
        risks.append("text_contamination_possible")
    if visual_review_count < 4:
        risks.append("insufficient_future_review_support")
    return "keep_residual_mixed_conflict", "keep_audit_only", False, False, False, reasons, risks


def collect_text_boxes(m2902_document: dict[str, Any], width: int, height: int) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for raw in m2902_document.get("textBoxes", []):
        if not isinstance(raw, dict):
            continue
        bbox = parse_bbox(raw.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        boxes.append({"id": str(raw.get("id") or ""), "bbox": bbox, "text": str(raw.get("text") or ""), "confidence": float(raw.get("confidence", 1.0))})
    return boxes


def index_m2913_conflicts(m2913_document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(conflict.get("sourceVisualEvidenceItemId")): conflict
        for conflict in m2913_document.get("conflicts", [])
        if isinstance(conflict, dict) and conflict.get("sourceVisualEvidenceItemId")
    }


def index_m2907_decisions(m2907_document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(decision.get("sourceVisualEvidenceItemId")): decision
        for decision in m2907_document.get("ownershipDecisions", [])
        if isinstance(decision, dict) and decision.get("sourceVisualEvidenceItemId")
    }


def overlapping_text_boxes(bbox: list[int], text_boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [text for text in text_boxes if intersection_area(bbox, text["bbox"]) > 0]


def matching_m2911_findings(item_id: str, bbox: list[int], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = [finding for finding in findings if str(finding.get("matchedM2903VisualEvidenceItemId") or "") == item_id]
    if matches:
        return matches
    return [finding for finding in findings if (other := parse_bbox(finding.get("bbox"))) is not None and max(bbox_iou(bbox, other), intersection_over_smaller(bbox, other)) >= 0.55]


def overlap_with_text_union(bbox: list[int], text_boxes: list[dict[str, Any]], *, denominator: Literal["bbox", "text"]) -> float:
    if not text_boxes:
        return 0.0
    total = sum(intersection_area(bbox, text["bbox"]) for text in text_boxes)
    if denominator == "text":
        return total / max(1, sum(bbox_area(text["bbox"]) for text in text_boxes))
    return total / max(1, bbox_area(bbox))


def intersection_area(left: list[int], right: list[int]) -> int:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    return max(0, x2 - x1) * max(0, y2 - y1)


def intersection_over_smaller(left: list[int], right: list[int]) -> float:
    return intersection_area(left, right) / max(1, min(bbox_area(left), bbox_area(right)))


def is_single_text_like_token(text: str) -> bool:
    value = text.strip()
    if not value:
        return False
    compact = "".join(value.split())
    if len(compact) <= 1:
        return True
    return all(char.isdigit() or char in string.punctuation or char in "￥¥$%元人课分秒时天月年" for char in compact)


def has_baseline_stroke_pattern(candidates: list[dict[str, Any]], bbox: list[int]) -> bool:
    if len(candidates) < 3:
        return False
    centers = []
    for candidate in candidates:
        candidate_bbox = parse_bbox(candidate.get("bbox"))
        if candidate_bbox is not None:
            centers.append(candidate_bbox[1] + candidate_bbox[3] / 2)
    if len(centers) < 3:
        return False
    return max(centers) - min(centers) <= max(3, bbox[3] * 0.35) and bbox[2] / max(1, bbox[3]) >= 2.8


def count_duplicate_topology(bbox: list[int], all_bboxes: list[list[int]], options: M29032Options) -> int:
    count = 0
    skipped_self = False
    for other in all_bboxes:
        if not skipped_self and other == bbox:
            skipped_self = True
            continue
        size_close = abs(bbox[2] - other[2]) <= max(4, min(bbox[2], other[2]) * 0.25) and abs(bbox[3] - other[3]) <= max(4, min(bbox[3], other[3]) * 0.25)
        if size_close or bbox_iou(bbox, other) >= options.duplicate_iou_min:
            count += 1
    return count


def has_repeated_compact_alignment(bbox: list[int], all_bboxes: list[list[int]], options: M29032Options) -> bool:
    aligned = 0
    center_y = bbox[1] + bbox[3] / 2
    center_x = bbox[0] + bbox[2] / 2
    for other in all_bboxes:
        if other == bbox:
            continue
        if max(other[2], other[3]) > options.compact_max_edge or bbox_area(other) > options.compact_max_area:
            continue
        other_y = other[1] + other[3] / 2
        other_x = other[0] + other[2] / 2
        if abs(center_y - other_y) <= options.repeated_alignment_tolerance or abs(center_x - other_x) <= options.repeated_alignment_tolerance:
            aligned += 1
    return aligned >= 2


def has_label_adjacent_relation(bbox: list[int], text_boxes: list[dict[str, Any]], options: M29032Options) -> bool:
    for text in text_boxes:
        other = text["bbox"]
        vertical_gap = max(0, max(bbox[1], other[1]) - min(bbox[1] + bbox[3], other[1] + other[3]))
        horizontal_gap = max(0, max(bbox[0], other[0]) - min(bbox[0] + bbox[2], other[0] + other[2]))
        if vertical_gap <= options.label_adjacency_max_gap and horizontal_gap <= max(options.label_adjacency_max_gap, bbox[2]):
            return True
    return False


def export_review_examples(pixels: PngPixels, output_dir: Path, reviews: list[ResidualMixedReviewItem], options: M29032Options) -> None:
    folder_by_conclusion = {
        "m2903_tightening_candidate": "tightening_candidates",
        "m2913_classification_adjustment_candidate": "text_rejected_review",
        "keep_residual_mixed_conflict": "keep_mixed_review",
        "candidate_for_future_uncertain_review": "future_promotable_review",
        "insufficient_evidence": "insufficient_evidence",
    }
    counts: dict[str, int] = {}
    for index, review in enumerate(reviews):
        count = counts.get(review.review_conclusion, 0)
        if count >= options.max_examples_per_conclusion:
            continue
        counts[review.review_conclusion] = count + 1
        folder = folder_by_conclusion[review.review_conclusion]
        target_dir = output_dir / "assets" / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{review.review_conclusion}_{count + 1:04d}_{review.id}.png"
        path.write_bytes(crop_pixels(pixels, review.bbox))
        reviews[index] = ResidualMixedReviewItem(**{**review.__dict__, "example_crop_path": str(path.relative_to(output_dir))})


def write_review_sheet(pixels: PngPixels, output_dir: Path, reviews: list[ResidualMixedReviewItem]) -> str:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {
        "m2903_tightening_candidate": (235, 64, 52),
        "m2913_classification_adjustment_candidate": (180, 80, 220),
        "keep_residual_mixed_conflict": (238, 190, 40),
        "candidate_for_future_uncertain_review": (0, 120, 255),
        "insufficient_evidence": (120, 120, 120),
    }
    for review in reviews:
        draw_rect(rows, pixels.width, pixels.height, review.bbox, colors[review.review_conclusion], 2)
    path = output_dir / "review_sheet_remaining_mixed.png"
    path.write_bytes(encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows]))
    return str(path.relative_to(output_dir))


def build_summary(reviews: list[ResidualMixedReviewItem], m2907_document: dict[str, Any] | None, m2902_document: dict[str, Any] | None) -> dict[str, Any]:
    counts = count_by([review.review_conclusion for review in reviews])
    m2913_counts = count_by([review.m2913_classification or "missing" for review in reviews])
    bad_routing = 0
    for decision in (m2907_document or {}).get("ownershipDecisions", []):
        if not isinstance(decision, dict) or decision.get("sourceVisualKind") != "mixed_symbol_text_candidate":
            continue
        if decision.get("ownership") != "mixed_or_uncertain" or decision.get("allowedForObjectFormingVisualSide") is not False:
            bad_routing += 1
    return {
        "residualMixedCount": len(reviews),
        "m2903TighteningCandidateCount": counts.get("m2903_tightening_candidate", 0),
        "m2913AdjustmentCandidateCount": counts.get("m2913_classification_adjustment_candidate", 0),
        "keepResidualMixedCount": counts.get("keep_residual_mixed_conflict", 0),
        "futureUncertainReviewCandidateCount": counts.get("candidate_for_future_uncertain_review", 0),
        "insufficientEvidenceCount": counts.get("insufficient_evidence", 0),
        "m2913FutureCount": m2913_counts.get("future_promotable_uncertain_symbol_candidate", 0),
        "m2913KeepCount": m2913_counts.get("keep_mixed_symbol_text_conflict", 0),
        "m2913TextRejectedCount": m2913_counts.get("text_owned_rejected_lineage", 0),
        "badRoutingCountFromM2907": bad_routing,
        "sourceTextBoxCountFromM2902": len((m2902_document or {}).get("textBoxes", [])),
        "byReviewConclusion": counts,
        "byM2913Classification": m2913_counts,
    }


def write_outputs(document: M29032Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "residual_mixed_boundary_review.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "residual_mixed_boundary_review.md").write_text(build_markdown_report(document), encoding="utf-8")


def build_markdown_report(document: M29032Document) -> str:
    lines = [
        "# M29.0.3.2 Residual Mixed Boundary Review",
        "",
        f"- Source M29.0.3: `{document.source_m2903_visual_evidence_json}`",
        f"- Reviews: {len(document.reviews)}",
        f"- By review conclusion: `{document.summary.get('byReviewConclusion', {})}`",
        "- Note: example crops are audit evidence, not formal visual assets.",
        "- Note: this document is not a routing contract.",
        "",
        "## Reviews",
        "",
    ]
    for review in document.reviews[:220]:
        lines.append(
            f"- `{review.id}` `{review.review_conclusion}` next=`{review.recommended_next_stage}` "
            f"bbox={review.bbox} m2903=`{review.source_visual_evidence_item_id}` "
            f"m2913=`{review.m2913_classification}` reasons={','.join(review.reasons[:4])}"
        )
    return "\n".join(lines).rstrip() + "\n"


def validate_m29032_document(document: M29032Document, output_dir: Path, width: int, height: int) -> None:
    if document.schema_name != "M29032ResidualMixedBoundaryReviewDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.3.2 document schema")
    ids: set[str] = set()
    for review in document.reviews:
        if review.id in ids:
            raise ValueError(f"duplicate M29.0.3.2 review id: {review.id}")
        ids.add(review.id)
        if not bbox_in_bounds(review.bbox, width, height):
            raise ValueError(f"M29.0.3.2 review bbox out of bounds: {review.id}")
        if review.allowed_for_promotion_now or review.allowed_for_visual_side_now or review.allowed_for_formal_asset_now:
            raise ValueError(f"M29.0.3.2 review has forbidden downstream permission: {review.id}")
        if review.example_crop_path:
            assert_readable_relative_png(output_dir, review.example_crop_path)
    metadata = assert_readable_relative_png(output_dir, document.debug.review_sheet_remaining_mixed)
    if metadata.width != width or metadata.height != height:
        raise ValueError("M29.0.3.2 review sheet dimensions do not match source image")
    serialized = json.dumps(document.to_dict(), ensure_ascii=False).lower()
    for term in find_forbidden_contract_terms(serialized):
        raise ValueError(f"M29.0.3.2 output contains forbidden contract term: {term}")


def assert_readable_relative_png(output_dir: Path, path: str):
    resolved = output_dir / path
    metadata = read_png_metadata(resolved.read_bytes()) if resolved.exists() else None
    if metadata is None:
        raise ValueError(f"M29.0.3.2 PNG output missing or unreadable: {path}")
    return metadata


def build_batch_summary(
    image_documents: list[tuple[str, M29032Document]],
    output_dir: Path,
    *,
    failures: list[dict[str, Any]] | None = None,
    m2905_by_image: dict[str, dict[str, Any]] | None = None,
    m2906_by_image: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    failures_by_image = {str(item.get("imageId")): item for item in failures or []}
    for image_id, document in image_documents:
        summary = document.summary
        m2905 = (m2905_by_image or {}).get(image_id, {})
        m2906 = (m2906_by_image or {}).get(image_id, {})
        m2905_summary = m2905.get("summary", {}) if isinstance(m2905.get("summary"), dict) else {}
        m2906_summary = m2906.get("summary", {}) if isinstance(m2906.get("summary"), dict) else {}
        rows.append(
            {
                "imageId": image_id,
                "sourceImage": document.source_image,
                "residualMixedCount": summary.get("residualMixedCount", 0),
                "m2903TighteningCandidateCount": summary.get("m2903TighteningCandidateCount", 0),
                "m2913AdjustmentCandidateCount": summary.get("m2913AdjustmentCandidateCount", 0),
                "keepResidualMixedCount": summary.get("keepResidualMixedCount", 0),
                "futureUncertainReviewCandidateCount": summary.get("futureUncertainReviewCandidateCount", 0),
                "insufficientEvidenceCount": summary.get("insufficientEvidenceCount", 0),
                "m2913FutureCount": summary.get("m2913FutureCount", 0),
                "m2913KeepCount": summary.get("m2913KeepCount", 0),
                "m2913TextRejectedCount": summary.get("m2913TextRejectedCount", 0),
                "badRoutingCountFromM2907": summary.get("badRoutingCountFromM2907", 0),
                "visualAssetCountFromM2905": m2905_summary.get("visualAssetCount", len(m2905.get("visualAssets", []))),
                "textMemberCountFromM2905": m2905_summary.get("textMemberCount", len(m2905.get("textMembers", []))),
                "weakTextNoiseRatioFromM2906": m2906_summary.get("weakTextNoiseUnresolvedRatio", 0),
                "failedStage": "",
                "error": "",
            }
        )
    for image_id, failure in failures_by_image.items():
        rows.append(
            {
                "imageId": image_id,
                "sourceImage": failure.get("sourceImage", ""),
                "residualMixedCount": 0,
                "m2903TighteningCandidateCount": 0,
                "m2913AdjustmentCandidateCount": 0,
                "keepResidualMixedCount": 0,
                "futureUncertainReviewCandidateCount": 0,
                "insufficientEvidenceCount": 0,
                "m2913FutureCount": 0,
                "m2913KeepCount": 0,
                "m2913TextRejectedCount": 0,
                "badRoutingCountFromM2907": 0,
                "visualAssetCountFromM2905": 0,
                "textMemberCountFromM2905": 0,
                "weakTextNoiseRatioFromM2906": 0,
                "failedStage": failure.get("failedStage", "unknown"),
                "error": failure.get("error", ""),
            }
        )
    rows = sorted(rows, key=lambda item: item["imageId"])
    totals = {
        "totalImages": len(rows),
        "completedImages": len(image_documents),
        "failedImages": len(failures or []),
        "partialFailureCount": len(failures or []),
        "totalResidualMixed": sum(int(row["residualMixedCount"]) for row in rows),
        "totalTighteningCandidates": sum(int(row["m2903TighteningCandidateCount"]) for row in rows),
        "totalM2913AdjustmentCandidates": sum(int(row["m2913AdjustmentCandidateCount"]) for row in rows),
        "totalFutureReviewCandidates": sum(int(row["futureUncertainReviewCandidateCount"]) for row in rows),
        "totalKeepResidualMixed": sum(int(row["keepResidualMixedCount"]) for row in rows),
        "totalInsufficientEvidence": sum(int(row["insufficientEvidenceCount"]) for row in rows),
        "maxWeakTextNoiseRatio": max([float(row["weakTextNoiseRatioFromM2906"]) for row in rows], default=0),
        "totalBadRouting": sum(int(row["badRoutingCountFromM2907"]) for row in rows),
        "totalVisualAssets": sum(int(row["visualAssetCountFromM2905"]) for row in rows),
        "totalTextMembers": sum(int(row["textMemberCountFromM2905"]) for row in rows),
    }
    payload = {"schemaName": "M29032ResidualMixedBoundaryReviewBatchSummary", "schemaVersion": "0.1", "totals": totals, "rows": rows}
    (output_dir / "m29_0_3_2_batch_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "m29_0_3_2_batch_summary.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()) if rows else ["imageId"])
        writer.writeheader()
        writer.writerows(rows)
    return payload


def count_by(items: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def dedupe_strings(items: list[str]) -> list[str]:
    output: list[str] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output
