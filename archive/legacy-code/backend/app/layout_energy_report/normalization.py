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
        action = str(item.get("finalReplayAction") or "")
        seen.add(plan_id)
        items.append(
            {
                "planItemId": plan_id,
                "sourceObjectId": source_id,
                "bbox": bbox,
                "finalReplayAction": action,
                "confidence": str(item.get("confidence") or "low"),
                "visible": action in VISIBLE_REPLAY_ACTIONS,
            }
        )
    return sorted(items, key=lambda item: item["planItemId"]), warnings


def normalize_sibling_groups(raw_groups: Any, visible_source_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    groups: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, item in enumerate(raw_groups if isinstance(raw_groups, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_sibling_group:{index}")
            continue
        group_id = str(item.get("id") or f"m29_sibling_group_{index + 1:04d}")
        member_ids = [str(value) for value in item.get("memberSourceObjectIds", []) if isinstance(value, str) and value in visible_source_ids]
        if len(member_ids) < 2:
            warnings.append(f"skipped_sibling_group_too_few_visible_members:{group_id}")
            continue
        groups.append(
            {
                "id": group_id,
                "memberSourceObjectIds": sorted(member_ids),
                "groupPattern": str(item.get("groupPattern") or "unknown"),
                "source": str(item.get("source") or "unknown"),
                "confidence": str(item.get("confidence") or "low"),
                "score": safe_float(item.get("score")),
            }
        )
    return sorted(groups, key=lambda item: item["id"]), warnings


def normalize_selected_parents(raw_selected: Any, visible_source_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    selected: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, item in enumerate(raw_selected if isinstance(raw_selected, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_hierarchy_parent:{index}")
            continue
        parent = str(item.get("parentSourceObjectId") or "")
        child = str(item.get("childSourceObjectId") or "")
        if not parent or child not in visible_source_ids or parent == child:
            warnings.append(f"skipped_invalid_hierarchy_parent_child:{index}")
            continue
        selected.append(
            {
                "parentSourceObjectId": parent,
                "childSourceObjectId": child,
                "parentPlanItemId": item.get("parentPlanItemId"),
                "childPlanItemId": item.get("childPlanItemId"),
                "confidence": str(item.get("confidence") or "low"),
                "score": safe_float(item.get("score")),
            }
        )
    return selected, warnings


def safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
