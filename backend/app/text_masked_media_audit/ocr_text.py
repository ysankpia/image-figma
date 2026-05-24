from __future__ import annotations

from typing import Any

from ..visual_primitive_graph import M29TextBox
from .regions import parse_bbox


def text_boxes_from_ocr_document(payload: dict[str, Any]) -> tuple[list[M29TextBox], list[str]]:
    warnings: list[str] = []
    boxes: list[M29TextBox] = []
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return [], ["ocr_json_missing_blocks"]
    for index, item in enumerate(blocks):
        if not isinstance(item, dict):
            warnings.append(f"ocr_block_{index + 1}_invalid")
            continue
        bbox = parse_bbox(item.get("bbox"))
        if bbox is None:
            warnings.append(f"ocr_block_{item.get('id', index + 1)}_invalid_bbox")
            continue
        raw_meta = item.get("meta")
        block_meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
        boxes.append(
            M29TextBox(
                id=str(item.get("id") or f"ocr_text_{index + 1:03d}"),
                bbox=bbox,
                text=str(item.get("text", "")).strip() or None,
                confidence=float(item.get("confidence", 1.0)),
                source="ocr",
                kind="line",
                meta=block_meta,
            )
        )
    return boxes, warnings
