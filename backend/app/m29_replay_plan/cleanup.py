from __future__ import annotations

from typing import Any

MAX_INTERNAL_ICON_CLEANUP_TEXT_OVERLAP = 0.18
MAX_INTERNAL_ICON_CLEANUP_EDGE_ALPHA_COVERAGE = 0.18
MAX_INTERNAL_ICON_CLEANUP_EDGE_ALPHA_MEAN = 36.0
MIN_INTERNAL_ICON_CLEANUP_ALPHA_COVERAGE = 0.04
MAX_INTERNAL_ICON_CLEANUP_ALPHA_COVERAGE = 0.88
MIN_INTERNAL_ICON_CLEANUP_LARGEST_COMPONENT = 0.35
MAX_SHAPE_CLEANUP_TEXT_OVERLAP = 0.24
MIN_SHAPE_CLEANUP_EVIDENCE_SCORE = 0.68
FOREGROUND_CLAIM_PROMOTION_SOURCES = {
    "m29_6_foreground_claim",
    "perception_model_foreground_claim",
}
INTERNAL_ICON_PROMOTION_SOURCES = {
    "m29_6_internal_icon_candidate",
    *FOREGROUND_CLAIM_PROMOTION_SOURCES,
}
INTERNAL_SHAPE_PROMOTION_SOURCES = {
    "m29_6_internal_shape_candidate",
    *FOREGROUND_CLAIM_PROMOTION_SOURCES,
}


def cleanup_targets_for(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    targets = [{"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"}]
    risks: list[str] = []
    if item["replayDecision"] == "icon_replay":
        internal_targets, internal_risks = promoted_internal_asset_cleanup_targets(item, source_objects, edge_lookup)
        blocked_targets, blocked_risks = label_anchored_blocked_asset_cleanup_targets(item, source_objects, edge_lookup)
        targets.extend(internal_targets)
        targets.extend(blocked_targets)
        risks.extend(internal_risks)
        risks.extend(blocked_risks)
        return targets, risks
    if item["replayDecision"] == "shape_replay":
        shape_targets, shape_risks = shape_cleanup_targets(item, source_objects, edge_lookup)
        targets.extend(shape_targets)
        risks.extend(shape_risks)
        return targets, risks
    if item["replayDecision"] != "text_replay":
        return targets, risks
    for other in source_objects:
        if other["id"] == item["id"]:
            continue
        edge = edge_lookup.get(frozenset({item["id"], other["id"]}))
        if not edge:
            continue
        if other["replayDecision"] != "image_replay" or other["pixelOwner"] != "preserve_raster":
            continue
        if text_is_contained_by_media(item["id"], other["id"], edge):
            targets.append(
                {
                    "target": "copied_image_asset",
                    "targetSourceObjectId": other["id"],
                    "reason": "editable_text_contained_by_media",
                }
            )
    return targets, risks


def shape_cleanup_targets(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    targets: list[dict[str, Any]] = []
    risks: list[str] = []
    for other in source_objects:
        if other["id"] == item["id"]:
            continue
        if other["replayDecision"] != "image_replay" or other["pixelOwner"] != "preserve_raster":
            continue
        edge = edge_lookup.get(frozenset({item["id"], other["id"]}))
        if shape_is_contained_by_media(item["id"], other["id"], edge):
            risk = shape_cleanup_risk_reason(item, other, edge)
            if risk:
                risks.append(risk)
                continue
            evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
            target = {
                "target": "copied_image_asset",
                "targetSourceObjectId": other["id"],
                "reason": cleanup_reason_for_shape(item),
            }
            if is_foreground_claim_source(evidence):
                target.update(foreground_claim_cleanup_fields(evidence))
            targets.append(
                target
            )
    return targets, risks


def promoted_internal_asset_cleanup_targets(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    if evidence.get("promotionSource") not in INTERNAL_ICON_PROMOTION_SOURCES:
        return [], []
    media_id = str(evidence.get("mediaSourceObjectId") or "")
    if not media_id:
        return [], []
    targets: list[dict[str, Any]] = []
    risks: list[str] = []
    for target_media_id in promoted_internal_icon_cleanup_media_ids(evidence):
        media = next((other for other in source_objects if other["id"] == target_media_id), None)
        if media is None or media["replayDecision"] != "image_replay" or media["pixelOwner"] != "preserve_raster":
            continue
        edge = edge_lookup.get(frozenset({item["id"], target_media_id}))
        if not edge or not internal_asset_is_contained_by_media(item["id"], target_media_id, edge):
            continue
        risk = promoted_internal_icon_cleanup_risk_reason(item, media, edge)
        if risk:
            risks.append(risk)
            continue
        target = {
            "target": "copied_image_asset",
            "targetSourceObjectId": target_media_id,
            "reason": "foreground_claim_removed_from_residual_media" if is_foreground_claim_source(evidence) else "promoted_internal_asset_contained_by_media",
        }
        if is_foreground_claim_source(evidence):
            target.update(foreground_claim_cleanup_fields(evidence))
        targets.append(target)
    return targets, risks


def promoted_internal_icon_cleanup_media_ids(evidence: dict[str, Any]) -> list[str]:
    media_ids: list[str] = []
    parent_control_id = str(evidence.get("parentControlSourceObjectId") or "")
    if parent_control_id:
        media_ids.append(parent_control_id)
    media_id = str(evidence.get("mediaSourceObjectId") or "")
    if media_id and media_id not in media_ids:
        media_ids.append(media_id)
    return media_ids


def label_anchored_blocked_asset_cleanup_targets(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    if not evidence.get("labelAnchorOcrBoxId") or not evidence.get("blockedIds"):
        return [], []
    targets: list[dict[str, Any]] = []
    risks: list[str] = []
    for other in source_objects:
        if other["id"] == item["id"]:
            continue
        if other["replayDecision"] != "image_replay" or other["pixelOwner"] != "preserve_raster":
            continue
        edge = edge_lookup.get(frozenset({item["id"], other["id"]}))
        if not edge or not internal_asset_is_contained_by_media(item["id"], other["id"], edge):
            continue
        risk = label_anchored_blocked_asset_cleanup_risk_reason(item, other, edge)
        if risk:
            risks.append(risk)
            continue
        targets.append(
            {
                "target": "copied_image_asset",
                "targetSourceObjectId": other["id"],
                "reason": "label_anchored_blocked_asset_contained_by_media",
            }
        )
    return targets, risks


def contained_media_edge_ids(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[str]:
    edge_ids: list[str] = []
    if item["replayDecision"] != "text_replay":
        return edge_ids
    for other in source_objects:
        edge = edge_lookup.get(frozenset({item["id"], other["id"]}))
        if not edge:
            continue
        if other["replayDecision"] == "image_replay" and text_is_contained_by_media(item["id"], other["id"], edge):
            edge_id = str(edge.get("edgeId") or "")
            if edge_id:
                edge_ids.append(edge_id)
    return edge_ids


def text_is_contained_by_media(text_id: str, media_id: str, edge: dict[str, Any]) -> bool:
    primary = edge.get("primarySetRelation")
    left = str(edge.get("leftObjectId") or "")
    right = str(edge.get("rightObjectId") or "")
    if primary == "near_equal":
        return True
    if left == text_id and right == media_id:
        return primary == "contained_by" or text_overlap_ratio(edge, text_on_left=True) >= 0.20
    if left == media_id and right == text_id:
        return primary == "contains" or text_overlap_ratio(edge, text_on_left=False) >= 0.20
    return False


def internal_asset_is_contained_by_media(asset_id: str, media_id: str, edge: dict[str, Any]) -> bool:
    primary = edge.get("primarySetRelation")
    left = str(edge.get("leftObjectId") or "")
    right = str(edge.get("rightObjectId") or "")
    if primary == "near_equal":
        return True
    if left == asset_id and right == media_id:
        return primary == "contained_by" or text_overlap_ratio(edge, text_on_left=True) >= 0.20
    if left == media_id and right == asset_id:
        return primary == "contains" or text_overlap_ratio(edge, text_on_left=False) >= 0.20
    return False


def shape_is_contained_by_media(shape_id: str, media_id: str, edge: dict[str, Any] | None) -> bool:
    if not edge:
        return False
    primary = edge.get("primarySetRelation")
    left = str(edge.get("leftObjectId") or "")
    right = str(edge.get("rightObjectId") or "")
    if primary == "near_equal":
        return True
    if left == shape_id and right == media_id:
        return primary == "contained_by" or text_overlap_ratio(edge, text_on_left=True) >= 0.70
    if left == media_id and right == shape_id:
        return primary == "contains" or text_overlap_ratio(edge, text_on_left=False) >= 0.70
    return False


def promoted_internal_icon_cleanup_risk_reason(item: dict[str, Any], media: dict[str, Any], edge: dict[str, Any]) -> str:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    if media["id"] not in promoted_internal_icon_cleanup_media_ids(evidence):
        return "cleanup_rejected_parent_media_mismatch"
    if not evidence.get("transparentAssetPath") and evidence.get("controlRowSourceCropEligible") is not True:
        return "cleanup_rejected_missing_transparent_replacement"
    text_overlap = safe_float(evidence.get("textOverlapRatio"))
    if text_overlap > MAX_INTERNAL_ICON_CLEANUP_TEXT_OVERLAP:
        return "cleanup_rejected_text_overlap_risk"
    alpha_coverage = optional_float(evidence.get("transparentAssetAlphaCoverage"))
    if alpha_coverage is not None and not (MIN_INTERNAL_ICON_CLEANUP_ALPHA_COVERAGE <= alpha_coverage <= MAX_INTERNAL_ICON_CLEANUP_ALPHA_COVERAGE):
        return "cleanup_rejected_alpha_coverage_risk"
    edge_alpha_coverage = optional_float(evidence.get("transparentAssetEdgeAlphaCoverageGt32"))
    if edge_alpha_coverage is not None and edge_alpha_coverage > MAX_INTERNAL_ICON_CLEANUP_EDGE_ALPHA_COVERAGE:
        return "cleanup_rejected_edge_alpha_risk"
    edge_alpha_mean = optional_float(evidence.get("transparentAssetEdgeAlphaMean"))
    if edge_alpha_mean is not None and edge_alpha_mean > MAX_INTERNAL_ICON_CLEANUP_EDGE_ALPHA_MEAN:
        return "cleanup_rejected_edge_alpha_risk"
    largest_component = optional_float(evidence.get("transparentAssetLargestComponentRatio"))
    if largest_component is not None and largest_component < MIN_INTERNAL_ICON_CLEANUP_LARGEST_COMPONENT:
        return "cleanup_rejected_fragmented_replacement_risk"
    return ""


def label_anchored_blocked_asset_cleanup_risk_reason(item: dict[str, Any], media: dict[str, Any], edge: dict[str, Any]) -> str:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    media_containment = optional_float(evidence.get("mediaContainmentRatio"))
    if media_containment is not None and media_containment < 0.80:
        return "cleanup_rejected_low_media_containment"
    return ""


def shape_cleanup_risk_reason(item: dict[str, Any], media: dict[str, Any], edge: dict[str, Any] | None) -> str:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    if evidence.get("mediaSourceObjectId") and evidence.get("mediaSourceObjectId") != media["id"]:
        return "cleanup_rejected_parent_media_mismatch"
    text_overlap = safe_float(evidence.get("textOverlapRatio"))
    if text_overlap > MAX_SHAPE_CLEANUP_TEXT_OVERLAP:
        return "cleanup_rejected_text_overlap_risk"
    if evidence.get("promotionSource") in INTERNAL_SHAPE_PROMOTION_SOURCES:
        score = safe_float(evidence.get("evidenceScore"))
        role = str(evidence.get("internalRole") or "")
        has_style = bool(evidence.get("shapeFillOverride") or evidence.get("shapeRadiusOverride"))
        if score < MIN_SHAPE_CLEANUP_EVIDENCE_SCORE and not shape_role_has_styled_foreground_claim(role, has_style):
            return "cleanup_rejected_low_shape_evidence"
        if role in {"status_dot_candidate", "table_marker_candidate", "internal_overlay_badge", "internal_pill_button", "internal_circle_control"} and not has_style:
            return "cleanup_rejected_missing_shape_replacement_style"
    return ""


def cleanup_reason_for_shape(item: dict[str, Any]) -> str:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    if is_foreground_claim_source(evidence):
        return "foreground_claim_removed_from_residual_media"
    return "shape_background_contained_by_media"


def is_foreground_claim_source(evidence: dict[str, Any]) -> bool:
    return str(evidence.get("promotionSource") or "") in FOREGROUND_CLAIM_PROMOTION_SOURCES or bool(evidence.get("foregroundClaimId"))


def shape_role_has_styled_foreground_claim(role: str, has_style: bool) -> bool:
    return has_style and role in {
        "internal_control_background",
        "internal_overlay_badge",
        "internal_pill_button",
        "internal_circle_control",
    }


def foreground_claim_cleanup_fields(evidence: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "foregroundClaimId": evidence.get("foregroundClaimId"),
        "maskKind": evidence.get("claimMaskKind") or "bbox",
    }
    return {key: value for key, value in fields.items() if value}


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float:
    return optional_float(value) or 0.0


def text_overlap_ratio(edge: dict[str, Any], *, text_on_left: bool) -> float:
    metrics = edge.get("metrics") if isinstance(edge.get("metrics"), dict) else {}
    key = "leftInRightRatio" if text_on_left else "rightInLeftRatio"
    try:
        return float(metrics.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0
