from __future__ import annotations

from typing import Any

from ..region_relation_kernel import normalize_bbox
from .types import VISIBLE_REPLAY_ACTIONS


def normalize_source_objects(raw_objects: Any) -> tuple[list[dict[str, Any]], list[str]]:
    objects: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_objects if isinstance(raw_objects, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_source_object:{index}")
            continue
        source_id = str(item.get("id") or "").strip()
        if not source_id:
            warnings.append(f"skipped_missing_source_object_id:{index}")
            continue
        if source_id in seen:
            warnings.append(f"skipped_duplicate_source_object_id:{source_id}")
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"sourceObjects[{index}].bbox")
        except ValueError:
            warnings.append(f"skipped_invalid_source_object_bbox:{source_id}")
            continue
        seen.add(source_id)
        objects.append(
            {
                "sourceObjectId": source_id,
                "bbox": bbox,
                "visualKind": str(item.get("visualKind") or ""),
                "pixelOwner": str(item.get("pixelOwner") or ""),
                "replayDecision": str(item.get("replayDecision") or ""),
                "confidence": str(item.get("confidence") or "low"),
            }
        )
    return sorted(objects, key=lambda item: item["sourceObjectId"]), warnings


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
    seen: set[str] = set()
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
        if edge_id in seen:
            warnings.append(f"skipped_duplicate_relation_edge_id:{edge_id}")
            continue
        seen.add(edge_id)
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
