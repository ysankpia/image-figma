from __future__ import annotations

from typing import Any

from .geometry import size_signature


def stability_score_for(
    pattern: str,
    member_ids: list[str],
    nodes: dict[str, dict[str, Any]],
    internal_edges: list[dict[str, Any]],
) -> float:
    possible_edge_count = max(1, len(member_ids) * (len(member_ids) - 1) // 2)
    edge_density = min(1.0, len(internal_edges) / possible_edge_count)
    confidence_score = sum(confidence_value(nodes[node_id].get("confidence")) for node_id in member_ids) / len(member_ids)
    primary_signal = sum(1 for edge in internal_edges if edge["primarySetRelation"] != "disjoint") / len(internal_edges)
    repeatability_score = repeatability_score_for(member_ids, nodes, internal_edges)

    if pattern == "repeated_size_subgraph":
        return min(1.0, 0.62 + repeatability_score * 0.22 + edge_density * 0.08 + confidence_score * 0.08)
    if pattern == "containment_anchor_subgraph":
        return min(1.0, 0.68 + primary_signal * 0.15 + confidence_score * 0.12 + edge_density * 0.05)
    if pattern == "directed_row_subgraph" or pattern == "directed_column_subgraph":
        return min(1.0, 0.58 + edge_density * 0.12 + confidence_score * 0.16 + primary_signal * 0.08)
    return min(1.0, 0.8 + confidence_score * 0.08 + primary_signal * 0.06 + edge_density * 0.06)


def repeatability_score_for(member_ids: list[str], nodes: dict[str, dict[str, Any]], internal_edges: list[dict[str, Any]]) -> float:
    if len(member_ids) < 3:
        return 0.0
    secondary_counts = count_values(relation for edge in internal_edges for relation in edge.get("secondaryGeometryRelations", []))
    owner_counts = count_values(nodes[node_id].get("pixelOwner", "") for node_id in member_ids)
    size_counts = count_values(size_signature(nodes[node_id]["bbox"]) for node_id in member_ids)
    owner_repeat = max(owner_counts.values(), default=1) / len(member_ids)
    size_repeat = max(size_counts.values(), default=1) / len(member_ids)
    repeated_edges = secondary_counts.get("same_size", 0) + min(secondary_counts.get("same_width", 0), secondary_counts.get("same_height", 0))
    repeated_edge_ratio = min(1.0, repeated_edges / max(1, len(internal_edges)))
    return min(1.0, owner_repeat * 0.35 + size_repeat * 0.35 + repeated_edge_ratio * 0.30)


def cluster_risks(member_ids: list[str], nodes: dict[str, dict[str, Any]], internal_edges: list[dict[str, Any]]) -> list[str]:
    risks: list[str] = []
    if any(nodes[node_id].get("confidence") == "low" for node_id in member_ids):
        risks.append("contains_low_confidence_member")
    if any(nodes[node_id].get("pixelOwner") == "diagnostic_only" for node_id in member_ids):
        risks.append("contains_diagnostic_member")
    if any(edge.get("primarySetRelation") == "near_equal" for edge in internal_edges):
        risks.append("near_equal_members_may_be_duplicate_evidence")
    return risks


def count_values(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def confidence_value(value: Any) -> float:
    if value == "high":
        return 1.0
    if value == "medium":
        return 0.75
    if value == "low":
        return 0.4
    return 0.5
