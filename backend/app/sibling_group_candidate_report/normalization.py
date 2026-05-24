from __future__ import annotations

from typing import Any

from ..region_relation_kernel import normalize_bbox
from .types import VISIBLE_REPLAY_ACTIONS


def normalize_plan_items(raw_items: Any) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items if isinstance(raw_items, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_plan_item:{index}")
            continue
        plan_id = str(item.get("id") or f"plan_item_{index + 1:04d}")
        source_id = str(item.get("sourceObjectId") or "").strip()
        if not source_id:
            warnings.append(f"skipped_missing_plan_source_object_id:{plan_id}")
            continue
        if plan_id in seen:
            warnings.append(f"skipped_duplicate_plan_item_id:{plan_id}")
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"planItems[{index}].bbox")
        except ValueError:
            warnings.append(f"skipped_invalid_plan_item_bbox:{plan_id}")
            continue
        seen.add(plan_id)
        action = str(item.get("finalReplayAction") or "")
        items.append(
            {
                "planItemId": plan_id,
                "sourceObjectId": source_id,
                "bbox": bbox,
                "finalReplayAction": action,
                "targetRole": item.get("targetRole"),
                "pixelOwner": str(item.get("pixelOwner") or ""),
                "confidence": str(item.get("confidence") or "low"),
                "visible": action in VISIBLE_REPLAY_ACTIONS,
            }
        )
    return sorted(items, key=lambda item: item["planItemId"]), warnings


def normalize_edges(raw_edges: Any, valid_source_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    edges: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, item in enumerate(raw_edges if isinstance(raw_edges, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_relation_edge:{index}")
            continue
        edge_id = str(item.get("edgeId") or f"m2931_edge_{index + 1:04d}")
        left_id = str(item.get("leftObjectId") or "")
        right_id = str(item.get("rightObjectId") or "")
        if left_id not in valid_source_ids or right_id not in valid_source_ids or left_id == right_id:
            warnings.append(f"skipped_invalid_relation_edge_endpoint:{edge_id}")
            continue
        edges.append(
            {
                "edgeId": edge_id,
                "leftObjectId": left_id,
                "rightObjectId": right_id,
                "primarySetRelation": str(item.get("primarySetRelation") or ""),
                "secondaryGeometryRelations": [str(value) for value in item.get("secondaryGeometryRelations", []) if isinstance(value, str)]
                if isinstance(item.get("secondaryGeometryRelations"), list)
                else [],
                "metrics": item.get("metrics") if isinstance(item.get("metrics"), dict) else {},
            }
        )
    return sorted(edges, key=lambda item: item["edgeId"]), warnings


def normalize_clusters(raw_clusters: Any, valid_source_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    clusters: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, item in enumerate(raw_clusters if isinstance(raw_clusters, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_m294_cluster:{index}")
            continue
        cluster_id = str(item.get("id") or f"m294_cluster_{index + 1:04d}")
        member_ids = [str(value) for value in item.get("memberNodeIds", []) if isinstance(value, str) and value in valid_source_ids]
        if len(member_ids) < 2:
            warnings.append(f"skipped_m294_cluster_too_few_visible_members:{cluster_id}")
            continue
        clusters.append(
            {
                "clusterId": cluster_id,
                "memberSourceObjectIds": sorted(member_ids),
                "roleHint": item.get("roleHint"),
                "clusterPattern": str(item.get("clusterPattern") or ""),
                "stabilityScore": safe_float(item.get("stabilityScore")),
                "repeatabilityScore": safe_float(item.get("repeatabilityScore")),
            }
        )
    return sorted(clusters, key=lambda item: item["clusterId"]), warnings


def normalize_hierarchy_edges(raw_selected: Any) -> set[frozenset[str]]:
    excluded: set[frozenset[str]] = set()
    for item in raw_selected if isinstance(raw_selected, list) else []:
        if not isinstance(item, dict):
            continue
        parent = str(item.get("parentSourceObjectId") or "")
        child = str(item.get("childSourceObjectId") or "")
        if parent and child and parent != child:
            excluded.add(frozenset({parent, child}))
    return excluded


def safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
