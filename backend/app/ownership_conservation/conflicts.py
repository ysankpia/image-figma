from __future__ import annotations

from typing import Any

from .geometry import intersection_area, overlap_ratio, union_bbox
from .relations import edge_between, edge_is_near_equal, relation_contains_object, relation_contains_text
from .types import NON_VISIBLE_REPLAY_ACTIONS, VISIBLE_REPLAY_ACTIONS

MAX_PROMOTED_INTERNAL_ICON_LABEL_TEXT_OVERLAP_RATIO = 0.14


def detect_conflicts(
    *,
    source_objects: list[dict[str, Any]],
    plan_items: list[dict[str, Any]],
    visible_claims: list[dict[str, Any]],
    cleanup_claims: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    source_lookup = {item["sourceObjectId"]: item for item in source_objects}
    plan_lookup = {item["planItemId"]: item for item in plan_items}
    conflicts: list[dict[str, Any]] = []
    conflicts.extend(detect_non_visible_claims(plan_items))
    conflicts.extend(detect_visible_overlap_conflicts(visible_claims, edge_lookup))
    conflicts.extend(detect_missing_copied_cleanup(source_lookup, plan_items, edge_lookup))
    conflicts.extend(detect_invalid_cleanup_claims(source_lookup, plan_lookup, cleanup_claims, edge_lookup))
    return sorted(conflicts, key=lambda item: (item["severity"], item["type"], item.get("sourceObjectIds", []), item.get("planItemIds", [])))


def detect_non_visible_claims(plan_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for item in plan_items:
        action = item["finalReplayAction"]
        if action in VISIBLE_REPLAY_ACTIONS:
            continue
        if item["targetRole"] is not None or action not in NON_VISIBLE_REPLAY_ACTIONS:
            conflicts.append(
                conflict(
                    "non_visible_action_has_visible_claim",
                    "error",
                    [item["sourceObjectId"]],
                    [item["planItemId"]],
                    item["bbox"],
                    f"non-visible action {action} must not claim a visible target role",
                )
            )
    return conflicts


def detect_visible_overlap_conflicts(
    visible_claims: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for index, left in enumerate(visible_claims):
        for right in visible_claims[index + 1 :]:
            intersection = intersection_area(left["bbox"], right["bbox"])
            ratio = overlap_ratio(left["bbox"], right["bbox"])
            if ratio < 0.20 and not edge_is_near_equal(edge_between(edge_lookup, left["sourceObjectId"], right["sourceObjectId"])):
                continue
            if overlap_is_explainable(left, right, edge_lookup):
                continue
            conflicts.append(
                conflict(
                    "visible_ownership_overlap",
                    "warning",
                    [left["sourceObjectId"], right["sourceObjectId"]],
                    [left["planItemId"], right["planItemId"]],
                    union_bbox(left["bbox"], right["bbox"]),
                    "accepted visible replay claims overlap without an explainable owner relation",
                    metrics={"intersectionArea": intersection, "overlapRatio": ratio},
                )
            )
    return conflicts


def detect_missing_copied_cleanup(
    source_lookup: dict[str, dict[str, Any]],
    plan_items: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    visible_items = [item for item in plan_items if item["finalReplayAction"] in VISIBLE_REPLAY_ACTIONS]
    for text in visible_items:
        if text["finalReplayAction"] != "text_replay":
            continue
        for media in visible_items:
            if media["sourceObjectId"] == text["sourceObjectId"] or media["finalReplayAction"] != "image_replay":
                continue
            media_source = source_lookup.get(media["sourceObjectId"])
            if not media_source or media_source["pixelOwner"] != "preserve_raster" or media_source["replayDecision"] != "image_replay":
                continue
            edge = edge_between(edge_lookup, text["sourceObjectId"], media["sourceObjectId"])
            if not relation_contains_text(edge, text_id=text["sourceObjectId"], media_id=media["sourceObjectId"]):
                continue
            if has_copied_cleanup_target(text, media["sourceObjectId"]):
                continue
            conflicts.append(
                conflict(
                    "missing_copied_image_asset_cleanup",
                    "warning",
                    [text["sourceObjectId"], media["sourceObjectId"]],
                    [text["planItemId"], media["planItemId"]],
                    union_bbox(text["bbox"], media["bbox"]),
                    "editable text is contained by replayed preserve-raster media but has no copied image asset cleanup target",
                )
            )
    return conflicts


def detect_invalid_cleanup_claims(
    source_lookup: dict[str, dict[str, Any]],
    plan_lookup: dict[str, dict[str, Any]],
    cleanup_claims: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for claim in cleanup_claims:
        if claim["cleanupTarget"] == "fallback":
            if plan_lookup.get(claim["planItemId"], {}).get("finalReplayAction") not in VISIBLE_REPLAY_ACTIONS:
                conflicts.append(
                    conflict(
                        "invalid_fallback_cleanup_claim",
                        "error",
                        [claim["sourceObjectId"]],
                        [claim["planItemId"]],
                        claim["bbox"],
                        "fallback cleanup claim must belong to an accepted visible replay item",
                    )
                )
            continue
        target_id = str(claim.get("targetSourceObjectId") or "")
        plan_item = plan_lookup.get(claim["planItemId"])
        target = source_lookup.get(target_id)
        if not plan_item:
            conflicts.append(invalid_copied_cleanup_conflict(claim, "copied image cleanup plan item is missing"))
            continue
        if target is None:
            conflicts.append(invalid_copied_cleanup_conflict(claim, "copied image cleanup target source object is missing"))
            continue
        if target["pixelOwner"] != "preserve_raster" or target["replayDecision"] != "image_replay":
            conflicts.append(invalid_copied_cleanup_conflict(claim, "copied image cleanup target must be preserve_raster image_replay media"))
            continue
        if copied_cleanup_is_valid_for_text(plan_item, claim, target_id, edge_lookup):
            continue
        if copied_cleanup_is_valid_for_promoted_internal_asset(plan_item, claim, target_id, edge_lookup):
            continue
        if copied_cleanup_is_valid_for_label_anchored_blocked_asset(plan_item, claim, target_id, edge_lookup):
            continue
        if copied_cleanup_is_valid_for_shape_background(plan_item, claim, target_id, edge_lookup):
            continue
        conflicts.append(
            invalid_copied_cleanup_conflict(
                claim,
                "copied image cleanup must be authorized by editable text containment or promoted internal asset containment",
            )
        )
    return conflicts


def copied_cleanup_is_valid_for_text(
    plan_item: dict[str, Any],
    claim: dict[str, Any],
    target_id: str,
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> bool:
    if plan_item["finalReplayAction"] != "text_replay":
        return False
    edge = edge_between(edge_lookup, claim["sourceObjectId"], target_id)
    return relation_contains_text(edge, text_id=claim["sourceObjectId"], media_id=target_id)


def copied_cleanup_is_valid_for_promoted_internal_asset(
    plan_item: dict[str, Any],
    claim: dict[str, Any],
    target_id: str,
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> bool:
    if plan_item["finalReplayAction"] != "icon_replay":
        return False
    if claim.get("reason") != "promoted_internal_asset_contained_by_media":
        return False
    evidence = plan_item.get("sourceEvidence") if isinstance(plan_item.get("sourceEvidence"), dict) else {}
    if evidence.get("promotionSource") != "m29_6_internal_icon_candidate":
        return False
    if evidence.get("mediaSourceObjectId") != target_id:
        return False
    if not evidence.get("transparentAssetPath"):
        return False
    edge = edge_between(edge_lookup, claim["sourceObjectId"], target_id)
    return relation_contains_object(edge, object_id=claim["sourceObjectId"], media_id=target_id)


def copied_cleanup_is_valid_for_label_anchored_blocked_asset(
    plan_item: dict[str, Any],
    claim: dict[str, Any],
    target_id: str,
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> bool:
    if plan_item["finalReplayAction"] != "icon_replay":
        return False
    if claim.get("reason") != "label_anchored_blocked_asset_contained_by_media":
        return False
    evidence = plan_item.get("sourceEvidence") if isinstance(plan_item.get("sourceEvidence"), dict) else {}
    if not evidence.get("labelAnchorOcrBoxId") or not evidence.get("blockedIds"):
        return False
    edge = edge_between(edge_lookup, claim["sourceObjectId"], target_id)
    return relation_contains_object(edge, object_id=claim["sourceObjectId"], media_id=target_id)


def copied_cleanup_is_valid_for_shape_background(
    plan_item: dict[str, Any],
    claim: dict[str, Any],
    target_id: str,
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> bool:
    if plan_item["finalReplayAction"] != "shape_replay":
        return False
    if claim.get("reason") != "shape_background_contained_by_media":
        return False
    edge = edge_between(edge_lookup, claim["sourceObjectId"], target_id)
    return relation_contains_object(edge, object_id=claim["sourceObjectId"], media_id=target_id)


def promoted_internal_icon_has_visible_replay_evidence(evidence: dict[str, Any]) -> bool:
    return evidence.get("promotionSource") == "m29_6_internal_icon_candidate" and (
        bool(evidence.get("transparentAssetPath")) or evidence.get("controlRowSourceCropEligible") is True
    )


def overlap_is_explainable(left: dict[str, Any], right: dict[str, Any], edge_lookup: dict[frozenset[str], dict[str, Any]]) -> bool:
    actions = {left["finalReplayAction"], right["finalReplayAction"]}
    if "shape_replay" in actions and actions & {"text_replay", "icon_replay", "image_replay"}:
        return True
    if actions == {"image_replay", "icon_replay"}:
        icon = left if left["finalReplayAction"] == "icon_replay" else right
        image = right if icon is left else left
        evidence = icon.get("sourceEvidence") if isinstance(icon.get("sourceEvidence"), dict) else {}
        if (
            promoted_internal_icon_has_visible_replay_evidence(evidence)
            and evidence.get("mediaSourceObjectId") == image["sourceObjectId"]
        ):
            return True
        return bool(evidence.get("labelAnchorOcrBoxId")) and bool(evidence.get("blockedIds")) and has_copied_cleanup_target(
            icon,
            image["sourceObjectId"],
        )
    if actions == {"image_replay", "text_replay"}:
        text = left if left["finalReplayAction"] == "text_replay" else right
        image = right if text is left else left
        edge = edge_between(edge_lookup, text["sourceObjectId"], image["sourceObjectId"])
        return relation_contains_text(edge, text_id=text["sourceObjectId"], media_id=image["sourceObjectId"]) and has_copied_cleanup_target(
            text,
            image["sourceObjectId"],
        )
    if actions == {"icon_replay", "text_replay"}:
        icon = left if left["finalReplayAction"] == "icon_replay" else right
        text = right if icon is left else left
        return is_promoted_internal_icon_label_overlap(icon, text)
    return False


def is_promoted_internal_icon_label_overlap(icon: dict[str, Any], text: dict[str, Any]) -> bool:
    evidence = icon.get("sourceEvidence") if isinstance(icon.get("sourceEvidence"), dict) else {}
    if not promoted_internal_icon_has_visible_replay_evidence(evidence):
        return False
    media_id = str(evidence.get("mediaSourceObjectId") or "")
    if not media_id:
        return False
    text_overlap = optional_float(evidence.get("textOverlapRatio"))
    if text_overlap is not None and text_overlap > MAX_PROMOTED_INTERNAL_ICON_LABEL_TEXT_OVERLAP_RATIO:
        return False
    if text_overlap is not None and evidence.get("transparentAssetPath"):
        return True
    if text_overlap is not None and evidence.get("controlRowSourceCropEligible") is True:
        return True
    if not has_copied_cleanup_target(icon, media_id) or not has_copied_cleanup_target(text, media_id):
        return False
    return True


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def has_copied_cleanup_target(plan_item: dict[str, Any], target_source_id: str) -> bool:
    for target in plan_item.get("cleanupTargets", []):
        if not isinstance(target, dict):
            continue
        if target.get("target") == "copied_image_asset" and target.get("targetSourceObjectId") == target_source_id:
            return True
    return False


def invalid_copied_cleanup_conflict(claim: dict[str, Any], reason: str) -> dict[str, Any]:
    source_ids = [claim["sourceObjectId"]]
    if claim.get("targetSourceObjectId"):
        source_ids.append(str(claim["targetSourceObjectId"]))
    return conflict("invalid_copied_image_asset_cleanup", "error", source_ids, [claim["planItemId"]], claim["bbox"], reason)


def conflict(
    conflict_type: str,
    severity: str,
    source_object_ids: list[str],
    plan_item_ids: list[str],
    bbox: list[int],
    reason: str,
    *,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "type": conflict_type,
        "severity": severity,
        "sourceObjectIds": source_object_ids,
        "planItemIds": plan_item_ids,
        "bbox": bbox,
        "reason": reason,
    }
    if metrics:
        item["metrics"] = metrics
    return item
