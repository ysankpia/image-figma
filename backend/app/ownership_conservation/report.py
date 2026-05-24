from __future__ import annotations

from typing import Any


def build_summary(
    *,
    source_objects: list[dict[str, Any]],
    visible_claims: list[dict[str, Any]],
    cleanup_claims: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    conflict_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    cleanup_counts: dict[str, int] = {}
    visible_counts: dict[str, int] = {}
    for conflict in conflicts:
        conflict_type = str(conflict.get("type") or "unknown")
        severity = str(conflict.get("severity") or "unknown")
        conflict_counts[conflict_type] = conflict_counts.get(conflict_type, 0) + 1
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    for claim in cleanup_claims:
        cleanup_target = str(claim.get("cleanupTarget") or "unknown")
        cleanup_counts[cleanup_target] = cleanup_counts.get(cleanup_target, 0) + 1
    for claim in visible_claims:
        action = str(claim.get("finalReplayAction") or "unknown")
        visible_counts[action] = visible_counts.get(action, 0) + 1
    return {
        "sourceObjectCount": len(source_objects),
        "visibleReplayClaimCount": len(visible_claims),
        "cleanupClaimCount": len(cleanup_claims),
        "conflictCount": len(conflicts),
        "errorCount": severity_counts.get("error", 0),
        "warningConflictCount": severity_counts.get("warning", 0),
        "warningCount": len(warnings),
        "visibleReplayActionCounts": dict(sorted(visible_counts.items())),
        "cleanupTargetCounts": dict(sorted(cleanup_counts.items())),
        "conflictTypeCounts": dict(sorted(conflict_counts.items())),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
    }

