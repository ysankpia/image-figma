from __future__ import annotations

from typing import Any

from ..region_relation_kernel import normalize_bbox


def normalize_source_objects(raw_objects: Any) -> tuple[list[dict[str, Any]], list[str]]:
    objects: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_objects if isinstance(raw_objects, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_source_object:{index}")
            continue
        object_id = str(item.get("id") or "").strip()
        if not object_id:
            warnings.append(f"skipped_missing_source_object_id:{index}")
            continue
        if object_id in seen:
            warnings.append(f"skipped_duplicate_source_object_id:{object_id}")
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"sourceObjects[{index}].bbox")
        except ValueError:
            warnings.append(f"skipped_invalid_source_object_bbox:{object_id}")
            continue
        evidence = item.get("sourceEvidence")
        objects.append(
            {
                "sourceObjectId": object_id,
                "bbox": bbox,
                "visualKind": str(item.get("visualKind") or ""),
                "pixelOwner": str(item.get("pixelOwner") or ""),
                "replayDecision": str(item.get("replayDecision") or ""),
                "confidence": str(item.get("confidence") or "low"),
                "sourceEvidence": evidence if isinstance(evidence, dict) else {},
                "reasons": [str(value) for value in item.get("reasons", []) if isinstance(value, str)]
                if isinstance(item.get("reasons"), list)
                else [],
                "risks": [str(value) for value in item.get("risks", []) if isinstance(value, str)]
                if isinstance(item.get("risks"), list)
                else [],
            }
        )
        seen.add(object_id)
    return sorted(objects, key=lambda item: item["sourceObjectId"]), warnings


def normalize_ocr_blocks(raw_blocks: Any) -> tuple[list[dict[str, Any]], list[str]]:
    blocks: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, item in enumerate(raw_blocks if isinstance(raw_blocks, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_ocr_block:{index}")
            continue
        block_id = str(item.get("id") or "").strip()
        if not block_id:
            warnings.append(f"skipped_missing_ocr_block_id:{index}")
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"ocr.blocks[{index}].bbox")
        except ValueError:
            warnings.append(f"skipped_invalid_ocr_block_bbox:{block_id}")
            continue
        blocks.append({"ocrBoxId": block_id, "bbox": bbox, "confidence": float(item.get("confidence") or 0.0)})
    return sorted(blocks, key=lambda item: item["ocrBoxId"]), warnings


def normalize_media_internal_candidates(raw_items: Any) -> tuple[list[dict[str, Any]], list[str]]:
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, item in enumerate(raw_items if isinstance(raw_items, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_media_internal_candidate:{index}")
            continue
        candidate_id = str(item.get("candidateId") or "").strip()
        if not candidate_id:
            warnings.append(f"skipped_missing_media_internal_candidate_id:{index}")
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"internalCandidates[{index}].bbox")
        except ValueError:
            warnings.append(f"skipped_invalid_media_internal_candidate_bbox:{candidate_id}")
            continue
        breakdown = item.get("scoreBreakdown")
        metrics = item.get("metrics")
        candidates.append(
            {
                "candidateId": candidate_id,
                "sourceObjectId": candidate_id,
                "mediaSourceObjectId": str(item.get("mediaSourceObjectId") or ""),
                "rawNodeId": str(item.get("rawNodeId") or ""),
                "bbox": bbox,
                "visualKind": "internal_icon_candidate",
                "pixelOwner": "internal_candidate",
                "replayDecision": "candidate_only",
                "role": str(item.get("role") or ""),
                "rawType": str(item.get("rawType") or ""),
                "rawSubtype": str(item.get("rawSubtype") or ""),
                "matchedOcrBoxId": str(item.get("matchedOcrBoxId") or ""),
                "anchorRelation": str(item.get("anchorRelation") or ""),
                "candidateDecision": str(item.get("candidateDecision") or ""),
                "confidence": str(item.get("confidence") or "low"),
                "score": float(item.get("score") or 0.0),
                "scoreBreakdown": breakdown if isinstance(breakdown, dict) else {},
                "metrics": metrics if isinstance(metrics, dict) else {},
                "groupSupportedExecution": item.get("groupSupportedExecution") is True,
                "controlRowSupportedExecution": item.get("controlRowSupportedExecution") is True,
            }
        )
    return sorted(candidates, key=lambda item: item["candidateId"]), warnings
