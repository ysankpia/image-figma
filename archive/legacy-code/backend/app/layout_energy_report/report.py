from __future__ import annotations

from typing import Any


def build_summary(
    *,
    plan_items: list[dict[str, Any]],
    layout_subjects: list[dict[str, Any]],
    layout_candidates: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "planItemCount": len(plan_items),
        "visiblePlanItemCount": sum(1 for item in plan_items if item["visible"]),
        "layoutSubjectCount": len(layout_subjects),
        "layoutEnergyCandidateCount": len(layout_candidates),
        "warningCount": len(warnings),
        "bestModelCounts": count_values(candidate.get("bestModel") for candidate in layout_candidates),
        "confidenceCounts": count_values(candidate.get("confidence") for candidate in layout_candidates),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "materializationChanged": False,
        "autoLayoutPermission": False,
    }


def strip_internal_subject_fields(subjects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in subject.items() if not key.startswith("_")} for subject in subjects]


def count_values(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
