from __future__ import annotations

import csv
import json
import re
import string
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngPixels, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_evidence_normalization import parse_bbox
from .visual_primitive_graph import bbox_area, bbox_in_bounds, bbox_iou, crop_pixels, draw_rect, measure_region


ConflictClassification = Literal[
    "future_promotable_uncertain_symbol_candidate",
    "keep_mixed_symbol_text_conflict",
    "text_owned_rejected_lineage",
]
ConfidenceLevel = Literal["low", "medium", "high"]
OcrCoverageKind = Literal["none", "partial_ocr_overlap", "full_ocr_coverage", "single_text_overlap", "multiple_text_overlap"]

FORBIDDEN_CONTRACT_TERMS = {
    "bottom_nav",
    "tab",
    "toolbar",
    "grid",
    "ecommerce",
    "education",
    "recoverable_icon",
    "promotable_icon",
    "icon_recovery",
    "restore",
}


@dataclass(frozen=True)
class M2913Options:
    full_ocr_coverage_min: float = 0.72
    partial_ocr_overlap_min: float = 0.08
    text_like_aspect_min: float = 3.5
    compact_max_edge: int = 128
    compact_max_area: int = 14000
    repeated_alignment_tolerance: int = 8
    label_adjacency_max_gap: int = 40
    duplicate_iou_min: float = 0.65
    max_examples_per_classification: int = 40

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConflictSignals:
    lineage_strength: str
    lineage_source: str
    compact_geometry: bool
    ocr_coverage_kind: OcrCoverageKind
    glyph_sequence_risk: bool
    repeated_compact_alignment: bool
    label_adjacent_relation: bool
    duplicate_topology_count: int
    visual_structure_hint: bool
    text_like_aspect_risk: bool
    full_ocr_coverage: bool
    partial_ocr_overlap: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineageStrength": self.lineage_strength,
            "lineageSource": self.lineage_source,
            "compactGeometry": self.compact_geometry,
            "ocrCoverageKind": self.ocr_coverage_kind,
            "glyphSequenceRisk": self.glyph_sequence_risk,
            "repeatedCompactAlignment": self.repeated_compact_alignment,
            "labelAdjacentRelation": self.label_adjacent_relation,
            "duplicateTopologyCount": self.duplicate_topology_count,
            "visualStructureHint": self.visual_structure_hint,
            "textLikeAspectRisk": self.text_like_aspect_risk,
            "fullOcrCoverage": self.full_ocr_coverage,
            "partialOcrOverlap": self.partial_ocr_overlap,
        }


@dataclass(frozen=True)
class MixedSymbolTextConflict:
    id: str
    source_visual_evidence_item_id: str
    source_evidence_id: str | None
    source_m291_group_id: str | None
    source_m291_candidate_ids: list[str]
    source_m2911_finding_ids: list[str]
    source_m2907_ownership_decision_id: str | None
    bbox: list[int]
    classification: ConflictClassification
    classification_confidence: ConfidenceLevel
    promotion_risk: ConfidenceLevel
    text_contamination_risk: ConfidenceLevel
    allowed_for_current_promotion: bool
    allowed_for_object_forming_visual_side: bool
    allowed_for_formal_visual_asset: bool
    allowed_for_routing_change: bool
    signals: ConflictSignals
    reasons: list[str]
    risks: list[str]
    example_asset_paths: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceVisualEvidenceItemId": self.source_visual_evidence_item_id,
            "sourceEvidenceId": self.source_evidence_id,
            "sourceM291GroupId": self.source_m291_group_id,
            "sourceM291CandidateIds": self.source_m291_candidate_ids,
            "sourceM2911FindingIds": self.source_m2911_finding_ids,
            "sourceM2907OwnershipDecisionId": self.source_m2907_ownership_decision_id,
            "bbox": self.bbox,
            "classification": self.classification,
            "classificationConfidence": self.classification_confidence,
            "promotionRisk": self.promotion_risk,
            "textContaminationRisk": self.text_contamination_risk,
            "allowedForCurrentPromotion": self.allowed_for_current_promotion,
            "allowedForObjectFormingVisualSide": self.allowed_for_object_forming_visual_side,
            "allowedForFormalVisualAsset": self.allowed_for_formal_visual_asset,
            "allowedForRoutingChange": self.allowed_for_routing_change,
            "signals": self.signals.to_dict(),
            "reasons": self.reasons,
            "risks": self.risks,
            "exampleAssetPaths": self.example_asset_paths,
        }


@dataclass(frozen=True)
class M2913DebugArtifacts:
    mixed_symbol_text_conflicts: str

    def to_dict(self) -> dict[str, str]:
        return {"mixedSymbolTextConflicts": self.mixed_symbol_text_conflicts}


@dataclass(frozen=True)
class M2913Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_m2903_visual_evidence_json: str
    source_m2907_ownership_json: str | None
    source_m291_group_nodes_json: str | None
    source_m2911_lineage_audit_json: str | None
    source_m2902_audit_json: str | None
    options: M2913Options
    conflicts: list[MixedSymbolTextConflict]
    summary: dict[str, Any]
    debug: M2913DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM2903VisualEvidenceJson": self.source_m2903_visual_evidence_json,
            "sourceM2907OwnershipJson": self.source_m2907_ownership_json,
            "sourceM291GroupNodesJson": self.source_m291_group_nodes_json,
            "sourceM2911LineageAuditJson": self.source_m2911_lineage_audit_json,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "options": self.options.to_dict(),
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "summary": self.summary,
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }


def extract_mixed_symbol_text_conflict_audit(
    *,
    png_data: bytes,
    source_image: str,
    m2903_document: dict[str, Any],
    m2903_visual_evidence_json_path: str,
    output_dir: Path,
    m2907_document: dict[str, Any] | None = None,
    m2907_ownership_json_path: str | None = None,
    m291_document: dict[str, Any] | None = None,
    m291_group_nodes_json_path: str | None = None,
    m2911_document: dict[str, Any] | None = None,
    m2911_lineage_audit_json_path: str | None = None,
    m2902_document: dict[str, Any] | None = None,
    m2902_audit_json_path: str | None = None,
    options: M2913Options | None = None,
    warnings: list[str] | None = None,
) -> M2913Document:
    options = options or M2913Options()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    text_boxes = collect_text_boxes(m2902_document or {}, pixels.width, pixels.height)
    m2907_by_item_id = index_m2907_decisions(m2907_document or {})
    m291_groups_by_id = {str(group.get("id")): group for group in (m291_document or {}).get("groups", []) if isinstance(group, dict)}
    m291_candidates_by_id = {str(candidate.get("id")): candidate for candidate in (m291_document or {}).get("candidates", []) if isinstance(candidate, dict)}
    m2911_findings = [item for item in (m2911_document or {}).get("findings", []) if isinstance(item, dict)]
    mixed_items = [item for item in m2903_document.get("items", []) if isinstance(item, dict) and item.get("visualKind") == "mixed_symbol_text_candidate"]
    conflicts = build_conflicts(
        mixed_items=mixed_items,
        text_boxes=text_boxes,
        m2907_by_item_id=m2907_by_item_id,
        m291_groups_by_id=m291_groups_by_id,
        m291_candidates_by_id=m291_candidates_by_id,
        m2911_findings=m2911_findings,
        pixels=pixels,
        options=options,
    )
    export_examples(pixels, output_dir, conflicts, options)
    overlay_path = write_overlay(pixels, output_dir, conflicts)
    document = M2913Document(
        schema_name="M2913MixedSymbolTextConflictAuditDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m2903_visual_evidence_json=m2903_visual_evidence_json_path,
        source_m2907_ownership_json=m2907_ownership_json_path,
        source_m291_group_nodes_json=m291_group_nodes_json_path,
        source_m2911_lineage_audit_json=m2911_lineage_audit_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        options=options,
        conflicts=conflicts,
        summary=build_summary(conflicts, m2907_document),
        debug=M2913DebugArtifacts(mixed_symbol_text_conflicts=overlay_path),
        warnings=warnings or [],
        meta={"notes": "m29_1_3_mixed_symbol_text_conflict_classification_audit", "conflictCount": len(conflicts)},
    )
    validate_m2913_document(document, output_dir, pixels.width, pixels.height)
    write_outputs(document, output_dir)
    return document


def build_conflicts(
    *,
    mixed_items: list[dict[str, Any]],
    text_boxes: list[dict[str, Any]],
    m2907_by_item_id: dict[str, dict[str, Any]],
    m291_groups_by_id: dict[str, dict[str, Any]],
    m291_candidates_by_id: dict[str, dict[str, Any]],
    m2911_findings: list[dict[str, Any]],
    pixels: PngPixels,
    options: M2913Options,
) -> list[MixedSymbolTextConflict]:
    conflicts: list[MixedSymbolTextConflict] = []
    all_mixed_bboxes = [parse_bbox(item.get("bbox")) for item in mixed_items]
    all_mixed_bboxes = [bbox for bbox in all_mixed_bboxes if bbox is not None]
    for item in mixed_items:
        bbox = parse_bbox(item.get("bbox"))
        item_id = str(item.get("id") or "")
        if bbox is None or not item_id or not bbox_in_bounds(bbox, pixels.width, pixels.height):
            continue
        lineage = item.get("sourceLineage") if isinstance(item.get("sourceLineage"), dict) else {}
        group_id = str(lineage.get("m291GroupId") or "") or None
        candidate_ids = [str(value) for value in lineage.get("m291CandidateIds", []) if value]
        if not candidate_ids:
            candidate_id = str(lineage.get("sourceOwnerId") or "")
            candidate_ids = [candidate_id] if candidate_id else []
        m291_group = m291_groups_by_id.get(group_id or "")
        m291_candidates = [m291_candidates_by_id[candidate_id] for candidate_id in candidate_ids if candidate_id in m291_candidates_by_id]
        matched_text = overlapping_text_boxes(bbox, text_boxes)
        matched_findings = matching_m2911_findings(item_id, bbox, m2911_findings)
        signals = build_signals(item, bbox, lineage, m291_group, m291_candidates, matched_text, text_boxes, matched_findings, all_mixed_bboxes, pixels, options)
        classification, confidence, promotion_risk, text_risk, reasons, risks = classify_conflict(item, lineage, signals, matched_text, matched_findings)
        conflicts.append(
            MixedSymbolTextConflict(
                id=f"mixed_conflict_{len(conflicts) + 1:04d}",
                source_visual_evidence_item_id=item_id,
                source_evidence_id=str(item.get("sourceEvidenceId") or "") or None,
                source_m291_group_id=group_id,
                source_m291_candidate_ids=candidate_ids,
                source_m2911_finding_ids=[str(finding.get("id")) for finding in matched_findings if finding.get("id")],
                source_m2907_ownership_decision_id=str(m2907_by_item_id.get(item_id, {}).get("id") or "") or None,
                bbox=bbox,
                classification=classification,
                classification_confidence=confidence,
                promotion_risk=promotion_risk,
                text_contamination_risk=text_risk,
                allowed_for_current_promotion=False,
                allowed_for_object_forming_visual_side=False,
                allowed_for_formal_visual_asset=False,
                allowed_for_routing_change=False,
                signals=signals,
                reasons=dedupe_strings(reasons),
                risks=dedupe_strings(risks),
                example_asset_paths=[],
            )
        )
    return conflicts


def build_signals(
    item: dict[str, Any],
    bbox: list[int],
    lineage: dict[str, Any],
    m291_group: dict[str, Any] | None,
    m291_candidates: list[dict[str, Any]],
    matched_text: list[dict[str, Any]],
    all_text_boxes: list[dict[str, Any]],
    matched_findings: list[dict[str, Any]],
    all_mixed_bboxes: list[list[int]],
    pixels: PngPixels,
    options: M2913Options,
) -> ConflictSignals:
    text_overlap = overlap_with_text_union(bbox, matched_text, denominator="bbox")
    text_cover = overlap_with_text_union(bbox, matched_text, denominator="text")
    full_ocr_coverage = text_overlap >= options.full_ocr_coverage_min or text_cover >= options.full_ocr_coverage_min
    partial_ocr_overlap = text_overlap >= options.partial_ocr_overlap_min and not full_ocr_coverage
    ocr_kind: OcrCoverageKind
    if not matched_text:
        ocr_kind = "none"
    elif full_ocr_coverage:
        ocr_kind = "full_ocr_coverage"
    elif len(matched_text) > 1:
        ocr_kind = "multiple_text_overlap"
    elif partial_ocr_overlap:
        ocr_kind = "partial_ocr_overlap"
    else:
        ocr_kind = "single_text_overlap"
    aspect = bbox[2] / max(1, bbox[3])
    text_like_aspect = aspect >= options.text_like_aspect_min
    finding_kinds = {str(finding.get("findingKind") or "") for finding in matched_findings}
    text_preview = " ".join(str(text.get("text") or "") for text in matched_text).strip()
    glyph_sequence = (
        "text_like_glyph_sequence" in finding_kinds
        or text_like_aspect
        or is_single_text_like_token(text_preview)
        or has_baseline_stroke_pattern(m291_candidates, bbox)
    )
    metrics = measure_region(pixels, bbox)
    compact = max(bbox[2], bbox[3]) <= options.compact_max_edge and bbox_area(bbox) <= options.compact_max_area
    visual_structure = metrics.edge_score >= 0.18 and metrics.fill_ratio >= 0.08 and not text_like_aspect
    duplicate_count = count_duplicate_topology(bbox, all_mixed_bboxes, options)
    repeated_alignment = has_repeated_compact_alignment(bbox, all_mixed_bboxes, options)
    label_adjacent = has_label_adjacent_relation(bbox, all_text_boxes, options)
    return ConflictSignals(
        lineage_strength=str(lineage.get("lineageStrength") or "weak"),
        lineage_source=str(lineage.get("lineageSource") or "unknown"),
        compact_geometry=compact,
        ocr_coverage_kind=ocr_kind,
        glyph_sequence_risk=glyph_sequence,
        repeated_compact_alignment=repeated_alignment,
        label_adjacent_relation=label_adjacent,
        duplicate_topology_count=duplicate_count,
        visual_structure_hint=visual_structure,
        text_like_aspect_risk=text_like_aspect,
        full_ocr_coverage=full_ocr_coverage,
        partial_ocr_overlap=partial_ocr_overlap,
    )


def classify_conflict(
    item: dict[str, Any],
    lineage: dict[str, Any],
    signals: ConflictSignals,
    matched_text: list[dict[str, Any]],
    matched_findings: list[dict[str, Any]],
) -> tuple[ConflictClassification, ConfidenceLevel, ConfidenceLevel, ConfidenceLevel, list[str], list[str]]:
    reasons = ["mixed_symbol_text_conflict_audit", "pre_ocr_symbol_lineage"]
    risks = ["lineage_conflict"]
    finding_kinds = {str(finding.get("findingKind") or "") for finding in matched_findings}
    text_preview = " ".join(str(text.get("text") or "") for text in matched_text).strip()
    if (
        signals.full_ocr_coverage
        or signals.glyph_sequence_risk
        or "text_like_glyph_sequence" in finding_kinds
        or (signals.lineage_strength == "weak" and signals.lineage_source == "eligible_blocked")
    ):
        reasons.append("text_ownership_counter_evidence")
        if signals.full_ocr_coverage:
            reasons.append("full_ocr_coverage")
        if signals.glyph_sequence_risk:
            reasons.append("glyph_sequence_risk")
        if is_single_text_like_token(text_preview):
            reasons.append("single_text_like_token")
        risks.append("text_contamination_possible")
        return "text_owned_rejected_lineage", "high" if signals.full_ocr_coverage or "text_like_glyph_sequence" in finding_kinds else "medium", "high", "low", reasons, risks
    promotable_signals = [
        signals.lineage_strength in {"strong", "medium"},
        signals.lineage_source in {"m291_group", "m29_symbol"},
        signals.compact_geometry,
        signals.partial_ocr_overlap,
        not signals.full_ocr_coverage,
        not signals.glyph_sequence_risk,
        signals.repeated_compact_alignment or signals.label_adjacent_relation or signals.duplicate_topology_count > 1,
        signals.visual_structure_hint,
    ]
    if all(promotable_signals):
        reasons.extend(["future_review_candidate", "compact_geometry", "partial_ocr_overlap"])
        if signals.repeated_compact_alignment:
            reasons.append("repeated_compact_alignment")
        if signals.label_adjacent_relation:
            reasons.append("label_adjacent_relation")
        return "future_promotable_uncertain_symbol_candidate", "medium", "medium", "medium", reasons, risks
    reasons.append("signals_remain_conflicted")
    if not signals.repeated_compact_alignment:
        risks.append("insufficient_repeated_alignment")
    if not signals.label_adjacent_relation:
        risks.append("insufficient_label_adjacent_relation")
    if signals.partial_ocr_overlap:
        risks.append("text_contamination_possible")
    if "pre_ocr_symbol_lineage_preserved" in item.get("reasons", []):
        reasons.append("pre_ocr_symbol_lineage_preserved")
    return "keep_mixed_symbol_text_conflict", "medium", "high", "medium", reasons, risks


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


def index_m2907_decisions(m2907_document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for raw in m2907_document.get("ownershipDecisions", []):
        if isinstance(raw, dict) and raw.get("sourceVisualEvidenceItemId"):
            output[str(raw["sourceVisualEvidenceItemId"])] = raw
    return output


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
    if all(char.isdigit() or char in string.punctuation or char in "￥¥$%元人课分秒时天月年" for char in compact):
        return True
    return False


def has_baseline_stroke_pattern(candidates: list[dict[str, Any]], bbox: list[int]) -> bool:
    if len(candidates) < 3:
        return False
    centers = []
    for candidate in candidates:
        candidate_bbox = parse_bbox(candidate.get("bbox"))
        if candidate_bbox is None:
            continue
        centers.append(candidate_bbox[1] + candidate_bbox[3] / 2)
    if len(centers) < 3:
        return False
    return max(centers) - min(centers) <= max(3, bbox[3] * 0.35) and bbox[2] / max(1, bbox[3]) >= 2.8


def count_duplicate_topology(bbox: list[int], all_bboxes: list[list[int]], options: M2913Options) -> int:
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


def has_repeated_compact_alignment(bbox: list[int], all_bboxes: list[list[int]], options: M2913Options) -> bool:
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


def has_label_adjacent_relation(bbox: list[int], text_boxes: list[dict[str, Any]], options: M2913Options) -> bool:
    for text in text_boxes:
        other = text["bbox"]
        vertical_gap = max(0, max(bbox[1], other[1]) - min(bbox[1] + bbox[3], other[1] + other[3]))
        horizontal_gap = max(0, max(bbox[0], other[0]) - min(bbox[0] + bbox[2], other[0] + other[2]))
        if vertical_gap <= options.label_adjacency_max_gap and horizontal_gap <= max(options.label_adjacency_max_gap, bbox[2]):
            return True
    return False


def export_examples(pixels: PngPixels, output_dir: Path, conflicts: list[MixedSymbolTextConflict], options: M2913Options) -> None:
    folder_by_classification = {
        "future_promotable_uncertain_symbol_candidate": "future_promotable_examples",
        "keep_mixed_symbol_text_conflict": "keep_mixed_examples",
        "text_owned_rejected_lineage": "text_owned_rejected_examples",
    }
    counts: dict[str, int] = {}
    for index, conflict in enumerate(conflicts):
        count = counts.get(conflict.classification, 0)
        if count >= options.max_examples_per_classification:
            continue
        counts[conflict.classification] = count + 1
        folder = folder_by_classification[conflict.classification]
        target_dir = output_dir / "assets" / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{conflict.classification}_{count + 1:04d}_{conflict.id}.png"
        path.write_bytes(crop_pixels(pixels, conflict.bbox))
        conflicts[index] = MixedSymbolTextConflict(**{**conflict.__dict__, "example_asset_paths": [str(path.relative_to(output_dir))]})


def write_overlay(pixels: PngPixels, output_dir: Path, conflicts: list[MixedSymbolTextConflict]) -> str:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {
        "future_promotable_uncertain_symbol_candidate": (0, 120, 255),
        "keep_mixed_symbol_text_conflict": (238, 190, 40),
        "text_owned_rejected_lineage": (235, 64, 52),
    }
    for conflict in conflicts:
        draw_rect(rows, pixels.width, pixels.height, conflict.bbox, colors[conflict.classification], 2)
    path = output_dir / "overlay_mixed_symbol_text_conflicts.png"
    path.write_bytes(encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows]))
    return str(path.relative_to(output_dir))


def build_summary(conflicts: list[MixedSymbolTextConflict], m2907_document: dict[str, Any] | None) -> dict[str, Any]:
    counts = count_by([conflict.classification for conflict in conflicts])
    total = len(conflicts)
    bad_routing = 0
    for decision in (m2907_document or {}).get("ownershipDecisions", []):
        if not isinstance(decision, dict) or decision.get("sourceVisualKind") != "mixed_symbol_text_candidate":
            continue
        if decision.get("ownership") != "mixed_or_uncertain" or decision.get("allowedForObjectFormingVisualSide") is not False:
            bad_routing += 1
    return {
        "mixedCount": total,
        "futurePromotableCount": counts.get("future_promotable_uncertain_symbol_candidate", 0),
        "keepMixedCount": counts.get("keep_mixed_symbol_text_conflict", 0),
        "textRejectedCount": counts.get("text_owned_rejected_lineage", 0),
        "futurePromotableRatio": ratio(counts.get("future_promotable_uncertain_symbol_candidate", 0), total),
        "keepMixedRatio": ratio(counts.get("keep_mixed_symbol_text_conflict", 0), total),
        "textRejectedRatio": ratio(counts.get("text_owned_rejected_lineage", 0), total),
        "futurePromotableExampleCount": example_count(conflicts, "future_promotable_uncertain_symbol_candidate"),
        "keepMixedExampleCount": example_count(conflicts, "keep_mixed_symbol_text_conflict"),
        "textRejectedExampleCount": example_count(conflicts, "text_owned_rejected_lineage"),
        "highRiskPromotionCount": sum(1 for conflict in conflicts if conflict.promotion_risk == "high"),
        "badRoutingCountFromM2907": bad_routing,
        "byClassification": counts,
        "byConfidence": count_by([conflict.classification_confidence for conflict in conflicts]),
    }


def write_outputs(document: M2913Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "mixed_symbol_text_conflict_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "mixed_symbol_text_conflict_audit.md").write_text(build_markdown_report(document), encoding="utf-8")


def build_markdown_report(document: M2913Document) -> str:
    lines = [
        "# M29.1.3 Mixed Symbol/Text Conflict Classification Audit",
        "",
        f"- Source M29.0.3: `{document.source_m2903_visual_evidence_json}`",
        f"- Conflicts: {len(document.conflicts)}",
        f"- By classification: `{document.summary.get('byClassification', {})}`",
        "- Note: example crops are audit evidence, not assets.",
        "",
        "## Conflicts",
        "",
    ]
    for conflict in document.conflicts[:180]:
        lines.append(
            f"- `{conflict.id}` `{conflict.classification}` confidence=`{conflict.classification_confidence}` "
            f"bbox={conflict.bbox} m2903=`{conflict.source_visual_evidence_item_id}` "
            f"reasons={','.join(conflict.reasons[:4])}"
        )
    return "\n".join(lines).rstrip() + "\n"


def validate_m2913_document(document: M2913Document, output_dir: Path, width: int, height: int) -> None:
    if document.schema_name != "M2913MixedSymbolTextConflictAuditDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.1.3 document schema")
    ids: set[str] = set()
    for conflict in document.conflicts:
        if conflict.id in ids:
            raise ValueError(f"duplicate M29.1.3 conflict id: {conflict.id}")
        ids.add(conflict.id)
        if not bbox_in_bounds(conflict.bbox, width, height):
            raise ValueError(f"M29.1.3 conflict bbox out of bounds: {conflict.id}")
        if conflict.allowed_for_current_promotion or conflict.allowed_for_object_forming_visual_side or conflict.allowed_for_formal_visual_asset or conflict.allowed_for_routing_change:
            raise ValueError(f"M29.1.3 conflict has forbidden downstream permission: {conflict.id}")
        for path in conflict.example_asset_paths:
            assert_readable_relative_png(output_dir, path)
    for path in document.debug.to_dict().values():
        metadata = assert_readable_relative_png(output_dir, path)
        if metadata.width != width or metadata.height != height:
            raise ValueError(f"M29.1.3 overlay dimensions do not match source image: {path}")
    serialized = json.dumps(document.to_dict(), ensure_ascii=False).lower()
    for term in find_forbidden_contract_terms(serialized):
        if term:
            raise ValueError(f"M29.1.3 output contains forbidden contract term: {term}")


def assert_readable_relative_png(output_dir: Path, path: str):
    resolved = output_dir / path
    metadata = read_png_metadata(resolved.read_bytes()) if resolved.exists() else None
    if metadata is None:
        raise ValueError(f"M29.1.3 PNG output missing or unreadable: {path}")
    return metadata


def find_forbidden_contract_terms(text: str) -> list[str]:
    hits: list[str] = []
    for term in sorted(FORBIDDEN_CONTRACT_TERMS):
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text):
            hits.append(term)
    return hits


def build_batch_summary(image_documents: list[tuple[str, M2913Document]], output_dir: Path, *, m2905_by_image: dict[str, dict[str, Any]] | None = None, m2906_by_image: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for image_id, document in image_documents:
        summary = document.summary
        visual_asset_count = len((m2905_by_image or {}).get(image_id, {}).get("visualAssets", []))
        weak_ratio = ((m2906_by_image or {}).get(image_id, {}).get("summary", {}) or {}).get("weakTextNoiseUnresolvedRatio", 0)
        row = {
            "imageId": image_id,
            "mixedCount": summary.get("mixedCount", 0),
            "futurePromotableCount": summary.get("futurePromotableCount", 0),
            "keepMixedCount": summary.get("keepMixedCount", 0),
            "textRejectedCount": summary.get("textRejectedCount", 0),
            "futurePromotableRatio": summary.get("futurePromotableRatio", 0),
            "keepMixedRatio": summary.get("keepMixedRatio", 0),
            "textRejectedRatio": summary.get("textRejectedRatio", 0),
            "futurePromotableExampleCount": summary.get("futurePromotableExampleCount", 0),
            "keepMixedExampleCount": summary.get("keepMixedExampleCount", 0),
            "textRejectedExampleCount": summary.get("textRejectedExampleCount", 0),
            "highRiskPromotionCount": summary.get("highRiskPromotionCount", 0),
            "badRoutingCountFromM2907": summary.get("badRoutingCountFromM2907", 0),
            "visualAssetCountFromM2905": visual_asset_count,
            "weakTextNoiseRatioFromM2906": weak_ratio,
        }
        rows.append(row)
    (output_dir / "m29_1_3_batch_summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "m29_1_3_batch_summary.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()) if rows else ["imageId"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def ratio(value: int, total: int) -> float:
    return round(value / total, 6) if total else 0.0


def example_count(conflicts: list[MixedSymbolTextConflict], classification: str) -> int:
    return sum(1 for conflict in conflicts if conflict.classification == classification and conflict.example_asset_paths)


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
