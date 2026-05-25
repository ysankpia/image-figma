from __future__ import annotations

from typing import Any

from ..m29_materialization_utils import list_dicts
from .types import PlanMaterializerOptions, ReplayNode


def build_summary(
    *,
    m29_document: dict[str, Any],
    ocr_count: int,
    replayed: list[ReplayNode],
    skipped: list[dict[str, Any]],
    fallback_erased_count: int,
    copied_image_asset_text_erased_count: int,
    copied_image_asset_internal_erased_count: int,
    options: PlanMaterializerOptions,
    structure_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    replay_counts: dict[str, int] = {}
    for item in replayed:
        replay_counts[item.kind] = replay_counts.get(item.kind, 0) + 1
    skipped_counts: dict[str, int] = {}
    for item in skipped:
        reason = str(item.get("reason") or "unknown")
        skipped_counts[reason] = skipped_counts.get(reason, 0) + 1
    structure_summary = structure_report.get("summary", {}) if isinstance(structure_report, dict) and isinstance(structure_report.get("summary"), dict) else {}
    return {
        "m29NodeCount": len(list_dicts(m29_document.get("nodes"))),
        "ocrTextCount": ocr_count,
        "replayedTextCount": replay_counts.get("text", 0),
        "replayedImageCount": replay_counts.get("image", 0),
        "replayedSymbolCount": replay_counts.get("symbol", 0),
        "replayedShapeCount": replay_counts.get("shape", 0),
        "skippedBlockedCount": skipped_counts.get("blocked_primitive", 0),
        "skippedDuplicateCount": skipped_counts.get("duplicate_bbox", 0),
        "fallbackErasedBBoxCount": fallback_erased_count,
        "copiedImageAssetTextErasedCount": copied_image_asset_text_erased_count,
        "copiedImageAssetInternalErasedCount": copied_image_asset_internal_erased_count,
        "visibleNodeCount": len(replayed),
        "controlledStructureGroupCount": int(structure_summary.get("acceptedGroupCount") or 0),
        "controlledStructureRejectedGroupCount": int(structure_summary.get("rejectedGroupCount") or 0),
        "controlledStructureMaterializationChanged": bool(structure_summary.get("materializationChanged")),
        "autoLayoutCreated": bool(structure_summary.get("autoLayoutCreated")),
        "maxTotalVisibleNodesExceeded": len(replayed) >= options.max_total_visible_nodes and any(item.get("reason") == "node_budget_exceeded" for item in skipped),
        "skippedReasons": skipped_counts,
    }
