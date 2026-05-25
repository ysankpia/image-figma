from __future__ import annotations

from typing import Any

from .summary import float_value, int_value, summary_from, warning_count


NON_ACTIONABLE_SKIP_REASONS = {"diagnostic_only", "fallback_only", "preserve_in_parent_raster", "suppress_duplicate"}


def build_quality_summary(
    *,
    ownership_report: dict[str, Any] | None,
    hierarchy_report: dict[str, Any] | None,
    sibling_group_report: dict[str, Any] | None,
    layout_energy_report: dict[str, Any] | None,
    auto_layout_permission_report: dict[str, Any] | None,
    design_token_report: dict[str, Any] | None,
    materialization_report: dict[str, Any] | None,
) -> dict[str, Any]:
    ownership = summary_from(ownership_report)
    hierarchy = summary_from(hierarchy_report)
    sibling = summary_from(sibling_group_report)
    layout = summary_from(layout_energy_report)
    permission = summary_from(auto_layout_permission_report)
    tokens = summary_from(design_token_report)
    materialization = summary_from(materialization_report)

    risk = build_risk_summary(
        ownership=ownership,
        hierarchy=hierarchy,
        sibling=sibling,
        layout=layout,
        permission=permission,
        tokens=tokens,
        materialization=materialization,
        materialization_warning_count=warning_count(materialization_report),
        reports=[
            ownership_report,
            hierarchy_report,
            sibling_group_report,
            layout_energy_report,
            auto_layout_permission_report,
            design_token_report,
            materialization_report,
        ],
    )
    repair_cost = build_repair_cost(risk)
    score = quality_score(repair_cost)
    return {
        "qualitySummary": {
            "score": score,
            "grade": quality_grade(score),
            "visibleReplayClaimCount": int_value(ownership, "visibleReplayClaimCount"),
            "visibleNodeCount": int_value(materialization, "visibleNodeCount"),
            "hierarchyCandidateCount": int_value(hierarchy, "selectedParentCandidateCount"),
            "siblingGroupCandidateCount": int_value(sibling, "siblingGroupCandidateCount"),
            "layoutEnergyCandidateCount": int_value(layout, "layoutEnergyCandidateCount"),
            "autoLayoutAllowCandidateCount": int_value(permission, "allowCandidateCount"),
            "designTokenCandidateCount": design_token_count(tokens),
            "tokenCoverage": float_value(tokens, "tokenCoverage", 0.0),
        },
        "riskSummary": risk,
        "repairCost": repair_cost,
        "capabilityMaturity": capability_maturity(),
    }


def build_risk_summary(
    *,
    ownership: dict[str, Any],
    hierarchy: dict[str, Any],
    sibling: dict[str, Any],
    layout: dict[str, Any],
    permission: dict[str, Any],
    tokens: dict[str, Any],
    materialization: dict[str, Any],
    materialization_warning_count: int,
    reports: list[dict[str, Any] | None],
) -> dict[str, Any]:
    return {
        "ownershipErrorCount": int_value(ownership, "errorCount"),
        "ownershipConflictCount": int_value(ownership, "conflictCount"),
        "warningCount": sum(warning_count(report) for report in reports),
        "hierarchyLowSignalCount": max(0, int_value(hierarchy, "parentCandidateCount") - int_value(hierarchy, "selectedParentCandidateCount")),
        "deferredAutoLayoutCount": int_value(permission, "deferCount"),
        "rejectedAutoLayoutCount": int_value(permission, "rejectCount"),
        "tokenGapCount": 1 if design_token_count(tokens) == 0 else 0,
        "materializationWarningCount": materialization_warning_count,
        "materializationTotalSkippedCount": skipped_count(materialization),
        "materializationNonActionableSkippedCount": non_actionable_skipped_count(materialization),
        "materializationSkippedCount": actionable_skipped_count(materialization),
    }


def build_repair_cost(risk: dict[str, Any]) -> dict[str, Any]:
    items = [
        cost_item("ownership_errors", risk["ownershipErrorCount"], 8),
        cost_item("ownership_conflicts", risk["ownershipConflictCount"], 4),
        cost_item("materialization_warnings", risk["materializationWarningCount"], 3),
        cost_item("materialization_skips", risk["materializationSkippedCount"], 2),
        cost_item("deferred_auto_layout", risk["deferredAutoLayoutCount"], 1),
        cost_item("rejected_auto_layout", risk["rejectedAutoLayoutCount"], 2),
        cost_item("token_gaps", risk["tokenGapCount"], 1),
    ]
    total = sum(item["cost"] for item in items)
    return {
        "totalCost": total,
        "items": [item for item in items if item["count"] > 0],
    }


def cost_item(kind: str, count: int, weight: int) -> dict[str, Any]:
    return {"kind": kind, "count": count, "weight": weight, "cost": count * weight}


def quality_score(repair_cost: dict[str, Any]) -> float:
    total = float(repair_cost["totalCost"])
    return round(max(0.0, 1.0 - min(0.75, total / 400.0)), 3)


def quality_grade(score: float) -> str:
    if score >= 0.90:
        return "high"
    if score >= 0.72:
        return "medium"
    return "low"


def design_token_count(tokens: dict[str, Any]) -> int:
    return (
        int_value(tokens, "colorTokenCount")
        + int_value(tokens, "textStyleTokenCount")
        + int_value(tokens, "radiusTokenCount")
        + int_value(tokens, "spacingTokenCount")
    )


def actionable_skipped_count(materialization: dict[str, Any]) -> int:
    return skipped_count(materialization, exclude_reasons=NON_ACTIONABLE_SKIP_REASONS)


def non_actionable_skipped_count(materialization: dict[str, Any]) -> int:
    total = 0
    for reason in NON_ACTIONABLE_SKIP_REASONS:
        total += skipped_reason_count(materialization, reason)
    return total


def skipped_count(materialization: dict[str, Any], *, exclude_reasons: set[str] | None = None) -> int:
    skipped = materialization.get("skippedReasons")
    if not isinstance(skipped, dict):
        return 0
    total = 0
    for reason, value in skipped.items():
        if exclude_reasons and str(reason) in exclude_reasons:
            continue
        try:
            total += int(value)
        except (TypeError, ValueError):
            continue
    return total


def skipped_reason_count(materialization: dict[str, Any], reason: str) -> int:
    skipped = materialization.get("skippedReasons")
    if not isinstance(skipped, dict):
        return 0
    try:
        return int(skipped.get(reason) or 0)
    except (TypeError, ValueError):
        return 0


def capability_maturity() -> dict[str, str]:
    return {
        "ownershipConservation": "diagnostic-only",
        "hierarchyCandidates": "candidate-proposal",
        "siblingGroupCandidates": "candidate-proposal",
        "layoutEnergy": "candidate-proposal",
        "autoLayoutPermission": "permission-only",
        "designTokens": "candidate-proposal",
        "bStageQuality": "diagnostic-only",
    }
