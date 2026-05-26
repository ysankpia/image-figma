from __future__ import annotations

from typing import Any


def build_summary(traces: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    return {
        "traceCount": len(traces),
        "compiledCount": sum(1 for item in traces if item.get("compilerDecision") == "compiled_source_object"),
        "finalReplayCount": sum(1 for item in traces if item.get("finalReplayDecision") in {"text_replay", "image_replay", "icon_replay", "shape_replay"}),
        "materializedCount": sum(1 for item in traces if item.get("materializerDecision") == "replayed"),
        "cleanupAuthorizedCount": sum(1 for item in traces if item.get("cleanupDecision") == "copied_image_cleanup_authorized"),
        "blockedCount": sum(1 for item in traces if item.get("firstBlockingStage") not in {"none", ""}),
        "firstBlockingStageCounts": count_key(traces, "firstBlockingStage"),
        "firstBlockingReasonCounts": count_key(traces, "firstBlockingReason"),
        "compiledRoleCounts": count_key(traces, "compiledRole"),
        "warningCount": len(warnings),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "materializationChanged": False,
        "sourceOwnershipChanged": False,
    }


def count_key(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
