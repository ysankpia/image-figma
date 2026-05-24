from __future__ import annotations

from typing import Any

from .types import ReplayAction, TargetRole


def replay_action_for(item: dict[str, Any]) -> ReplayAction:
    decision = item["replayDecision"]
    owner = item["pixelOwner"]
    confidence = item["confidence"]
    if decision == "text_replay" and owner == "editable_text" and confidence != "low":
        return "text_replay"
    if decision == "image_replay" and owner == "preserve_raster" and confidence != "low":
        return "image_replay"
    if decision == "icon_replay" and owner == "raster_icon" and confidence != "low":
        return "icon_replay"
    if decision == "shape_replay" and owner == "shape_geometry" and confidence != "low":
        return "shape_replay"
    if decision == "preserve_in_parent_raster":
        return "preserve_in_parent_raster"
    if owner == "fallback_only":
        return "fallback_only"
    return "diagnostic_only"


def target_role_for_action(action: ReplayAction) -> TargetRole | None:
    return {
        "text_replay": "m29_text",
        "image_replay": "m29_image",
        "icon_replay": "m29_symbol",
        "shape_replay": "m29_shape",
    }.get(action)


def near_equal_duplicate_ids(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
    already_suppressed: set[str],
) -> tuple[list[str], list[str]]:
    suppressed: list[str] = []
    edge_ids: list[str] = []
    item_priority = replay_priority(item)
    for other in source_objects:
        if other["id"] <= item["id"] or other["id"] in already_suppressed:
            continue
        edge = edge_lookup.get(frozenset({item["id"], other["id"]}))
        if not edge or edge.get("primarySetRelation") != "near_equal":
            continue
        other_priority = replay_priority(other)
        if item_priority >= other_priority:
            suppressed.append(other["id"])
        else:
            suppressed.append(item["id"])
        edge_id = str(edge.get("edgeId") or "")
        if edge_id:
            edge_ids.append(edge_id)
    return sorted(set(suppressed)), sorted(set(edge_ids))


def replay_priority(item: dict[str, Any]) -> tuple[int, int]:
    owner_rank = {
        "editable_text": 50,
        "preserve_raster": 40,
        "raster_icon": 35,
        "shape_geometry": 30,
        "fallback_only": 10,
        "diagnostic_only": 0,
    }.get(item["pixelOwner"], 0)
    confidence_rank = {"high": 3, "medium": 2, "low": 1}.get(item["confidence"], 0)
    return owner_rank, confidence_rank
