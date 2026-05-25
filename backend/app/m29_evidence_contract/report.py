from __future__ import annotations

from typing import Any


def build_summary(*, source_objects: list[dict[str, Any]], internal_candidates: list[dict[str, Any]], transparent_items: list[dict[str, Any]], contract_items: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    return {
        "sourceObjectCount": len(source_objects),
        "internalCandidateCount": len(internal_candidates),
        "transparentItemCount": len(transparent_items),
        "contractItemCount": len(contract_items),
        "allowVisibleReplayCount": sum(1 for item in contract_items if item.get("decision", {}).get("mode") == "allow_visible_replay"),
        "reportOnlyCount": sum(1 for item in contract_items if item.get("decision", {}).get("mode") == "report_only"),
        "rejectCount": sum(1 for item in contract_items if item.get("decision", {}).get("mode") == "reject"),
        "decisionCounts": decision_counts(contract_items),
        "sourceKindCounts": source_kind_counts(contract_items),
        "warningCount": len(warnings),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "materializationChanged": False,
        "sourceOwnershipChanged": False,
        "materializerConsumesContracts": False,
        "blockingUpload": False,
    }


def decision_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        mode = str(item.get("decision", {}).get("mode") or "unknown")
        counts[mode] = counts.get(mode, 0) + 1
    return dict(sorted(counts.items()))


def source_kind_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        kind = str(item.get("sourceKind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))
