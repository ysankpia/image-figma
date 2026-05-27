from __future__ import annotations

from typing import Any


VISIBLE_ACTIONS = {"text_replay", "image_replay", "icon_replay", "shape_replay"}


def plan_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    action_order = {
        "shape_replay": 0,
        "image_replay": 1,
        "icon_replay": 2,
        "text_replay": 3,
        "preserve_in_parent_raster": 4,
        "fallback_only": 5,
        "diagnostic_only": 6,
        "suppress_duplicate": 7,
    }
    return action_order.get(str(item.get("finalReplayAction")), 99), str(item.get("sourceObjectId") or "")


def sort_plan_items_for_layer_order(plan_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_order = sorted(plan_items, key=plan_sort_key)
    base_index = {id(item): index for index, item in enumerate(base_order)}
    by_source_id = {
        str(item.get("sourceObjectId") or ""): item
        for item in base_order
        if str(item.get("sourceObjectId") or "")
    }
    dependencies: dict[str, set[str]] = {
        source_id: set()
        for source_id, item in by_source_id.items()
        if is_visible_plan_item(item)
    }
    for source_id, item in by_source_id.items():
        if source_id not in dependencies:
            continue
        for parent_id in foreground_parent_source_ids(item):
            parent = by_source_id.get(parent_id)
            if parent is None or not is_visible_plan_item(parent):
                continue
            if parent_id != source_id:
                dependencies[source_id].add(parent_id)

    ordered: list[dict[str, Any]] = []
    emitted: set[str] = set()
    remaining = [item for item in base_order]
    while remaining:
        ready = [
            item
            for item in remaining
            if dependencies.get(str(item.get("sourceObjectId") or ""), set()).issubset(emitted)
        ]
        if not ready:
            ready = [min(remaining, key=lambda item: base_index[id(item)])]
        item = min(ready, key=lambda item: base_index[id(item)])
        remaining.remove(item)
        ordered.append(item)
        source_id = str(item.get("sourceObjectId") or "")
        if source_id:
            emitted.add(source_id)
    return ordered


def is_visible_plan_item(item: dict[str, Any]) -> bool:
    return str(item.get("finalReplayAction") or "") in VISIBLE_ACTIONS


def foreground_parent_source_ids(item: dict[str, Any]) -> list[str]:
    parent_ids: list[str] = []
    for target in item.get("cleanupTargets", []) if isinstance(item.get("cleanupTargets"), list) else []:
        if not isinstance(target, dict):
            continue
        if target.get("target") != "copied_image_asset":
            continue
        parent_id = str(target.get("targetSourceObjectId") or "")
        if parent_id:
            parent_ids.append(parent_id)

    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    if evidence.get("promotionSource") or evidence.get("foregroundClaimId"):
        for key in ("parentControlSourceObjectId", "mediaSourceObjectId"):
            parent_id = str(evidence.get(key) or "")
            if parent_id:
                parent_ids.append(parent_id)
    return dedupe_preserve_order(parent_ids)


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
