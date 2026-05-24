from __future__ import annotations

from typing import Any


def build_edge_lookup(edges: list[dict[str, Any]]) -> dict[frozenset[str], dict[str, Any]]:
    return {frozenset({edge["leftObjectId"], edge["rightObjectId"]}): edge for edge in edges}


def edge_between(edge_lookup: dict[frozenset[str], dict[str, Any]], left_id: str, right_id: str) -> dict[str, Any] | None:
    return edge_lookup.get(frozenset({left_id, right_id}))


def child_in_parent_ratio(edge: dict[str, Any], *, parent_id: str, child_id: str) -> float:
    metrics = edge.get("metrics") if isinstance(edge.get("metrics"), dict) else {}
    left_id = str(edge.get("leftObjectId") or "")
    right_id = str(edge.get("rightObjectId") or "")
    if left_id == parent_id and right_id == child_id:
        return safe_float(metrics.get("rightInLeftRatio"))
    if left_id == child_id and right_id == parent_id:
        return safe_float(metrics.get("leftInRightRatio"))
    return 0.0


def relation_supports_parent(edge: dict[str, Any], *, parent_id: str, child_id: str, minimum_overlap: float = 0.55) -> bool:
    primary = str(edge.get("primarySetRelation") or "")
    if primary == "near_equal" or primary == "disjoint":
        return False
    left_id = str(edge.get("leftObjectId") or "")
    right_id = str(edge.get("rightObjectId") or "")
    if left_id == parent_id and right_id == child_id and primary == "contains":
        return True
    if left_id == child_id and right_id == parent_id and primary == "contained_by":
        return True
    return primary == "overlaps" and child_in_parent_ratio(edge, parent_id=parent_id, child_id=child_id) >= minimum_overlap


def safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
