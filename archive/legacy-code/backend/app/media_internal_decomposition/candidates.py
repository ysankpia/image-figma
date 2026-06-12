from __future__ import annotations

from statistics import median
from math import exp
from typing import Any

from ..image_math import ImageScaleProfile, build_scale_profile
from ..png_tools import PngMetadata, PngPixels
from ..visual_primitive.metrics import color_distance
from ..visual_primitive.geometry import fit_low_contrast_support_geometry, geometry_radius, support_region_metrics
from ..visual_primitive.support_scoring import find_low_contrast_support_bbox, find_text_support_background_bbox, score_text_support_background_candidate
from ..visual_primitive.types import M29VisualPrimitiveOptions
from ..region_relation_kernel import bbox_area, center_x, center_y, x2, y2
from .geometry import area_ratio, containment_ratio, gap_stability_score, is_near_equal, long_thin, overlap_ratio, padded_bbox, row_alignment_score
from .types import COMPOSITE_MEDIA_PIXEL_OWNER, COMPOSITE_MEDIA_REPLAY_DECISION, INTERNAL_CANDIDATE_TYPES


ANCHOR_DIRECTIONS = ("above_text", "below_text", "left_of_text", "right_of_text", "near_text")
PIXEL_COMPONENT_MIN_AREA = 20
PIXEL_COMPONENT_MAX_AREA = 5200
PIXEL_COMPONENT_MIN_SHORT_EDGE = 8
PIXEL_COMPONENT_MAX_ASPECT_RATIO = 10.0
PIXEL_FOREGROUND_DISTANCE = 55
PIXEL_FOREGROUND_MIN_SATURATION = 15
PIXEL_FOREGROUND_MIN_LUMA = 18
GENERIC_SCAN_MAX_WINDOWS = 96
GENERIC_FOREGROUND_MAX_CANDIDATES = 80
PIXEL_COMPONENT_MIN_RETURNED = 24
SELECTED_MARKER_MIN_ASPECT_RATIO = 3.2
SMALL_MARKER_MAX_ASPECT_RATIO = 1.8
OVERLAY_CONTROL_SUBTYPES = {"badge_background", "text_support_background", "low_contrast_support", "rect", "pill"}
OVERLAY_CONTROL_ROLES = {"internal_overlay_badge", "internal_pill_button", "internal_circle_control", "internal_control_background"}


def build_composite_media_items(
    *,
    source_objects: list[dict[str, Any]],
    raw_nodes: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
    image_size: dict[str, int],
    pixels: PngPixels | None = None,
    scale_profile: ImageScaleProfile | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    text_masks: list[dict[str, Any]] = []
    internal_candidates: list[dict[str, Any]] = []
    rejected_fragments: list[dict[str, Any]] = []
    matched_groups: list[dict[str, Any]] = []
    media_items: list[dict[str, Any]] = []
    scale_profile = scale_profile or build_scale_profile(image_size=image_size, ocr_blocks=ocr_blocks, source_objects=source_objects)

    for source in source_objects:
        if not is_preserve_raster_image(source):
            continue
        text_inside = [block for block in ocr_blocks if text_belongs_to_media_context(block["bbox"], source["bbox"])]
        raw_inside = [node for node in raw_nodes if raw_inside_media(node, source)]
        if not is_composite_media(source, text_inside, raw_inside, pixels):
            continue

        source_text_masks = [build_text_mask(source, block, image_size, scale_profile) for block in text_inside]
        text_masks.extend(source_text_masks)
        candidates = score_internal_candidates(source, raw_inside, source_text_masks, text_inside, pixels, scale_profile)
        internal_candidates.extend(candidates)
        groups = build_matched_internal_groups(candidates, text_inside, source["sourceObjectId"], len(matched_groups) + 1)
        apply_group_support(candidates, groups)
        matched_groups.extend(groups)
        rejected_fragments.extend([rejected_summary(item) for item in candidates if item["candidateDecision"] == "rejected_fragment"])
        media_items.append(
            {
                "mediaId": f"m29_media_internal_{len(media_items) + 1:04d}",
                "sourceObjectId": source["sourceObjectId"],
                "bbox": source["bbox"],
                "pixelOwner": source["pixelOwner"],
                "replayDecision": source["replayDecision"],
                "confidence": source["confidence"],
                "riskHints": source["risks"],
                "internalTextBoxIds": [block["ocrBoxId"] for block in text_inside],
                "rawInsideNodeIds": [node["rawNodeId"] for node in raw_inside],
                "textMaskIds": [mask["textMaskId"] for mask in source_text_masks],
                "candidateIds": [item["candidateId"] for item in candidates],
                "compositeReasons": composite_reasons(source, text_inside, raw_inside),
                "reportOnly": True,
            }
        )

    return media_items, text_masks, internal_candidates, matched_groups, rejected_fragments


def is_preserve_raster_image(source: dict[str, Any]) -> bool:
    return source["pixelOwner"] == COMPOSITE_MEDIA_PIXEL_OWNER and source["replayDecision"] == COMPOSITE_MEDIA_REPLAY_DECISION


def is_composite_media(source: dict[str, Any], text_inside: list[dict[str, Any]], raw_inside: list[dict[str, Any]], pixels: PngPixels | None = None) -> bool:
    risks = set(source.get("risks", []))
    if bool(text_inside) or len(raw_inside) >= 2 or "contains_internal_text" in risks:
        return True
    return pixels is not None and source["bbox"][2] >= 24 and source["bbox"][3] >= 24


def raw_inside_media(node: dict[str, Any], media: dict[str, Any]) -> bool:
    if containment_ratio(node["bbox"], media["bbox"]) < 0.95:
        return False
    return not is_near_equal(node["bbox"], media["bbox"], 0.88)


def text_belongs_to_media_context(text_bbox: list[int], media_bbox: list[int]) -> bool:
    if containment_ratio(text_bbox, media_bbox) >= 0.95:
        return True
    horizontal_overlap = intersection_1d(text_bbox[0], x2(text_bbox), media_bbox[0], x2(media_bbox)) / max(1, text_bbox[2])
    if horizontal_overlap < 0.95:
        return False
    media_context = expanded_media_anchor_bbox(media_bbox, text_bbox)
    return containment_ratio(text_bbox, media_context) >= 0.95


def expanded_media_anchor_bbox(media_bbox: list[int], text_bbox: list[int]) -> list[int]:
    padding_x = max(4, min(12, round(media_bbox[2] * 0.02)))
    padding_y = max(8, min(18, round(max(media_bbox[3] * 0.18, text_bbox[3] * 0.55))))
    return [media_bbox[0] - padding_x, media_bbox[1] - padding_y, media_bbox[2] + padding_x * 2, media_bbox[3] + padding_y * 2]


def build_text_mask(media: dict[str, Any], block: dict[str, Any], image_size: dict[str, int], scale_profile: ImageScaleProfile) -> dict[str, Any]:
    padding = scale_profile.length(3, minimum=2, maximum=12)
    return {
        "textMaskId": f"{media['sourceObjectId']}:{block['ocrBoxId']}:text_mask",
        "mediaSourceObjectId": media["sourceObjectId"],
        "ocrBoxId": block["ocrBoxId"],
        "bbox": block["bbox"],
        "paddedBbox": padded_bbox(block["bbox"], padding, padding, image_size),
        "padding": {"x": padding, "y": padding},
        "reason": "internal_ocr_text_protection",
    }


def composite_reasons(source: dict[str, Any], text_inside: list[dict[str, Any]], raw_inside: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    if text_inside:
        reasons.append("contains_internal_ocr_text")
    if raw_inside:
        reasons.append("contains_raw_internal_evidence")
    if "contains_internal_text" in source.get("risks", []):
        reasons.append("source_risk_contains_internal_text")
    return reasons


def score_internal_candidates(
    media: dict[str, Any],
    raw_inside: list[dict[str, Any]],
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    pixels: PngPixels | None,
    scale_profile: ImageScaleProfile,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for node in raw_inside:
        if node["type"] not in INTERNAL_CANDIDATE_TYPES:
            continue
        candidate = score_one_candidate(media, node, text_masks, text_inside, len(candidates) + 1, scale_profile)
        candidates.append(candidate)
    if pixels is not None:
        pixel_candidates = pixel_anchor_candidates(
            media=media,
            pixels=pixels,
            text_masks=text_masks,
            text_inside=text_inside,
            existing_candidates=candidates,
            start_index=len(candidates) + 1,
            scale_profile=scale_profile,
        )
        candidates.extend(pixel_candidates)
        candidates.extend(
            generic_foreground_candidates(
                media=media,
                pixels=pixels,
                text_masks=text_masks,
                text_inside=text_inside,
                existing_candidates=candidates,
                start_index=len(candidates) + 1,
                scale_profile=scale_profile,
            )
        )
        candidates.extend(
            text_support_control_candidates(
                media=media,
                pixels=pixels,
                text_masks=text_masks,
                text_inside=text_inside,
                existing_candidates=candidates,
                start_index=len(candidates) + 1,
                scale_profile=scale_profile,
            )
        )
    apply_marker_repetition_roles(candidates, scale_profile)
    candidates.extend(merge_overlay_control_fragments(media, candidates, text_masks, text_inside, len(candidates) + 1, scale_profile))
    apply_repetition_scores(candidates)
    apply_single_control_row_support(candidates, text_inside, scale_profile)
    candidates.extend(merge_anchor_icon_fragments(media, candidates, text_masks, text_inside, len(candidates) + 1, scale_profile))
    apply_foreground_claim_fields(candidates)
    return candidates


def score_one_candidate(
    media: dict[str, Any],
    node: dict[str, Any],
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    index: int,
    scale_profile: ImageScaleProfile,
) -> dict[str, Any]:
    bbox = node["bbox"]
    metrics = node.get("metrics", {})
    text_overlap = max((overlap_ratio(bbox, mask["paddedBbox"]) for mask in text_masks), default=0.0)
    best_anchor = best_text_anchor(bbox, text_inside)
    size = size_score(bbox, media["bbox"], scale_profile)
    compact = compactness_score(bbox, metrics)
    color = color_coherence_score(metrics)
    hero = hero_graphic_penalty(bbox, media["bbox"], metrics, best_anchor["score"])
    separator = long_thin(bbox) or node["subtype"] == "separator"
    foreground_layer = foreground_layer_evidence(bbox, media["bbox"], metrics)
    overlay_geometry = overlay_geometry_score(bbox, metrics)
    role = candidate_role(node, separator)
    text_containment = text_containment_score(role, text_overlap, best_anchor["score"])
    score = round(
        size * 0.18
        + compact * 0.16
        + color * 0.12
        + best_anchor["score"] * 0.34
        + text_containment * 0.16
        + overlay_geometry * 0.10
        + foreground_layer * 0.08
        - hero * 0.20,
        3,
    )
    reasons: list[str] = []
    risks: list[str] = []
    decision = "accepted_report_candidate"
    if should_reject_text_overlap(role, text_overlap):
        decision = "rejected_fragment"
        risks.append("overlaps_internal_text_mask")
    if should_reject_large_fragment(
        role,
        area_ratio(bbox, media["bbox"]),
        foreground_layer=foreground_layer,
        overlay_geometry=overlay_geometry,
        hero=hero,
    ):
        decision = "rejected_fragment"
        risks.append("large_media_fragment")
    if separator:
        decision = "rejected_fragment"
        risks.append("separator_not_icon")
    if hero >= 0.62 and best_anchor["score"] < 0.35:
        decision = "rejected_fragment"
        risks.append("hero_or_texture_fragment")
    if score < 0.36 and best_anchor["score"] < 0.35:
        decision = "rejected_fragment"
        risks.append("weak_internal_candidate_score")
    if best_anchor["ocrBoxId"]:
        reasons.append("text_anchor_geometry")
    if node["type"] == "symbol":
        reasons.append("raw_symbol_inside_media")
    if node["type"] == "shape":
        reasons.append("raw_shape_inside_media")

    return {
        "candidateId": f"{media['sourceObjectId']}:internal_candidate_{index:04d}",
        "mediaSourceObjectId": media["sourceObjectId"],
        "rawNodeId": node["rawNodeId"],
        "rawType": node["type"],
        "rawSubtype": node["subtype"],
        "role": role,
        "bbox": bbox,
        "candidateDecision": decision,
        "confidence": confidence_label(score, best_anchor["score"], decision),
        "score": score,
        "scoreBreakdown": {
            "sizeScore": size,
            "compactnessScore": compact,
            "colorCoherenceScore": color,
            "textAnchorScore": best_anchor["score"],
            "relationConsistencyScore": best_anchor["relationScore"],
            "repetitionScore": 0.0,
            "heroGraphicPenalty": hero,
            "textMaskOverlap": text_overlap,
            "textContainmentScore": text_containment,
            "foregroundLayerEvidence": foreground_layer,
            "overlayGeometryScore": overlay_geometry,
        },
        "matchedOcrBoxId": best_anchor["ocrBoxId"],
        "anchorRelation": best_anchor["relation"],
        "metrics": {
            "areaRatioInMedia": area_ratio(bbox, media["bbox"]),
            "rawConfidence": node["confidence"],
            "fillRatio": round(float(metrics.get("fillRatio") or 0.0), 4),
            "textureScore": round(float(metrics.get("textureScore") or 0.0), 4),
            "colorCount": int(metrics.get("colorCount") or 0),
        },
        "reasons": reasons,
        "risks": risks,
        "reportOnly": True,
    }


def size_score(bbox: list[int], media_bbox: list[int], scale_profile: ImageScaleProfile) -> float:
    area = bbox_area(bbox)
    min_area = scale_profile.area(16, minimum=8, maximum=256)
    full_score_area = scale_profile.area(48, minimum=24, maximum=768)
    max_area = min(scale_profile.area(12000, minimum=12000), max(64, int(bbox_area(media_bbox) * 0.12)))
    if area < min_area or area > max_area:
        return 0.0
    if area < full_score_area:
        return round(area / full_score_area, 3)
    return 1.0


def compactness_score(bbox: list[int], metrics: dict[str, Any]) -> float:
    fill_ratio = float(metrics.get("fillRatio") or 0.0)
    if fill_ratio <= 0:
        fill_ratio = min(1.0, bbox_area(bbox) / max(1, bbox_area(bbox)))
    return round(max(0.0, min(1.0, fill_ratio / 0.55)), 3)


def color_coherence_score(metrics: dict[str, Any]) -> float:
    color_count = int(metrics.get("colorCount") or 0)
    if color_count <= 0:
        return 0.5
    return round(max(0.0, 1.0 - min(1.0, color_count / 96)), 3)


def best_text_anchor(bbox: list[int], text_inside: list[dict[str, Any]]) -> dict[str, Any]:
    best = {"ocrBoxId": None, "score": 0.0, "relation": None, "relationScore": 0.0}
    for block in text_inside:
        text_bbox = block["bbox"]
        relation = best_anchor_relation(bbox, text_bbox)
        score = relation["score"]
        if score > best["score"]:
            best = {
                "ocrBoxId": block["ocrBoxId"],
                "score": round(score, 3),
                "relation": relation["relation"],
                "relationScore": round(relation["relationScore"], 3),
            }
    return best


def best_anchor_relation(bbox: list[int], text_bbox: list[int]) -> dict[str, Any]:
    candidates = [
        directional_anchor_score(bbox, text_bbox, "above_text"),
        directional_anchor_score(bbox, text_bbox, "below_text"),
        directional_anchor_score(bbox, text_bbox, "left_of_text"),
        directional_anchor_score(bbox, text_bbox, "right_of_text"),
        near_anchor_score(bbox, text_bbox),
    ]
    return max(candidates, key=lambda item: item["score"])


def directional_anchor_score(bbox: list[int], text_bbox: list[int], relation: str) -> dict[str, Any]:
    if relation == "above_text":
        cross_delta = abs(center_x(bbox) - center_x(text_bbox))
        gap = text_bbox[1] - y2(bbox)
        candidate_extent = bbox[3]
        text_extent = text_bbox[3]
        cross_extent = max(bbox[2], text_bbox[2])
    elif relation == "below_text":
        cross_delta = abs(center_x(bbox) - center_x(text_bbox))
        gap = bbox[1] - y2(text_bbox)
        candidate_extent = bbox[3]
        text_extent = text_bbox[3]
        cross_extent = max(bbox[2], text_bbox[2])
    elif relation == "left_of_text":
        cross_delta = abs(center_y(bbox) - center_y(text_bbox))
        gap = text_bbox[0] - x2(bbox)
        candidate_extent = bbox[2]
        text_extent = text_bbox[2]
        cross_extent = max(bbox[3], text_bbox[3])
    else:
        cross_delta = abs(center_y(bbox) - center_y(text_bbox))
        gap = bbox[0] - x2(text_bbox)
        candidate_extent = bbox[2]
        text_extent = text_bbox[2]
        cross_extent = max(bbox[3], text_bbox[3])
    if gap < -candidate_extent * 0.25:
        return {"relation": relation, "score": 0.0, "relationScore": 0.0}
    sigma_cross = max(16.0, cross_extent * 0.85)
    sigma_gap = max(12.0, text_extent * 0.90)
    ideal_gap = max(4.0, text_extent * 0.45)
    cross_score = exp(-(cross_delta**2) / (2 * sigma_cross**2))
    gap_score = exp(-((gap - ideal_gap) ** 2) / (2 * sigma_gap**2))
    score = cross_score * gap_score
    return {"relation": relation, "score": score, "relationScore": score}


def near_anchor_score(bbox: list[int], text_bbox: list[int]) -> dict[str, Any]:
    dx = abs(center_x(bbox) - center_x(text_bbox))
    dy = abs(center_y(bbox) - center_y(text_bbox))
    sigma_x = max(24.0, max(bbox[2], text_bbox[2]) * 1.15)
    sigma_y = max(18.0, max(bbox[3], text_bbox[3]) * 1.15)
    overlap_penalty = 0.35 if overlap_ratio(bbox, text_bbox) > 0 else 1.0
    score = exp(-(dx**2) / (2 * sigma_x**2)) * exp(-(dy**2) / (2 * sigma_y**2)) * overlap_penalty
    return {"relation": "near_text", "score": score, "relationScore": score * 0.82}


def hero_graphic_penalty(bbox: list[int], media_bbox: list[int], metrics: dict[str, Any], anchor_score: float) -> float:
    ratio = area_ratio(bbox, media_bbox)
    texture = float(metrics.get("textureScore") or 0.0)
    distance_x = abs(center_x(bbox) - center_x(media_bbox)) / max(1.0, media_bbox[2] / 2)
    distance_y = abs(center_y(bbox) - center_y(media_bbox)) / max(1.0, media_bbox[3] / 2)
    center_score = max(0.0, 1.0 - min(1.0, (distance_x + distance_y) / 1.4))
    large_score = min(1.0, ratio / 0.14)
    penalty = center_score * 0.30 + min(1.0, texture / 0.30) * 0.28 + large_score * 0.32 - anchor_score * 0.25
    return round(max(0.0, min(1.0, penalty)), 3)


def candidate_role(node: dict[str, Any], separator: bool) -> str:
    if separator:
        return "internal_separator_candidate"
    if node["type"] == "symbol":
        return "internal_icon_candidate"
    if node["type"] == "shape":
        subtype = str(node.get("subtype") or "")
        metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
        bbox = node.get("bbox") if isinstance(node.get("bbox"), list) else [0, 0, 0, 0]
        if subtype in OVERLAY_CONTROL_SUBTYPES and overlay_geometry_score(bbox, metrics) >= 0.60:
            return overlay_role_for_bbox(bbox)
        return "internal_shape_candidate"
    return "internal_decorative_candidate"


def overlay_role_for_bbox(bbox: list[int]) -> str:
    width = max(1, bbox[2])
    height = max(1, bbox[3])
    aspect = width / height
    if 0.78 <= aspect <= 1.28:
        return "internal_circle_control"
    if aspect >= 2.2:
        return "internal_pill_button"
    return "internal_overlay_badge"


def overlay_geometry_score(bbox: list[int], metrics: dict[str, Any]) -> float:
    width = max(1, bbox[2])
    height = max(1, bbox[3])
    aspect = width / height
    fill_ratio = float(metrics.get("fillRatio") or 0.0)
    texture = float(metrics.get("textureScore") or 0.0)
    color_count = int(metrics.get("colorCount") or 0)
    fill_score = max(0.0, min(1.0, fill_ratio / 0.62))
    texture_score = max(0.0, 1.0 - min(1.0, texture / 0.18))
    color_score = max(0.0, 1.0 - min(1.0, color_count / 48))
    if 0.78 <= aspect <= 1.28:
        shape_score = 0.90
    elif aspect >= 1.8:
        shape_score = 1.0
    else:
        shape_score = 0.62
    return round(max(0.0, min(1.0, shape_score * 0.38 + fill_score * 0.28 + texture_score * 0.20 + color_score * 0.14)), 3)


def foreground_layer_evidence(bbox: list[int], media_bbox: list[int], metrics: dict[str, Any]) -> float:
    texture = float(metrics.get("textureScore") or 0.0)
    edge = float(metrics.get("edgeScore") or 0.0)
    fill = float(metrics.get("fillRatio") or 0.0)
    color_count = int(metrics.get("colorCount") or 0)
    area = area_ratio(bbox, media_bbox)
    stability = max(0.0, 1.0 - min(1.0, texture / 0.20)) * 0.32
    boundary = min(1.0, edge / 0.20) * 0.18
    fill_score = min(1.0, fill / 0.65) * 0.24
    color_score = max(0.0, 1.0 - min(1.0, color_count / 64)) * 0.16
    support_size = 0.10 if 0.00005 <= area <= 0.14 else 0.0
    return round(max(0.0, min(1.0, stability + boundary + fill_score + color_score + support_size)), 3)


def pixel_candidate_role(
    *,
    bbox: list[int],
    media_bbox: list[int],
    component: dict[str, Any],
    anchor_relation: str,
    anchor_block: dict[str, Any] | None,
    scale_profile: ImageScaleProfile,
) -> str:
    if anchor_relation == "non_ocr_foreground" and overlay_component_geometry(bbox, media_bbox, component.get("metrics", {}), scale_profile):
        return overlay_role_for_bbox(bbox)
    if anchor_block is not None and selected_marker_geometry(bbox, anchor_block["bbox"], anchor_relation, scale_profile):
        return "selected_marker_candidate"
    if small_marker_geometry(bbox, media_bbox, component.get("metrics", {}), scale_profile) and anchor_relation not in {"above_text", "below_text"}:
        return "status_dot_candidate"
    return "internal_icon_candidate"


def overlay_component_geometry(bbox: list[int], media_bbox: list[int], metrics: dict[str, Any], scale_profile: ImageScaleProfile) -> bool:
    short = min(bbox[2], bbox[3])
    long = max(bbox[2], bbox[3])
    if short < scale_profile.length(16, minimum=10, maximum=56):
        return False
    if long < scale_profile.length(24, minimum=16, maximum=80):
        return False
    if area_ratio(bbox, media_bbox) > 0.16:
        return False
    if overlay_geometry_score(bbox, metrics) < 0.62:
        return False
    return foreground_layer_evidence(bbox, media_bbox, metrics) >= 0.52


def selected_marker_geometry(bbox: list[int], text_bbox: list[int], anchor_relation: str, scale_profile: ImageScaleProfile) -> bool:
    if anchor_relation != "below_text":
        return False
    width = bbox[2]
    height = bbox[3]
    if height <= 0 or width / max(1, height) < SELECTED_MARKER_MIN_ASPECT_RATIO:
        return False
    if height > max(scale_profile.length(18, minimum=5), round(text_bbox[3] * 0.75)):
        return False
    text_center = center_x(text_bbox)
    marker_center = center_x(bbox)
    dx = abs(marker_center - text_center)
    vertical_gap = bbox[1] - y2(text_bbox)
    width_ratio = width / max(1, text_bbox[2])
    return (
        dx <= max(scale_profile.length(12, minimum=4), text_bbox[2] * 0.45)
        and 0 <= vertical_gap <= max(scale_profile.length(28, minimum=8), text_bbox[3] * 1.15)
        and 0.45 <= width_ratio <= 2.20
    )


def small_marker_geometry(bbox: list[int], media_bbox: list[int], metrics: dict[str, Any], scale_profile: ImageScaleProfile) -> bool:
    short = min(bbox[2], bbox[3])
    long = max(bbox[2], bbox[3])
    if short < scale_profile.length(4, minimum=3, maximum=18):
        return False
    if long > scale_profile.length(28, minimum=12, maximum=80):
        return False
    if long / max(1, short) > SMALL_MARKER_MAX_ASPECT_RATIO:
        return False
    if area_ratio(bbox, media_bbox) > 0.035:
        return False
    fill_ratio = float(metrics.get("fillRatio") or 0.0)
    return fill_ratio >= 0.35


def confidence_label(score: float, anchor: float, decision: str) -> str:
    if decision == "rejected_fragment":
        return "low"
    if score >= 0.68 and anchor >= 0.45:
        return "high"
    if score >= 0.45 or anchor >= 0.35:
        return "medium"
    return "low"


def apply_repetition_scores(candidates: list[dict[str, Any]]) -> None:
    accepted = [
        item
        for item in candidates
        if item["candidateDecision"] == "accepted_report_candidate" and item["role"] == "internal_icon_candidate" and item.get("matchedOcrBoxId")
    ]
    if len(accepted) < 2:
        return
    row_score = row_alignment_score([item["bbox"] for item in accepted])
    gap_score = gap_stability_score([item["bbox"] for item in accepted])
    repetition = round((row_score + gap_score) / 2, 3)
    for item in accepted:
        item["scoreBreakdown"]["repetitionScore"] = repetition
        item["score"] = round(min(1.0, item["score"] + repetition * 0.12), 3)
        if repetition >= 0.55:
            item["reasons"].append("repeated_icon_text_row_geometry")
            item["groupSupportedExecution"] = item["confidence"] in {"high", "medium"}
        item["confidence"] = confidence_label(item["score"], item["scoreBreakdown"]["textAnchorScore"], item["candidateDecision"])


def apply_single_control_row_support(candidates: list[dict[str, Any]], text_inside: list[dict[str, Any]], scale_profile: ImageScaleProfile) -> None:
    text_lookup = {block["ocrBoxId"]: block for block in text_inside}
    for item in candidates:
        if item["candidateDecision"] != "accepted_report_candidate" or item["role"] != "internal_icon_candidate":
            continue
        if item.get("groupSupportedExecution") is True:
            continue
        ocr_id = item.get("matchedOcrBoxId")
        block = text_lookup.get(str(ocr_id or ""))
        if block is None:
            continue
        if not single_control_row_icon_geometry(item, block, scale_profile):
            continue
        item["controlRowSupportedExecution"] = True
        item["reasons"].append("single_control_row_icon_text_geometry")


def single_control_row_icon_geometry(candidate: dict[str, Any], block: dict[str, Any], scale_profile: ImageScaleProfile) -> bool:
    relation = str(candidate.get("anchorRelation") or "")
    if relation not in {"above_text", "below_text", "left_of_text", "right_of_text"}:
        return False
    breakdown = candidate.get("scoreBreakdown") if isinstance(candidate.get("scoreBreakdown"), dict) else {}
    text_anchor = float(breakdown.get("textAnchorScore") or 0.0)
    relation_score = float(breakdown.get("relationConsistencyScore") or 0.0)
    text_overlap = float(breakdown.get("textMaskOverlap") or 0.0)
    hero = float(breakdown.get("heroGraphicPenalty") or 0.0)
    compactness = float(breakdown.get("compactnessScore") or 0.0)
    if text_anchor < 0.82 or relation_score < 0.70 or text_overlap > 0.14 or hero > 0.28 or compactness < 0.45:
        return False
    bbox = candidate["bbox"]
    text_bbox = block["bbox"]
    icon_short = min(bbox[2], bbox[3])
    icon_long = max(bbox[2], bbox[3])
    text_height = max(1, text_bbox[3])
    if icon_short < scale_profile.length(8, minimum=5, maximum=40):
        return False
    if icon_long > max(scale_profile.length(96, minimum=36, maximum=220), text_height * 4.2):
        return False
    if bbox_area(bbox) > max(scale_profile.area(7200, minimum=3200), bbox_area(text_bbox) * 2.8):
        return False
    if relation in {"left_of_text", "right_of_text"}:
        vertical_delta = abs(center_y(bbox) - center_y(text_bbox))
        horizontal_gap = text_bbox[0] - x2(bbox) if relation == "left_of_text" else bbox[0] - x2(text_bbox)
        return (
            vertical_delta <= max(scale_profile.length(18, minimum=8, maximum=56), text_height * 0.80)
            and -icon_long * 0.20 <= horizontal_gap <= max(scale_profile.length(52, minimum=16, maximum=140), text_height * 2.3)
            and 0.35 <= bbox[3] / text_height <= 3.4
        )
    horizontal_delta = abs(center_x(bbox) - center_x(text_bbox))
    vertical_gap = text_bbox[1] - y2(bbox) if relation == "above_text" else bbox[1] - y2(text_bbox)
    return (
        horizontal_delta <= max(scale_profile.length(28, minimum=10, maximum=100), text_bbox[2] * 0.55)
        and -icon_long * 0.20 <= vertical_gap <= max(scale_profile.length(52, minimum=16, maximum=140), text_height * 2.3)
        and 0.35 <= bbox[2] / max(1, text_bbox[2]) <= 2.6
    )


def apply_marker_repetition_roles(candidates: list[dict[str, Any]], scale_profile: ImageScaleProfile) -> None:
    markers = [
        item
        for item in candidates
        if item["candidateDecision"] == "accepted_report_candidate" and item["role"] == "status_dot_candidate"
    ]
    if len(markers) < 3:
        return
    repeated_ids: set[str] = set()
    for cluster in aligned_marker_clusters(markers, scale_profile, axis="x"):
        if len(cluster) >= 3:
            repeated_ids.update(item["candidateId"] for item in cluster)
    for cluster in aligned_marker_clusters(markers, scale_profile, axis="y"):
        if len(cluster) >= 3:
            repeated_ids.update(item["candidateId"] for item in cluster)
    for item in markers:
        if item["candidateId"] not in repeated_ids:
            continue
        item["role"] = "table_marker_candidate"
        item["scoreBreakdown"]["repetitionScore"] = max(float(item["scoreBreakdown"].get("repetitionScore") or 0.0), 0.72)
        item["score"] = round(min(1.0, item["score"] + 0.06), 3)
        item["confidence"] = generic_confidence_label(item["score"], item["candidateDecision"])
        item["reasons"].append("repeated_small_marker_geometry")


def apply_foreground_claim_fields(candidates: list[dict[str, Any]]) -> None:
    for item in candidates:
        breakdown = item.get("scoreBreakdown") if isinstance(item.get("scoreBreakdown"), dict) else {}
        foreground_layer = float(breakdown.get("foregroundLayerEvidence") or 0.0)
        overlay_geometry = float(breakdown.get("overlayGeometryScore") or 0.0)
        text_overlap = float(breakdown.get("textMaskOverlap") or 0.0)
        hero = float(breakdown.get("heroGraphicPenalty") or 0.0)
        role = str(item.get("role") or "")
        claim_score = foreground_claim_score(item, foreground_layer, overlay_geometry, text_overlap, hero)
        item["parentMediaSourceObjectId"] = item.get("mediaSourceObjectId")
        item["foregroundClaimId"] = f"{item.get('candidateId')}:foreground_claim"
        item["foregroundLayerEvidence"] = round(foreground_layer, 4)
        item["claimScore"] = claim_score
        item["maskKind"] = mask_kind_for_candidate(item)
        item["claimDecision"] = foreground_claim_decision(item, claim_score, foreground_layer, overlay_geometry, text_overlap, hero)
        if item["claimDecision"] == "propose_foreground_claim" and role in OVERLAY_CONTROL_ROLES:
            if "overlay_control_foreground_claim" not in item["reasons"]:
                item["reasons"].append("overlay_control_foreground_claim")


def foreground_claim_score(item: dict[str, Any], foreground_layer: float, overlay_geometry: float, text_overlap: float, hero: float) -> float:
    breakdown = item.get("scoreBreakdown") if isinstance(item.get("scoreBreakdown"), dict) else {}
    role = str(item.get("role") or "")
    base_score = float(item.get("score") or 0.0)
    compact = float(breakdown.get("compactnessScore") or 0.0)
    repetition = float(breakdown.get("repetitionScore") or 0.0)
    relation = float(breakdown.get("relationConsistencyScore") or 0.0)
    text_containment = float(breakdown.get("textContainmentScore") or 0.0)
    merged_overlay_bonus = 0.08 if role in OVERLAY_CONTROL_ROLES and item.get("sourceFragmentCandidateIds") else 0.0
    compact_weight = 0.08 if role in OVERLAY_CONTROL_ROLES else 0.16
    overlay_weight = 0.28 if role in OVERLAY_CONTROL_ROLES else 0.22
    foreground_weight = 0.26 if role in OVERLAY_CONTROL_ROLES else 0.22
    text_containment_weight = 0.16 if role in {"internal_control_background", "internal_overlay_badge", "internal_pill_button"} else 0.0
    score = (
        base_score * 0.24
        + compact * compact_weight
        + foreground_layer * foreground_weight
        + overlay_geometry * overlay_weight
        + repetition * 0.08
        + relation * 0.08
        + text_containment * text_containment_weight
        + merged_overlay_bonus
        - text_overlap_penalty(role, text_overlap)
        - hero * 0.14
    )
    return round(max(0.0, min(1.0, score)), 4)


def foreground_claim_decision(item: dict[str, Any], claim_score: float, foreground_layer: float, overlay_geometry: float, text_overlap: float, hero: float) -> str:
    if item.get("candidateDecision") != "accepted_report_candidate":
        return "reject"
    role = str(item.get("role") or "")
    if role in OVERLAY_CONTROL_ROLES:
        strong_overlay_geometry = foreground_layer >= 0.64 and overlay_geometry >= 0.84 and claim_score >= 0.70
        text_contained_control = (
            role in {"internal_control_background", "internal_overlay_badge", "internal_pill_button"}
            and text_overlap > 0.30
            and foreground_layer >= 0.54
            and overlay_geometry >= 0.72
            and claim_score >= 0.60
            and hero <= 0.58
        )
        max_text_overlap = 1.0 if role in {"internal_control_background", "internal_overlay_badge", "internal_pill_button"} else 0.24
        if text_contained_control:
            return "propose_foreground_claim"
        if claim_score >= 0.66 and foreground_layer >= 0.56 and overlay_geometry >= 0.60 and text_overlap <= max_text_overlap and hero <= 0.48:
            return "propose_foreground_claim"
        if strong_overlay_geometry and text_overlap <= max_text_overlap and hero <= 0.56:
            return "propose_foreground_claim"
        if claim_score >= 0.42:
            return "report_only"
        return "reject"
    if role in {"selected_marker_candidate", "status_dot_candidate", "table_marker_candidate", "internal_icon_candidate"}:
        if claim_score >= 0.66 and hero <= 0.48 and text_overlap <= 0.24:
            return "propose_foreground_claim"
        if claim_score >= 0.42:
            return "report_only"
    return "report_only" if claim_score >= 0.42 else "reject"


def mask_kind_for_candidate(item: dict[str, Any]) -> str:
    role = str(item.get("role") or "")
    if role == "internal_circle_control" or circular_bbox(item.get("bbox") or [0, 0, 0, 0]):
        return "circle"
    if role in {"internal_overlay_badge", "internal_pill_button", "internal_control_background"}:
        return "rounded_rect"
    if role == "internal_icon_candidate":
        return "alpha"
    return "bbox"


def text_overlap_penalty(role: str, text_overlap: float) -> float:
    if role in {"internal_control_background", "internal_overlay_badge", "internal_pill_button"}:
        return min(1.0, text_overlap / 1.0) * 0.02
    return min(1.0, text_overlap / 0.30) * 0.18


def text_containment_score(role: str, text_overlap: float, anchor_score: float) -> float:
    if role not in {"internal_control_background", "internal_overlay_badge", "internal_pill_button"}:
        return 0.0
    if text_overlap <= 0:
        return 0.0
    return round(max(0.0, min(1.0, text_overlap * 0.72 + anchor_score * 0.28)), 3)


def should_reject_text_overlap(role: str, text_overlap: float) -> bool:
    if role in {"internal_control_background", "internal_overlay_badge", "internal_pill_button"}:
        return False
    return text_overlap > 0.30


def should_reject_large_fragment(
    role: str,
    ratio: float,
    *,
    foreground_layer: float,
    overlay_geometry: float,
    hero: float,
) -> bool:
    if role in {"internal_control_background", "internal_overlay_badge", "internal_pill_button"}:
        if ratio <= 0.60 and foreground_layer >= 0.50 and overlay_geometry >= 0.72 and hero <= 0.58:
            return False
        return ratio > 0.60
    return ratio > 0.18


def circular_bbox(bbox: list[int]) -> bool:
    if len(bbox) != 4 or bbox[2] <= 0 or bbox[3] <= 0:
        return False
    ratio = bbox[2] / max(1, bbox[3])
    return 0.78 <= ratio <= 1.28


def merge_overlay_control_fragments(
    media: dict[str, Any],
    candidates: list[dict[str, Any]],
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    start_index: int,
    scale_profile: ImageScaleProfile,
) -> list[dict[str, Any]]:
    fragments = [
        item
        for item in candidates
        if item["candidateDecision"] == "accepted_report_candidate"
        and (
            (item["rawType"] == "shape" and item["rawSubtype"] in OVERLAY_CONTROL_SUBTYPES)
            or (item["rawType"] == "pixel_component" and item["role"] in OVERLAY_CONTROL_ROLES)
        )
        and area_ratio(item["bbox"], media["bbox"]) <= 0.14
    ]
    if len(fragments) < 2:
        return []
    clusters = overlay_fragment_clusters(fragments, scale_profile)
    merged: list[dict[str, Any]] = []
    existing_bboxes = [item["bbox"] for item in candidates if item["candidateDecision"] == "accepted_report_candidate"]
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        bbox = cluster[0]["bbox"]
        for item in cluster[1:]:
            bbox = union_bbox(bbox, item["bbox"])
        if any(is_near_equal(bbox, existing, 0.94) or containment_ratio(bbox, existing) >= 0.96 for existing in existing_bboxes):
            continue
        candidate = score_merged_overlay_candidate(
            media=media,
            bbox=bbox,
            fragments=cluster,
            text_masks=text_masks,
            text_inside=text_inside,
            index=start_index + len(merged),
            scale_profile=scale_profile,
        )
        if candidate["candidateDecision"] == "accepted_report_candidate":
            existing_bboxes.append(candidate["bbox"])
        merged.append(candidate)
    return merged


def overlay_fragment_clusters(fragments: list[dict[str, Any]], scale_profile: ImageScaleProfile) -> list[list[dict[str, Any]]]:
    remaining = sorted(fragments, key=lambda item: (item["bbox"][1], item["bbox"][0]))
    clusters: list[list[dict[str, Any]]] = []
    gap_limit = scale_profile.length(12, minimum=4, maximum=48)
    while remaining:
        cluster = [remaining.pop(0)]
        changed = True
        while changed:
            changed = False
            for item in list(remaining):
                if any(overlay_fragments_mergeable(item, member, gap_limit) for member in cluster):
                    cluster.append(item)
                    remaining.remove(item)
                    changed = True
        clusters.append(sorted(cluster, key=lambda item: item["bbox"][0]))
    return clusters


def overlay_fragments_mergeable(left: dict[str, Any], right: dict[str, Any], gap_limit: int) -> bool:
    left_box = left["bbox"]
    right_box = right["bbox"]
    vertical_overlap = intersection_1d(left_box[1], y2(left_box), right_box[1], y2(right_box)) / max(1, min(left_box[3], right_box[3]))
    horizontal_overlap = intersection_1d(left_box[0], x2(left_box), right_box[0], x2(right_box)) / max(1, min(left_box[2], right_box[2]))
    horizontal_gap = max(0, max(left_box[0], right_box[0]) - min(x2(left_box), x2(right_box)))
    vertical_gap = max(0, max(left_box[1], right_box[1]) - min(y2(left_box), y2(right_box)))
    left_metrics = left.get("metrics") if isinstance(left.get("metrics"), dict) else {}
    right_metrics = right.get("metrics") if isinstance(right.get("metrics"), dict) else {}
    brightness_delta = abs(float(left_metrics.get("brightness") or 0.0) - float(right_metrics.get("brightness") or 0.0))
    return (
        brightness_delta <= 48
        and (
            (vertical_overlap >= 0.42 and horizontal_gap <= gap_limit)
            or (horizontal_overlap >= 0.42 and vertical_gap <= gap_limit)
        )
    )


def score_merged_overlay_candidate(
    *,
    media: dict[str, Any],
    bbox: list[int],
    fragments: list[dict[str, Any]],
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    index: int,
    scale_profile: ImageScaleProfile,
) -> dict[str, Any]:
    text_overlap = max((overlap_ratio(bbox, mask["paddedBbox"]) for mask in text_masks), default=0.0)
    best_anchor = best_text_anchor(bbox, text_inside)
    fill_ratio = min(1.0, sum(bbox_area(fragment["bbox"]) * float(fragment["metrics"].get("fillRatio") or 0.0) for fragment in fragments) / max(1, bbox_area(bbox)))
    texture = sum(float(fragment["metrics"].get("textureScore") or 0.0) for fragment in fragments) / len(fragments)
    edge = max(float(fragment["metrics"].get("edgeScore") or 0.0) for fragment in fragments)
    color_count = max(int(fragment["metrics"].get("colorCount") or 0) for fragment in fragments)
    brightness = sum(float(fragment["metrics"].get("brightness") or 0.0) for fragment in fragments) / len(fragments)
    mean_rgb = average_mean_rgb(fragments)
    metrics = {
        "fillRatio": round(fill_ratio, 4),
        "textureScore": round(texture, 4),
        "edgeScore": round(edge, 4),
        "colorCount": color_count,
        "brightness": round(brightness, 3),
        "meanRgb": mean_rgb,
    }
    size = size_score(bbox, media["bbox"], scale_profile)
    compact = compactness_score(bbox, metrics)
    color = color_coherence_score(metrics)
    overlay_geometry = overlay_geometry_score(bbox, metrics)
    foreground_layer = foreground_layer_evidence(bbox, media["bbox"], metrics)
    hero = hero_graphic_penalty(bbox, media["bbox"], metrics, best_anchor["score"])
    text_containment = text_containment_score(overlay_role_for_bbox(bbox), text_overlap, best_anchor["score"])
    score = round(
        size * 0.16
        + compact * 0.18
        + color * 0.10
        + overlay_geometry * 0.22
        + foreground_layer * 0.20
        + best_anchor["score"] * 0.08
        + text_containment * 0.16
        - hero * 0.14
        + 0.08,
        3,
    )
    role = overlay_role_for_bbox(bbox)
    decision = "accepted_report_candidate"
    risks: list[str] = []
    if should_reject_text_overlap(role, text_overlap):
        decision = "rejected_fragment"
        risks.append("overlaps_internal_text_mask")
    if should_reject_large_fragment(
        role,
        area_ratio(bbox, media["bbox"]),
        foreground_layer=foreground_layer,
        overlay_geometry=overlay_geometry,
        hero=hero,
    ):
        decision = "rejected_fragment"
        risks.append("large_media_fragment")
    if hero >= 0.62 and foreground_layer < 0.55:
        decision = "rejected_fragment"
        risks.append("hero_or_texture_fragment")
    if overlay_geometry < 0.55 or score < 0.58:
        decision = "rejected_fragment"
        risks.append("weak_overlay_control_score")
    return {
        "candidateId": f"{media['sourceObjectId']}:internal_candidate_{index:04d}",
        "mediaSourceObjectId": media["sourceObjectId"],
        "rawNodeId": "merged_overlay_" + "_".join(fragment["rawNodeId"] for fragment in fragments),
        "rawType": "merged_shape_fragment",
        "rawSubtype": "overlay_control",
        "role": role,
        "bbox": bbox,
        "candidateDecision": decision,
        "confidence": generic_confidence_label(score, decision),
        "score": score,
        "scoreBreakdown": {
            "sizeScore": size,
            "compactnessScore": compact,
            "colorCoherenceScore": color,
            "textAnchorScore": round(best_anchor["score"], 3),
            "relationConsistencyScore": round(best_anchor["relationScore"], 3),
            "repetitionScore": 0.0,
            "heroGraphicPenalty": hero,
            "textMaskOverlap": text_overlap,
            "textContainmentScore": text_containment,
            "foregroundLayerEvidence": foreground_layer,
            "overlayGeometryScore": overlay_geometry,
        },
        "matchedOcrBoxId": best_anchor["ocrBoxId"] if best_anchor["score"] >= 0.30 else None,
        "anchorRelation": best_anchor["relation"] if best_anchor["score"] >= 0.30 else "non_ocr_foreground",
        "metrics": {
            "areaRatioInMedia": area_ratio(bbox, media["bbox"]),
            "rawConfidence": round(sum(float(fragment["metrics"].get("rawConfidence") or 0.0) for fragment in fragments) / len(fragments), 3),
            "fillRatio": round(fill_ratio, 4),
            "textureScore": round(texture, 4),
            "colorCount": color_count,
        },
        "sourceFragmentCandidateIds": [fragment["candidateId"] for fragment in fragments],
        "reasons": ["merged_overlay_control_fragments"],
        "risks": risks,
        "reportOnly": True,
    }


def average_mean_rgb(fragments: list[dict[str, Any]]) -> list[int]:
    values: list[list[float]] = []
    for fragment in fragments:
        metrics = fragment.get("metrics") if isinstance(fragment.get("metrics"), dict) else {}
        rgb = metrics.get("meanRgb")
        if isinstance(rgb, list) and len(rgb) == 3:
            values.append([float(rgb[0]), float(rgb[1]), float(rgb[2])])
    if not values:
        return [0, 0, 0]
    return [round(sum(item[channel] for item in values) / len(values)) for channel in range(3)]


def aligned_marker_clusters(markers: list[dict[str, Any]], scale_profile: ImageScaleProfile, *, axis: str) -> list[list[dict[str, Any]]]:
    threshold = scale_profile.length(10, minimum=5, maximum=40)
    ordered = sorted(markers, key=lambda item: center_x(item["bbox"]) if axis == "x" else center_y(item["bbox"]))
    clusters: list[list[dict[str, Any]]] = []
    for marker in ordered:
        marker_center = center_x(marker["bbox"]) if axis == "x" else center_y(marker["bbox"])
        placed = False
        for cluster in clusters:
            centers = [center_x(item["bbox"]) if axis == "x" else center_y(item["bbox"]) for item in cluster]
            if abs(marker_center - median(centers)) <= threshold and marker_size_compatible(marker, cluster):
                cluster.append(marker)
                placed = True
                break
        if not placed:
            clusters.append([marker])
    return clusters


def marker_size_compatible(marker: dict[str, Any], cluster: list[dict[str, Any]]) -> bool:
    marker_area = bbox_area(marker["bbox"])
    areas = [bbox_area(item["bbox"]) for item in cluster]
    median_area = median(areas)
    ratio = marker_area / max(1, median_area)
    return 0.45 <= ratio <= 2.20


def merge_anchor_icon_fragments(
    media: dict[str, Any],
    candidates: list[dict[str, Any]],
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    start_index: int,
    scale_profile: ImageScaleProfile,
) -> list[dict[str, Any]]:
    fragments_by_anchor: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidates:
        if candidate["candidateDecision"] != "accepted_report_candidate" or candidate["role"] != "internal_icon_candidate":
            continue
        ocr_id = candidate.get("matchedOcrBoxId")
        relation = candidate.get("anchorRelation")
        if not ocr_id or relation not in {"above_text", "below_text", "left_of_text", "right_of_text"}:
            continue
        fragments_by_anchor.setdefault((ocr_id, relation), []).append(candidate)

    merged: list[dict[str, Any]] = []
    existing_bboxes = [item["bbox"] for item in candidates if item["candidateDecision"] == "accepted_report_candidate"]
    for (ocr_id, relation), fragments in fragments_by_anchor.items():
        if len(fragments) < 2:
            continue
        ordered = sorted(fragments, key=lambda item: item["score"], reverse=True)
        for first_index, first in enumerate(ordered):
            for second in ordered[first_index + 1 :]:
                if not mergeable_icon_fragments(first["bbox"], second["bbox"], relation, scale_profile):
                    continue
                bbox = union_bbox(first["bbox"], second["bbox"])
                if any(is_near_equal(bbox, existing, 0.92) or containment_ratio(bbox, existing) >= 0.94 for existing in existing_bboxes):
                    continue
                candidate = score_merged_anchor_candidate(
                    media=media,
                    bbox=bbox,
                    fragments=[first, second],
                    ocr_id=ocr_id,
                    anchor_relation=relation,
                    text_masks=text_masks,
                    text_inside=text_inside,
                    index=start_index + len(merged),
                    scale_profile=scale_profile,
                )
                if candidate["candidateDecision"] == "accepted_report_candidate":
                    existing_bboxes.append(candidate["bbox"])
                merged.append(candidate)
                break
            if merged and merged[-1].get("sourceFragmentCandidateIds") and first["candidateId"] in merged[-1]["sourceFragmentCandidateIds"]:
                break
    return merged


def mergeable_icon_fragments(left: list[int], right: list[int], relation: str, scale_profile: ImageScaleProfile) -> bool:
    union = union_bbox(left, right)
    if bbox_area(union) > scale_profile.area(12000, minimum=12000) or long_thin(union):
        return False
    if relation in {"above_text", "below_text"}:
        horizontal_overlap = intersection_1d(left[0], x2(left), right[0], x2(right)) / max(1, min(left[2], right[2]))
        horizontal_center_delta = abs(center_x(left) - center_x(right))
        vertical_gap = max(0, max(left[1], right[1]) - min(y2(left), y2(right)))
        return (
            horizontal_overlap >= 0.25
            and horizontal_center_delta <= max(left[2], right[2]) * 0.60
            and vertical_gap <= max(scale_profile.length(8, minimum=4), min(left[3], right[3]) * 0.65)
        )
    vertical_overlap = intersection_1d(left[1], y2(left), right[1], y2(right)) / max(1, min(left[3], right[3]))
    vertical_center_delta = abs(center_y(left) - center_y(right))
    horizontal_gap = max(0, max(left[0], right[0]) - min(x2(left), x2(right)))
    return (
        vertical_overlap >= 0.25
        and vertical_center_delta <= max(left[3], right[3]) * 0.60
        and horizontal_gap <= max(scale_profile.length(8, minimum=4), min(left[2], right[2]) * 0.65)
    )


def score_merged_anchor_candidate(
    *,
    media: dict[str, Any],
    bbox: list[int],
    fragments: list[dict[str, Any]],
    ocr_id: str,
    anchor_relation: str,
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    index: int,
    scale_profile: ImageScaleProfile,
) -> dict[str, Any]:
    text_overlap = max((overlap_ratio(bbox, mask["paddedBbox"]) for mask in text_masks), default=0.0)
    anchor_block = next((block for block in text_inside if block["ocrBoxId"] == ocr_id), None)
    union_anchor = directional_anchor_score(bbox, anchor_block["bbox"], anchor_relation) if anchor_block else {"score": 0.0, "relationScore": 0.0}
    anchor_score = max(union_anchor["score"], max((fragment["scoreBreakdown"]["textAnchorScore"] for fragment in fragments), default=0.0))
    fill_ratio = min(1.0, sum(bbox_area(fragment["bbox"]) * float(fragment["metrics"].get("fillRatio") or 0.0) for fragment in fragments) / max(1, bbox_area(bbox)))
    texture = sum(float(fragment["metrics"].get("textureScore") or 0.0) for fragment in fragments) / len(fragments)
    color_count = max(int(fragment["metrics"].get("colorCount") or 0) for fragment in fragments)
    metrics = {"fillRatio": round(fill_ratio, 4), "textureScore": round(texture, 4), "colorCount": color_count}
    size = size_score(bbox, media["bbox"], scale_profile)
    compact = compactness_score(bbox, metrics)
    color = color_coherence_score(metrics)
    hero = hero_graphic_penalty(bbox, media["bbox"], metrics, anchor_score)
    score = round(size * 0.18 + compact * 0.16 + color * 0.12 + anchor_score * 0.34 - hero * 0.20 + 0.06, 3)
    decision = "accepted_report_candidate"
    risks: list[str] = []
    if text_overlap > 0.30:
        decision = "rejected_fragment"
        risks.append("overlaps_internal_text_mask")
    if area_ratio(bbox, media["bbox"]) > 0.12:
        decision = "rejected_fragment"
        risks.append("large_media_fragment")
    if hero >= 0.62 and anchor_score < 0.35:
        decision = "rejected_fragment"
        risks.append("hero_or_texture_fragment")
    if score < 0.50 and anchor_score < 0.45:
        decision = "rejected_fragment"
        risks.append("weak_merged_fragment_score")
    return {
        "candidateId": f"{media['sourceObjectId']}:internal_candidate_{index:04d}",
        "mediaSourceObjectId": media["sourceObjectId"],
        "rawNodeId": "merged_" + "_".join(fragment["rawNodeId"] for fragment in fragments),
        "rawType": "merged_fragment",
        "rawSubtype": anchor_relation,
        "role": "internal_icon_candidate",
        "bbox": bbox,
        "candidateDecision": decision,
        "confidence": confidence_label(score, anchor_score, decision),
        "score": score,
        "scoreBreakdown": {
            "sizeScore": size,
            "compactnessScore": compact,
            "colorCoherenceScore": color,
            "textAnchorScore": round(anchor_score, 3),
            "relationConsistencyScore": round(max(float(union_anchor["relationScore"]), anchor_score), 3),
            "repetitionScore": 0.0,
            "heroGraphicPenalty": hero,
            "textMaskOverlap": text_overlap,
        },
        "matchedOcrBoxId": ocr_id,
        "anchorRelation": anchor_relation,
        "metrics": {
            "areaRatioInMedia": area_ratio(bbox, media["bbox"]),
            "rawConfidence": round(sum(float(fragment["metrics"].get("rawConfidence") or 0.0) for fragment in fragments) / len(fragments), 3),
            "fillRatio": round(fill_ratio, 4),
            "textureScore": round(texture, 4),
            "colorCount": color_count,
        },
        "sourceFragmentCandidateIds": [fragment["candidateId"] for fragment in fragments],
        "reasons": ["merged_anchor_icon_fragments", "text_anchor_geometry"],
        "risks": risks,
        "reportOnly": True,
        "groupSupportedExecution": decision == "accepted_report_candidate",
    }


def union_bbox(left: list[int], right: list[int]) -> list[int]:
    left_x = min(left[0], right[0])
    top = min(left[1], right[1])
    return [left_x, top, max(x2(left), x2(right)) - left_x, max(y2(left), y2(right)) - top]


def intersection_1d(left_start: int, left_end: int, right_start: int, right_end: int) -> int:
    return max(0, min(left_end, right_end) - max(left_start, right_start))


def build_matched_internal_groups(
    internal_candidates: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
    media_source_object_id: str,
    group_index: int,
) -> list[dict[str, Any]]:
    by_ocr: dict[str, dict[str, Any]] = {}
    for candidate in internal_candidates:
        if candidate["candidateDecision"] != "accepted_report_candidate" or candidate["role"] != "internal_icon_candidate":
            continue
        ocr_id = candidate.get("matchedOcrBoxId")
        if not ocr_id:
            continue
        current = by_ocr.get(ocr_id)
        if current is None or candidate["score"] > current["score"]:
            by_ocr[ocr_id] = candidate
    if len(by_ocr) < 2:
        return []
    block_lookup = {block["ocrBoxId"]: block for block in ocr_blocks}
    pairs = [(block_lookup[ocr_id], candidate) for ocr_id, candidate in by_ocr.items() if ocr_id in block_lookup]
    pairs = sorted(pairs, key=lambda item: center_x(item[0]["bbox"]))
    groups: list[dict[str, Any]] = []
    for cluster in row_pair_clusters(pairs):
        if len(cluster) < 2:
            continue
        icon_boxes = [candidate["bbox"] for _, candidate in cluster]
        text_boxes = [block["bbox"] for block, _ in cluster]
        row_score = min(row_alignment_score(icon_boxes), row_alignment_score(text_boxes))
        gap_score = min(gap_stability_score(icon_boxes), gap_stability_score(text_boxes))
        confidence = round(0.40 + row_score * 0.25 + gap_score * 0.20 + min(len(cluster), 4) * 0.035, 3)
        if confidence < 0.50:
            continue
        groups.append(
            {
                "groupId": f"m29_media_internal_group_{group_index + len(groups):04d}",
                "mediaSourceObjectId": media_source_object_id,
                "role": "action_row",
                "layoutModel": "row",
                "items": [
                    {
                        "candidateId": candidate["candidateId"],
                        "rawNodeId": candidate["rawNodeId"],
                        "ocrBoxId": block["ocrBoxId"],
                        "iconBbox": candidate["bbox"],
                        "textBbox": block["bbox"],
                    }
                    for block, candidate in cluster
                ],
                "score": min(1.0, confidence),
                "confidence": "high" if confidence >= 0.74 else "medium" if confidence >= 0.55 else "low",
                "metrics": {
                    "itemCount": len(cluster),
                    "iconRowAlignmentScore": row_alignment_score(icon_boxes),
                    "textRowAlignmentScore": row_alignment_score(text_boxes),
                    "iconGapStabilityScore": gap_stability_score(icon_boxes),
                    "textGapStabilityScore": gap_stability_score(text_boxes),
                },
                "reasons": ["text_anchor_pairs", "repeated_row_geometry"],
                "reportOnly": True,
            }
        )
    return groups


def row_pair_clusters(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[list[tuple[dict[str, Any], dict[str, Any]]]]:
    ordered = sorted(pairs, key=lambda item: center_y(item[0]["bbox"]))
    clusters: list[list[tuple[dict[str, Any], dict[str, Any]]]] = []
    for pair in ordered:
        block, candidate = pair
        placed = False
        for cluster in clusters:
            text_boxes = [item[0]["bbox"] for item in cluster]
            icon_boxes = [item[1]["bbox"] for item in cluster]
            text_threshold = max(10.0, median([bbox[3] for bbox in text_boxes + [block["bbox"]]]) * 0.85)
            icon_threshold = max(14.0, median([bbox[3] for bbox in icon_boxes + [candidate["bbox"]]]) * 1.25)
            if (
                abs(center_y(block["bbox"]) - median([center_y(bbox) for bbox in text_boxes])) <= text_threshold
                and abs(center_y(candidate["bbox"]) - median([center_y(bbox) for bbox in icon_boxes])) <= icon_threshold
            ):
                cluster.append(pair)
                placed = True
                break
        if not placed:
            clusters.append([pair])
    return [sorted(cluster, key=lambda item: center_x(item[0]["bbox"])) for cluster in clusters]


def apply_group_support(candidates: list[dict[str, Any]], groups: list[dict[str, Any]]) -> None:
    supported_ids = {
        item["candidateId"]
        for group in groups
        if group.get("role") == "action_row" and group.get("confidence") in {"high", "medium"}
        for item in group.get("items", [])
        if isinstance(item, dict) and item.get("candidateId")
    }
    if not supported_ids:
        return
    for candidate in candidates:
        if candidate["candidateId"] not in supported_ids:
            continue
        if candidate["candidateDecision"] != "accepted_report_candidate" or candidate["role"] != "internal_icon_candidate":
            continue
        if candidate["confidence"] == "medium":
            candidate["groupSupportedExecution"] = True
            candidate["reasons"].append("group_supported_medium_internal_icon")
        elif candidate["confidence"] == "high":
            candidate["groupSupportedExecution"] = True


def pixel_anchor_candidates(
    *,
    media: dict[str, Any],
    pixels: PngPixels,
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    existing_candidates: list[dict[str, Any]],
    start_index: int,
    scale_profile: ImageScaleProfile,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_bboxes = [item["bbox"] for item in existing_candidates if item["candidateDecision"] == "accepted_report_candidate"]
    for block in text_inside:
        for window in anchor_windows(block["bbox"], media["bbox"], pixels.width, pixels.height, scale_profile):
            for component in foreground_components_in_window(
                pixels,
                window["bbox"],
                text_masks,
                scale_profile,
                allow_thin_marker=window["relation"] == "below_text",
            ):
                bbox = component["bbox"]
                if any(is_near_equal(bbox, existing, 0.72) or containment_ratio(bbox, existing) >= 0.82 for existing in seen_bboxes):
                    continue
                candidate = score_pixel_anchor_candidate(
                    media=media,
                    bbox=bbox,
                    component=component,
                    anchor_block=block,
                    anchor_relation=window["relation"],
                    text_masks=text_masks,
                    text_inside=text_inside,
                    index=start_index + len(candidates),
                    scale_profile=scale_profile,
                )
                if candidate["candidateDecision"] == "accepted_report_candidate":
                    seen_bboxes.append(candidate["bbox"])
                candidates.append(candidate)
    return candidates


def generic_foreground_candidates(
    *,
    media: dict[str, Any],
    pixels: PngPixels,
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    existing_candidates: list[dict[str, Any]],
    start_index: int,
    scale_profile: ImageScaleProfile,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_bboxes = [item["bbox"] for item in existing_candidates if item["candidateDecision"] == "accepted_report_candidate"]
    max_candidates = generic_foreground_candidate_budget(media["bbox"], scale_profile)
    for window in generic_scan_windows(media["bbox"], pixels.width, pixels.height, scale_profile):
        for component in foreground_components_in_window(pixels, window["bbox"], text_masks, scale_profile):
            bbox = component["bbox"]
            if any(is_near_equal(bbox, existing, 0.72) or containment_ratio(bbox, existing) >= 0.82 for existing in seen_bboxes):
                continue
            candidate = score_generic_foreground_candidate(
                media=media,
                bbox=bbox,
                component=component,
                text_masks=text_masks,
                text_inside=text_inside,
                index=start_index + len(candidates),
                scale_profile=scale_profile,
            )
            if candidate["candidateDecision"] == "accepted_report_candidate":
                seen_bboxes.append(candidate["bbox"])
            candidates.append(candidate)
            if len(candidates) >= max_candidates:
                return candidates
    return candidates


def text_support_control_candidates(
    *,
    media: dict[str, Any],
    pixels: PngPixels,
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    existing_candidates: list[dict[str, Any]],
    start_index: int,
    scale_profile: ImageScaleProfile,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_bboxes = [item["bbox"] for item in existing_candidates if item["candidateDecision"] == "accepted_report_candidate"]
    options = internal_support_options(media, scale_profile)
    image = PngMetadata(pixels.width, pixels.height, 8, 2, 0, 0, 0)
    foreground_bboxes = [
        item["bbox"]
        for item in existing_candidates
        if item["candidateDecision"] == "accepted_report_candidate"
        and item.get("role") in {"internal_icon_candidate", "selected_marker_candidate", "status_dot_candidate", "table_marker_candidate"}
    ]
    for block in text_inside:
        if not text_can_anchor_control_background(block["bbox"], media["bbox"], scale_profile):
            continue
        for bbox, source in text_support_candidate_bboxes(pixels, block["bbox"], foreground_bboxes, image, options):
            if containment_ratio(bbox, media["bbox"]) < 0.95:
                continue
            if any(is_near_equal(bbox, existing, 0.78) or containment_ratio(bbox, existing) >= 0.88 for existing in seen_bboxes):
                continue
            candidate = score_text_support_control_candidate(
                media=media,
                pixels=pixels,
                bbox=bbox,
                source=source,
                anchor_block=block,
                text_masks=text_masks,
                text_inside=text_inside,
                index=start_index + len(candidates),
                scale_profile=scale_profile,
                options=options,
            )
            if candidate["candidateDecision"] == "accepted_report_candidate":
                seen_bboxes.append(candidate["bbox"])
            candidates.append(candidate)
    return candidates


def internal_support_options(media: dict[str, Any], scale_profile: ImageScaleProfile) -> M29VisualPrimitiveOptions:
    media_bbox = media["bbox"]
    media_area = max(1, bbox_area(media_bbox))
    min_height = scale_profile.length(18, minimum=14, maximum=72)
    max_area_ratio = max(0.08, min(0.28, scale_profile.area(26000, minimum=9000, maximum=90000) / media_area))
    return M29VisualPrimitiveOptions(
        low_contrast_support_min_width=scale_profile.length(48, minimum=36, maximum=180),
        low_contrast_support_min_height=min_height,
        low_contrast_support_max_area_ratio=max_area_ratio,
        low_contrast_support_max_width_ratio=0.96,
        low_contrast_support_max_texture=0.18,
        low_contrast_support_max_color_count=320,
        low_contrast_support_min_edge_delta=4,
        low_contrast_support_max_edge_delta=150,
        text_support_background_min_area_ratio=1.10,
        text_support_background_max_area_ratio=14.00,
        text_support_background_min_aspect=1.60,
    )


def text_can_anchor_control_background(text_bbox: list[int], media_bbox: list[int], scale_profile: ImageScaleProfile) -> bool:
    if text_bbox[2] < scale_profile.length(18, minimum=12, maximum=96):
        return False
    if text_bbox[3] < scale_profile.length(8, minimum=6, maximum=36):
        return False
    if area_ratio(text_bbox, media_bbox) > 0.08:
        return False
    return True


def text_support_candidate_bboxes(
    pixels: PngPixels,
    text_bbox: list[int],
    foreground_bboxes: list[list[int]],
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> list[tuple[list[int], str]]:
    candidates: list[tuple[list[int], str]] = []
    text_support = find_text_support_background_bbox(pixels, text_bbox, image, options)
    if text_support is not None:
        candidates.append((text_support, "text_support_background"))
    low_contrast = find_low_contrast_support_bbox(pixels, text_bbox, foreground_bboxes, image, options)
    if low_contrast is not None:
        candidates.append((low_contrast, "low_contrast_support_background"))
    for bbox in expanded_text_support_bboxes(text_bbox, image, options):
        if score_text_support_background_candidate(pixels, bbox, text_bbox, image, options) is not None:
            candidates.append((bbox, "expanded_text_support_background"))
    return dedupe_support_bboxes(candidates)


def expanded_text_support_bboxes(text_bbox: list[int], image: PngMetadata, options: M29VisualPrimitiveOptions) -> list[list[int]]:
    _, _, width, height = text_bbox
    pad_x_values = [
        max(8, round(width * 0.55)),
        max(10, round(width * 0.80)),
        max(12, round(width * 1.05)),
        max(14, round(width * 1.35)),
        max(16, round(width * 1.70)),
    ]
    pad_y_values = [
        max(4, round(height * 0.55)),
        max(6, round(height * 0.85)),
        max(8, round(height * 1.10)),
    ]
    max_width = round(image.width * options.low_contrast_support_max_width_ratio)
    max_height = max(options.low_contrast_support_min_height, min(140, round(height * 3.4)))
    bboxes: list[list[int]] = []
    for pad_x in pad_x_values:
        for pad_y in pad_y_values:
            bbox = clamp_bbox_to_media(
                [text_bbox[0] - pad_x, text_bbox[1] - pad_y, text_bbox[2] + pad_x * 2, text_bbox[3] + pad_y * 2],
                [0, 0, image.width, image.height],
                image.width,
                image.height,
            )
            if bbox is None:
                continue
            if bbox[2] > max_width or bbox[3] > max_height:
                continue
            bboxes.append(bbox)
    return bboxes


def dedupe_support_bboxes(candidates: list[tuple[list[int], str]]) -> list[tuple[list[int], str]]:
    deduped: list[tuple[list[int], str]] = []
    for bbox, source in sorted(candidates, key=lambda item: (bbox_area(item[0]), item[0][1], item[0][0])):
        if any(is_near_equal(bbox, existing, 0.88) for existing, _ in deduped):
            continue
        deduped.append((bbox, source))
    return deduped[:4]


def score_text_support_control_candidate(
    *,
    media: dict[str, Any],
    pixels: PngPixels,
    bbox: list[int],
    source: str,
    anchor_block: dict[str, Any],
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    index: int,
    scale_profile: ImageScaleProfile,
    options: M29VisualPrimitiveOptions,
) -> dict[str, Any]:
    text_bbox = anchor_block["bbox"]
    metrics_model = support_region_metrics(pixels, bbox)
    ignored = [mask["paddedBbox"] for mask in text_masks if overlap_ratio(mask["paddedBbox"], bbox) > 0]
    geometry = fit_low_contrast_support_geometry(pixels, bbox, ignored + [text_bbox])
    radius = geometry_radius(geometry, bbox)
    metrics = {
        "fillRatio": round(metrics_model.fill_ratio, 4),
        "textureScore": round(metrics_model.texture_score, 4),
        "edgeScore": round(metrics_model.edge_score, 4),
        "colorCount": int(metrics_model.color_count),
        "brightness": round(metrics_model.brightness, 3),
        "meanRgb": [int(value) for value in metrics_model.mean_rgb],
        **({"shapeRadius": radius} if radius is not None else {}),
    }
    text_overlap = max((overlap_ratio(bbox, mask["paddedBbox"]) for mask in text_masks), default=0.0)
    best_anchor = best_text_anchor(bbox, text_inside)
    size = size_score(bbox, media["bbox"], scale_profile)
    compact = compactness_score(bbox, metrics)
    color = color_coherence_score(metrics)
    overlay_geometry = max(overlay_geometry_score(bbox, metrics), support_geometry_score(geometry, bbox))
    foreground_layer = foreground_layer_evidence(bbox, media["bbox"], metrics)
    hero = hero_graphic_penalty(bbox, media["bbox"], metrics, max(best_anchor["score"], 0.80))
    role = overlay_role_for_bbox(bbox)
    text_containment = text_containment_score(role, text_overlap, max(best_anchor["score"], 0.86))
    support_score = normalized_support_score(score_text_support_background_candidate(pixels, bbox, text_bbox, PngMetadata(pixels.width, pixels.height, 8, 2, 0, 0, 0), options))
    score = round(
        size * 0.10
        + compact * 0.12
        + color * 0.08
        + overlay_geometry * 0.22
        + foreground_layer * 0.18
        + text_containment * 0.18
        + support_score * 0.12
        - hero * 0.08,
        3,
    )
    decision = "accepted_report_candidate"
    risks: list[str] = []
    if role == "internal_circle_control":
        role = "internal_control_background"
    if text_overlap <= 0.24:
        decision = "rejected_fragment"
        risks.append("missing_text_containment_evidence")
    if should_reject_large_fragment(
        role,
        area_ratio(bbox, media["bbox"]),
        foreground_layer=foreground_layer,
        overlay_geometry=overlay_geometry,
        hero=hero,
    ):
        decision = "rejected_fragment"
        risks.append("large_media_fragment")
    if overlay_geometry < 0.58 or foreground_layer < 0.44:
        decision = "rejected_fragment"
        risks.append("weak_support_geometry")
    if hero >= 0.62 and overlay_geometry < 0.74:
        decision = "rejected_fragment"
        risks.append("hero_or_texture_fragment")
    if score < 0.58:
        decision = "rejected_fragment"
        risks.append("weak_text_support_control_score")
    return {
        "candidateId": f"{media['sourceObjectId']}:internal_candidate_{index:04d}",
        "mediaSourceObjectId": media["sourceObjectId"],
        "rawNodeId": f"text_support_control_{anchor_block['ocrBoxId']}_{index:04d}",
        "rawType": "inferred_shape",
        "rawSubtype": source,
        "role": role,
        "bbox": bbox,
        "candidateDecision": decision,
        "confidence": generic_confidence_label(score, decision),
        "score": score,
        "scoreBreakdown": {
            "sizeScore": size,
            "compactnessScore": compact,
            "colorCoherenceScore": color,
            "textAnchorScore": round(max(best_anchor["score"], 0.86), 3),
            "relationConsistencyScore": round(max(best_anchor["relationScore"], 0.86), 3),
            "repetitionScore": 0.0,
            "heroGraphicPenalty": hero,
            "textMaskOverlap": text_overlap,
            "textContainmentScore": text_containment,
            "foregroundLayerEvidence": foreground_layer,
            "overlayGeometryScore": overlay_geometry,
            "supportBackgroundScore": support_score,
        },
        "matchedOcrBoxId": anchor_block["ocrBoxId"],
        "anchorRelation": "contains_text",
        "metrics": {
            "areaRatioInMedia": area_ratio(bbox, media["bbox"]),
            "rawConfidence": 0.74,
            "fillRatio": round(float(metrics.get("fillRatio") or 0.0), 4),
            "textureScore": round(float(metrics.get("textureScore") or 0.0), 4),
            "colorCount": int(metrics.get("colorCount") or 0),
            "meanRgb": metrics.get("meanRgb") or [0, 0, 0],
            **({"shapeRadius": radius} if radius is not None else {}),
        },
        "geometry": geometry,
        "reasons": ["inferred_text_support_control_background", "text_containment_geometry", "local_support_pixel_evidence"],
        "risks": risks,
        "reportOnly": True,
    }


def support_geometry_score(geometry: dict[str, Any], bbox: list[int]) -> float:
    kind = str(geometry.get("kind") or "")
    confidence = str(geometry.get("confidence") or "")
    metrics = geometry.get("metrics") if isinstance(geometry.get("metrics"), dict) else {}
    center = float(metrics.get("centerFillRatio") or 0.0)
    edge = float(metrics.get("edgeFillRatio") or 0.0)
    corner_missing = float(metrics.get("cornerMissingRatio") or 0.0)
    kind_score = 0.94 if kind == "pill" else 0.84 if kind == "rounded_rect" else 0.74 if kind == "rect" else 0.50
    confidence_score = 1.0 if confidence == "high" else 0.76 if confidence == "medium" else 0.40
    aspect_bonus = 0.06 if bbox[2] / max(1, bbox[3]) >= 2.0 else 0.0
    return round(max(0.0, min(1.0, kind_score * 0.32 + confidence_score * 0.22 + center * 0.22 + edge * 0.16 + corner_missing * 0.08 + aspect_bonus)), 3)


def normalized_support_score(score: float | None) -> float:
    if score is None:
        return 0.0
    return round(max(0.0, min(1.0, score / 48.0)), 3)


def generic_foreground_candidate_budget(media_bbox: list[int], scale_profile: ImageScaleProfile) -> int:
    unit_area = max(1, scale_profile.area(1600, minimum=800, maximum=8000))
    density_budget = max(GENERIC_FOREGROUND_MAX_CANDIDATES, round(bbox_area(media_bbox) / unit_area))
    return min(240, density_budget)


def generic_scan_windows(media_bbox: list[int], image_width: int, image_height: int, scale_profile: ImageScaleProfile) -> list[dict[str, Any]]:
    media = clamp_bbox_to_media(media_bbox, media_bbox, image_width, image_height)
    if media is None:
        return []
    width = media[2]
    height = media[3]
    if width <= 180 and height <= 180:
        return [{"relation": "non_ocr_foreground", "bbox": media}]

    min_window = scale_profile.length(72, minimum=48, maximum=216)
    max_window = scale_profile.length(180, minimum=120, maximum=420)
    min_step = scale_profile.length(36, minimum=24, maximum=160)
    window_width = max(min_window, min(max_window, round(width / 3)))
    window_height = max(min_window, min(max_window, round(height / 3)))
    step_x = max(min_step, round(window_width * 0.55))
    step_y = max(min_step, round(window_height * 0.55))
    xs = scan_starts(media[0], width, window_width, step_x)
    ys = scan_starts(media[1], height, window_height, step_y)
    windows: list[dict[str, Any]] = []
    for y in ys:
        for x in xs:
            clamped = clamp_bbox_to_media([x, y, window_width, window_height], media, image_width, image_height)
            if clamped is None:
                continue
            if any(is_near_equal(clamped, item["bbox"], 0.96) for item in windows):
                continue
            windows.append({"relation": "non_ocr_foreground", "bbox": clamped})
            if len(windows) >= generic_scan_window_budget(media, scale_profile):
                return windows
    return windows


def generic_scan_window_budget(media_bbox: list[int], scale_profile: ImageScaleProfile) -> int:
    unit_area = max(1, scale_profile.area(3600, minimum=1800, maximum=16000))
    density_budget = max(GENERIC_SCAN_MAX_WINDOWS, round(bbox_area(media_bbox) / unit_area))
    return min(320, density_budget)


def scan_starts(origin: int, extent: int, window_extent: int, step: int) -> list[int]:
    if extent <= window_extent:
        return [origin]
    starts = list(range(origin, origin + extent - window_extent + 1, step))
    last = origin + extent - window_extent
    if starts[-1] != last:
        starts.append(last)
    return starts


def score_generic_foreground_candidate(
    *,
    media: dict[str, Any],
    bbox: list[int],
    component: dict[str, Any],
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    index: int,
    scale_profile: ImageScaleProfile,
) -> dict[str, Any]:
    metrics = component["metrics"]
    text_overlap = max((overlap_ratio(bbox, mask["paddedBbox"]) for mask in text_masks), default=0.0)
    best_anchor = best_text_anchor(bbox, text_inside)
    size = size_score(bbox, media["bbox"], scale_profile)
    compact = compactness_score(bbox, metrics)
    color = color_coherence_score(metrics)
    hero = hero_graphic_penalty(bbox, media["bbox"], metrics, best_anchor["score"])
    overlay_geometry = overlay_geometry_score(bbox, metrics)
    foreground_layer = foreground_layer_evidence(bbox, media["bbox"], metrics)
    role = pixel_candidate_role(
        bbox=bbox,
        media_bbox=media["bbox"],
        component=component,
        anchor_relation=best_anchor["relation"] or "non_ocr_foreground",
        anchor_block=None,
        scale_profile=scale_profile,
    )
    if role in OVERLAY_CONTROL_ROLES:
        score = round(size * 0.16 + compact * 0.18 + color * 0.10 + max(0.0, 1.0 - hero) * 0.14 + overlay_geometry * 0.22 + foreground_layer * 0.20, 3)
    else:
        score = round(size * 0.24 + compact * 0.22 + color * 0.16 + max(0.0, 1.0 - hero) * 0.28 + best_anchor["score"] * 0.10, 3)
    decision = "accepted_report_candidate"
    risks: list[str] = []
    if should_reject_text_overlap(role, text_overlap):
        decision = "rejected_fragment"
        risks.append("overlaps_internal_text_mask")
    if should_reject_large_fragment(
        role,
        area_ratio(bbox, media["bbox"]),
        foreground_layer=foreground_layer,
        overlay_geometry=overlay_geometry,
        hero=hero,
    ):
        decision = "rejected_fragment"
        risks.append("large_media_fragment")
    if role == "internal_icon_candidate" and long_thin(bbox):
        decision = "rejected_fragment"
        risks.append("separator_not_icon")
    if best_anchor["score"] < 0.30 and hero >= 0.50 and area_ratio(bbox, media["bbox"]) >= 0.10 and overlay_geometry < 0.72:
        decision = "rejected_fragment"
        risks.append("hero_or_texture_fragment")
    if hero >= 0.60 and best_anchor["score"] < 0.30:
        decision = "rejected_fragment"
        risks.append("hero_or_texture_fragment")
    if score < 0.58 and best_anchor["score"] < 0.30:
        decision = "rejected_fragment"
        risks.append("weak_internal_candidate_score")
    return {
        "candidateId": f"{media['sourceObjectId']}:internal_candidate_{index:04d}",
        "mediaSourceObjectId": media["sourceObjectId"],
        "rawNodeId": f"pixel_foreground_{media['sourceObjectId']}_{index:04d}",
        "rawType": "pixel_component",
        "rawSubtype": "non_ocr_foreground",
        "role": role,
        "bbox": bbox,
        "candidateDecision": decision,
        "confidence": generic_confidence_label(score, decision),
        "score": score,
        "scoreBreakdown": {
            "sizeScore": size,
            "compactnessScore": compact,
            "colorCoherenceScore": color,
            "textAnchorScore": round(best_anchor["score"], 3),
            "relationConsistencyScore": round(best_anchor["relationScore"], 3),
            "repetitionScore": 0.0,
            "heroGraphicPenalty": hero,
            "textMaskOverlap": text_overlap,
            "foregroundLayerEvidence": foreground_layer,
            "overlayGeometryScore": overlay_geometry,
        },
        "matchedOcrBoxId": best_anchor["ocrBoxId"] if best_anchor["score"] >= 0.30 else None,
        "anchorRelation": best_anchor["relation"] if best_anchor["score"] >= 0.30 else "non_ocr_foreground",
        "metrics": {
            "areaRatioInMedia": area_ratio(bbox, media["bbox"]),
            "rawConfidence": 0.72,
            "fillRatio": round(float(metrics.get("fillRatio") or 0.0), 4),
            "textureScore": round(float(metrics.get("textureScore") or 0.0), 4),
            "colorCount": int(metrics.get("colorCount") or 0),
        },
        "reasons": ["non_ocr_internal_foreground_component", "local_pixel_foreground"],
        "risks": risks,
        "reportOnly": True,
    }


def generic_confidence_label(score: float, decision: str) -> str:
    if decision == "rejected_fragment":
        return "low"
    if score >= 0.76:
        return "high"
    if score >= 0.58:
        return "medium"
    return "low"


def anchor_windows(text_bbox: list[int], media_bbox: list[int], image_width: int, image_height: int, scale_profile: ImageScaleProfile) -> list[dict[str, Any]]:
    width = max(scale_profile.length(56, minimum=36), min(scale_profile.length(140, minimum=96), int(text_bbox[2] * 2.4)))
    height = max(scale_profile.length(36, minimum=24), min(scale_profile.length(92, minimum=64), int(text_bbox[3] * 2.8)))
    side_width = max(scale_profile.length(36, minimum=24), min(scale_profile.length(96, minimum=64), int(text_bbox[3] * 2.6)))
    side_height = max(scale_profile.length(34, minimum=22), min(scale_profile.length(88, minimum=60), int(text_bbox[3] * 2.4)))
    cx_text = center_x(text_bbox)
    cy_text = center_y(text_bbox)
    gap = max(scale_profile.length(4, minimum=3), round(text_bbox[3] * 0.35))
    raw = [
        ("above_text", [round(cx_text - width / 2), text_bbox[1] - height - gap, width, height]),
        ("below_text", [round(cx_text - width / 2), y2(text_bbox) + gap, width, height]),
        ("left_of_text", [text_bbox[0] - side_width - gap, round(cy_text - side_height / 2), side_width, side_height]),
        ("right_of_text", [x2(text_bbox) + gap, round(cy_text - side_height / 2), side_width, side_height]),
        ("near_text", [round(cx_text - width / 2), round(cy_text - height / 2), width, height]),
    ]
    windows: list[dict[str, Any]] = []
    for relation, bbox in raw:
        clamped = clamp_bbox_to_media(bbox, media_bbox, image_width, image_height)
        if clamped is None:
            continue
        windows.append({"relation": relation, "bbox": clamped})
    return windows


def foreground_components_in_window(
    pixels: PngPixels,
    bbox: list[int],
    text_masks: list[dict[str, Any]],
    scale_profile: ImageScaleProfile,
    *,
    allow_thin_marker: bool = False,
) -> list[dict[str, Any]]:
    background = median_edge_rgb(pixels, bbox)
    x, y, width, height = bbox
    mask = bytearray(width * height)
    for row in range(height):
        source_row = pixels.rows[y + row]
        for column in range(width):
            absolute_x = x + column
            absolute_y = y + row
            if point_in_any_text_mask(absolute_x, absolute_y, text_masks):
                continue
            offset = absolute_x * 3
            rgb = (source_row[offset], source_row[offset + 1], source_row[offset + 2])
            if foreground_pixel(rgb, background):
                mask[row * width + column] = 1
    return connected_pixel_components(mask, bbox, pixels, scale_profile, allow_thin_marker=allow_thin_marker)


def foreground_pixel(rgb: tuple[int, int, int], background: tuple[int, int, int]) -> bool:
    saturation = max(rgb) - min(rgb)
    luma = rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114
    return (
        color_distance(rgb, background) >= PIXEL_FOREGROUND_DISTANCE
        and saturation >= PIXEL_FOREGROUND_MIN_SATURATION
        and luma >= PIXEL_FOREGROUND_MIN_LUMA
    )


def connected_pixel_components(
    mask: bytearray,
    window_bbox: list[int],
    pixels: PngPixels,
    scale_profile: ImageScaleProfile,
    *,
    allow_thin_marker: bool = False,
) -> list[dict[str, Any]]:
    width = window_bbox[2]
    height = window_bbox[3]
    visited = bytearray(width * height)
    components: list[dict[str, Any]] = []
    for index, value in enumerate(mask):
        if not value or visited[index]:
            continue
        stack = [index]
        visited[index] = 1
        points: list[tuple[int, int]] = []
        while stack:
            current = stack.pop()
            y, x = divmod(current, width)
            points.append((x, y))
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    neighbor = ny * width + nx
                    if not visited[neighbor] and mask[neighbor]:
                        visited[neighbor] = 1
                        stack.append(neighbor)
        if len(points) < pixel_component_min_area(scale_profile) or len(points) > pixel_component_max_area(scale_profile):
            continue
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        bbox = [
            window_bbox[0] + min(xs),
            window_bbox[1] + min(ys),
            max(xs) - min(xs) + 1,
            max(ys) - min(ys) + 1,
        ]
        short_edge = min(bbox[2], bbox[3])
        aspect = max(bbox[2], bbox[3]) / max(1, short_edge)
        thin_marker = allow_thin_marker and is_thin_marker_component(bbox, scale_profile)
        if (short_edge < pixel_component_min_short_edge(scale_profile) or aspect > PIXEL_COMPONENT_MAX_ASPECT_RATIO) and not thin_marker:
            continue
        fill_ratio = len(points) / max(1, bbox_area(bbox))
        metrics = measure_pixel_component(pixels, bbox, fill_ratio)
        components.append({"bbox": bbox, "area": len(points), "metrics": metrics})
    return sorted(components, key=lambda item: item["area"], reverse=True)[: pixel_component_return_budget(window_bbox, scale_profile)]


def pixel_component_min_area(scale_profile: ImageScaleProfile) -> int:
    return scale_profile.area(PIXEL_COMPONENT_MIN_AREA, minimum=8, maximum=320)


def pixel_component_max_area(scale_profile: ImageScaleProfile) -> int:
    return scale_profile.area(PIXEL_COMPONENT_MAX_AREA, minimum=PIXEL_COMPONENT_MAX_AREA)


def pixel_component_min_short_edge(scale_profile: ImageScaleProfile) -> int:
    return scale_profile.length(PIXEL_COMPONENT_MIN_SHORT_EDGE, minimum=4, maximum=32)


def pixel_component_return_budget(window_bbox: list[int], scale_profile: ImageScaleProfile) -> int:
    unit_area = max(1, scale_profile.area(900, minimum=450, maximum=3600))
    density_budget = max(PIXEL_COMPONENT_MIN_RETURNED, round(bbox_area(window_bbox) / unit_area))
    return min(96, density_budget)


def is_thin_marker_component(bbox: list[int], scale_profile: ImageScaleProfile) -> bool:
    short = min(bbox[2], bbox[3])
    long = max(bbox[2], bbox[3])
    return (
        bbox[2] > bbox[3]
        and long / max(1, short) >= SELECTED_MARKER_MIN_ASPECT_RATIO
        and short >= scale_profile.length(4, minimum=3, maximum=18)
        and long <= scale_profile.length(96, minimum=32, maximum=220)
    )


def score_pixel_anchor_candidate(
    *,
    media: dict[str, Any],
    bbox: list[int],
    component: dict[str, Any],
    anchor_block: dict[str, Any],
    anchor_relation: str,
    text_masks: list[dict[str, Any]],
    text_inside: list[dict[str, Any]],
    index: int,
    scale_profile: ImageScaleProfile,
) -> dict[str, Any]:
    metrics = component["metrics"]
    text_overlap = max((overlap_ratio(bbox, mask["paddedBbox"]) for mask in text_masks), default=0.0)
    best_anchor = best_text_anchor(bbox, text_inside)
    anchor_score = max(best_anchor["score"], directional_anchor_score(bbox, anchor_block["bbox"], anchor_relation)["score"])
    size = size_score(bbox, media["bbox"], scale_profile)
    compact = compactness_score(bbox, metrics)
    color = color_coherence_score(metrics)
    hero = hero_graphic_penalty(bbox, media["bbox"], metrics, anchor_score)
    overlay_geometry = overlay_geometry_score(bbox, metrics)
    foreground_layer = foreground_layer_evidence(bbox, media["bbox"], metrics)
    role = pixel_candidate_role(
        bbox=bbox,
        media_bbox=media["bbox"],
        component=component,
        anchor_relation=anchor_relation,
        anchor_block=anchor_block,
        scale_profile=scale_profile,
    )
    score = round(size * 0.18 + compact * 0.16 + color * 0.12 + anchor_score * 0.34 - hero * 0.20, 3)
    decision = "accepted_report_candidate"
    risks: list[str] = []
    if should_reject_text_overlap(role, text_overlap):
        decision = "rejected_fragment"
        risks.append("overlaps_internal_text_mask")
    if should_reject_large_fragment(
        role,
        area_ratio(bbox, media["bbox"]),
        foreground_layer=foreground_layer,
        overlay_geometry=overlay_geometry,
        hero=hero,
    ):
        decision = "rejected_fragment"
        risks.append("large_media_fragment")
    if role == "internal_icon_candidate" and long_thin(bbox):
        decision = "rejected_fragment"
        risks.append("separator_not_icon")
    if hero >= 0.62 and anchor_score < 0.35:
        decision = "rejected_fragment"
        risks.append("hero_or_texture_fragment")
    if score < 0.42 and anchor_score < 0.38:
        decision = "rejected_fragment"
        risks.append("weak_internal_candidate_score")
    return {
        "candidateId": f"{media['sourceObjectId']}:internal_candidate_{index:04d}",
        "mediaSourceObjectId": media["sourceObjectId"],
        "rawNodeId": f"pixel_anchor_{anchor_block['ocrBoxId']}_{index:04d}",
        "rawType": "pixel_component",
        "rawSubtype": anchor_relation,
        "role": role,
        "bbox": bbox,
        "candidateDecision": decision,
        "confidence": confidence_label(score, anchor_score, decision),
        "score": score,
        "scoreBreakdown": {
            "sizeScore": size,
            "compactnessScore": compact,
            "colorCoherenceScore": color,
            "textAnchorScore": round(anchor_score, 3),
            "relationConsistencyScore": round(best_anchor["relationScore"], 3),
            "repetitionScore": 0.0,
            "heroGraphicPenalty": hero,
            "textMaskOverlap": text_overlap,
            "foregroundLayerEvidence": foreground_layer,
            "overlayGeometryScore": overlay_geometry,
        },
        "matchedOcrBoxId": best_anchor["ocrBoxId"] or anchor_block["ocrBoxId"],
        "anchorRelation": best_anchor["relation"] or anchor_relation,
        "metrics": {
            "areaRatioInMedia": area_ratio(bbox, media["bbox"]),
            "rawConfidence": 0.78,
            "fillRatio": round(float(metrics.get("fillRatio") or 0.0), 4),
            "textureScore": round(float(metrics.get("textureScore") or 0.0), 4),
            "colorCount": int(metrics.get("colorCount") or 0),
        },
        "reasons": ["ocr_anchor_foreground_component", "local_pixel_foreground"],
        "risks": risks,
        "reportOnly": True,
    }


def measure_pixel_component(pixels: PngPixels, bbox: list[int], fill_ratio: float) -> dict[str, Any]:
    x, y, width, height = bbox
    buckets: dict[tuple[int, int, int], int] = {}
    samples = 0
    red_sum = green_sum = blue_sum = 0
    texture_total = 0
    edge_hits = 0
    edge_checks = 0
    for row_index in range(y, y + height):
        row = pixels.rows[row_index]
        next_row = pixels.rows[min(pixels.height - 1, row_index + 1)]
        for column in range(x, x + width):
            offset = column * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            red_sum += rgb[0]
            green_sum += rgb[1]
            blue_sum += rgb[2]
            buckets[(rgb[0] // 16, rgb[1] // 16, rgb[2] // 16)] = buckets.get((rgb[0] // 16, rgb[1] // 16, rgb[2] // 16), 0) + 1
            samples += 1
            if column + 1 < pixels.width:
                neighbor_offset = (column + 1) * 3
                diff = color_distance(rgb, (row[neighbor_offset], row[neighbor_offset + 1], row[neighbor_offset + 2]))
                texture_total += diff
                edge_checks += 1
                edge_hits += 1 if diff > 48 else 0
            if row_index + 1 < pixels.height:
                diff = color_distance(rgb, (next_row[offset], next_row[offset + 1], next_row[offset + 2]))
                texture_total += diff
                edge_checks += 1
                edge_hits += 1 if diff > 48 else 0
    samples = max(1, samples)
    mean_rgb = [round(red_sum / samples), round(green_sum / samples), round(blue_sum / samples)]
    return {
        "colorCount": len(buckets),
        "textureScore": round((texture_total / max(1, edge_checks)) / 255, 4),
        "edgeScore": round(edge_hits / max(1, edge_checks), 4),
        "fillRatio": round(fill_ratio, 4),
        "aspectRatio": round(width / max(1, height), 4),
        "brightness": round(mean_rgb[0] * 0.299 + mean_rgb[1] * 0.587 + mean_rgb[2] * 0.114, 3),
        "meanRgb": mean_rgb,
    }


def median_edge_rgb(pixels: PngPixels, bbox: list[int]) -> tuple[int, int, int]:
    x, y, width, height = bbox
    samples: list[tuple[int, int, int]] = []
    for column in range(x, x + width):
        samples.append(pixel_rgb(pixels, column, y))
        samples.append(pixel_rgb(pixels, column, y + height - 1))
    for row in range(y, y + height):
        samples.append(pixel_rgb(pixels, x, row))
        samples.append(pixel_rgb(pixels, x + width - 1, row))
    return tuple(int(median([sample[channel] for sample in samples])) for channel in range(3))


def pixel_rgb(pixels: PngPixels, x: int, y: int) -> tuple[int, int, int]:
    row = pixels.rows[y]
    offset = x * 3
    return row[offset], row[offset + 1], row[offset + 2]


def point_in_any_text_mask(x: int, y: int, text_masks: list[dict[str, Any]]) -> bool:
    for mask in text_masks:
        bbox = mask["paddedBbox"]
        if bbox[0] <= x < x2(bbox) and bbox[1] <= y < y2(bbox):
            return True
    return False


def clamp_bbox_to_media(bbox: list[int], media_bbox: list[int], image_width: int, image_height: int) -> list[int] | None:
    media_context = expanded_media_anchor_bbox(media_bbox, bbox)
    left = max(0, media_context[0], bbox[0])
    top = max(0, media_context[1], bbox[1])
    right = min(image_width, x2(media_context), x2(bbox))
    bottom = min(image_height, y2(media_context), y2(bbox))
    if right - left <= 2 or bottom - top <= 2:
        return None
    return [left, top, right - left, bottom - top]


def rejected_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidateId": candidate["candidateId"],
        "mediaSourceObjectId": candidate["mediaSourceObjectId"],
        "rawNodeId": candidate["rawNodeId"],
        "bbox": candidate["bbox"],
        "role": candidate["role"],
        "reason": candidate["risks"][0] if candidate["risks"] else "rejected_fragment",
        "score": candidate["score"],
        "scoreBreakdown": candidate["scoreBreakdown"],
    }
