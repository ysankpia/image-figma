from __future__ import annotations

from typing import Any

from ..visual_primitive_graph import M29PrimitiveMetrics, bbox_area
from .parsing import media_candidate_confidence
from .text_overlap import text_lineage_counter_evidence
from .lineage import lineage_is_rejected_text_like, lineage_survives_as_conflict, rejected_lineage
from .types import VisualEvidenceDecision, VisualEvidenceKind, VisualEvidenceOptions


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

def confidence_from_overlap(text_overlap: float) -> float:
    return min(0.99, max(0.55, 0.55 + text_overlap * 0.4))
