from __future__ import annotations

from typing import Any

from ..region_relation_kernel import normalize_bbox


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
        cleanup_targets = item.get("cleanupTargets")
        items.append(
            {
                "planItemId": plan_id,
                "sourceObjectId": source_id,
                "bbox": bbox,
                "finalReplayAction": str(item.get("finalReplayAction") or ""),
                "targetRole": item.get("targetRole"),
                "pixelOwner": str(item.get("pixelOwner") or ""),
                "cleanupTargets": cleanup_targets if isinstance(cleanup_targets, list) else [],
                "confidence": str(item.get("confidence") or "low"),
            }
        )
    return sorted(items, key=lambda item: item["planItemId"]), warnings

