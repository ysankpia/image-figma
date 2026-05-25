from __future__ import annotations

from typing import Any

from ..region_relation_kernel import normalize_bbox


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
                "sourceEvidence": item.get("sourceEvidence") if isinstance(item.get("sourceEvidence"), dict) else {},
            }
        )
    return sorted(objects, key=lambda item: item["id"]), skipped
