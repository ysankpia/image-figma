from __future__ import annotations

from typing import Any

from .budget import visible_plan_sort_key
from .utils import dedupe_preserve_order


def suppress_visible_overlap_duplicates(
    plan_items: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    suppressed_by_id: dict[str, dict[str, Any]] = {}
    for item in sorted(plan_items, key=overlap_priority_sort_key):
        if item["sourceObjectId"] in suppressed_by_id:
            continue
        duplicate_ids: list[str] = []
        relation_edge_ids = set(item["relationEdgeIds"])
        for other in plan_items:
            other_id = other["sourceObjectId"]
            if other_id == item["sourceObjectId"] or other_id in suppressed_by_id:
                continue
            edge = edge_lookup.get(frozenset({item["sourceObjectId"], other_id}))
            if not should_suppress_visible_overlap(item, other, edge):
                continue
            duplicate_ids.append(other_id)
            edge_id = str((edge or {}).get("edgeId") or "")
            if edge_id:
                relation_edge_ids.add(edge_id)
            suppressed_by_id[other_id] = suppress_visible_overlap_item(other, edge_id)
        kept = dict(item)
        kept["suppressedSourceObjectIds"] = dedupe_preserve_order([*kept["suppressedSourceObjectIds"], *duplicate_ids])
        kept["relationEdgeIds"] = sorted(relation_edge_ids)
        if duplicate_ids:
            kept["reasons"] = dedupe_preserve_order([*kept["reasons"], "visible_overlap_duplicate_suppression"])
        accepted.append(kept)
    suppressed = [suppressed_by_id[source_id] for source_id in sorted(suppressed_by_id)]
    return sorted(accepted, key=visible_plan_sort_key), suppressed


def overlap_priority_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    action_rank = {"shape_replay": 0, "icon_replay": 1, "image_replay": 2, "text_replay": 3}.get(item["finalReplayAction"], 9)
    confidence_rank = {"high": 0, "medium": 1, "low": 2}.get(item["confidence"], 2)
    return action_rank, confidence_rank, -bbox_area(item["bbox"]), item["sourceObjectId"]


def should_suppress_visible_overlap(left: dict[str, Any], right: dict[str, Any], edge: dict[str, Any] | None) -> bool:
    if left["finalReplayAction"] != right["finalReplayAction"]:
        return False
    if left["finalReplayAction"] not in {"icon_replay", "shape_replay"}:
        return False
    if left["pixelOwner"] != right["pixelOwner"]:
        return False
    if str((edge or {}).get("primarySetRelation") or "") == "near_equal":
        return True
    left_area = bbox_area(left["bbox"])
    right_area = bbox_area(right["bbox"])
    intersection = intersection_area(left["bbox"], right["bbox"])
    if intersection <= 0 or min(left_area, right_area) <= 0:
        return False
    containment_ratio = intersection / min(left_area, right_area)
    if containment_ratio >= 0.92:
        return True
    if left["finalReplayAction"] == "shape_replay":
        return containment_ratio >= 0.25 and str((edge or {}).get("primarySetRelation") or "") in {"contains", "contained_by", "overlaps"}
    return containment_ratio >= 0.20 and str((edge or {}).get("primarySetRelation") or "") in {"contains", "contained_by", "overlaps"}


def suppress_visible_overlap_item(item: dict[str, Any], edge_id: str) -> dict[str, Any]:
    suppressed = dict(item)
    suppressed["finalReplayAction"] = "suppress_duplicate"
    suppressed["targetRole"] = None
    suppressed["cleanupTargets"] = []
    suppressed["suppressedSourceObjectIds"] = []
    if edge_id:
        suppressed["relationEdgeIds"] = dedupe_preserve_order([*suppressed["relationEdgeIds"], edge_id])
    suppressed["reasons"] = dedupe_preserve_order([*suppressed["reasons"], "visible_overlap_duplicate_suppressed"])
    suppressed["risks"] = dedupe_preserve_order([*suppressed["risks"], "visible_overlap_duplicate"])
    return suppressed


def bbox_area(bbox: list[int]) -> int:
    return max(0, int(bbox[2])) * max(0, int(bbox[3]))


def intersection_area(left: list[int], right: list[int]) -> int:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    return max(0, x2 - x1) * max(0, y2 - y1)
