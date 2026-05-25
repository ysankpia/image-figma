from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..region_relation_kernel import normalize_bbox
from .types import M29InternalSourcePromotionResult, REPORT_META


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
        and item.get("role") == "internal_icon_candidate"
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
        and item.get("sourceKind") == "m29_6_internal_icon_candidate"
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
    selected_by_bbox: dict[tuple[int, int, int, int], dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    for item in promoted:
        bbox = tuple(normalize_bbox(item.get("bbox"), "promoted.bbox"))
        current = selected_by_bbox.get(bbox)
        if current is None or promotion_rank(item) > promotion_rank(current):
            if current is not None:
                rejected.append(rejected_duplicate(current))
            selected_by_bbox[bbox] = item
        else:
            rejected.append(rejected_duplicate(item))
    kept = list(selected_by_bbox.values())
    for index, item in enumerate(kept, start=1):
        item["id"] = f"m292_promoted_internal_icon_{index:04d}"
    return kept, rejected


def promotion_rank(item: dict[str, Any]) -> tuple[float, int, str]:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    try:
        score = float(evidence.get("evidenceScore") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    candidate_id = str(evidence.get("mediaInternalCandidateId") or "")
    media_id = str(evidence.get("mediaSourceObjectId") or "")
    return (score, len(candidate_id), media_id)


def rejected_duplicate(item: dict[str, Any]) -> dict[str, Any]:
    evidence = item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {}
    return {
        "candidateId": evidence.get("mediaInternalCandidateId"),
        "reason": "duplicate_promoted_internal_bbox",
        "bbox": item.get("bbox"),
        "keptBy": "highest_evidence_score",
    }


def reject_reason(candidate: dict[str, Any] | None, transparent_item: dict[str, Any] | None, evidence_contract: dict[str, Any] | None, base_ids: set[str]) -> str:
    if candidate is None:
        return "missing_media_internal_candidate"
    if candidate.get("role") != "internal_icon_candidate":
        return "not_internal_icon_candidate"
    if candidate.get("candidateDecision") != "accepted_report_candidate":
        return "internal_candidate_not_accepted"
    media_id = str(candidate.get("mediaSourceObjectId") or "")
    if not media_id or media_id not in base_ids:
        return "missing_parent_media_source_object"
    try:
        normalize_bbox(candidate.get("bbox"), "candidate.bbox")
    except ValueError:
        return "invalid_candidate_bbox"
    if transparent_item is None:
        return "missing_transparent_asset_item"
    if transparent_item.get("decision") != "allow" or transparent_item.get("assetPath") is None:
        return "missing_transparent_asset_path"
    if evidence_contract is None:
        return "missing_evidence_contract"
    decision = evidence_contract.get("decision") if isinstance(evidence_contract.get("decision"), dict) else {}
    if decision.get("mode") != "allow_visible_replay":
        return "evidence_contract_not_allowing_visible_replay"
    return ""


def promoted_object(candidate: dict[str, Any], transparent_item: dict[str, Any], evidence_contract: dict[str, Any], index: int) -> dict[str, Any]:
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


def build_promoted_m292_document(source: dict[str, Any], source_objects: list[dict[str, Any]], promoted_count: int) -> dict[str, Any]:
    document = deepcopy(source)
    document["sourceObjects"] = source_objects
    summary = dict(document.get("summary") if isinstance(document.get("summary"), dict) else {})
    summary["sourceObjectCount"] = len(source_objects)
    summary["rasterIconCount"] = int(summary.get("rasterIconCount") or 0) + promoted_count
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
