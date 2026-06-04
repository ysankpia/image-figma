from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .jsonio import write_json


def write_container_foreground_audit(artifact_dir: Path) -> Path | None:
    sources = load_sources(artifact_dir)
    if sources is None:
        return None
    audit = build_container_foreground_audit(sources)
    path = artifact_dir / "container_foreground_audit.v1.json"
    write_json(path, audit)
    return path


def load_sources(artifact_dir: Path) -> dict[str, Any] | None:
    evidence_path = artifact_dir / "m29_physical_evidence.v1.json"
    replay_path = artifact_dir / "m29-pencil-replay.v1.json"
    if not evidence_path.exists() or not replay_path.exists():
        return None
    psdlike_debug = artifact_dir / "psdlike_debug"
    return {
        "evidence": json.loads(evidence_path.read_text(encoding="utf-8")),
        "replay": json.loads(replay_path.read_text(encoding="utf-8")),
        "layerStack": read_optional_json(psdlike_debug / "layer_stack.v1.json"),
        "ocrBlocks": read_ocr_blocks(psdlike_debug / "input.ocr_blocks.v1.json"),
    }


def read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_ocr_blocks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = data.get("blocks") if isinstance(data, dict) else data
    if not isinstance(blocks, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        bbox = normalize_bbox(block.get("bbox") or block.get("box") or block.get("rect") or {})
        text = str(block.get("text") or block.get("content") or block.get("value") or "").strip()
        if not text or area_of(bbox) <= 0:
            continue
        normalized.append(
            {
                "id": str(block.get("id") or f"ocr_{index:04d}"),
                "text": text,
                "bbox": bbox,
                "confidence": block.get("confidence"),
                "source": block.get("source"),
            }
        )
    return normalized


def build_container_foreground_audit(sources: dict[str, Any]) -> dict[str, Any]:
    evidence = sources["evidence"]
    replay = sources["replay"]
    image = evidence.get("image") or {}
    canvas = {"width": int(image.get("width") or 0), "height": int(image.get("height") or 0)}
    layers = list(replay.get("layers") or [])
    layer_stack = sources.get("layerStack") or {}
    ocr_blocks = sources.get("ocrBlocks") or []
    emitted_text_ids = emitted_text_block_ids(layer_stack)
    missing_ocr = [block for block in ocr_blocks if block["id"] not in emitted_text_ids]
    containers = [layer for layer in layers if is_candidate_container(layer, canvas)]

    conflicts = []
    for container in containers:
        contained_missing_text = [
            block
            for block in missing_ocr
            if ioa(block["bbox"], container["bbox"]) >= 0.70
        ]
        contained_layers = [
            summarize_layer(layer)
            for layer in layers
            if layer is not container and ioa(layer.get("bbox") or {}, container["bbox"]) >= 0.72
        ]
        repeated_groups = build_repeated_local_groups(contained_missing_text, container, canvas)
        if contained_missing_text or len(contained_layers) >= 2 or repeated_groups:
            conflicts.append(
                {
                    "containerId": container.get("id"),
                    "sourcePrimitiveId": container.get("sourcePrimitiveId"),
                    "role": container.get("role"),
                    "bbox": container.get("bbox"),
                    "areaRatio": round(area_of(container.get("bbox") or {}) / max(1.0, canvas["width"] * canvas["height"]), 4),
                    "containedMissingOcrText": contained_missing_text,
                    "containedLayerCount": len(contained_layers),
                    "containedLayers": contained_layers[:80],
                    "repeatedLocalGroups": repeated_groups,
                    "decision": "foreground_conflict" if repeated_groups or contained_missing_text else "container_contains_layers",
                    "reason": "large_container_contains_repeated_or_missing_foreground_evidence",
                }
            )

    return {
        "schema": "pencil.container_foreground_audit.v1",
        "canvas": canvas,
        "summary": {
            "containerCount": len(containers),
            "rawOcrBlockCount": len(ocr_blocks),
            "emittedTextBlockCount": len(emitted_text_ids),
            "missingOcrBlockCount": len(missing_ocr),
            "conflictCount": len(conflicts),
            "repeatedGroupCount": sum(len(item.get("repeatedLocalGroups") or []) for item in conflicts),
        },
        "rules": {
            "policy": "container_foreground_ownership_repair.audit.v1",
            "sourceTruth": ["raw OCR bbox", "replay primitive bbox", "containment", "alignment", "spacing"],
            "forbiddenSignals": ["file name", "brand", "visible text literal", "fixed coordinate", "screen-specific branch"],
        },
        "missingOcrBlocks": missing_ocr,
        "conflicts": conflicts,
    }


def emitted_text_block_ids(layer_stack: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for layer in layer_stack.get("layers") or []:
        if isinstance(layer, dict) and layer.get("type") == "text" and layer.get("id"):
            ids.add(str(layer["id"]))
    return ids


def is_candidate_container(layer: dict[str, Any], canvas: dict[str, int]) -> bool:
    bbox = layer.get("bbox") or {}
    area = area_of(bbox)
    canvas_area = max(1.0, float(canvas["width"]) * float(canvas["height"]))
    if area <= canvas_area * 0.015 or area >= canvas_area * 0.90:
        return False
    if layer.get("role") not in {"image_region", "surface_region", "unknown_region"}:
        return False
    return float(bbox.get("width") or 0) >= 48 and float(bbox.get("height") or 0) >= 40


def build_repeated_local_groups(
    blocks: list[dict[str, Any]],
    container: dict[str, Any],
    canvas: dict[str, int],
) -> list[dict[str, Any]]:
    if len(blocks) < 3:
        return []
    groups: list[dict[str, Any]] = []
    for axis in ("x", "y"):
        band_groups = split_into_alignment_bands(blocks, cross_axis(axis))
        for band in band_groups:
            if len(band) < 3 or not has_regular_spacing(band, axis, canvas):
                continue
            groups.append(
                {
                    "id": f"group_{len(groups) + 1:04d}",
                    "axis": axis,
                    "bbox": bbox_union([item["bbox"] for item in band]),
                    "memberCount": len(band),
                    "members": [{"ocrId": item["id"], "text": item["text"], "bbox": item["bbox"]} for item in band],
                    "containerId": container.get("id"),
                    "policy": "repeated_local_foreground_items.v1",
                    "reason": "aligned_repeated_missing_ocr_foreground",
                }
            )
    return dedupe_groups(groups)


def split_into_alignment_bands(items: list[dict[str, Any]], axis: str) -> list[list[dict[str, Any]]]:
    bands: list[list[dict[str, Any]]] = []
    for item in sorted(items, key=lambda value: center(value["bbox"], axis)):
        item_center = center(item["bbox"], axis)
        item_size = float(item["bbox"]["height" if axis == "y" else "width"])
        for band in bands:
            band_center = sum(center(member["bbox"], axis) for member in band) / len(band)
            band_size = max(float(member["bbox"]["height" if axis == "y" else "width"]) for member in band)
            if abs(item_center - band_center) <= max(14.0, min(item_size, band_size) * 0.80):
                band.append(item)
                break
        else:
            bands.append([item])
    return bands


def has_regular_spacing(items: list[dict[str, Any]], axis: str, canvas: dict[str, int]) -> bool:
    centers = sorted(center(item["bbox"], axis) for item in items)
    gaps = [b - a for a, b in zip(centers, centers[1:]) if b > a]
    if len(gaps) < 2:
        return False
    median = sorted(gaps)[len(gaps) // 2]
    if median <= 0:
        return False
    max_deviation = max(abs(gap - median) for gap in gaps)
    short_side = max(1.0, float(min(canvas["width"], canvas["height"])))
    return max_deviation <= max(18.0, short_side * 0.04, median * 0.45)


def dedupe_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for group in groups:
        key = (group["axis"], tuple(item["ocrId"] for item in group["members"]))
        if key not in seen:
            seen.add(key)
            kept.append(group)
    return kept


def summarize_layer(layer: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": layer.get("id"),
        "sourcePrimitiveId": layer.get("sourcePrimitiveId"),
        "role": layer.get("role"),
        "bbox": layer.get("bbox"),
        "z": layer.get("z"),
    }


def normalize_bbox(raw: dict[str, Any]) -> dict[str, float]:
    return {
        "x": float(raw.get("x") or 0),
        "y": float(raw.get("y") or 0),
        "width": max(0.0, float(raw.get("width") or 0)),
        "height": max(0.0, float(raw.get("height") or 0)),
    }


def area_of(bbox: dict[str, Any]) -> float:
    return max(0.0, float(bbox.get("width") or 0)) * max(0.0, float(bbox.get("height") or 0))


def intersection_area(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax1 = float(a.get("x") or 0)
    ay1 = float(a.get("y") or 0)
    ax2 = ax1 + float(a.get("width") or 0)
    ay2 = ay1 + float(a.get("height") or 0)
    bx1 = float(b.get("x") or 0)
    by1 = float(b.get("y") or 0)
    bx2 = bx1 + float(b.get("width") or 0)
    by2 = by1 + float(b.get("height") or 0)
    return max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))


def ioa(inner: dict[str, Any], outer: dict[str, Any]) -> float:
    return intersection_area(inner, outer) / max(1.0, area_of(inner))


def bbox_union(boxes: list[dict[str, Any]]) -> dict[str, float]:
    x1 = min(float(box["x"]) for box in boxes)
    y1 = min(float(box["y"]) for box in boxes)
    x2 = max(float(box["x"]) + float(box["width"]) for box in boxes)
    y2 = max(float(box["y"]) + float(box["height"]) for box in boxes)
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}


def center(bbox: dict[str, Any], axis: str) -> float:
    if axis == "x":
        return float(bbox["x"]) + float(bbox["width"]) / 2.0
    return float(bbox["y"]) + float(bbox["height"]) / 2.0


def cross_axis(axis: str) -> str:
    return "y" if axis == "x" else "x"
