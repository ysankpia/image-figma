from __future__ import annotations

from typing import Any


def build_summary(
    *,
    source_objects: list[dict[str, Any]],
    raw_nodes: list[dict[str, Any]],
    ocr_blocks: list[dict[str, Any]],
    plan_items: list[dict[str, Any]],
    composite_media_items: list[dict[str, Any]],
    text_masks: list[dict[str, Any]],
    internal_candidates: list[dict[str, Any]],
    matched_internal_groups: list[dict[str, Any]],
    rejected_fragments: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "sourceObjectCount": len(source_objects),
        "rawNodeCount": len(raw_nodes),
        "ocrBlockCount": len(ocr_blocks),
        "planItemCount": len(plan_items),
        "compositeMediaCount": len(composite_media_items),
        "textMaskCount": len(text_masks),
        "internalCandidateCount": len(internal_candidates),
        "acceptedInternalCandidateCount": sum(1 for item in internal_candidates if item["candidateDecision"] == "accepted_report_candidate"),
        "rejectedFragmentCount": len(rejected_fragments),
        "matchedInternalGroupCount": len(matched_internal_groups),
        "warningCount": len(warnings),
        "confidenceCounts": confidence_counts(internal_candidates + matched_internal_groups),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "materializationChanged": False,
        "blockingUpload": False,
    }


def confidence_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        confidence = str(item.get("confidence") or "unknown")
        counts[confidence] = counts.get(confidence, 0) + 1
    return dict(sorted(counts.items()))
