from __future__ import annotations

from typing import Any

from ..region_relation_kernel import normalize_bbox
from .geometry import node_sort_key
from .types import PRIMARY_RELATIONS, SECONDARY_RELATIONS


def normalize_nodes(raw_nodes: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_nodes if isinstance(raw_nodes, list) else []):
        if not isinstance(item, dict):
            skipped.append({"index": index, "reason": "invalid_node", "message": "node must be an object"})
            continue
        node_id = str(item.get("id") or "").strip()
        if not node_id:
            skipped.append({"index": index, "reason": "missing_node_id", "message": "node id is required"})
            continue
        if node_id in seen_ids:
            skipped.append({"sourceObjectId": node_id, "index": index, "reason": "duplicate_node_id"})
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"nodes[{index}].bbox")
        except ValueError as error:
            skipped.append({"sourceObjectId": node_id, "index": index, "reason": "invalid_bbox", "message": str(error)})
            continue
        seen_ids.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "bbox": bbox,
                "pixelOwner": str(item.get("pixelOwner") or ""),
                "replayDecision": str(item.get("replayDecision") or ""),
                "confidence": str(item.get("confidence") or ""),
                "visualKind": str(item.get("visualKind") or ""),
            }
        )
    return sorted(nodes, key=node_sort_key), skipped


def normalize_edges(raw_edges: Any, valid_node_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    edges: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, item in enumerate(raw_edges if isinstance(raw_edges, list) else []):
        if not isinstance(item, dict):
            skipped.append({"index": index, "reason": "invalid_edge", "message": "edge must be an object"})
            continue
        edge_id = str(item.get("edgeId") or f"m2931_edge_{index + 1:04d}")
        left_id = str(item.get("leftObjectId") or "")
        right_id = str(item.get("rightObjectId") or "")
        if left_id not in valid_node_ids or right_id not in valid_node_ids or left_id == right_id:
            skipped.append({"edgeId": edge_id, "index": index, "reason": "invalid_edge_endpoint"})
            continue
        primary = str(item.get("primarySetRelation") or "")
        if primary not in PRIMARY_RELATIONS:
            skipped.append({"edgeId": edge_id, "index": index, "reason": "invalid_primary_relation"})
            continue
        secondary_raw = item.get("secondaryGeometryRelations")
        if not isinstance(secondary_raw, list):
            skipped.append({"edgeId": edge_id, "index": index, "reason": "invalid_secondary_relations"})
            continue
        secondary = [str(relation) for relation in secondary_raw if str(relation) in SECONDARY_RELATIONS]
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        edges.append(
            {
                "edgeId": edge_id,
                "leftObjectId": left_id,
                "rightObjectId": right_id,
                "primarySetRelation": primary,
                "secondaryGeometryRelations": secondary,
                "metrics": metrics,
            }
        )
    return sorted(edges, key=lambda edge: edge["edgeId"]), skipped
