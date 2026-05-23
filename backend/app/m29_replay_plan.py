from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .region_relation_kernel import normalize_bbox


ReplayAction = Literal[
    "text_replay",
    "image_replay",
    "icon_replay",
    "shape_replay",
    "preserve_in_parent_raster",
    "suppress_duplicate",
    "fallback_only",
    "diagnostic_only",
]
TargetRole = Literal["m29_direct_text", "m29_direct_image", "m29_direct_symbol", "m29_direct_shape"]


@dataclass(frozen=True)
class M295ReplayPlanOptions:
    max_visible_nodes: int = 260

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M295ReplayPlanResult:
    report: dict[str, Any]
    output_dir: Path


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
        cleanup_targets = cleanup_targets_for(item, source_objects, edge_lookup) if action == "text_replay" else []
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
            "reasons": reasons_for(item, action, duplicate_ids, cluster_ids, cleanup_targets),
            "risks": list(item["risks"]),
        }
        if action in {"text_replay", "image_replay", "icon_replay", "shape_replay"}:
            replay_candidates.append(plan_item)
        else:
            plan_items.append(plan_item)

    accepted, node_budget_suppressed = apply_node_budget(replay_candidates, options.max_visible_nodes)
    plan_items.extend(accepted)
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


def normalize_source_objects(raw_objects: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    objects: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_objects if isinstance(raw_objects, list) else []):
        if not isinstance(item, dict):
            skipped.append({"index": index, "reason": "invalid_source_object"})
            continue
        source_id = str(item.get("id") or "").strip()
        if not source_id:
            skipped.append({"index": index, "reason": "missing_source_object_id"})
            continue
        if source_id in seen:
            skipped.append({"sourceObjectId": source_id, "index": index, "reason": "duplicate_source_object_id"})
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"sourceObjects[{index}].bbox")
        except ValueError as error:
            skipped.append({"sourceObjectId": source_id, "index": index, "reason": "invalid_bbox", "message": str(error)})
            continue
        seen.add(source_id)
        objects.append(
            {
                "id": source_id,
                "bbox": bbox,
                "visualKind": str(item.get("visualKind") or ""),
                "pixelOwner": str(item.get("pixelOwner") or ""),
                "replayDecision": str(item.get("replayDecision") or ""),
                "confidence": str(item.get("confidence") or "low"),
                "reasons": [str(reason) for reason in item.get("reasons", []) if isinstance(reason, str)],
                "risks": [str(risk) for risk in item.get("risks", []) if isinstance(risk, str)],
            }
        )
    return sorted(objects, key=lambda item: item["id"]), skipped


def build_edge_lookup(report: dict[str, Any]) -> dict[frozenset[str], dict[str, Any]]:
    lookup: dict[frozenset[str], dict[str, Any]] = {}
    for edge in report.get("edges", []) if isinstance(report.get("edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        left = str(edge.get("leftObjectId") or "")
        right = str(edge.get("rightObjectId") or "")
        if not left or not right or left == right:
            continue
        lookup[frozenset({left, right})] = edge
    return lookup


def build_cluster_lookup(report: dict[str, Any]) -> tuple[dict[str, list[str]], int]:
    lookup: dict[str, list[str]] = {}
    malformed = 0
    for cluster in report.get("clusters", []) if isinstance(report.get("clusters"), list) else []:
        if not isinstance(cluster, dict):
            malformed += 1
            continue
        cluster_id = str(cluster.get("id") or "")
        member_ids = cluster.get("memberNodeIds")
        if not cluster_id or not isinstance(member_ids, list):
            malformed += 1
            continue
        for member_id in member_ids:
            if isinstance(member_id, str) and member_id:
                lookup.setdefault(member_id, []).append(cluster_id)
    return {key: sorted(values) for key, values in lookup.items()}, malformed


def replay_action_for(item: dict[str, Any]) -> ReplayAction:
    decision = item["replayDecision"]
    owner = item["pixelOwner"]
    confidence = item["confidence"]
    if decision == "text_replay" and owner == "editable_text" and confidence != "low":
        return "text_replay"
    if decision == "image_replay" and owner == "preserve_raster" and confidence != "low":
        return "image_replay"
    if decision == "icon_replay" and owner == "raster_icon" and confidence != "low":
        return "icon_replay"
    if decision == "shape_replay" and owner == "shape_geometry" and confidence != "low":
        return "shape_replay"
    if decision == "preserve_in_parent_raster":
        return "preserve_in_parent_raster"
    if owner == "fallback_only":
        return "fallback_only"
    return "diagnostic_only"


def target_role_for_action(action: ReplayAction) -> TargetRole | None:
    return {
        "text_replay": "m29_direct_text",
        "image_replay": "m29_direct_image",
        "icon_replay": "m29_direct_symbol",
        "shape_replay": "m29_direct_shape",
    }.get(action)


def near_equal_duplicate_ids(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
    already_suppressed: set[str],
) -> tuple[list[str], list[str]]:
    suppressed: list[str] = []
    edge_ids: list[str] = []
    item_priority = replay_priority(item)
    for other in source_objects:
        if other["id"] <= item["id"] or other["id"] in already_suppressed:
            continue
        edge = edge_lookup.get(frozenset({item["id"], other["id"]}))
        if not edge or edge.get("primarySetRelation") != "near_equal":
            continue
        other_priority = replay_priority(other)
        if item_priority >= other_priority:
            suppressed.append(other["id"])
        else:
            suppressed.append(item["id"])
        edge_id = str(edge.get("edgeId") or "")
        if edge_id:
            edge_ids.append(edge_id)
    return sorted(set(suppressed)), sorted(set(edge_ids))


def replay_priority(item: dict[str, Any]) -> tuple[int, int]:
    owner_rank = {
        "editable_text": 50,
        "preserve_raster": 40,
        "raster_icon": 35,
        "shape_geometry": 30,
        "fallback_only": 10,
        "diagnostic_only": 0,
    }.get(item["pixelOwner"], 0)
    confidence_rank = {"high": 3, "medium": 2, "low": 1}.get(item["confidence"], 0)
    return owner_rank, confidence_rank


def cleanup_targets_for(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    targets = [{"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"}]
    for other in source_objects:
        if other["id"] == item["id"]:
            continue
        edge = edge_lookup.get(frozenset({item["id"], other["id"]}))
        if not edge:
            continue
        if other["replayDecision"] != "image_replay" or other["pixelOwner"] != "preserve_raster":
            continue
        if text_is_contained_by_media(item["id"], other["id"], edge):
            targets.append(
                {
                    "target": "copied_image_asset",
                    "targetSourceObjectId": other["id"],
                    "reason": "editable_text_contained_by_media",
                }
            )
    return targets


def contained_media_edge_ids(
    item: dict[str, Any],
    source_objects: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> list[str]:
    edge_ids: list[str] = []
    if item["replayDecision"] != "text_replay":
        return edge_ids
    for other in source_objects:
        edge = edge_lookup.get(frozenset({item["id"], other["id"]}))
        if not edge:
            continue
        if other["replayDecision"] == "image_replay" and text_is_contained_by_media(item["id"], other["id"], edge):
            edge_id = str(edge.get("edgeId") or "")
            if edge_id:
                edge_ids.append(edge_id)
    return edge_ids


def text_is_contained_by_media(text_id: str, media_id: str, edge: dict[str, Any]) -> bool:
    primary = edge.get("primarySetRelation")
    left = str(edge.get("leftObjectId") or "")
    right = str(edge.get("rightObjectId") or "")
    if primary == "near_equal":
        return True
    if left == text_id and right == media_id:
        return primary == "contained_by"
    if left == media_id and right == text_id:
        return primary == "contains"
    return False


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


def apply_node_budget(plan_items: list[dict[str, Any]], max_visible_nodes: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(plan_items, key=visible_plan_sort_key)
    accepted = ordered[:max_visible_nodes]
    suppressed: list[dict[str, Any]] = []
    for item in ordered[max_visible_nodes:]:
        suppressed_item = dict(item)
        suppressed_item["finalReplayAction"] = "suppress_duplicate"
        suppressed_item["targetRole"] = None
        suppressed_item["cleanupTargets"] = []
        suppressed_item["reasons"] = dedupe_preserve_order([*suppressed_item["reasons"], "node_budget_suppressed"])
        suppressed_item["risks"] = dedupe_preserve_order([*suppressed_item["risks"], "node_budget_exceeded"])
        suppressed.append(suppressed_item)
    return accepted, suppressed


def visible_plan_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    action_rank = {"shape_replay": 0, "image_replay": 1, "icon_replay": 2, "text_replay": 3}.get(item["finalReplayAction"], 9)
    confidence_rank = {"high": 0, "medium": 1, "low": 2}.get(item["confidence"], 2)
    return action_rank, confidence_rank, item["sourceObjectId"]


def suppressed_duplicate_items(
    source_objects: list[dict[str, Any]],
    suppressed_source_ids: set[str],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
    cluster_lookup: dict[str, list[str]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    by_id = {item["id"]: item for item in source_objects}
    for source_id in sorted(suppressed_source_ids):
        item = by_id.get(source_id)
        if item is None:
            continue
        relation_edges = [
            str(edge.get("edgeId") or "")
            for key, edge in edge_lookup.items()
            if source_id in key and edge.get("primarySetRelation") == "near_equal"
        ]
        items.append(
            {
                "id": "",
                "sourceObjectId": source_id,
                "bbox": item["bbox"],
                "finalReplayAction": "suppress_duplicate",
                "targetRole": None,
                "pixelOwner": item["pixelOwner"],
                "cleanupTargets": [],
                "suppressedSourceObjectIds": [],
                "relationEdgeIds": sorted(edge_id for edge_id in relation_edges if edge_id),
                "clusterIds": cluster_lookup.get(source_id, []),
                "confidence": item["confidence"],
                "reasons": dedupe_preserve_order([*item["reasons"], "near_equal_duplicate_suppressed"]),
                "risks": item["risks"],
            }
        )
    return items


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
        "skippedInvalidSourceObjectCount": len(skipped_items),
        "warningCount": len(warnings),
        "finalReplayActionCounts": dict(sorted(action_counts.items())),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
    }


def validate_replay_plan(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M295ReplayPlan":
        raise ValueError("invalid M29.5 schemaName")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("M29.5 summary must be an object")
    if summary.get("dslChanged") is not False:
        raise ValueError("M29.5 must not change DSL")
    if summary.get("assetChanged") is not False:
        raise ValueError("M29.5 must not change assets")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("M29.5 must not create visible nodes")


def plan_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    action_order = {
        "shape_replay": 0,
        "image_replay": 1,
        "icon_replay": 2,
        "text_replay": 3,
        "preserve_in_parent_raster": 4,
        "fallback_only": 5,
        "diagnostic_only": 6,
        "suppress_duplicate": 7,
    }
    return action_order.get(str(item.get("finalReplayAction")), 99), str(item.get("sourceObjectId") or "")


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
