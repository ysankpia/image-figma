from __future__ import annotations

from statistics import median
from math import exp
from typing import Any

from ..image_math import ImageScaleProfile, build_scale_profile
from ..png_tools import PngPixels
from ..visual_primitive.metrics import color_distance
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
    apply_repetition_scores(candidates)
    candidates.extend(merge_anchor_icon_fragments(media, candidates, text_masks, text_inside, len(candidates) + 1, scale_profile))
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
    score = round(size * 0.18 + compact * 0.16 + color * 0.12 + best_anchor["score"] * 0.34 - hero * 0.20, 3)
    role = candidate_role(node, separator)
    reasons: list[str] = []
    risks: list[str] = []
    decision = "accepted_report_candidate"
    if text_overlap > 0.30:
        decision = "rejected_fragment"
        risks.append("overlaps_internal_text_mask")
    if area_ratio(bbox, media["bbox"]) > 0.18:
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
        return "internal_shape_candidate"
    return "internal_decorative_candidate"


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
            for component in foreground_components_in_window(pixels, window["bbox"], text_masks, scale_profile):
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
    score = round(size * 0.24 + compact * 0.22 + color * 0.16 + max(0.0, 1.0 - hero) * 0.28 + best_anchor["score"] * 0.10, 3)
    decision = "accepted_report_candidate"
    risks: list[str] = []
    if text_overlap > 0.30:
        decision = "rejected_fragment"
        risks.append("overlaps_internal_text_mask")
    if area_ratio(bbox, media["bbox"]) > 0.12:
        decision = "rejected_fragment"
        risks.append("large_media_fragment")
    if long_thin(bbox):
        decision = "rejected_fragment"
        risks.append("separator_not_icon")
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
        "role": "internal_icon_candidate",
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


def foreground_components_in_window(pixels: PngPixels, bbox: list[int], text_masks: list[dict[str, Any]], scale_profile: ImageScaleProfile) -> list[dict[str, Any]]:
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
    return connected_pixel_components(mask, bbox, pixels, scale_profile)


def foreground_pixel(rgb: tuple[int, int, int], background: tuple[int, int, int]) -> bool:
    saturation = max(rgb) - min(rgb)
    luma = rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114
    return (
        color_distance(rgb, background) >= PIXEL_FOREGROUND_DISTANCE
        and saturation >= PIXEL_FOREGROUND_MIN_SATURATION
        and luma >= PIXEL_FOREGROUND_MIN_LUMA
    )


def connected_pixel_components(mask: bytearray, window_bbox: list[int], pixels: PngPixels, scale_profile: ImageScaleProfile) -> list[dict[str, Any]]:
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
        aspect = max(bbox[2], bbox[3]) / max(1, min(bbox[2], bbox[3]))
        if min(bbox[2], bbox[3]) < pixel_component_min_short_edge(scale_profile) or aspect > PIXEL_COMPONENT_MAX_ASPECT_RATIO:
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
    score = round(size * 0.18 + compact * 0.16 + color * 0.12 + anchor_score * 0.34 - hero * 0.20, 3)
    decision = "accepted_report_candidate"
    risks: list[str] = []
    if text_overlap > 0.30:
        decision = "rejected_fragment"
        risks.append("overlaps_internal_text_mask")
    if area_ratio(bbox, media["bbox"]) > 0.18:
        decision = "rejected_fragment"
        risks.append("large_media_fragment")
    if long_thin(bbox):
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
            "relationConsistencyScore": round(best_anchor["relationScore"], 3),
            "repetitionScore": 0.0,
            "heroGraphicPenalty": hero,
            "textMaskOverlap": text_overlap,
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
