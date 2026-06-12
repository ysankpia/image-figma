from __future__ import annotations

from typing import Any


def build_edge_lookup(report: dict[str, Any] | None) -> dict[frozenset[str], dict[str, Any]]:
    lookup: dict[frozenset[str], dict[str, Any]] = {}
    edges = (report or {}).get("edges", [])
    for edge in edges if isinstance(edges, list) else []:
        if not isinstance(edge, dict):
            continue
        left = str(edge.get("leftObjectId") or "")
        right = str(edge.get("rightObjectId") or "")
        if not left or not right or left == right:
            continue
        lookup[frozenset({left, right})] = edge
    return lookup


def edge_between(edge_lookup: dict[frozenset[str], dict[str, Any]], left_id: str, right_id: str) -> dict[str, Any] | None:
    return edge_lookup.get(frozenset({left_id, right_id}))


def relation_contains_object(edge: dict[str, Any] | None, *, object_id: str, media_id: str) -> bool:
    if edge is None:
        return False
    primary = str(edge.get("primarySetRelation") or "")
    if primary == "near_equal":
        return True
    left = str(edge.get("leftObjectId") or "")
    right = str(edge.get("rightObjectId") or "")
    if left == media_id and right == object_id:
        return primary == "contains" or text_overlap_ratio(edge, text_on_left=False) >= 0.20
    if left == object_id and right == media_id:
        return primary == "contained_by" or text_overlap_ratio(edge, text_on_left=True) >= 0.20
    return False


def relation_contains_text(edge: dict[str, Any] | None, *, text_id: str, media_id: str) -> bool:
    return relation_contains_object(edge, object_id=text_id, media_id=media_id)


def edge_is_near_equal(edge: dict[str, Any] | None) -> bool:
    return str((edge or {}).get("primarySetRelation") or "") == "near_equal"


def text_overlap_ratio(edge: dict[str, Any], *, text_on_left: bool) -> float:
    metrics = edge.get("metrics") if isinstance(edge.get("metrics"), dict) else {}
    key = "leftInRightRatio" if text_on_left else "rightInLeftRatio"
    try:
        return float(metrics.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0
