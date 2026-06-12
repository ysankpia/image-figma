from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .report import build_summary
from .scoring import PROMOTABLE_SHAPE_ROLES, build_label_anchored_blocked_contract_item, build_m296_contract_item, build_m296_shape_contract_item
from .types import M29EvidenceContractResult, REPORT_ONLY_META
from .validation import validate_m29_evidence_contract_report


def extract_m29_evidence_contract_report(
    *,
    task_id: str,
    m292_document: dict[str, Any],
    media_internal_report: dict[str, Any],
    transparent_asset_report: dict[str, Any],
    output_dir: Path,
) -> M29EvidenceContractResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_objects = [item for item in m292_document.get("sourceObjects", []) if isinstance(item, dict)]
    internal_candidates = [item for item in media_internal_report.get("internalCandidates", []) if isinstance(item, dict)]
    transparent_items = [item for item in transparent_asset_report.get("items", []) if isinstance(item, dict)]
    warnings: list[str] = []
    contract_items = build_contract_items(
        source_objects=source_objects,
        internal_candidates=internal_candidates,
        transparent_items=transparent_items,
        warnings=warnings,
    )
    report_path = output_dir / "evidence_contract_report.json"
    report = {
        "schemaName": "M29EvidenceContractReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m292_document.get("schemaName"),
        "sourceSchemaVersion": m292_document.get("schemaVersion"),
        "mediaInternalSchemaName": media_internal_report.get("schemaName"),
        "mediaInternalSchemaVersion": media_internal_report.get("schemaVersion"),
        "transparentAssetSchemaName": transparent_asset_report.get("schemaName"),
        "transparentAssetSchemaVersion": transparent_asset_report.get("schemaVersion"),
        "outputReport": str(report_path),
        "summary": build_summary(
            source_objects=source_objects,
            internal_candidates=internal_candidates,
            transparent_items=transparent_items,
            contract_items=contract_items,
            warnings=warnings,
        ),
        "contractItems": contract_items,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_2_plus_m29_6_plus_transparent_asset_evidence_consistency",
            **REPORT_ONLY_META,
        },
    }
    validate_m29_evidence_contract_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29EvidenceContractResult(report=report, output_dir=output_dir)


def build_contract_items(
    *,
    source_objects: list[dict[str, Any]],
    internal_candidates: list[dict[str, Any]],
    transparent_items: list[dict[str, Any]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    media_lookup = {str(item.get("id") or item.get("sourceObjectId") or ""): item for item in source_objects if is_preserve_raster_media(item)}
    transparent_by_source = {str(item.get("sourceObjectId") or ""): item for item in transparent_items if item.get("sourceObjectId")}
    items: list[dict[str, Any]] = []
    for candidate in internal_candidates:
        role = str(candidate.get("role") or "")
        try:
            if role == "internal_icon_candidate":
                items.append(
                    build_m296_contract_item(
                        contract_id=f"m29_evidence_contract_{len(items) + 1:04d}",
                        candidate=candidate,
                        parent_media=media_lookup.get(str(candidate.get("mediaSourceObjectId") or "")),
                        transparent_item=transparent_by_source.get(str(candidate.get("candidateId") or "")),
                    )
                )
            elif role in PROMOTABLE_SHAPE_ROLES:
                items.append(
                    build_m296_shape_contract_item(
                        contract_id=f"m29_evidence_contract_{len(items) + 1:04d}",
                        candidate=candidate,
                        parent_media=media_lookup.get(str(candidate.get("mediaSourceObjectId") or "")),
                    )
                )
        except ValueError as error:
            warnings.append(f"skipped_invalid_internal_candidate:{candidate.get('candidateId')}:{error}")
    for source in source_objects:
        if not is_label_anchored_blocked_icon(source):
            continue
        try:
            parent_media = best_parent_media(source, source_objects)
            items.append(
                build_label_anchored_blocked_contract_item(
                    contract_id=f"m29_evidence_contract_{len(items) + 1:04d}",
                    source=source,
                    parent_media=parent_media,
                    transparent_item=transparent_by_source.get(str(source.get("id") or "")),
                )
            )
        except ValueError as error:
            warnings.append(f"skipped_invalid_label_anchored_blocked_icon:{source.get('id')}:{error}")
    return items


def is_preserve_raster_media(source: dict[str, Any]) -> bool:
    return source.get("pixelOwner") == "preserve_raster" and source.get("replayDecision") == "image_replay"


def is_label_anchored_blocked_icon(source: dict[str, Any]) -> bool:
    evidence = source.get("sourceEvidence") if isinstance(source.get("sourceEvidence"), dict) else {}
    return (
        source.get("visualKind") == "raster_icon"
        and source.get("pixelOwner") == "raster_icon"
        and source.get("replayDecision") == "icon_replay"
        and bool(evidence.get("labelAnchorOcrBoxId"))
        and bool(evidence.get("blockedIds"))
    )


def best_parent_media(source: dict[str, Any], source_objects: list[dict[str, Any]]) -> dict[str, Any] | None:
    evidence = source.get("sourceEvidence") if isinstance(source.get("sourceEvidence"), dict) else {}
    media_id = str(evidence.get("mediaSourceObjectId") or "")
    if media_id:
        for item in source_objects:
            if str(item.get("id") or "") == media_id and is_preserve_raster_media(item):
                return item
    media_candidates = [item for item in source_objects if is_preserve_raster_media(item)]
    if not media_candidates:
        return None
    bbox = source.get("bbox")
    best = None
    best_score = -1.0
    for media in media_candidates:
        score = bbox_containment_ratio(bbox, media.get("bbox"))
        if score > best_score:
            best = media
            best_score = score
    return best if best_score >= 0.80 else None


def bbox_containment_ratio(bbox: Any, container: Any) -> float:
    if not isinstance(bbox, list) or len(bbox) != 4 or not isinstance(container, list) or len(container) != 4:
        return 0.0
    left = max(int(bbox[0]), int(container[0]))
    top = max(int(bbox[1]), int(container[1]))
    right = min(int(bbox[0]) + int(bbox[2]), int(container[0]) + int(container[2]))
    bottom = min(int(bbox[1]) + int(bbox[3]), int(container[1]) + int(container[3]))
    area = max(0, right - left) * max(0, bottom - top)
    return area / max(1, int(bbox[2]) * int(bbox[3]))
