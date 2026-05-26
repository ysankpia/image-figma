from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..region_relation_kernel import bbox_area, center_x, center_y, intersection_area, normalize_bbox
from ..transparent_asset_report.gates import visible_replay_block_reason, visible_replay_eligible
from .types import M29InternalSourcePromotionResult, REPORT_META


PROMOTABLE_SHAPE_ROLES = {
    "selected_marker_candidate",
    "status_dot_candidate",
    "table_marker_candidate",
    "internal_shape_candidate",
    "internal_control_background",
}
PROMOTION_DUPLICATE_IOU_THRESHOLD = 0.72
PROMOTION_DUPLICATE_CONTAINMENT_THRESHOLD = 0.82
PROMOTION_DUPLICATE_CENTER_SHIFT_RATIO = 0.25
PROMOTION_DUPLICATE_SIZE_DRIFT_RATIO = 0.25


def extract_m29_internal_source_promotion_report(
    *,
    task_id: str,
    m292_document: dict[str, Any],
    media_internal_report: dict[str, Any],
    transparent_asset_report: dict[str, Any],
    evidence_contract_report: dict[str, Any],
    output_dir: Path,
) -> M29InternalSourcePromotionResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    base_objects = [deepcopy(item) for item in m292_document.get("sourceObjects", []) if isinstance(item, dict)]
    promoted_objects, rejected_candidates = build_promoted_objects(
        base_objects=base_objects,
        media_internal_report=media_internal_report,
        transparent_asset_report=transparent_asset_report,
        evidence_contract_report=evidence_contract_report,
    )
    promoted_document = build_promoted_m292_document(m292_document, base_objects + promoted_objects, len(promoted_objects))
    document_path = output_dir / "source_ui_physical_graph.promoted.json"
    report_path = output_dir / "internal_source_promotion_report.json"
    report = {
        "schemaName": "M29InternalSourcePromotionReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m292_document.get("schemaName"),
        "sourceSchemaVersion": m292_document.get("schemaVersion"),
        "mediaInternalSchemaName": media_internal_report.get("schemaName"),
        "mediaInternalSchemaVersion": media_internal_report.get("schemaVersion"),
        "transparentAssetSchemaName": transparent_asset_report.get("schemaName"),
        "transparentAssetSchemaVersion": transparent_asset_report.get("schemaVersion"),
        "evidenceContractSchemaName": evidence_contract_report.get("schemaName"),
        "evidenceContractSchemaVersion": evidence_contract_report.get("schemaVersion"),
        "outputReport": str(report_path),
        "outputPromotedM292": str(document_path),
        "summary": {
            "baseSourceObjectCount": len(base_objects),
            "promotedSourceObjectCount": len(promoted_objects),
            "finalSourceObjectCount": len(base_objects) + len(promoted_objects),
            "rejectedCandidateCount": len(rejected_candidates),
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "materializationChanged": False,
            "sourceOwnershipChanged": bool(promoted_objects),
        },
        "promotedSourceObjects": promoted_objects,
        "rejectedCandidates": rejected_candidates,
        "warnings": [],
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_2_plus_m29_6_plus_transparent_asset_plus_evidence_contract",
            **REPORT_META,
            "sourceOwnershipChanged": bool(promoted_objects),
        },
    }
    validate_report(report)
    document_path.write_text(json.dumps(promoted_document, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29InternalSourcePromotionResult(report=report, m292_document=promoted_document, output_dir=output_dir)


def build_promoted_objects(
    *,
    base_objects: list[dict[str, Any]],
    media_internal_report: dict[str, Any],
    transparent_asset_report: dict[str, Any],
    evidence_contract_report: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_ids = {str(item.get("id") or "") for item in base_objects}
    candidates = {
        str(item.get("candidateId") or ""): item
        for item in media_internal_report.get("internalCandidates", [])
        if isinstance(item, dict)
        and (item.get("role") == "internal_icon_candidate" or item.get("role") in PROMOTABLE_SHAPE_ROLES)
    }
    transparent_items = {
        str(item.get("sourceObjectId") or ""): item
        for item in transparent_asset_report.get("items", [])
        if isinstance(item, dict)
        and item.get("source") == "m29_6_internal_icon_candidate"
        and item.get("sourceObjectId")
    }
    contracts = {
        str(item.get("candidateId") or ""): item
        for item in evidence_contract_report.get("contractItems", [])
        if isinstance(item, dict)
        and item.get("sourceKind") in {"m29_6_internal_icon_candidate", "m29_6_internal_shape_candidate"}
        and item.get("candidateId")
    }
    promotion_candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate_id, candidate in candidates.items():
        item = transparent_items.get(candidate_id)
        contract = contracts.get(candidate_id)
        candidate = candidates.get(candidate_id)
        reason = reject_reason(candidate, item, contract, base_ids)
        if reason:
            rejected.append({"candidateId": candidate_id, "reason": reason, "bbox": candidate.get("bbox") if candidate else (item or {}).get("bbox")})
            continue
        promotion_candidates.append(promoted_object(candidate, item, contract, len(promotion_candidates) + 1))
    promoted, duplicate_rejections = dedupe_promoted_objects(promotion_candidates)
    rejected.extend(duplicate_rejections)
    return promoted, rejected


def dedupe_promoted_objects(promoted: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in sorted(promoted, key=promotion_rank, reverse=True):
        match = spatial_promotion_match(item, kept)
        if match is None:
            kept.append(item)
            continue
        current, metrics = match
        if promotion_role(item) == promotion_role(current):
            remember_merged_candidate(current, item)
            rejected.append(rejected_duplicate(item, current, metrics))
        else:
            rejected.append(rejected_role_conflict(item, current, metrics))
    next_index = {"raster_icon": 1, "shape_geometry": 1}
    for item in kept:
        owner = str(item.get("pixelOwner") or "")
        if owner == "shape_geometry":
            item["id"] = f"m292_promoted_internal_shape_{next_index[owner]:04d}"
            next_index[owner] += 1
        else:
            item["id"] = f"m292_promoted_internal_icon_{next_index['raster_icon']:04d}"
            next_index["raster_icon"] += 1
    return kept, rejected


def spatial_promotion_match(item: dict[str, Any], kept: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    matches: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for current in kept:
        metrics = spatial_overlap_metrics(item, current)
        if metrics is None or not metrics["promotionDuplicateGeometry"]:
            continue
        matches.append((float(metrics["spatialOverlapScore"]), current, metrics))
    if not matches:
        return None
    _, current, metrics = max(matches, key=lambda match: match[0])
    return current, metrics


def spatial_overlap_metrics(left_item: dict[str, Any], right_item: dict[str, Any]) -> dict[str, Any] | None:
    left = normalize_bbox(left_item.get("bbox"), "left_promoted.bbox")
    right = normalize_bbox(right_item.get("bbox"), "right_promoted.bbox")
    intersection = intersection_area(left, right)
    if intersection <= 0:
        return None
    left_area = bbox_area(left)
    right_area = bbox_area(right)
    union = max(1, left_area + right_area - intersection)
    iou = intersection / union
    left_containment = intersection / max(1, left_area)
    right_containment = intersection / max(1, right_area)
    min_width = max(1, min(left[2], right[2]))
    min_height = max(1, min(left[3], right[3]))
    center_shift_ratio = max(abs(center_x(left) - center_x(right)) / min_width, abs(center_y(left) - center_y(right)) / min_height)
    size_drift_ratio = max(abs(left[2] - right[2]) / max(1, max(left[2], right[2])), abs(left[3] - right[3]) / max(1, max(left[3], right[3])))
    duplicate_geometry = (
        iou >= PROMOTION_DUPLICATE_IOU_THRESHOLD
        or max(left_containment, right_containment) >= PROMOTION_DUPLICATE_CONTAINMENT_THRESHOLD
        or (
            center_shift_ratio <= PROMOTION_DUPLICATE_CENTER_SHIFT_RATIO
            and size_drift_ratio <= PROMOTION_DUPLICATE_SIZE_DRIFT_RATIO
            and min(left_containment, right_containment) >= 0.50
        )
    )
    return {
        "intersectionArea": intersection,
        "iou": round(iou, 6),
        "leftContainment": round(left_containment, 6),
        "rightContainment": round(right_containment, 6),
        "centerShiftRatio": round(center_shift_ratio, 6),
        "sizeDriftRatio": round(size_drift_ratio, 6),
        "spatialOverlapScore": round(max(iou, left_containment, right_containment), 6),
        "promotionDuplicateGeometry": duplicate_geometry,
    }


def promotion_role(item: dict[str, Any]) -> str:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    internal_role = str(evidence.get("internalRole") or "")
    if internal_role:
        return internal_role
    source = str(evidence.get("promotionSource") or "")
    if source:
        return source
    return str(item.get("pixelOwner") or "")


def promotion_rank(item: dict[str, Any]) -> tuple[float, int, str]:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    try:
        score = float(evidence.get("evidenceScore") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    candidate_id = str(evidence.get("mediaInternalCandidateId") or "")
    media_id = str(evidence.get("mediaSourceObjectId") or "")
    return (score, len(candidate_id), media_id)


def remember_merged_candidate(kept: dict[str, Any], duplicate: dict[str, Any]) -> None:
    kept_evidence = kept.get("sourceEvidence") if isinstance(kept.get("sourceEvidence"), dict) else {}
    duplicate_evidence = duplicate.get("sourceEvidence") if isinstance(duplicate.get("sourceEvidence"), dict) else {}
    duplicate_id = duplicate_evidence.get("mediaInternalCandidateId")
    if not duplicate_id:
        return
    merged = list(kept_evidence.get("mergedMediaInternalCandidateIds") or [])
    if duplicate_id not in merged:
        merged.append(duplicate_id)
    kept_evidence["mergedMediaInternalCandidateIds"] = merged


def rejected_duplicate(item: dict[str, Any], kept: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    kept_evidence = kept.get("sourceEvidence") if isinstance(kept.get("sourceEvidence"), dict) else {}
    item_bbox = normalize_bbox(item.get("bbox"), "duplicate.bbox")
    kept_bbox = normalize_bbox(kept.get("bbox"), "kept.bbox")
    return {
        "candidateId": evidence.get("mediaInternalCandidateId"),
        "reason": "duplicate_promoted_internal_bbox" if item_bbox == kept_bbox else "duplicate_promoted_internal_spatial_overlap",
        "bbox": item.get("bbox"),
        "keptCandidateId": kept_evidence.get("mediaInternalCandidateId"),
        "keptRole": promotion_role(kept),
        "keptBy": "highest_evidence_role_compatible_spatial_merge",
        "overlapMetrics": metrics,
    }


def rejected_role_conflict(item: dict[str, Any], kept: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    kept_evidence = kept.get("sourceEvidence") if isinstance(kept.get("sourceEvidence"), dict) else {}
    return {
        "candidateId": evidence.get("mediaInternalCandidateId"),
        "reason": "conflicting_promoted_internal_role_overlap",
        "bbox": item.get("bbox"),
        "role": promotion_role(item),
        "keptCandidateId": kept_evidence.get("mediaInternalCandidateId"),
        "keptRole": promotion_role(kept),
        "keptBy": "highest_evidence_role_conflict",
        "overlapMetrics": metrics,
    }


def reject_reason(candidate: dict[str, Any] | None, transparent_item: dict[str, Any] | None, evidence_contract: dict[str, Any] | None, base_ids: set[str]) -> str:
    if candidate is None:
        return "missing_media_internal_candidate"
    role = str(candidate.get("role") or "")
    if role != "internal_icon_candidate" and role not in PROMOTABLE_SHAPE_ROLES:
        return "not_promotable_internal_candidate"
    if candidate.get("candidateDecision") != "accepted_report_candidate":
        return "internal_candidate_not_accepted"
    media_id = str(candidate.get("mediaSourceObjectId") or "")
    if not media_id or media_id not in base_ids:
        return "missing_parent_media_source_object"
    try:
        normalize_bbox(candidate.get("bbox"), "candidate.bbox")
    except ValueError:
        return "invalid_candidate_bbox"
    if role == "internal_icon_candidate":
        if transparent_item is None:
            return "missing_transparent_asset_item"
        if not visible_replay_eligible(transparent_item):
            return visible_replay_block_reason(transparent_item)
    if evidence_contract is None:
        return "missing_evidence_contract"
    decision = evidence_contract.get("decision") if isinstance(evidence_contract.get("decision"), dict) else {}
    if decision.get("mode") != "allow_visible_replay":
        return "evidence_contract_not_allowing_visible_replay"
    return ""


def promoted_object(candidate: dict[str, Any], transparent_item: dict[str, Any], evidence_contract: dict[str, Any], index: int) -> dict[str, Any]:
    if str(candidate.get("role") or "") in PROMOTABLE_SHAPE_ROLES:
        return promoted_shape_object(candidate, evidence_contract, index)
    candidate_id = str(candidate["candidateId"])
    media_id = str(candidate["mediaSourceObjectId"])
    raw_node_id = str(candidate.get("rawNodeId") or "")
    candidate_bbox = normalize_bbox(candidate["bbox"], "candidate.bbox")
    bbox = normalize_bbox(transparent_item.get("analysisBbox") or candidate_bbox, "transparent_item.analysisBbox")
    decision = evidence_contract.get("decision") if isinstance(evidence_contract.get("decision"), dict) else {}
    return {
        "id": f"m292_promoted_internal_icon_{index:04d}",
        "bbox": bbox,
        "visualKind": "raster_icon",
        "pixelOwner": "raster_icon",
        "replayDecision": "icon_replay",
        "sourceEvidence": {
            "m29NodeIds": [raw_node_id] if raw_node_id else [],
            "ocrBoxIds": [],
            "blockedIds": [],
            "mediaSourceObjectId": media_id,
            "candidateBbox": candidate_bbox,
            "mediaInternalCandidateId": candidate_id,
            "transparentAssetPath": transparent_item.get("assetPath"),
            "transparentAssetBbox": bbox,
            "transparentAssetCandidateId": transparent_item.get("candidateId"),
            "transparentAssetAlphaCoverage": transparent_item.get("alphaCoverage"),
            "transparentAssetForegroundAreaRatio": transparent_item.get("foregroundAreaRatio"),
            "transparentAssetEdgeAlphaCoverageGt32": transparent_item.get("edgeAlphaCoverageGt32"),
            "transparentAssetEdgeAlphaMean": transparent_item.get("edgeAlphaMean"),
            "transparentAssetLargestComponentRatio": transparent_item.get("largestComponentRatio"),
            "evidenceContractId": evidence_contract.get("contractId"),
            "evidenceContractDecision": decision.get("mode"),
            "evidenceScore": decision.get("evidenceScore"),
            "promotionSource": "m29_6_internal_icon_candidate",
            "localBackgroundConfidence": 0.0,
            "textOverlapRatio": round(float(transparent_item.get("textOverlap") or 0.0), 4),
            "mediaContainmentRatio": 1.0,
        },
        "confidence": "high" if candidate.get("confidence") == "high" else "medium",
        "reasons": [
            "m29_6_high_confidence_internal_icon_candidate"
            if candidate.get("confidence") == "high"
            else "m29_6_group_supported_internal_icon_candidate",
            "transparent_asset_allow",
            "evidence_contract_allow_visible_replay",
            "internal_source_promotion",
        ],
        "risks": ["promoted_internal_media_foreground"],
    }


def promoted_shape_object(candidate: dict[str, Any], evidence_contract: dict[str, Any], index: int) -> dict[str, Any]:
    candidate_id = str(candidate["candidateId"])
    media_id = str(candidate["mediaSourceObjectId"])
    raw_node_id = str(candidate.get("rawNodeId") or "")
    role = str(candidate.get("role") or "")
    bbox = normalize_bbox(candidate["bbox"], "candidate.bbox")
    decision = evidence_contract.get("decision") if isinstance(evidence_contract.get("decision"), dict) else {}
    extra_shape_evidence = shape_style_evidence(candidate, role, bbox)
    return {
        "id": f"m292_promoted_internal_shape_{index:04d}",
        "bbox": bbox,
        "visualKind": visual_kind_for_shape_role(role),
        "pixelOwner": "shape_geometry",
        "replayDecision": "shape_replay",
        "sourceEvidence": {
            "m29NodeIds": [raw_node_id] if raw_node_id else [],
            "ocrBoxIds": [str(candidate.get("matchedOcrBoxId"))] if candidate.get("matchedOcrBoxId") else [],
            "blockedIds": [],
            "mediaSourceObjectId": media_id,
            "candidateBbox": bbox,
            "mediaInternalCandidateId": candidate_id,
            "evidenceContractId": evidence_contract.get("contractId"),
            "evidenceContractDecision": decision.get("mode"),
            "evidenceScore": decision.get("evidenceScore"),
            "promotionSource": "m29_6_internal_shape_candidate",
            "internalRole": role,
            "localBackgroundConfidence": 0.0,
            "textOverlapRatio": round(float_score(candidate, "textMaskOverlap"), 4),
            "mediaContainmentRatio": 1.0,
            **extra_shape_evidence,
        },
        "confidence": "high" if candidate.get("confidence") == "high" else "medium",
        "reasons": [
            "m29_6_internal_shape_candidate",
            f"{role}_shape_role",
            "evidence_contract_allow_visible_replay",
            "internal_source_promotion",
        ],
        "risks": ["promoted_internal_media_shape"],
    }


def visual_kind_for_shape_role(role: str) -> str:
    if role == "selected_marker_candidate":
        return "separator"
    return "control_background"


def shape_style_evidence(candidate: dict[str, Any], role: str, bbox: list[int]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    if role in {"status_dot_candidate", "table_marker_candidate"}:
        evidence["shapeRadiusOverride"] = max(1, min(bbox[2], bbox[3]) // 2)
    metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
    mean_rgb = metrics.get("meanRgb")
    if isinstance(mean_rgb, list) and len(mean_rgb) == 3:
        try:
            evidence["shapeFillOverride"] = rgb_to_hex([int(value) for value in mean_rgb])
        except (TypeError, ValueError):
            pass
    return evidence


def rgb_to_hex(rgb: list[int]) -> str:
    return "#" + "".join(f"{max(0, min(255, value)):02X}" for value in rgb[:3])


def float_score(candidate: dict[str, Any], key: str) -> float:
    breakdown = candidate.get("scoreBreakdown") if isinstance(candidate.get("scoreBreakdown"), dict) else {}
    try:
        return float(breakdown.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def build_promoted_m292_document(source: dict[str, Any], source_objects: list[dict[str, Any]], promoted_count: int) -> dict[str, Any]:
    document = deepcopy(source)
    document["sourceObjects"] = source_objects
    summary = dict(document.get("summary") if isinstance(document.get("summary"), dict) else {})
    summary["sourceObjectCount"] = len(source_objects)
    summary["rasterIconCount"] = sum(1 for item in source_objects if item.get("visualKind") == "raster_icon")
    summary["shapeGeometryCount"] = sum(1 for item in source_objects if item.get("pixelOwner") == "shape_geometry")
    summary["promotedInternalSourceObjectCount"] = promoted_count
    summary["dslChanged"] = False
    summary["assetChanged"] = False
    document["summary"] = summary
    document.setdefault("warnings", [])
    document["meta"] = {
        **(document.get("meta") if isinstance(document.get("meta"), dict) else {}),
        "truthSource": "source_png_plus_ocr_plus_m29_primitives_plus_m29_6_promotion",
        "sourceOwnershipChanged": promoted_count > 0,
        "dslChanged": False,
        "assetChanged": False,
    }
    return document


def validate_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M29InternalSourcePromotionReport":
        raise ValueError("invalid internal source promotion schemaName")
    summary = report.get("summary")
    meta = report.get("meta")
    if not isinstance(summary, dict) or not isinstance(meta, dict):
        raise ValueError("internal source promotion summary/meta must be objects")
    for key in ["dslChanged", "assetChanged", "materializationChanged"]:
        if summary.get(key) is not False or meta.get(key) is not False:
            raise ValueError(f"internal source promotion must not change {key}")
    if summary.get("createdVisibleNodeCount") != 0 or meta.get("createdVisibleNodeCount") != 0:
        raise ValueError("internal source promotion must not create visible nodes")
    if meta.get("promotionOnly") is not True:
        raise ValueError("internal source promotion must declare promotionOnly")
