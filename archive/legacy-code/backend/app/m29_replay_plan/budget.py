from __future__ import annotations

from typing import Any

from .utils import dedupe_preserve_order


def apply_node_budget(plan_items: list[dict[str, Any]], max_visible_nodes: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(plan_items, key=visible_plan_sort_key)
    accepted = ordered[:max_visible_nodes]
    suppressed: list[dict[str, Any]] = []
    for item in ordered[max_visible_nodes:]:
        suppressed_item = dict(item)
        suppressed_item["finalReplayAction"] = "suppress_duplicate"
        suppressed_item["targetRole"] = None
        suppressed_item["cleanupTargets"] = []
        suppressed_item["reasons"] = dedupe_preserve_order([*suppressed_item["reasons"], "node_budget_suppressed"])
        suppressed_item["risks"] = dedupe_preserve_order([*suppressed_item["risks"], "node_budget_exceeded"])
        suppressed.append(suppressed_item)
    return accepted, suppressed


def visible_plan_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    action_rank = {"shape_replay": 0, "image_replay": 1, "icon_replay": 2, "text_replay": 3}.get(item["finalReplayAction"], 9)
    confidence_rank = {"high": 0, "medium": 1, "low": 2}.get(item["confidence"], 2)
    return action_rank, confidence_rank, item["sourceObjectId"]


def suppressed_duplicate_items(
    source_objects: list[dict[str, Any]],
    suppressed_source_ids: set[str],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
    cluster_lookup: dict[str, list[str]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    by_id = {item["id"]: item for item in source_objects}
    for source_id in sorted(suppressed_source_ids):
        item = by_id.get(source_id)
        if item is None:
            continue
        relation_edges = [
            str(edge.get("edgeId") or "")
            for key, edge in edge_lookup.items()
            if source_id in key and edge.get("primarySetRelation") == "near_equal"
        ]
        items.append(
            {
                "id": "",
                "sourceObjectId": source_id,
                "bbox": item["bbox"],
                "finalReplayAction": "suppress_duplicate",
                "targetRole": None,
                "pixelOwner": item["pixelOwner"],
                "cleanupTargets": [],
                "suppressedSourceObjectIds": [],
                "relationEdgeIds": sorted(edge_id for edge_id in relation_edges if edge_id),
                "clusterIds": cluster_lookup.get(source_id, []),
                "confidence": item["confidence"],
                "reasons": dedupe_preserve_order([*item["reasons"], "near_equal_duplicate_suppressed"]),
                "risks": item["risks"],
            }
        )
    return items
