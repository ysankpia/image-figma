from __future__ import annotations

from typing import Any


def build_summary(*, source_objects: list[dict[str, Any]], candidates: list[dict[str, Any]], items: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    return {
        "sourceObjectCount": len(source_objects),
        "candidateCount": len(candidates),
        "allowedCount": sum(1 for item in items if item["decision"] == "allow"),
        "rejectedCount": sum(1 for item in items if item["decision"] == "reject"),
        "analysisAllowedCount": sum(1 for item in items if item.get("analysisAllowed") is True),
        "assetGeneratedCount": sum(1 for item in items if item.get("assetGenerated") is True),
        "visibleReplayEligibleCount": sum(1 for item in items if item.get("visibleReplayEligible") is True),
        "cleanupEligibleCount": sum(1 for item in items if item.get("cleanupEligible") is True),
        "assetCount": sum(1 for item in items if item.get("assetPath")),
        "warningCount": len(warnings),
        "sourceCounts": source_counts(items),
        "rejectionReasonCounts": rejection_reason_counts(items),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "materializationChanged": False,
        "materializerConsumesAssets": False,
        "blockingUpload": False,
    }


def source_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        source = str(item.get("source") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return dict(sorted(counts.items()))


def rejection_reason_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    non_rejection_reasons = {
        "m29_2_raster_icon_source_object",
        "m29_6_internal_icon_candidate",
        "m29_6_high_confidence_internal_icon_candidate",
    }
    counts: dict[str, int] = {}
    for item in items:
        if item.get("decision") != "reject":
            continue
        for reason in item.get("reasons", []):
            if reason in non_rejection_reasons:
                continue
            counts[str(reason)] = counts.get(str(reason), 0) + 1
    return dict(sorted(counts.items()))
