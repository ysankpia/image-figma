from __future__ import annotations

from typing import Any

from .budget import visible_plan_sort_key
from .utils import dedupe_preserve_order


def suppress_visible_overlap_duplicates(
    plan_items: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    suppressed_by_id: dict[str, dict[str, Any]] = {}
    for item in sorted(plan_items, key=overlap_priority_sort_key):
        if item["sourceObjectId"] in suppressed_by_id:
            continue
        duplicate_ids: list[str] = []
        relation_edge_ids = set(item["relationEdgeIds"])
        for other in plan_items:
            other_id = other["sourceObjectId"]
            if other_id == item["sourceObjectId"] or other_id in suppressed_by_id:
                continue
            edge = edge_lookup.get(frozenset({item["sourceObjectId"], other_id}))
            if not should_suppress_visible_overlap(item, other, edge):
                continue
            duplicate_ids.append(other_id)
            edge_id = str((edge or {}).get("edgeId") or "")
            if edge_id:
                relation_edge_ids.add(edge_id)
            suppressed_by_id[other_id] = suppress_visible_overlap_item(other, edge_id)
        kept = dict(item)
        kept["suppressedSourceObjectIds"] = dedupe_preserve_order([*kept["suppressedSourceObjectIds"], *duplicate_ids])
        kept["relationEdgeIds"] = sorted(relation_edge_ids)
        if duplicate_ids:
            kept["reasons"] = dedupe_preserve_order([*kept["reasons"], "visible_overlap_duplicate_suppression"])
        accepted.append(kept)
    suppressed = [suppressed_by_id[source_id] for source_id in sorted(suppressed_by_id)]
    return sorted(accepted, key=visible_plan_sort_key), suppressed


MAX_PROMOTED_INTERNAL_ICON_TEXT_OVERLAP_RATIO = 0.14
SAME_FOREGROUND_DUPLICATE_IOU_THRESHOLD = 0.60
SAME_FOREGROUND_DUPLICATE_CONTAINMENT_THRESHOLD = 0.80
INTERNAL_ICON_PROMOTION_SOURCES = {
    "m29_6_internal_icon_candidate",
    "m29_6_foreground_claim",
    "perception_model_foreground_claim",
}


def overlap_priority_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    action_rank = {"image_replay": 0, "text_replay": 1, "shape_replay": 2, "icon_replay": 3}.get(item["finalReplayAction"], 9)
    confidence_rank = {"high": 0, "medium": 1, "low": 2}.get(item["confidence"], 2)
    return action_rank, confidence_rank, -bbox_area(item["bbox"]), item["sourceObjectId"]


def should_suppress_visible_overlap(left: dict[str, Any], right: dict[str, Any], edge: dict[str, Any] | None) -> bool:
    left_action = left["finalReplayAction"]
    right_action = right["finalReplayAction"]
    actions = {left_action, right_action}
    if str((edge or {}).get("primarySetRelation") or "") == "near_equal":
        return left_action == right_action or right_action == lower_priority_overlap_action(left_action, right_action)
    left_area = bbox_area(left["bbox"])
    right_area = bbox_area(right["bbox"])
    intersection = intersection_area(left["bbox"], right["bbox"])
    if intersection <= 0 or min(left_area, right_area) <= 0:
        return False
    containment_ratio = intersection / min(left_area, right_area)
    primary = str((edge or {}).get("primarySetRelation") or "")
    if primary not in {"contains", "contained_by", "overlaps"}:
        return False
    if left_action == right_action:
        if left["pixelOwner"] != right["pixelOwner"]:
            return False
        if left_action == "image_replay" and is_perception_foreground_image_over_parent_media(left, right):
            return False
        if left_action in {"icon_replay", "shape_replay"}:
            return should_suppress_same_foreground_overlap(left, right, primary, intersection, containment_ratio)
        if left_action == "image_replay":
            return containment_ratio >= 0.35 or (primary in {"contains", "contained_by"} and containment_ratio >= 0.20)
        if left_action == "text_replay":
            return containment_ratio >= 0.20
        return False
    if actions == {"image_replay", "icon_replay"}:
        image = left if left_action == "image_replay" else right
        if is_perception_selectable_raster_crop(image):
            return False
        if is_perception_control_child_icon_over_parent_control(left, right):
            return False
        if is_promoted_internal_icon_over_parent_media(left, right):
            return False
        if is_label_anchored_blocked_icon_over_parent_media(left, right):
            return False
        return left_action == "image_replay" and containment_ratio >= 0.20
    if actions == {"text_replay", "icon_replay"}:
        if is_promoted_internal_icon_label_overlap(left, right):
            return False
        return left_action == "text_replay" and containment_ratio >= 0.25
    return False


def should_suppress_same_foreground_overlap(
    left: dict[str, Any],
    right: dict[str, Any],
    primary: str,
    intersection: int,
    containment_ratio: float,
) -> bool:
    if not same_visual_role_family(left, right):
        return False
    if bbox_iou(left["bbox"], right["bbox"], intersection) >= SAME_FOREGROUND_DUPLICATE_IOU_THRESHOLD:
        return True
    return primary in {"contains", "contained_by"} and containment_ratio >= SAME_FOREGROUND_DUPLICATE_CONTAINMENT_THRESHOLD


def same_visual_role_family(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("finalReplayAction") != right.get("finalReplayAction"):
        return False
    if left.get("visualKind") and right.get("visualKind") and left.get("visualKind") == right.get("visualKind"):
        return True
    left_evidence = left.get("sourceEvidence") if isinstance(left.get("sourceEvidence"), dict) else {}
    right_evidence = right.get("sourceEvidence") if isinstance(right.get("sourceEvidence"), dict) else {}
    left_role = str(left_evidence.get("internalRole") or "")
    right_role = str(right_evidence.get("internalRole") or "")
    return bool(left_role and right_role and left_role == right_role)


def is_promoted_internal_icon(item: dict[str, Any]) -> bool:
    if item.get("finalReplayAction") != "icon_replay":
        return False
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    return evidence.get("promotionSource") in INTERNAL_ICON_PROMOTION_SOURCES and (
        bool(evidence.get("transparentAssetPath")) or evidence.get("controlRowSourceCropEligible") is True
    )


def is_promoted_internal_icon_label_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    icon = left if left["finalReplayAction"] == "icon_replay" else right if right["finalReplayAction"] == "icon_replay" else None
    text = left if left["finalReplayAction"] == "text_replay" else right if right["finalReplayAction"] == "text_replay" else None
    if icon is None or text is None or not is_promoted_internal_icon(icon):
        return False
    evidence = icon.get("sourceEvidence") if isinstance(icon.get("sourceEvidence"), dict) else {}
    return safe_float(evidence.get("textOverlapRatio")) <= MAX_PROMOTED_INTERNAL_ICON_TEXT_OVERLAP_RATIO


def is_promoted_internal_icon_over_parent_media(left: dict[str, Any], right: dict[str, Any]) -> bool:
    icon = left if left["finalReplayAction"] == "icon_replay" else right if right["finalReplayAction"] == "icon_replay" else None
    media = left if left["finalReplayAction"] == "image_replay" else right if right["finalReplayAction"] == "image_replay" else None
    if icon is None or media is None:
        return False
    evidence = icon.get("sourceEvidence") if isinstance(icon.get("sourceEvidence"), dict) else {}
    return (
        evidence.get("promotionSource") in INTERNAL_ICON_PROMOTION_SOURCES
        and evidence.get("mediaSourceObjectId") == media["sourceObjectId"]
        and (bool(evidence.get("transparentAssetPath")) or evidence.get("controlRowSourceCropEligible") is True)
    )


def is_perception_control_child_icon_over_parent_control(left: dict[str, Any], right: dict[str, Any]) -> bool:
    icon = left if left["finalReplayAction"] == "icon_replay" else right if right["finalReplayAction"] == "icon_replay" else None
    media = left if left["finalReplayAction"] == "image_replay" else right if right["finalReplayAction"] == "image_replay" else None
    if icon is None or media is None:
        return False
    evidence = icon.get("sourceEvidence") if isinstance(icon.get("sourceEvidence"), dict) else {}
    return (
        evidence.get("promotionSource") == "perception_model_foreground_claim"
        and evidence.get("parentControlSourceObjectId") == media["sourceObjectId"]
        and evidence.get("controlRowSourceCropEligible") is True
    )


def is_perception_foreground_image_over_parent_media(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return perception_foreground_image_child(left, right) is not None


def perception_foreground_image_child(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any] | None:
    if left.get("finalReplayAction") != "image_replay" or right.get("finalReplayAction") != "image_replay":
        return None
    if is_perception_control_raster_child(child=left, parent=right):
        return left
    if is_perception_control_raster_child(child=right, parent=left):
        return right
    return None


def is_perception_control_raster_child(*, child: dict[str, Any], parent: dict[str, Any]) -> bool:
    evidence = child.get("sourceEvidence") if isinstance(child.get("sourceEvidence"), dict) else {}
    return (
        evidence.get("promotionSource") == "perception_model_foreground_claim"
        and evidence.get("internalRole") in {"internal_control_raster_background", "internal_selectable_raster_crop"}
        and evidence.get("mediaSourceObjectId") == parent.get("sourceObjectId")
        and bool(evidence.get("foregroundClaimId"))
    )


def is_perception_selectable_raster_crop(item: dict[str, Any]) -> bool:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    return (
        item.get("finalReplayAction") == "image_replay"
        and evidence.get("promotionSource") == "perception_model_foreground_claim"
        and evidence.get("internalRole") == "internal_selectable_raster_crop"
        and bool(evidence.get("foregroundClaimId"))
    )


def safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def is_label_anchored_blocked_icon_over_parent_media(left: dict[str, Any], right: dict[str, Any]) -> bool:
    icon = left if left["finalReplayAction"] == "icon_replay" else right if right["finalReplayAction"] == "icon_replay" else None
    media = left if left["finalReplayAction"] == "image_replay" else right if right["finalReplayAction"] == "image_replay" else None
    if icon is None or media is None:
        return False
    evidence = icon.get("sourceEvidence") if isinstance(icon.get("sourceEvidence"), dict) else {}
    media_evidence = media.get("sourceEvidence") if isinstance(media.get("sourceEvidence"), dict) else {}
    if not evidence.get("labelAnchorOcrBoxId"):
        return False
    if not evidence.get("blockedIds"):
        return False
    try:
        if float(evidence.get("mediaContainmentRatio") or 0.0) < 0.80:
            return False
    except (TypeError, ValueError):
        return False
    return "low_confidence_media_region" in set(media.get("risks", [])) or bool(media_evidence.get("ocrBoxIds"))


def lower_priority_overlap_action(left_action: str, right_action: str) -> str:
    rank = {"image_replay": 0, "text_replay": 1, "shape_replay": 2, "icon_replay": 3}
    if rank.get(left_action, 99) <= rank.get(right_action, 99):
        return right_action
    return left_action


def suppress_visible_overlap_item(item: dict[str, Any], edge_id: str) -> dict[str, Any]:
    suppressed = dict(item)
    suppressed["finalReplayAction"] = "suppress_duplicate"
    suppressed["targetRole"] = None
    suppressed["cleanupTargets"] = []
    suppressed["suppressedSourceObjectIds"] = []
    if edge_id:
        suppressed["relationEdgeIds"] = dedupe_preserve_order([*suppressed["relationEdgeIds"], edge_id])
    suppressed["reasons"] = dedupe_preserve_order([*suppressed["reasons"], "visible_overlap_duplicate_suppressed"])
    suppressed["risks"] = dedupe_preserve_order([*suppressed["risks"], "visible_overlap_duplicate"])
    return suppressed


def bbox_area(bbox: list[int]) -> int:
    return max(0, int(bbox[2])) * max(0, int(bbox[3]))


def bbox_iou(left: list[int], right: list[int], intersection: int | None = None) -> float:
    left_area = bbox_area(left)
    right_area = bbox_area(right)
    overlap = intersection_area(left, right) if intersection is None else intersection
    union = left_area + right_area - overlap
    if overlap <= 0 or union <= 0:
        return 0.0
    return overlap / union


def intersection_area(left: list[int], right: list[int]) -> int:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    return max(0, x2 - x1) * max(0, y2 - y1)
