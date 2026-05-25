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
        source_id = str(item.get("id") or "").strip()
        if not source_id:
            warnings.append(f"skipped_missing_source_object_id:{index}")
            continue
        if source_id in seen:
            warnings.append(f"skipped_duplicate_source_object_id:{source_id}")
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"sourceObjects[{index}].bbox")
        except ValueError:
            warnings.append(f"skipped_invalid_source_object_bbox:{source_id}")
            continue
        evidence = item.get("sourceEvidence")
        objects.append(
            {
                "sourceObjectId": source_id,
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
        seen.add(source_id)
    return sorted(objects, key=lambda item: item["sourceObjectId"]), warnings


def normalize_ocr_blocks(raw_blocks: Any) -> tuple[list[dict[str, Any]], list[str]]:
    blocks: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_blocks if isinstance(raw_blocks, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_ocr_block:{index}")
            continue
        block_id = str(item.get("id") or "").strip()
        if not block_id:
            warnings.append(f"skipped_missing_ocr_block_id:{index}")
            continue
        if block_id in seen:
            warnings.append(f"skipped_duplicate_ocr_block_id:{block_id}")
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"ocr.blocks[{index}].bbox")
        except ValueError:
            warnings.append(f"skipped_invalid_ocr_block_bbox:{block_id}")
            continue
        text = str(item.get("text") or "")
        blocks.append(
            {
                "ocrBoxId": block_id,
                "bbox": bbox,
                "confidence": float(item.get("confidence") or 0.0),
                "textLength": len(text),
                "lineId": str(item.get("lineId") or ""),
                "blockId": str(item.get("blockId") or ""),
            }
        )
        seen.add(block_id)
    return sorted(blocks, key=lambda item: item["ocrBoxId"]), warnings


def normalize_raw_nodes(raw_nodes: Any, raw_blocked: Any | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    nodes: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_nodes if isinstance(raw_nodes, list) else []):
        node = normalize_raw_node(item, f"nodes[{index}]", warnings)
        if node is None:
            continue
        if node["rawNodeId"] in seen:
            warnings.append(f"skipped_duplicate_raw_node_id:{node['rawNodeId']}")
            continue
        seen.add(node["rawNodeId"])
        nodes.append(node)
    for index, item in enumerate(raw_blocked if isinstance(raw_blocked, list) else []):
        node = normalize_raw_node(item, f"blocked[{index}]", warnings, fallback_type="blocked")
        if node is None:
            continue
        if node["rawNodeId"] in seen:
            warnings.append(f"skipped_duplicate_raw_node_id:{node['rawNodeId']}")
            continue
        seen.add(node["rawNodeId"])
        nodes.append(node)
    return sorted(nodes, key=lambda item: item["rawNodeId"]), warnings


def normalize_raw_node(
    item: Any,
    label: str,
    warnings: list[str],
    *,
    fallback_type: str = "",
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        warnings.append(f"skipped_invalid_raw_node:{label}")
        return None
    raw_id = str(item.get("id") or "").strip()
    if not raw_id:
        warnings.append(f"skipped_missing_raw_node_id:{label}")
        return None
    try:
        bbox = normalize_bbox(item.get("bbox"), f"{label}.bbox")
    except ValueError:
        warnings.append(f"skipped_invalid_raw_node_bbox:{raw_id}")
        return None
    metrics = item.get("metrics")
    return {
        "rawNodeId": raw_id,
        "bbox": bbox,
        "type": str(item.get("type") or fallback_type or ""),
        "subtype": str(item.get("subtype") or ""),
        "confidence": float(item.get("confidence") or 0.0),
        "source": str(item.get("source") or ""),
        "layerHint": str(item.get("layerHint") or ""),
        "metrics": metrics if isinstance(metrics, dict) else {},
        "reasons": [str(value) for value in item.get("reasons", []) if isinstance(value, str)]
        if isinstance(item.get("reasons"), list)
        else [],
    }


def normalize_plan_items(raw_items: Any) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items if isinstance(raw_items, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_plan_item:{index}")
            continue
        plan_id = str(item.get("id") or f"plan_item_{index + 1:04d}")
        if plan_id in seen:
            warnings.append(f"skipped_duplicate_plan_item_id:{plan_id}")
            continue
        source_id = str(item.get("sourceObjectId") or "").strip()
        if not source_id:
            warnings.append(f"skipped_missing_plan_source_object_id:{plan_id}")
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"planItems[{index}].bbox")
        except ValueError:
            warnings.append(f"skipped_invalid_plan_item_bbox:{plan_id}")
            continue
        items.append(
            {
                "planItemId": plan_id,
                "sourceObjectId": source_id,
                "bbox": bbox,
                "finalReplayAction": str(item.get("finalReplayAction") or ""),
                "targetRole": item.get("targetRole"),
                "pixelOwner": str(item.get("pixelOwner") or ""),
                "confidence": str(item.get("confidence") or "low"),
            }
        )
        seen.add(plan_id)
    return sorted(items, key=lambda item: item["planItemId"]), warnings
