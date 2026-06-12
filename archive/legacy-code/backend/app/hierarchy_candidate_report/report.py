from __future__ import annotations

from typing import Any


def build_summary(
    *,
    source_objects: list[dict[str, Any]],
    plan_items: list[dict[str, Any]],
    container_candidates: list[dict[str, Any]],
    parent_candidates: list[dict[str, Any]],
    selected_parent_candidates: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "sourceObjectCount": len(source_objects),
        "planItemCount": len(plan_items),
        "visiblePlanItemCount": sum(1 for item in plan_items if item["visible"]),
        "containerCandidateCount": len(container_candidates),
        "parentCandidateCount": len(parent_candidates),
        "selectedParentCandidateCount": len(selected_parent_candidates),
        "warningCount": len(warnings),
        "confidenceCounts": confidence_counts(container_candidates + selected_parent_candidates),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "materializationChanged": False,
    }


def confidence_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        confidence = str(item.get("confidence") or "unknown")
        counts[confidence] = counts.get(confidence, 0) + 1
    return dict(sorted(counts.items()))
