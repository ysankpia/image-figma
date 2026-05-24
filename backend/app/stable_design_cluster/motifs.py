from __future__ import annotations

from typing import Any

from .types import ClusterPattern, RoleHint


def group_edges_by_motif(edges: list[dict[str, Any]], nodes: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        "containment_anchor_subgraph": [],
        "directed_row_subgraph": [],
        "directed_column_subgraph": [],
        "repeated_size_subgraph": [],
        "stable_local_relation_subgraph": [],
    }
    for edge in edges:
        pattern, _, _ = classify_edge_motif(edge, nodes)
        grouped[pattern].append(edge)
    return grouped


def classify_edge_motif(
    edge: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
) -> tuple[ClusterPattern, RoleHint | None, list[str]]:
    left = nodes[edge["leftObjectId"]]
    right = nodes[edge["rightObjectId"]]
    primary = str(edge["primarySetRelation"])
    secondary = set(edge.get("secondaryGeometryRelations", []))

    has_row_flow = "left_of" in secondary or "right_of" in secondary
    has_column_flow = "above" in secondary or "below" in secondary
    has_repeat_signal = "same_size" in secondary or ("same_width" in secondary and "same_height" in secondary)
    has_containment = primary in {"contains", "contained_by"}
    has_near_equal = primary == "near_equal"
    has_overlap = primary == "overlaps"
    has_near = "near" in secondary

    if has_repeat_signal and has_near:
        return "repeated_size_subgraph", "repeated_item_like", ["repeated_size_or_dimension_relations"]
    if has_containment:
        return "containment_anchor_subgraph", "background_anchor_like", ["contains_or_contained_by_relations"]
    if has_row_flow and ("aligned_center_y" in secondary or "aligned_top" in secondary or "aligned_bottom" in secondary):
        return "directed_row_subgraph", "row_like", ["directed_horizontal_relation_flow"]
    if has_column_flow and ("aligned_center_x" in secondary or "aligned_left" in secondary or "aligned_right" in secondary):
        return "directed_column_subgraph", "column_like", ["directed_vertical_relation_flow"]
    if has_near_equal or has_overlap or has_near:
        if is_media_text_pair(left, right):
            return "containment_anchor_subgraph", "background_anchor_like", ["media_and_text_members_share_stable_relations"]
        return "stable_local_relation_subgraph", None, ["local_structural_relations"]
    return "stable_local_relation_subgraph", None, ["local_structural_relations"]


def is_media_text_pair(left: dict[str, Any], right: dict[str, Any]) -> bool:
    kinds = {str(left.get("visualKind") or ""), str(right.get("visualKind") or "")}
    return "media_region" in kinds and bool(kinds & {"editable_ui_text", "preserve_raster_text"})


def role_hint_for_pattern(pattern: str) -> RoleHint | None:
    return {
        "containment_anchor_subgraph": "background_anchor_like",
        "directed_row_subgraph": "row_like",
        "directed_column_subgraph": "column_like",
        "repeated_size_subgraph": "repeated_item_like",
        "stable_local_relation_subgraph": None,
    }[pattern]


def pattern_reasons_for_pattern(pattern: str) -> list[str]:
    return {
        "containment_anchor_subgraph": ["contains_or_contained_by_relations"],
        "directed_row_subgraph": ["directed_horizontal_relation_flow"],
        "directed_column_subgraph": ["directed_vertical_relation_flow"],
        "repeated_size_subgraph": ["repeated_size_or_dimension_relations"],
        "stable_local_relation_subgraph": ["local_structural_relations"],
    }[pattern]
