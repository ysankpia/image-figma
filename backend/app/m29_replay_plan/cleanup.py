from __future__ import annotations

from typing import Any


def cleanup_targets_for(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    targets = [{"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"}]
    if item["replayDecision"] != "text_replay":
        return targets
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
    return targets


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
        return primary == "contained_by"
    if left == media_id and right == text_id:
        return primary == "contains"
    return False
