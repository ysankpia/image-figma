from __future__ import annotations

from typing import Any

from .scoring import count_values


def build_summary(
    *,
    source_node_count: int,
    source_edge_count: int,
    structural_edge_count: int,
    clusters: list[dict[str, Any]],
    skipped_nodes: list[dict[str, Any]],
    skipped_edges: list[dict[str, Any]],
    skipped_clusters: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    pattern_counts = count_values(cluster.get("clusterPattern", "") for cluster in clusters)
    role_hint_counts = count_values(cluster.get("roleHint", "") for cluster in clusters if cluster.get("roleHint"))
    return {
        "sourceNodeCount": source_node_count,
        "sourceEdgeCount": source_edge_count,
        "structuralEdgeCount": structural_edge_count,
        "clusterCount": len(clusters),
        "skippedNodeCount": len(skipped_nodes),
        "skippedEdgeCount": len(skipped_edges),
        "skippedClusterCount": len(skipped_clusters),
        "warningCount": len(warnings),
        "clusterPatternCounts": dict(sorted(pattern_counts.items())),
        "roleHintCounts": dict(sorted(role_hint_counts.items())),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "componentChanged": False,
    }
