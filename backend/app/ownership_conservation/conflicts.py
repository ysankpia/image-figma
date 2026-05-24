from __future__ import annotations

from typing import Any

from .geometry import intersection_area, overlap_ratio, union_bbox
from .relations import edge_between, edge_is_near_equal, relation_contains_text
from .types import NON_VISIBLE_REPLAY_ACTIONS, VISIBLE_REPLAY_ACTIONS


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
            if intersection <= 0 and not edge_is_near_equal(edge_between(edge_lookup, left["sourceObjectId"], right["sourceObjectId"])):
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
                    metrics={"intersectionArea": intersection, "overlapRatio": overlap_ratio(left["bbox"], right["bbox"])},
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
        if not plan_item or plan_item["finalReplayAction"] != "text_replay":
            conflicts.append(invalid_copied_cleanup_conflict(claim, "copied image cleanup must belong to a text replay plan item"))
            continue
        if target is None:
            conflicts.append(invalid_copied_cleanup_conflict(claim, "copied image cleanup target source object is missing"))
            continue
        if target["pixelOwner"] != "preserve_raster" or target["replayDecision"] != "image_replay":
            conflicts.append(invalid_copied_cleanup_conflict(claim, "copied image cleanup target must be preserve_raster image_replay media"))
            continue
        edge = edge_between(edge_lookup, claim["sourceObjectId"], target_id)
        if not relation_contains_text(edge, text_id=claim["sourceObjectId"], media_id=target_id):
            conflicts.append(invalid_copied_cleanup_conflict(claim, "copied image cleanup relation must be media contains text or near_equal"))
    return conflicts


def overlap_is_explainable(left: dict[str, Any], right: dict[str, Any], edge_lookup: dict[frozenset[str], dict[str, Any]]) -> bool:
    actions = {left["finalReplayAction"], right["finalReplayAction"]}
    if "shape_replay" in actions and actions & {"text_replay", "icon_replay"}:
        return True
    if actions == {"image_replay", "text_replay"}:
        text = left if left["finalReplayAction"] == "text_replay" else right
        image = right if text is left else left
        edge = edge_between(edge_lookup, text["sourceObjectId"], image["sourceObjectId"])
        return relation_contains_text(edge, text_id=text["sourceObjectId"], media_id=image["sourceObjectId"]) and has_copied_cleanup_target(
            text,
            image["sourceObjectId"],
        )
    return False


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

