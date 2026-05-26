from __future__ import annotations

from typing import Any

from ..image_math import ImageScaleProfile, build_scale_profile
from ..region_relation_kernel import bbox_area
from .geometry import bbox_in_image, overlap_ratio


MAX_TRANSPARENT_ASSET_AREA = 12000
MAX_TEXT_OVERLAP = 0.20
MAX_INTERNAL_HERO_PENALTY = 0.42
MIN_TRANSPARENT_ICON_SHORT_EDGE = 8
MAX_TRANSPARENT_ICON_ASPECT_RATIO = 10.0
SOFT_EDGE_MIN_TEXT_ANCHOR = 0.70
SOFT_EDGE_MAX_HERO_PENALTY = 0.26
SOFT_EDGE_MAX_TEXT_OVERLAP = 0.14


def collect_transparent_asset_candidates(
    *,
    source_objects: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
    media_internal_candidates: list[dict[str, Any]],
    image_size: dict[str, int],
    scale_profile: ImageScaleProfile | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    media_lookup = {str(source["sourceObjectId"]): source for source in source_objects}
    scale_profile = scale_profile or build_scale_profile(image_size=image_size, ocr_blocks=ocr_blocks, source_objects=source_objects)
    for source in source_objects:
        if is_m292_icon_candidate(source):
            candidates.append(build_m292_candidate(source, ocr_blocks, image_size, len(candidates) + 1, scale_profile))
    for internal in media_internal_candidates:
        if is_m296_internal_icon_candidate(internal):
            candidates.append(build_m296_candidate(internal, ocr_blocks, image_size, len(candidates) + 1, media_lookup, scale_profile))
    return candidates


def is_m292_icon_candidate(source: dict[str, Any]) -> bool:
    return source["visualKind"] == "raster_icon" or source["pixelOwner"] == "raster_icon" or source["replayDecision"] == "icon_replay"


def is_m296_internal_icon_candidate(internal: dict[str, Any]) -> bool:
    return internal.get("role") == "internal_icon_candidate"


def build_m292_candidate(
    source: dict[str, Any],
    ocr_blocks: list[dict[str, Any]],
    image_size: dict[str, int],
    index: int,
    scale_profile: ImageScaleProfile,
) -> dict[str, Any]:
    bbox = source["bbox"]
    risks: list[str] = []
    reasons = ["m29_2_raster_icon_source_object"]
    if source["visualKind"] != "raster_icon" or source["pixelOwner"] != "raster_icon" or source["replayDecision"] != "icon_replay":
        risks.append("not_raster_icon_replay")
    if transparent_asset_too_large(bbox, scale_profile):
        risks.append("transparent_candidate_too_large")
    if icon_geometry_too_thin(bbox, scale_profile):
        risks.append("transparent_candidate_too_thin")
    if source.get("confidence") == "low":
        risks.append("low_source_confidence")
    if image_size and not bbox_in_image(bbox, int(image_size.get("width") or 0), int(image_size.get("height") or 0)):
        risks.append("bbox_out_of_image_bounds")
    text_overlap = max((overlap_ratio(bbox, block["bbox"]) for block in ocr_blocks), default=0.0)
    if text_overlap > MAX_TEXT_OVERLAP:
        risks.append("overlaps_ocr_text")
    return {
        "candidateId": f"m29_transparent_asset_candidate_{index:04d}",
        "source": "m29_2_raster_icon",
        "sourceObjectId": source["sourceObjectId"],
        "mediaSourceObjectId": None,
        "bbox": bbox,
        "inputConfidence": source["confidence"],
        "inputScore": None,
        "textOverlap": text_overlap,
        "candidateAllowedForAlpha": not risks,
        "preflightReasons": reasons,
        "preflightRisks": risks,
    }


def build_m296_candidate(
    internal: dict[str, Any],
    ocr_blocks: list[dict[str, Any]],
    image_size: dict[str, int],
    index: int,
    media_lookup: dict[str, dict[str, Any]],
    scale_profile: ImageScaleProfile,
) -> dict[str, Any]:
    bbox = internal["bbox"]
    breakdown = internal.get("scoreBreakdown", {})
    hero_penalty = float(breakdown.get("heroGraphicPenalty") or 0.0)
    text_overlap = max(float(breakdown.get("textMaskOverlap") or 0.0), max((overlap_ratio(bbox, block["bbox"]) for block in ocr_blocks), default=0.0))
    risks: list[str] = []
    reasons = ["m29_6_internal_icon_candidate"]
    if internal.get("role") != "internal_icon_candidate":
        risks.append("not_internal_icon_candidate")
    if internal.get("candidateDecision") != "accepted_report_candidate":
        risks.append("internal_candidate_not_accepted")
    group_supported = internal.get("groupSupportedExecution") is True
    execution_supported = internal.get("confidence") == "high" or group_supported
    independent_alpha_supported = allows_independent_alpha_analysis(internal, text_overlap, hero_penalty, media_lookup)
    if not execution_supported and not independent_alpha_supported:
        risks.append("internal_candidate_not_execution_supported")
    if transparent_asset_too_large(bbox, scale_profile):
        risks.append("transparent_candidate_too_large")
    if icon_geometry_too_thin(bbox, scale_profile):
        risks.append("transparent_candidate_too_thin")
    if text_overlap > MAX_TEXT_OVERLAP:
        risks.append("overlaps_ocr_text")
    if hero_penalty > MAX_INTERNAL_HERO_PENALTY:
        risks.append("hero_or_texture_risk")
    if image_size and not bbox_in_image(bbox, int(image_size.get("width") or 0), int(image_size.get("height") or 0)):
        risks.append("bbox_out_of_image_bounds")
    if group_supported:
        reasons.append("group_supported_internal_candidate")
    if independent_alpha_supported and not execution_supported:
        reasons.append("strong_independent_evidence_alpha_analysis")
    alpha_profile = "anchored_soft_edge_icon" if allows_anchored_soft_edge_profile(internal, text_overlap, hero_penalty, group_supported) else "default_icon"
    if alpha_profile == "anchored_soft_edge_icon":
        reasons.append("anchored_soft_edge_icon_profile")
    return {
        "candidateId": f"m29_transparent_asset_candidate_{index:04d}",
        "source": "m29_6_internal_icon_candidate",
        "sourceObjectId": internal["candidateId"],
        "mediaSourceObjectId": internal.get("mediaSourceObjectId") or None,
        "mediaBbox": (media_lookup.get(str(internal.get("mediaSourceObjectId") or "")) or {}).get("bbox"),
        "bbox": bbox,
        "inputConfidence": internal.get("confidence") or "low",
        "inputScore": internal.get("score"),
        "alphaProfile": alpha_profile,
        "textOverlap": round(text_overlap, 6),
        "executionSupportedForVisibleReplay": execution_supported,
        "analysisSupportedByIndependentEvidence": independent_alpha_supported,
        "candidateAllowedForAlpha": not risks,
        "preflightReasons": reasons,
        "preflightRisks": risks,
    }


def allows_independent_alpha_analysis(
    internal: dict[str, Any],
    text_overlap: float,
    hero_penalty: float,
    media_lookup: dict[str, dict[str, Any]],
) -> bool:
    breakdown = internal.get("scoreBreakdown", {})
    relation = str(internal.get("anchorRelation") or "")
    text_anchor = float(breakdown.get("textAnchorScore") or 0.0)
    compact = float(breakdown.get("compactnessScore") or 0.0)
    color = float(breakdown.get("colorCoherenceScore") or 0.0)
    media = media_lookup.get(str(internal.get("mediaSourceObjectId") or ""))
    media_containment = 0.0
    if media is not None:
        media_containment = containment_ratio(internal.get("bbox"), media.get("bbox"))
    return (
        internal.get("candidateDecision") == "accepted_report_candidate"
        and internal.get("confidence") == "medium"
        and bool(internal.get("matchedOcrBoxId"))
        and relation in {"above_text", "below_text", "left_of_text", "right_of_text"}
        and text_anchor >= SOFT_EDGE_MIN_TEXT_ANCHOR
        and text_overlap <= SOFT_EDGE_MAX_TEXT_OVERLAP
        and hero_penalty <= SOFT_EDGE_MAX_HERO_PENALTY
        and media_containment >= 0.95
        and compact >= 0.45
        and color >= 0.45
    )


def allows_anchored_soft_edge_profile(internal: dict[str, Any], text_overlap: float, hero_penalty: float, group_supported: bool) -> bool:
    breakdown = internal.get("scoreBreakdown", {})
    text_anchor = float(breakdown.get("textAnchorScore") or 0.0)
    relation = str(internal.get("anchorRelation") or "")
    has_anchor = bool(internal.get("matchedOcrBoxId")) and relation in {"above_text", "below_text", "left_of_text", "right_of_text"}
    execution_supported = internal.get("confidence") == "high" or group_supported
    return (
        has_anchor
        and execution_supported
        and group_supported
        and text_anchor >= SOFT_EDGE_MIN_TEXT_ANCHOR
        and text_overlap <= SOFT_EDGE_MAX_TEXT_OVERLAP
        and hero_penalty <= SOFT_EDGE_MAX_HERO_PENALTY
    )


def transparent_asset_too_large(bbox: list[int], scale_profile: ImageScaleProfile) -> bool:
    return bbox_area(bbox) > scale_profile.area(MAX_TRANSPARENT_ASSET_AREA, minimum=MAX_TRANSPARENT_ASSET_AREA)


def icon_geometry_too_thin(bbox: list[int], scale_profile: ImageScaleProfile) -> bool:
    short = min(bbox[2], bbox[3])
    long = max(bbox[2], bbox[3])
    return short < scale_profile.length(MIN_TRANSPARENT_ICON_SHORT_EDGE, minimum=4, maximum=32) or long / max(1, short) > MAX_TRANSPARENT_ICON_ASPECT_RATIO


def containment_ratio(bbox: Any, container: Any) -> float:
    if not isinstance(bbox, list) or len(bbox) != 4 or not isinstance(container, list) or len(container) != 4:
        return 0.0
    left = max(int(bbox[0]), int(container[0]))
    top = max(int(bbox[1]), int(container[1]))
    right = min(int(bbox[0]) + int(bbox[2]), int(container[0]) + int(container[2]))
    bottom = min(int(bbox[1]) + int(bbox[3]), int(container[1]) + int(container[3]))
    area = max(0, right - left) * max(0, bottom - top)
    return area / max(1, int(bbox[2]) * int(bbox[3]))
