from __future__ import annotations

from typing import Any


def build_summary(
    *,
    layout_candidates: list[dict[str, Any]],
    permission_items: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "layoutEnergyCandidateCount": len(layout_candidates),
        "permissionItemCount": len(permission_items),
        "allowCandidateCount": sum(1 for item in permission_items if item["permission"] == "allow_candidate"),
        "deferCount": sum(1 for item in permission_items if item["permission"] == "defer"),
        "rejectCount": sum(1 for item in permission_items if item["permission"] == "reject"),
        "warningCount": len(warnings),
        "permissionCounts": count_values(item.get("permission") for item in permission_items),
        "recommendedModelCounts": count_values(item.get("recommendedModel") for item in permission_items),
        "confidenceCounts": count_values(item.get("confidence") for item in permission_items),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "materializationChanged": False,
        "autoLayoutCreated": False,
        "permissionOnly": True,
    }


def count_values(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
