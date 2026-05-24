from __future__ import annotations

from typing import Any

from .types import ReplayAction
from .utils import dedupe_preserve_order


def reasons_for(
    item: dict[str, Any],
    action: ReplayAction,
    duplicate_ids: list[str],
    cluster_ids: list[str],
    cleanup_targets: list[dict[str, Any]],
) -> list[str]:
    reasons = list(item["reasons"])
    reasons.append(f"m29_5_action_{action}")
    if duplicate_ids:
        reasons.append("near_equal_duplicate_suppression")
    if cluster_ids:
        reasons.append("m29_4_cluster_supported")
    if any(target.get("target") == "copied_image_asset" for target in cleanup_targets):
        reasons.append("editable_text_cleans_containing_media_asset")
    return dedupe_preserve_order(reasons)


def build_summary(plan_items: list[dict[str, Any]], skipped_items: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    action_counts: dict[str, int] = {}
    for item in plan_items:
        action = str(item.get("finalReplayAction") or "")
        action_counts[action] = action_counts.get(action, 0) + 1
    cleanup_targets = [target for item in plan_items for target in item.get("cleanupTargets", []) if isinstance(target, dict)]
    return {
        "planItemCount": len(plan_items),
        "plannedVisibleNodeCount": sum(action_counts.get(action, 0) for action in {"text_replay", "image_replay", "icon_replay", "shape_replay"}),
        "plannedTextReplayCount": action_counts.get("text_replay", 0),
        "plannedImageReplayCount": action_counts.get("image_replay", 0),
        "plannedIconReplayCount": action_counts.get("icon_replay", 0),
        "plannedShapeReplayCount": action_counts.get("shape_replay", 0),
        "suppressedDuplicateCount": action_counts.get("suppress_duplicate", 0),
        "fallbackCleanupTargetCount": sum(1 for target in cleanup_targets if target.get("target") == "fallback"),
        "copiedImageAssetCleanupTargetCount": sum(1 for target in cleanup_targets if target.get("target") == "copied_image_asset"),
        "clusterSupportedPlanItemCount": sum(1 for item in plan_items if item.get("clusterIds")),
        "nodeBudgetSuppressedCount": sum(1 for item in plan_items if "node_budget_suppressed" in item.get("reasons", [])),
        "visibleOverlapSuppressedCount": sum(1 for item in plan_items if "visible_overlap_duplicate_suppressed" in item.get("reasons", [])),
        "skippedInvalidSourceObjectCount": len(skipped_items),
        "warningCount": len(warnings),
        "finalReplayActionCounts": dict(sorted(action_counts.items())),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
    }
