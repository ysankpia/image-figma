from __future__ import annotations

import json
import string
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_primitive_graph import (
    M29PrimitiveMetrics,
    bbox_area,
    bbox_in_bounds,
    crop_pixels,
    draw_rect,
    metrics_to_dict,
)


VisualEvidenceSource = Literal[
    "m29_image",
    "m29_unknown",
    "m29_symbol",
    "m29_shape",
    "m29_blocked",
    "m291_group",
    "after_text_mask_candidate",
]
VisualEvidenceKind = Literal[
    "accepted_image",
    "media_candidate",
    "icon_candidate",
    "mixed_symbol_text_candidate",
    "text_noise",
    "other_candidate",
]
VisualEvidenceDecision = Literal["accepted", "candidate", "uncertain", "noise", "rejected"]

TEXT_REJECTED_LINEAGE_FULL_OCR_COVERAGE_MIN = 0.72
TEXT_REJECTED_LINEAGE_ASPECT_MIN = 3.5


@dataclass(frozen=True)
class VisualEvidenceOptions:
    text_noise_overlap_threshold: float = 0.35
    media_candidate_text_overlap_max: float = 0.20
    icon_candidate_text_overlap_max: float = 0.20
    media_candidate_min_area: int = 1200
    media_candidate_min_color_count: int = 32
    media_candidate_min_texture_score: float = 0.18
    media_candidate_max_aspect_ratio: float = 4.0
    media_candidate_symbol_min_edge: int = 72
    icon_candidate_min_area: int = 16
    icon_candidate_max_area: int = 12000
    icon_candidate_max_edge: int = 128
    output_preview_max_thumb: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualEvidenceItem:
    id: str
    source_evidence_id: str
    source: VisualEvidenceSource
    bbox: list[int]
    region_name: str
    visual_kind: VisualEvidenceKind
    decision: VisualEvidenceDecision
    confidence: float
    asset_path: str
    text_overlap_ratio: float
    image_overlap_ratio: float
    metrics: M29PrimitiveMetrics
    reasons: list[str]
    source_decision: str
    suggested_next_action: str
    source_lineage: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "sourceEvidenceId": self.source_evidence_id,
            "source": self.source,
            "bbox": self.bbox,
            "regionName": self.region_name,
            "visualKind": self.visual_kind,
            "decision": self.decision,
            "confidence": round(self.confidence, 3),
            "assetPath": self.asset_path,
            "textOverlapRatio": round(self.text_overlap_ratio, 4),
            "imageOverlapRatio": round(self.image_overlap_ratio, 4),
            "metrics": metrics_to_dict(self.metrics),
            "reasons": self.reasons,
            "sourceDecision": self.source_decision,
            "suggestedNextAction": self.suggested_next_action,
        }
        if self.source_lineage is not None:
            data["sourceLineage"] = self.source_lineage
        return data


@dataclass(frozen=True)
class VisualEvidenceDebugArtifacts:
    visual_evidence_buckets: str | None = None
    media_candidates: str | None = None
    text_noise: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "visualEvidenceBuckets": self.visual_evidence_buckets,
                "mediaCandidates": self.media_candidates,
                "textNoise": self.text_noise,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class VisualEvidenceDocument:
    schema_name: str
    schema_version: str
    source_image: str
    source_m2902_audit_json: str
    options: VisualEvidenceOptions
    items: list[VisualEvidenceItem]
    groups: dict[str, Any]
    debug: VisualEvidenceDebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "options": self.options.to_dict(),
            "items": [item.to_dict() for item in self.items],
            "groups": self.groups,
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }


def extract_visual_evidence_normalization(
    *,
    png_data: bytes,
    source_image: str,
    m2902_document: dict[str, Any],
    m2902_audit_json_path: str,
    output_dir: Path,
    options: VisualEvidenceOptions | None = None,
    m291_lineage_document: dict[str, Any] | None = None,
    m291_lineage_json_path: str | None = None,
    warnings: list[str] | None = None,
    emit_debug_artifacts: bool = True,
    emit_preview_artifacts: bool = True,
) -> VisualEvidenceDocument:
    options = options or VisualEvidenceOptions()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    media_evidence = m2902_document.get("mediaEvidence")
    if not isinstance(media_evidence, list):
        raise ValueError("M29.0.3 requires M29.0.2 mediaEvidence list")
    text_boxes = collect_text_boxes(m2902_document, pixels.width, pixels.height) if m291_lineage_document is not None else []

    items = normalize_evidence_items(
        pixels=pixels,
        output_dir=output_dir,
        media_evidence=media_evidence,
        text_boxes=text_boxes,
        options=options,
        lineage_lookup=build_lineage_lookup(m291_lineage_document),
    )
    debug = VisualEvidenceDebugArtifacts()
    if emit_debug_artifacts:
        debug = write_debug_artifacts(pixels, output_dir, items)
    if emit_preview_artifacts and debug.to_dict():
        preview_path = output_dir / "preview_visual_evidence.png"
        preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, items, options))
    document = VisualEvidenceDocument(
        schema_name="M2903VisualEvidenceDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m2902_audit_json=m2902_audit_json_path,
        options=options,
        items=items,
        groups=build_groups(items),
        debug=debug,
        warnings=warnings or [],
        meta=build_meta(m2902_audit_json_path, media_evidence, items, m291_lineage_json_path),
    )
    validate_visual_evidence_document(document, output_dir, pixels.width, pixels.height, expected_count=len(media_evidence))
    write_outputs(document, output_dir)
    return document


def normalize_evidence_items(
    *,
    pixels: PngPixels,
    output_dir: Path,
    media_evidence: list[Any],
    text_boxes: list[dict[str, Any]],
    options: VisualEvidenceOptions,
    lineage_lookup: dict[str, dict[str, Any]] | None = None,
) -> list[VisualEvidenceItem]:
    items: list[VisualEvidenceItem] = []
    counters: dict[str, int] = {}
    for raw in media_evidence:
        if not isinstance(raw, dict):
            raise ValueError("M29.0.3 mediaEvidence item must be an object")
        source_evidence_id = str(raw.get("id") or "")
        source = parse_source(raw.get("source"))
        bbox = parse_bbox(raw.get("bbox"))
        if not source_evidence_id or source is None or bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
            raise ValueError(f"M29.0.3 invalid mediaEvidence item: {source_evidence_id or '<missing id>'}")
        metrics = parse_metrics(raw.get("metrics"))
        source_lineage = lookup_source_lineage(raw, bbox, lineage_lookup)
        matched_text_boxes = overlapping_text_boxes(bbox, text_boxes)
        visual_kind, decision, confidence, classification_reasons, source_lineage = classify_evidence(raw, bbox, metrics, options, source_lineage, matched_text_boxes)
        id = next_item_id(visual_kind, counters)
        asset_path = export_visual_evidence_asset(pixels, output_dir, visual_kind, id, bbox)
        items.append(
            VisualEvidenceItem(
                id=id,
                source_evidence_id=source_evidence_id,
                source=source,
                bbox=bbox,
                region_name=str(raw.get("regionName") or "unknown"),
                visual_kind=visual_kind,
                decision=decision,
                confidence=confidence,
                asset_path=asset_path,
                text_overlap_ratio=float(raw.get("textOverlapRatio", 0.0)),
                image_overlap_ratio=float(raw.get("imageOverlapRatio", 0.0)),
                metrics=metrics,
                reasons=[*classification_reasons, *[str(reason) for reason in raw.get("reasons", [])]],
                source_decision=str(raw.get("decision") or ""),
                suggested_next_action=str(raw.get("suggestedNextAction") or ""),
                source_lineage=source_lineage,
            )
        )
    return sorted(items, key=item_sort_key)


def classify_evidence(
    raw: dict[str, Any],
    bbox: list[int],
    metrics: M29PrimitiveMetrics,
    options: VisualEvidenceOptions,
    source_lineage: dict[str, Any] | None = None,
    matched_text_boxes: list[dict[str, Any]] | None = None,
) -> tuple[VisualEvidenceKind, VisualEvidenceDecision, float, list[str], dict[str, Any] | None]:
    source = str(raw.get("source"))
    source_decision = str(raw.get("decision") or "")
    suggested = str(raw.get("suggestedNextAction") or "")
    text_overlap = float(raw.get("textOverlapRatio", 0.0))
    area = bbox_area(bbox)
    width, height = bbox[2], bbox[3]
    max_edge = max(width, height)
    aspect = width / max(1, height)
    if has_source_support_contract(raw):
        reasons = ["source_support_shape_retained"]
        source_subtype = source_support_subtype(raw)
        if source_subtype:
            reasons.append(f"sourceSubtype:{source_subtype}")
        return "other_candidate", "candidate", 0.74, reasons, source_lineage
    if text_overlap >= options.text_noise_overlap_threshold or suggested == "likely_text_noise":
        if lineage_is_rejected_text_like(source_lineage):
            rejected = rejected_lineage(source_lineage, "text_like_glyph_sequence")
            return "text_noise", "noise", confidence_from_overlap(text_overlap), ["text_noise_demoted", "rejected_pre_ocr_lineage_text_like", "text_owned_rejected_lineage"], rejected
        if lineage_survives_as_conflict(source_lineage):
            counter_evidence = text_lineage_counter_evidence(
                bbox=bbox,
                metrics=metrics,
                source_lineage=source_lineage,
                text_overlap=text_overlap,
                matched_text_boxes=matched_text_boxes or [],
                options=options,
            )
            if counter_evidence:
                rejected = rejected_lineage(source_lineage, "text_owned_rejected_lineage", counter_evidence)
                return "text_noise", "noise", confidence_from_overlap(text_overlap), ["text_noise_demoted", "text_owned_rejected_lineage", *counter_evidence], rejected
            return (
                "mixed_symbol_text_candidate",
                "uncertain",
                max(0.55, min(0.72, confidence_from_overlap(text_overlap) - 0.12)),
                ["symbol_text_ownership_conflict", "pre_ocr_symbol_lineage_preserved"],
                source_lineage,
            )
        return "text_noise", "noise", confidence_from_overlap(text_overlap), ["text_noise_demoted"], source_lineage
    if source == "m29_image" and suggested == "keep_accepted_image":
        return "accepted_image", "accepted", 0.92, ["accepted_m29_image"], source_lineage
    if (
        source in {"m29_unknown", "m29_symbol", "m29_blocked", "m291_group", "after_text_mask_candidate"}
        and text_overlap <= options.media_candidate_text_overlap_max
        and area >= options.media_candidate_min_area
        and aspect <= options.media_candidate_max_aspect_ratio
        and (source not in {"m29_symbol", "m291_group", "after_text_mask_candidate"} or max_edge >= options.media_candidate_symbol_min_edge)
        and (metrics.color_count >= options.media_candidate_min_color_count or metrics.texture_score >= options.media_candidate_min_texture_score)
    ):
        return "media_candidate", "candidate", media_candidate_confidence(metrics, area, options), ["media_candidate_promoted", f"from_{source_decision or source}"], source_lineage
    if (
        source in {"m29_symbol", "m29_blocked", "m291_group", "after_text_mask_candidate"}
        and text_overlap <= options.icon_candidate_text_overlap_max
        and options.icon_candidate_min_area <= area <= options.icon_candidate_max_area
        and max_edge <= options.icon_candidate_max_edge
    ):
        return "icon_candidate", "candidate", 0.68, ["icon_candidate_promoted", f"from_{source_decision or source}"], source_lineage
    return "other_candidate", "candidate", 0.45, ["other_candidate_retained", f"from_{source_decision or source}"], source_lineage


def has_source_support_contract(raw: dict[str, Any]) -> bool:
    subtype = source_support_subtype(raw)
    reasons = {
        str(reason)
        for key in ("sourceReasons", "reasons")
        for reason in raw.get(key, [])
        if isinstance(reason, str)
    }
    return subtype in {"low_contrast_support", "text_support_background"} or bool(
        reasons & {"low_contrast_support_region", "text_support_background_region"}
    )


def source_support_subtype(raw: dict[str, Any]) -> str:
    subtype = str(raw.get("sourceSubtype") or raw.get("sourceM29Subtype") or raw.get("subtype") or "")
    if subtype:
        return subtype
    for reason in raw.get("reasons", []):
        if not isinstance(reason, str):
            continue
        if reason.startswith("sourceSubtype:"):
            return reason.split(":", 1)[1]
    return ""


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


def rejected_lineage(source_lineage: dict[str, Any] | None, reason: str, counter_evidence: list[str] | None = None) -> dict[str, Any] | None:
    if not isinstance(source_lineage, dict):
        return source_lineage
    rejected = dict(source_lineage)
    rejected["rejectedLineageReason"] = reason
    rejected["conflictClass"] = "text_owned_rejected_lineage"
    rejected["ownershipHint"] = "text_owned"
    rejected["survivingPreOcrSymbolCandidate"] = False
    rejected["counterEvidence"] = dedupe_strings([*rejected.get("counterEvidence", []), *(counter_evidence or [])])
    rejected["risks"] = dedupe_strings([*rejected.get("risks", []), "text_contamination_possible"])
    rejected["reasons"] = dedupe_strings([*rejected.get("reasons", []), reason])
    return rejected


def lineage_survives_as_conflict(source_lineage: dict[str, Any] | None) -> bool:
    if not isinstance(source_lineage, dict):
        return False
    if source_lineage.get("rejectedLineageReason"):
        return False
    return bool(source_lineage.get("preOcrSymbolCandidate"))


def lineage_is_rejected_text_like(source_lineage: dict[str, Any] | None) -> bool:
    if not isinstance(source_lineage, dict):
        return False
    reason = str(source_lineage.get("rejectedLineageReason") or "")
    return reason in {"text_like_glyph_sequence", "image_like_merged_result"}


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


def build_lineage_lookup(document: dict[str, Any] | None) -> dict[str, dict[str, Any]] | None:
    if document is None:
        return None
    if document.get("schemaName") != "M291SymbolFragmentGroupingDocument" or document.get("schemaVersion") != "0.1":
        raise ValueError("M29.0.3 lineage input must be M291SymbolFragmentGroupingDocument v0.1")
    lookup: dict[str, dict[str, Any]] = {}
    candidate_bboxes_by_id = {
        str(candidate.get("id")): bbox
        for candidate in document.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("id") and (bbox := parse_bbox(candidate.get("bbox"))) is not None
    }
    for candidate in document.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        lineage = normalized_lineage(candidate.get("sourceLineage"), candidate)
        if lineage is None:
            continue
        lineage = attach_candidate_bboxes(lineage, candidate_bboxes_by_id)
        bbox = parse_bbox(candidate.get("bbox"))
        source_node_id = str(candidate.get("sourceNodeId") or "")
        source_kind = str(candidate.get("sourceKind") or "")
        if source_node_id:
            if source_kind == "symbol":
                lookup[f"source_node:m29_symbol:{source_node_id}"] = lineage
            elif source_kind == "blocked":
                lookup[f"source_node:m29_blocked:{source_node_id}"] = lineage
        if bbox is not None:
            lookup.setdefault(bbox_key(bbox), lineage)
    for group in document.get("groups", []):
        if not isinstance(group, dict):
            continue
        lineage = normalized_lineage(group.get("sourceLineage"), group)
        if lineage is None and group.get("rejectedLineageReason"):
            lineage = {
                "preOcrSymbolCandidate": False,
                "lineageStrength": "weak",
                "lineageSource": "m291_group",
                "m291GroupId": str(group.get("id") or ""),
                "ownershipHint": "text_owned",
                "rejectedLineageReason": str(group.get("rejectedLineageReason") or ""),
                "risks": ["text_like_sequence_risk"],
                "reasons": [str(reason) for reason in group.get("reasons", [])],
            }
        if lineage is None:
            continue
        lineage = attach_candidate_bboxes(lineage, candidate_bboxes_by_id)
        bbox = parse_bbox(group.get("bbox"))
        group_id = str(group.get("id") or "")
        if group_id:
            lookup[f"source_node:m291_group:{group_id}"] = lineage
        if bbox is not None:
            lookup[bbox_key(bbox)] = lineage
    return lookup


def normalized_lineage(value: object, owner: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    lineage = dict(value)
    owner_id = str(owner.get("id") or "")
    if owner_id and not lineage.get("sourceOwnerId"):
        lineage["sourceOwnerId"] = owner_id
    return lineage


def attach_candidate_bboxes(lineage: dict[str, Any], candidate_bboxes_by_id: dict[str, list[int]]) -> dict[str, Any]:
    candidate_ids = [str(value) for value in lineage.get("m291CandidateIds", []) if value]
    bboxes = [candidate_bboxes_by_id[candidate_id] for candidate_id in candidate_ids if candidate_id in candidate_bboxes_by_id]
    if not bboxes or lineage.get("m291CandidateBboxes"):
        return lineage
    output = dict(lineage)
    output["m291CandidateBboxes"] = bboxes
    return output


def lookup_source_lineage(raw: dict[str, Any], bbox: list[int], lineage_lookup: dict[str, dict[str, Any]] | None) -> dict[str, Any] | None:
    if not lineage_lookup:
        return None
    source = str(raw.get("source") or "")
    source_id = str(raw.get("sourceId") or raw.get("sourceNodeId") or raw.get("sourceGroupId") or "")
    if source_id:
        found = lineage_lookup.get(f"source_node:{source}:{source_id}")
        if found is not None:
            return found
    return lineage_lookup.get(bbox_key(bbox))


def bbox_key(bbox: list[int]) -> str:
    return "bbox:" + ",".join(str(int(item)) for item in bbox)


def confidence_from_overlap(text_overlap: float) -> float:
    return min(0.99, max(0.55, 0.55 + text_overlap * 0.4))


def media_candidate_confidence(metrics: M29PrimitiveMetrics, area: int, options: VisualEvidenceOptions) -> float:
    color_score = min(1.0, metrics.color_count / max(1, options.media_candidate_min_color_count * 2))
    texture_score = min(1.0, metrics.texture_score / max(0.001, options.media_candidate_min_texture_score * 2))
    area_score = min(1.0, area / max(1, options.media_candidate_min_area * 4))
    return 0.58 + 0.14 * color_score + 0.18 * texture_score + 0.10 * area_score


def export_visual_evidence_asset(
    pixels: PngPixels,
    output_dir: Path,
    visual_kind: VisualEvidenceKind,
    id: str,
    bbox: list[int],
) -> str:
    folder = {
        "accepted_image": "accepted_images",
        "media_candidate": "media_candidates",
        "icon_candidate": "icon_candidates",
        "mixed_symbol_text_candidate": "mixed_symbol_text_candidates",
        "text_noise": "text_noise",
        "other_candidate": "other_candidates",
    }[visual_kind]
    target_dir = output_dir / "assets" / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{id}.png"
    path.write_bytes(crop_pixels(pixels, bbox))
    return str(path.relative_to(output_dir))


def next_item_id(visual_kind: VisualEvidenceKind, counters: dict[str, int]) -> str:
    counters[visual_kind] = counters.get(visual_kind, 0) + 1
    return f"{visual_kind}_{counters[visual_kind]:03d}"


def build_groups(items: list[VisualEvidenceItem]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    by_decision: dict[str, int] = {}
    by_region: dict[str, dict[str, int]] = {}
    for item in items:
        by_kind[item.visual_kind] = by_kind.get(item.visual_kind, 0) + 1
        by_decision[item.decision] = by_decision.get(item.decision, 0) + 1
        region = by_region.setdefault(item.region_name, {})
        region[item.visual_kind] = region.get(item.visual_kind, 0) + 1
    return {
        "byVisualKind": dict(sorted(by_kind.items())),
        "byDecision": dict(sorted(by_decision.items())),
        "byRegion": {region: dict(sorted(counts.items())) for region, counts in sorted(by_region.items())},
    }


def write_debug_artifacts(pixels: PngPixels, output_dir: Path, items: list[VisualEvidenceItem]) -> VisualEvidenceDebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    buckets_path = overlay_dir / "13_visual_evidence_buckets.png"
    media_path = overlay_dir / "14_media_candidates.png"
    noise_path = overlay_dir / "15_text_noise.png"
    buckets_path.write_bytes(overlay_items(pixels, items, {"accepted_image", "media_candidate", "icon_candidate", "mixed_symbol_text_candidate", "other_candidate", "text_noise"}))
    media_path.write_bytes(overlay_items(pixels, items, {"accepted_image", "media_candidate"}))
    noise_path.write_bytes(overlay_items(pixels, items, {"text_noise"}))
    return VisualEvidenceDebugArtifacts(
        visual_evidence_buckets=str(buckets_path.relative_to(output_dir)),
        media_candidates=str(media_path.relative_to(output_dir)),
        text_noise=str(noise_path.relative_to(output_dir)),
    )


def overlay_items(pixels: PngPixels, items: list[VisualEvidenceItem], kinds: set[str]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in items:
        if item.visual_kind not in kinds:
            continue
        draw_rect(rows, pixels.width, pixels.height, item.bbox, item_color(item), 3 if item.decision == "accepted" else 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def build_preview_sheet(
    pixels: PngPixels,
    output_dir: Path,
    debug: VisualEvidenceDebugArtifacts,
    items: list[VisualEvidenceItem],
    options: VisualEvidenceOptions,
) -> bytes:
    bucket_overlay = decode_png_pixels((output_dir / debug.visual_evidence_buckets).read_bytes())
    media_overlay = decode_png_pixels((output_dir / debug.media_candidates).read_bytes())
    noise_overlay = decode_png_pixels((output_dir / debug.text_noise).read_bytes())
    sheet_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.38, (sheet_width - margin * 2 - gap * 3) / max(1, pixels.width * 4))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    crop_items = crop_previews_for_items(output_dir, items, options.output_preview_max_thumb)
    grid_h = grid_height(crop_items, sheet_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    x = margin
    for image in [pixels, bucket_overlay, media_overlay, noise_overlay]:
        paste_scaled(canvas, sheet_width, image, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, sheet_width, crop_items, margin, margin + top_h + margin, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])


def crop_previews_for_items(
    output_dir: Path,
    items: list[VisualEvidenceItem],
    max_edge: int,
) -> list[tuple[VisualEvidenceItem, PngPixels, int, int]]:
    previews: list[tuple[VisualEvidenceItem, PngPixels, int, int]] = []
    for item in sorted(items, key=item_sort_key):
        try:
            pixels = decode_png_pixels((output_dir / item.asset_path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, pixels.width, pixels.height))
        previews.append((item, pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews


def grid_height(previews: list[tuple[VisualEvidenceItem, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 48
    x = margin
    row_h = 0
    total = 0
    for _item, _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h


def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[VisualEvidenceItem, PngPixels, int, int]], x: int, y: int, gap: int) -> int:
    row_h = 0
    margin = x
    if not previews:
        fill_rect(canvas, sheet_width, x, y, sheet_width - x * 2, 48, (232, 232, 232))
        return y + 48
    for item, preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, item_color(item))
        fill_rect(canvas, sheet_width, x - 2, y - 2, width + 4, height + 4, (244, 244, 244))
        paste_scaled(canvas, sheet_width, preview, x, y, width, height)
        x += width + gap
        row_h = max(row_h, height)
    return y + row_h


def paste_scaled(canvas: list[bytearray], sheet_width: int, source: PngPixels, x: int, y: int, target_width: int, target_height: int) -> None:
    for target_y in range(target_height):
        source_y = min(source.height - 1, round(target_y * source.height / target_height))
        if y + target_y < 0 or y + target_y >= len(canvas):
            continue
        source_row = source.rows[source_y]
        target_row = canvas[y + target_y]
        for target_x in range(target_width):
            source_x = min(source.width - 1, round(target_x * source.width / target_width))
            dst_x = x + target_x
            if 0 <= dst_x < sheet_width:
                target_row[dst_x * 3 : dst_x * 3 + 3] = source_row[source_x * 3 : source_x * 3 + 3]


def fill_rect(canvas: list[bytearray], sheet_width: int, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            row[column * 3 : column * 3 + 3] = color_bytes


def item_sort_key(item: VisualEvidenceItem) -> tuple[int, int, int, int, str]:
    kind_rank = {
        "accepted_image": 0,
        "media_candidate": 1,
        "icon_candidate": 2,
        "other_candidate": 3,
        "mixed_symbol_text_candidate": 4,
        "text_noise": 5,
    }.get(item.visual_kind, 9)
    return (kind_rank, -bbox_area(item.bbox), item.bbox[1], item.bbox[0], item.id)


def item_color(item: VisualEvidenceItem) -> tuple[int, int, int]:
    return {
        "accepted_image": (0, 180, 210),
        "media_candidate": (235, 64, 52),
        "icon_candidate": (0, 200, 90),
        "mixed_symbol_text_candidate": (238, 140, 40),
        "other_candidate": (238, 190, 40),
        "text_noise": (170, 170, 170),
    }[item.visual_kind]


def write_outputs(document: VisualEvidenceDocument, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "visual_evidence.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "visual_evidence.md").write_text(build_markdown_report(document), encoding="utf-8")


def build_markdown_report(document: VisualEvidenceDocument) -> str:
    lines = [
        "# M29.0.3 Visual Evidence Normalization",
        "",
        f"- Source M29.0.2 audit: `{document.source_m2902_audit_json}`",
        f"- Items: {len(document.items)}",
        f"- Buckets: `{document.groups.get('byVisualKind', {})}`",
        f"- Decisions: `{document.groups.get('byDecision', {})}`",
        "",
        "## Evidence By Region",
        "",
    ]
    by_region = document.groups.get("byRegion", {})
    if isinstance(by_region, dict):
        for region, counts in by_region.items():
            lines.append(f"- `{region}`: `{counts}`")
    lines.extend(["", "## Items", ""])
    for item in document.items[:160]:
        lines.append(
            f"- `{item.id}` `{item.visual_kind}` `{item.decision}` source=`{item.source}` "
            f"sourceId=`{item.source_evidence_id}` bbox={item.bbox} textOverlap={item.text_overlap_ratio:.3f}"
        )
    return "\n".join(lines).rstrip() + "\n"


def validate_visual_evidence_document(
    document: VisualEvidenceDocument,
    output_dir: Path,
    width: int,
    height: int,
    *,
    expected_count: int,
) -> None:
    if document.schema_name != "M2903VisualEvidenceDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.3 document schema")
    if len(document.items) != expected_count:
        raise ValueError("M29.0.3 item count must match M29.0.2 mediaEvidence count")
    ids: set[str] = set()
    source_ids: set[str] = set()
    for item in document.items:
        if item.id in ids:
            raise ValueError(f"duplicate M29.0.3 item id: {item.id}")
        ids.add(item.id)
        if item.source_evidence_id in source_ids:
            raise ValueError(f"duplicate M29.0.2 source evidence id: {item.source_evidence_id}")
        source_ids.add(item.source_evidence_id)
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.3 item bbox out of bounds: {item.id}")
        assert_readable_relative_png(output_dir, item.asset_path)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)


def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29.0.3 PNG output missing or unreadable: {path}")


def build_meta(m2902_audit_json_path: str, media_evidence: list[Any], items: list[VisualEvidenceItem], m291_lineage_json_path: str | None = None) -> dict[str, Any]:
    return {
        "notes": "m29_0_3_visual_evidence_normalization",
        "sourceM2902AuditJson": m2902_audit_json_path,
        "sourceM291LineageJson": m291_lineage_json_path,
        "sourceEvidenceCount": len(media_evidence),
        "itemCount": len(items),
        "bucketCounts": build_groups(items)["byVisualKind"],
        "lineageAwareItemCount": sum(1 for item in items if item.source_lineage is not None),
    }


def parse_source(value: object) -> VisualEvidenceSource | None:
    if value in {"m29_image", "m29_unknown", "m29_symbol", "m29_shape", "m29_blocked", "m291_group", "after_text_mask_candidate"}:
        return value  # type: ignore[return-value]
    return None


def parse_bbox(value: object) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [int(item) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def parse_metrics(value: object) -> M29PrimitiveMetrics:
    if not isinstance(value, dict):
        raise ValueError("M29.0.3 mediaEvidence item requires metrics")
    mean = value.get("meanRgb", value.get("mean_rgb", [0, 0, 0]))
    if not isinstance(mean, list) or len(mean) != 3:
        raise ValueError("M29.0.3 metrics require meanRgb")
    return M29PrimitiveMetrics(
        color_count=int(value.get("colorCount", value.get("color_count", 0))),
        texture_score=float(value.get("textureScore", value.get("texture_score", 0.0))),
        edge_score=float(value.get("edgeScore", value.get("edge_score", 0.0))),
        fill_ratio=float(value.get("fillRatio", value.get("fill_ratio", 0.0))),
        aspect_ratio=float(value.get("aspectRatio", value.get("aspect_ratio", 0.0))),
        brightness=float(value.get("brightness", 0.0)),
        mean_rgb=(int(mean[0]), int(mean[1]), int(mean[2])),
    )
