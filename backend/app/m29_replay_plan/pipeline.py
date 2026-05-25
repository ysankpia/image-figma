from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .budget import apply_node_budget, suppressed_duplicate_items
from .cleanup import cleanup_targets_for, contained_media_edge_ids
from .decisions import near_equal_duplicate_ids, replay_action_for, target_role_for_action
from .lookups import build_cluster_lookup, build_edge_lookup
from .normalization import normalize_source_objects
from .overlap import suppress_visible_overlap_duplicates
from .report import build_summary, reasons_for
from .types import M295ReplayPlanOptions, M295ReplayPlanResult
from .utils import plan_sort_key
from .validation import validate_replay_plan


def build_m295_replay_plan(
    *,
    task_id: str,
    m292_document: dict[str, Any],
    m2931_report: dict[str, Any] | None,
    m294_report: dict[str, Any] | None,
    output_dir: Path,
    options: M295ReplayPlanOptions | None = None,
) -> M295ReplayPlanResult:
    options = options or M295ReplayPlanOptions()
    output_dir.mkdir(parents=True, exist_ok=True)

    source_objects, skipped_items = normalize_source_objects(m292_document.get("sourceObjects", []))
    edge_lookup = build_edge_lookup(m2931_report or {})
    cluster_lookup, malformed_cluster_count = build_cluster_lookup(m294_report or {})

    plan_items: list[dict[str, Any]] = []
    suppressed_source_ids: set[str] = set()
    warnings: list[str] = []
    if skipped_items:
        warnings.append(f"skipped_invalid_source_object:{len(skipped_items)}")
    if malformed_cluster_count:
        warnings.append(f"skipped_malformed_cluster:{malformed_cluster_count}")

    replay_candidates: list[dict[str, Any]] = []
    for item in source_objects:
        if item["id"] in suppressed_source_ids:
            continue
        duplicate_ids, duplicate_edges = near_equal_duplicate_ids(item, source_objects, edge_lookup, suppressed_source_ids)
        if duplicate_ids:
            suppressed_source_ids.update(duplicate_ids)
        if item["id"] in suppressed_source_ids:
            continue
        action = replay_action_for(item)
        target_role = target_role_for_action(action)
        cluster_ids = cluster_lookup.get(item["id"], [])
        relation_edge_ids = sorted(set(duplicate_edges + contained_media_edge_ids(item, source_objects, edge_lookup)))
        cleanup_targets = cleanup_targets_for(item, source_objects, edge_lookup) if action in {"text_replay", "image_replay", "icon_replay", "shape_replay"} else []
        plan_item = {
            "id": "",
            "sourceObjectId": item["id"],
            "bbox": item["bbox"],
            "finalReplayAction": action,
            "targetRole": target_role,
            "pixelOwner": item["pixelOwner"],
            "cleanupTargets": cleanup_targets,
            "suppressedSourceObjectIds": duplicate_ids,
            "relationEdgeIds": relation_edge_ids,
            "clusterIds": cluster_ids,
            "confidence": item["confidence"],
            "sourceEvidence": item.get("sourceEvidence", {}),
            "reasons": reasons_for(item, action, duplicate_ids, cluster_ids, cleanup_targets),
            "risks": list(item["risks"]),
        }
        if action in {"text_replay", "image_replay", "icon_replay", "shape_replay"}:
            replay_candidates.append(plan_item)
        else:
            plan_items.append(plan_item)

    replay_candidates, visible_overlap_suppressed = suppress_visible_overlap_duplicates(replay_candidates, edge_lookup)
    suppressed_visible_source_ids = {
        str(item.get("sourceObjectId") or "")
        for item in visible_overlap_suppressed
        if item.get("sourceObjectId")
    }
    replay_candidates = [
        prune_cleanup_targets_to_suppressed_visible_sources(item, suppressed_visible_source_ids)
        for item in replay_candidates
    ]
    accepted, node_budget_suppressed = apply_node_budget(replay_candidates, options.max_visible_nodes)
    plan_items.extend(accepted)
    plan_items.extend(visible_overlap_suppressed)
    plan_items.extend(node_budget_suppressed)
    plan_items.extend(suppressed_duplicate_items(source_objects, suppressed_source_ids, edge_lookup, cluster_lookup))
    plan_items = sorted(plan_items, key=plan_sort_key)
    for index, item in enumerate(plan_items, start=1):
        item["id"] = f"m295_plan_{index:04d}"

    report = {
        "schemaName": "M295ReplayPlan",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m292_document.get("schemaName"),
        "sourceSchemaVersion": m292_document.get("schemaVersion"),
        "outputReport": str(output_dir / "replay_plan.json"),
        "summary": build_summary(plan_items, skipped_items, warnings),
        "options": options.to_dict(),
        "planItems": plan_items,
        "skippedItems": skipped_items,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "truthSource": "m29_2_plus_m29_3_1_plus_m29_4",
            "roleHintsAreWeakStructuralEvidence": True,
        },
    }
    validate_replay_plan(report)
    (output_dir / "replay_plan.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M295ReplayPlanResult(report=report, output_dir=output_dir)


def prune_cleanup_targets_to_suppressed_visible_sources(item: dict[str, Any], suppressed_source_ids: set[str]) -> dict[str, Any]:
    if not suppressed_source_ids:
        return item
    cleanup_targets = item.get("cleanupTargets")
    if not isinstance(cleanup_targets, list):
        return item
    kept_targets = [
        target
        for target in cleanup_targets
        if not (isinstance(target, dict) and str(target.get("targetSourceObjectId") or "") in suppressed_source_ids)
    ]
    if len(kept_targets) == len(cleanup_targets):
        return item
    pruned = dict(item)
    pruned["cleanupTargets"] = kept_targets
    pruned["reasons"] = [
        reason
        for reason in pruned.get("reasons", [])
        if reason not in {"editable_text_cleans_containing_media_asset", "promoted_internal_asset_cleans_parent_media_asset", "shape_background_cleans_containing_media_asset"}
    ]
    pruned["risks"] = [
        *pruned.get("risks", []),
        "copied_image_cleanup_target_suppressed",
    ]
    return pruned
