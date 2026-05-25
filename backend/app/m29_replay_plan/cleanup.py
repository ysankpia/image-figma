from __future__ import annotations

from typing import Any


def cleanup_targets_for(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    targets = [{"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"}]
    if item["replayDecision"] == "icon_replay":
        targets.extend(promoted_internal_asset_cleanup_targets(item, source_objects, edge_lookup))
        return targets
    if item["replayDecision"] == "shape_replay":
        targets.extend(shape_cleanup_targets(item, source_objects, edge_lookup))
        return targets
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


def shape_cleanup_targets(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for other in source_objects:
        if other["id"] == item["id"]:
            continue
        if other["replayDecision"] != "image_replay" or other["pixelOwner"] != "preserve_raster":
            continue
        edge = edge_lookup.get(frozenset({item["id"], other["id"]}))
        if shape_is_contained_by_media(item["id"], other["id"], edge):
            targets.append(
                {
                    "target": "copied_image_asset",
                    "targetSourceObjectId": other["id"],
                    "reason": "shape_background_contained_by_media",
                }
            )
    return targets


def promoted_internal_asset_cleanup_targets(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    if evidence.get("promotionSource") != "m29_6_internal_icon_candidate":
        return []
    media_id = str(evidence.get("mediaSourceObjectId") or "")
    if not media_id:
        return []
    media = next((other for other in source_objects if other["id"] == media_id), None)
    if media is None or media["replayDecision"] != "image_replay" or media["pixelOwner"] != "preserve_raster":
        return []
    edge = edge_lookup.get(frozenset({item["id"], media_id}))
    if not edge or not internal_asset_is_contained_by_media(item["id"], media_id, edge):
        return []
    return [
        {
            "target": "copied_image_asset",
            "targetSourceObjectId": media_id,
            "reason": "promoted_internal_asset_contained_by_media",
        }
    ]


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


def text_overlap_ratio(edge: dict[str, Any], *, text_on_left: bool) -> float:
    metrics = edge.get("metrics") if isinstance(edge.get("metrics"), dict) else {}
    key = "leftInRightRatio" if text_on_left else "rightInLeftRatio"
    try:
        return float(metrics.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0
