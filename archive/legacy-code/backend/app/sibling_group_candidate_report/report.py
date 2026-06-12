from __future__ import annotations

from typing import Any


def build_summary(
    *,
    plan_items: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    sibling_groups: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "planItemCount": len(plan_items),
        "visiblePlanItemCount": sum(1 for item in plan_items if item["visible"]),
        "sourceEdgeCount": len(edges),
        "sourceClusterCount": len(clusters),
        "siblingGroupCandidateCount": len(sibling_groups),
        "warningCount": len(warnings),
        "groupPatternCounts": count_values(group.get("groupPattern") for group in sibling_groups),
        "confidenceCounts": count_values(group.get("confidence") for group in sibling_groups),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "materializationChanged": False,
        "groupMaterializationPermission": False,
    }


def count_values(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
