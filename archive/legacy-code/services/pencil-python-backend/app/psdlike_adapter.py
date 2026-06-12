from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from .container_foreground_audit import build_repeated_local_groups, read_ocr_blocks


class PSDLikeAdapterError(RuntimeError):
    pass


def adapt_psdlike_to_pencil_evidence(psdlike_dir: Path, output_dir: Path) -> Path:
    psdlike_dir = psdlike_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    layer_stack_path = psdlike_dir / "layer_stack.v1.json"
    if not layer_stack_path.exists():
        raise PSDLikeAdapterError(f"Missing PSD-like layer stack: {layer_stack_path}")
    layer_stack = json.loads(layer_stack_path.read_text(encoding="utf-8"))
    canvas = layer_stack.get("canvas") or {}
    width = int(canvas.get("width") or 0)
    height = int(canvas.get("height") or 0)
    if width <= 0 or height <= 0:
        raise PSDLikeAdapterError("PSD-like layer stack has invalid canvas size")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "crops").mkdir(exist_ok=True)
    (output_dir / "masks").mkdir(exist_ok=True)
    source_path = ensure_source_png(psdlike_dir, output_dir)
    source_diagnostics = layer_stack.get("diagnostics") or {}
    boundary_source = str(source_diagnostics.get("boundarySource") or "psdlike")

    primitives: list[dict[str, Any]] = []
    replay_layers: list[dict[str, Any]] = []
    source_layers = list(layer_stack.get("layers") or [])
    synthetic_text_layers = build_synthetic_foreground_text_layers(
        psdlike_dir=psdlike_dir,
        source_layers=source_layers,
        canvas_width=width,
        canvas_height=height,
    )
    synthetic_image_layers = build_synthetic_foreground_image_layers(
        psdlike_dir=psdlike_dir,
        source_layers=source_layers,
        canvas_width=width,
        canvas_height=height,
    )
    adapted_layers = sorted([*source_layers, *synthetic_image_layers, *synthetic_text_layers], key=lambda item: item.get("z", 0))
    for index, layer in enumerate(adapted_layers, start=1):
        layer_type = str(layer.get("type") or "")
        if layer_type == "raster":
            primitive, replay = adapt_raster_layer(
                layer,
                psdlike_dir,
                output_dir,
                index,
                width,
                height,
                source_path,
                source_layers,
            )
        elif layer_type == "shape":
            primitive, replay = adapt_shape_layer(layer, source_path, output_dir, index, width, height)
        elif layer_type == "text":
            primitive, replay = adapt_text_layer(layer, source_path, output_dir, index, width, height)
        else:
            continue
        primitives.append(primitive)
        replay_layers.append(replay)

    evidence = {
        "schema": "m29.physical_evidence.v1",
        "generator": {
            "name": "pencil-python-backend.psdlike_adapter",
            "source": "psdlike.layer_stack.v1",
        },
        "image": {
            "width": width,
            "height": height,
            "sourceRef": "source.png",
        },
        "diagnostics": {
            "pageBackground": layer_stack.get("pageBackground") or (layer_stack.get("diagnostics") or {}).get("pageBackground") or "#FFFFFF",
            "boundarySource": boundary_source,
            "psdlikeLayerCount": len(layer_stack.get("layers") or []),
            "psdlikeRasterLayerCount": sum(1 for item in layer_stack.get("layers") or [] if item.get("type") == "raster"),
            "psdlikeShapeLayerCount": sum(1 for item in layer_stack.get("layers") or [] if item.get("type") == "shape"),
            "psdlikeTextLayerCount": sum(1 for item in layer_stack.get("layers") or [] if item.get("type") == "text"),
            "psdlikeSyntheticForegroundTextCount": len(synthetic_text_layers),
            "psdlikeSyntheticForegroundImageCount": len(synthetic_image_layers),
            "hybridFallbackLayerCount": source_diagnostics.get("hybridFallbackLayerCount", 0),
            "hybridFallbackPolicy": source_diagnostics.get("hybridFallbackPolicy"),
        },
        "primitives": primitives,
    }
    replay = {
        "schema": "m29.pencil.replay.v1",
        "version": "1.0",
        "source": "generated_from_psdlike_layer_stack",
        "policy": {
            "mode": f"{boundary_source}_boundary_replay",
            "generatedBy": "psdlike_adapter.adapt_psdlike_to_pencil_evidence",
        },
        "layers": replay_layers,
        "summary": {
            "layerCount": len(replay_layers),
            "boundarySource": boundary_source,
        },
    }
    write_json(output_dir / "m29_physical_evidence.v1.json", evidence)
    write_json(output_dir / "m29-pencil-replay.v1.json", replay)
    copy_psdlike_debug(psdlike_dir, output_dir / "psdlike_debug")
    return output_dir


def build_synthetic_foreground_image_layers(
    *,
    psdlike_dir: Path,
    source_layers: list[dict[str, Any]],
    canvas_width: int,
    canvas_height: int,
) -> list[dict[str, Any]]:
    source_path = psdlike_dir / "source.png"
    if not source_path.exists():
        source_path = psdlike_dir / "input.png"
    if not source_path.exists():
        return []

    raw_blocks = read_ocr_blocks(psdlike_dir / "input.ocr_blocks.v1.json")
    assets_dir = psdlike_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    existing_boxes = [
        normalize_bbox(layer.get("bbox") or {})
        for layer in source_layers
        if layer.get("type") in {"raster", "shape"}
    ]
    selected: list[dict[str, Any]] = []
    selected_boxes: list[dict[str, int]] = []
    max_z = max((int(layer.get("z") or 0) for layer in source_layers), default=0)
    canvas_area = max(1, canvas_width * canvas_height)

    with Image.open(source_path) as image:
        source = image.convert("RGBA")
        for container in source_layers:
            if not is_texture_foreground_container(container, canvas_width, canvas_height):
                continue
            container_bbox = normalize_bbox(container.get("bbox") or {})
            boxes = repeated_texture_item_boxes(source, container_bbox, canvas_width, canvas_height)
            for box in boxes:
                if not is_valid_synthetic_image_box(
                    box=box,
                    container_bbox=container_bbox,
                    existing_boxes=existing_boxes,
                    selected_boxes=selected_boxes,
                    raw_blocks=raw_blocks,
                    canvas_area=canvas_area,
                ):
                    continue
                selected_boxes.append(box)
                asset_name = f"foreground_release_{len(selected_boxes):04d}.png"
                source.crop((box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"])).save(
                    assets_dir / asset_name
                )
                member_layers = [
                    str(layer.get("id"))
                    for layer in source_layers
                    if layer is not container and ioa_float(normalize_bbox(layer.get("bbox") or {}), box) >= 0.45
                ]
                member_ocr = [
                    block["id"]
                    for block in raw_blocks
                    if ioa_float(block["bbox"], box) >= 0.45
                ]
                selected.append(
                    {
                        "id": f"foreground_release_{len(selected_boxes):04d}",
                        "type": "raster",
                        "bbox": box,
                        "z": int(container.get("z") or max_z) + 1 + len(selected_boxes),
                        "asset": f"assets/{asset_name}",
                        "scores": foreground_box_scores(source, box),
                        "reason": "container_foreground_ownership_repair",
                        "syntheticForeground": True,
                        "ownershipRepair": {
                            "policy": "container_foreground_ownership_repair.v1",
                            "reason": "repeated_local_foreground_image_item",
                            "containerLayerId": container.get("id"),
                            "containerLayerType": container.get("type"),
                            "containerReason": container.get("reason"),
                            "containerBBox": container_bbox,
                            "sourceLayerIds": member_layers,
                            "ocrBlockIds": member_ocr,
                            "source": "source_pixel_repeated_local_item",
                        },
                    }
                )
    return selected


def is_texture_foreground_container(layer: dict[str, Any], canvas_width: int, canvas_height: int) -> bool:
    if layer.get("type") != "raster":
        return False
    bbox = normalize_bbox(layer.get("bbox") or {})
    area = bbox["width"] * bbox["height"]
    canvas_area = max(1, canvas_width * canvas_height)
    if area < canvas_area * 0.025 or area > canvas_area * 0.42:
        return False
    if bbox["width"] < 180 or bbox["height"] < 100:
        return False
    reason = str(layer.get("reason") or "")
    return any(token in reason for token in ("foreground_object", "high_texture", "source_raster", "fallback_object"))


def repeated_texture_item_boxes(
    source: Image.Image,
    container_bbox: dict[str, int],
    canvas_width: int,
    canvas_height: int,
) -> list[dict[str, int]]:
    tile = 8
    crop = source.crop(
        (
            container_bbox["x"],
            container_bbox["y"],
            container_bbox["x"] + container_bbox["width"],
            container_bbox["y"] + container_bbox["height"],
        )
    ).convert("RGB")
    scores = texture_tile_scores(crop, tile)
    if scores.size == 0:
        return []

    all_groups: list[list[dict[str, int]]] = []
    for percentile in (60.0, 65.0, 70.0):
        groups = texture_groups_for_percentile(
            scores=scores,
            percentile=percentile,
            tile=tile,
            container_bbox=container_bbox,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )
        all_groups.extend(groups)

    candidates: list[dict[str, int]] = []
    for group in sorted(all_groups, key=lambda value: (-len(value), group_area(value))):
        if not has_regular_box_spacing(group):
            continue
        for box in group:
            expanded = expand_bbox(box, max(4, tile), canvas_width, canvas_height)
            if any(iou(expanded, existing) >= 0.72 for existing in candidates):
                continue
            candidates.append(expanded)
    return candidates


def texture_tile_scores(crop: Image.Image, tile: int) -> np.ndarray:
    rgb = np.asarray(crop.convert("RGB"), dtype=np.float32)
    gray = np.asarray(crop.convert("L"), dtype=np.float32)
    tile_rows = gray.shape[0] // tile
    tile_cols = gray.shape[1] // tile
    if tile_rows <= 0 or tile_cols <= 0:
        return np.empty((0, 0), dtype=np.float32)

    grad_x = np.zeros_like(gray)
    grad_y = np.zeros_like(gray)
    grad_x[:, 1:] = np.abs(np.diff(gray, axis=1))
    grad_y[1:, :] = np.abs(np.diff(gray, axis=0))
    gradient = grad_x + grad_y

    scores = np.zeros((tile_rows, tile_cols), dtype=np.float32)
    for row in range(tile_rows):
        for col in range(tile_cols):
            sl = (slice(row * tile, (row + 1) * tile), slice(col * tile, (col + 1) * tile))
            rgb_tile = rgb[sl]
            gradient_tile = gradient[sl]
            scores[row, col] = float(
                rgb_tile.std(axis=(0, 1)).mean()
                + gradient_tile.mean() * 0.65
                + np.percentile(gradient_tile, 90) * 0.18
            )
    return scores


def texture_groups_for_percentile(
    *,
    scores: np.ndarray,
    percentile: float,
    tile: int,
    container_bbox: dict[str, int],
    canvas_width: int,
    canvas_height: int,
) -> list[list[dict[str, int]]]:
    active = scores > max(18.0, float(np.percentile(scores, percentile)))
    if not active.any():
        return []

    row_counts = active.sum(axis=1)
    row_threshold = max(4, int(active.shape[1] * 0.12))
    bands = contiguous_runs([int(index) for index in np.where(row_counts >= row_threshold)[0]])
    groups: list[list[dict[str, int]]] = []
    for start_row, end_row in bands:
        row_count = end_row - start_row + 1
        band_height = row_count * tile
        if not valid_texture_band_height(band_height, container_bbox, canvas_height):
            continue
        band = active[start_row : end_row + 1]
        col_counts = band.sum(axis=0)
        col_threshold = max(2, int(row_count * 0.25))
        col_runs = contiguous_runs([int(index) for index in np.where(col_counts >= col_threshold)[0]])
        boxes = [
            {
                "x": container_bbox["x"] + start_col * tile,
                "y": container_bbox["y"] + start_row * tile,
                "width": (end_col - start_col + 1) * tile,
                "height": band_height,
            }
            for start_col, end_col in col_runs
        ]
        boxes = [box for box in boxes if valid_texture_item_aspect(box, canvas_width, canvas_height)]
        if len(boxes) >= 3:
            groups.append(boxes)
    return groups


def contiguous_runs(values: list[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    runs: list[tuple[int, int]] = []
    start = previous = values[0]
    for value in values[1:]:
        if value <= previous + 1:
            previous = value
            continue
        runs.append((start, previous))
        start = previous = value
    runs.append((start, previous))
    return runs


def valid_texture_band_height(band_height: int, container_bbox: dict[str, int], canvas_height: int) -> bool:
    if band_height < 48:
        return False
    if band_height > max(240, int(canvas_height * 0.22)):
        return False
    return band_height <= max(72, int(container_bbox["height"] * 0.72))


def valid_texture_item_aspect(box: dict[str, int], canvas_width: int, canvas_height: int) -> bool:
    width = box["width"]
    height = box["height"]
    if width < 48 or height < 48:
        return False
    if width > max(160, canvas_width * 0.55) or height > max(128, canvas_height * 0.28):
        return False
    aspect = width / max(1, height)
    return 0.45 <= aspect <= 2.65


def has_regular_box_spacing(boxes: list[dict[str, int]]) -> bool:
    if len(boxes) < 3:
        return False
    widths = [box["width"] for box in boxes]
    heights = [box["height"] for box in boxes]
    if max(widths) > max(1, min(widths)) * 2.15:
        return False
    if max(heights) > max(1, min(heights)) * 1.45:
        return False
    centers = sorted(center_float(box, "x") for box in boxes)
    gaps = [b - a for a, b in zip(centers, centers[1:]) if b > a]
    if len(gaps) < 2:
        return False
    median = sorted(gaps)[len(gaps) // 2]
    if median <= 0:
        return False
    return max(abs(gap - median) for gap in gaps) <= max(24.0, median * 0.36)


def group_area(boxes: list[dict[str, int]]) -> int:
    return sum(box["width"] * box["height"] for box in boxes)


def is_valid_synthetic_image_box(
    *,
    box: dict[str, int],
    container_bbox: dict[str, int],
    existing_boxes: list[dict[str, int]],
    selected_boxes: list[dict[str, int]],
    raw_blocks: list[dict[str, Any]],
    canvas_area: int,
) -> bool:
    box_area = box["width"] * box["height"]
    if box_area < 2200 or box_area > canvas_area * 0.11:
        return False
    if ioa_float(box, container_bbox) < 0.92:
        return False
    if box_area > container_bbox["width"] * container_bbox["height"] * 0.68:
        return False
    if any(iou(box, selected) >= 0.58 for selected in selected_boxes):
        return False
    if any(iou(box, existing) >= 0.82 and (existing["width"] * existing["height"]) <= box_area * 1.25 for existing in existing_boxes):
        return False
    text_blocks = [block for block in raw_blocks if ioa_float(block["bbox"], box) >= 0.58]
    text_area = sum(area_float(block["bbox"]) for block in text_blocks)
    if len(text_blocks) >= 3 and text_area / max(1.0, float(box_area)) >= 0.10:
        return False
    return True


def foreground_box_scores(source: Image.Image, box: dict[str, int]) -> dict[str, float]:
    crop = source.crop((box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"])).convert("RGB")
    rgb = np.asarray(crop, dtype=np.float32)
    gray = np.asarray(crop.convert("L"), dtype=np.float32)
    if rgb.size == 0:
        return {"texture": 0.0, "edge": 0.0, "unique": 0.0}
    grad_x = np.zeros_like(gray)
    grad_y = np.zeros_like(gray)
    grad_x[:, 1:] = np.abs(np.diff(gray, axis=1))
    grad_y[1:, :] = np.abs(np.diff(gray, axis=0))
    return {
        "texture": round(float(rgb.std(axis=(0, 1)).mean() / 128.0), 4),
        "edge": round(float((grad_x + grad_y).mean() / 128.0), 4),
        "unique": round(float(len(np.unique(rgb.reshape(-1, 3), axis=0)) / max(1, rgb.shape[0] * rgb.shape[1])), 4),
    }


def build_synthetic_foreground_text_layers(
    *,
    psdlike_dir: Path,
    source_layers: list[dict[str, Any]],
    canvas_width: int,
    canvas_height: int,
) -> list[dict[str, Any]]:
    raw_blocks = read_ocr_blocks(psdlike_dir / "input.ocr_blocks.v1.json")
    if not raw_blocks:
        return []

    emitted_ids = {
        str(layer.get("id"))
        for layer in source_layers
        if layer.get("type") == "text" and layer.get("id")
    }
    missing_blocks = [
        block
        for block in raw_blocks
        if block["id"] not in emitted_ids and is_safe_missing_ocr_block(block, canvas_width, canvas_height)
    ]
    if not missing_blocks:
        return []

    canvas = {"width": canvas_width, "height": canvas_height}
    selected: dict[str, dict[str, Any]] = {}
    containers = [
        layer
        for layer in source_layers
        if is_foreground_release_container(layer, canvas_width, canvas_height)
    ]
    for container in containers:
        container_bbox = normalize_bbox(container.get("bbox") or {})
        contained = [
            block
            for block in missing_blocks
            if ioa_float(block["bbox"], container_bbox) >= 0.70
        ]
        if not contained:
            continue

        repeated_groups = build_repeated_local_groups(
            contained,
            {"id": container.get("id"), "bbox": to_float_bbox(container_bbox)},
            canvas,
        )
        for group in repeated_groups:
            for member in group.get("members") or []:
                block = next((item for item in contained if item["id"] == member.get("ocrId")), None)
                if block is not None:
                    select_missing_text_block(
                        selected,
                        block,
                        container,
                        reason="repeated_local_foreground_item",
                        group=group,
                    )
            for block in contained:
                if related_to_repeated_foreground_group(block, group, container_bbox):
                    select_missing_text_block(
                        selected,
                        block,
                        container,
                        reason="repeated_local_foreground_related_text",
                        group=group,
                    )

        for block in contained:
            if is_simple_control_foreground_text(block, container, canvas_width, canvas_height):
                select_missing_text_block(
                    selected,
                    block,
                    container,
                    reason="simple_control_foreground_text",
                    group=None,
                )

    if not selected:
        return []

    max_z = max((int(layer.get("z") or 0) for layer in source_layers), default=0)
    synthetic_layers: list[dict[str, Any]] = []
    for offset, block_id in enumerate(sorted(selected), start=1):
        block = selected[block_id]
        bbox = normalize_bbox(block["bbox"])
        synthetic_layers.append(
            {
                "id": block["id"],
                "type": "text",
                "bbox": bbox,
                "z": max_z + offset,
                "text": block["text"],
                "style": {},
                "confidence": block.get("confidence"),
                "reason": "container_foreground_ownership_repair",
                "syntheticForeground": True,
                "ownershipRepair": block["ownershipRepair"],
            }
        )
    return synthetic_layers


def is_safe_missing_ocr_block(block: dict[str, Any], canvas_width: int, canvas_height: int) -> bool:
    text = str(block.get("text") or "").strip()
    if not text:
        return False
    bbox = block["bbox"]
    area = area_float(bbox)
    canvas_area = max(1.0, float(canvas_width) * float(canvas_height))
    if area <= 12 or area > canvas_area * 0.035:
        return False
    if float(bbox.get("width") or 0) > canvas_width * 0.72:
        return False
    if float(bbox.get("height") or 0) > max(96.0, canvas_height * 0.085):
        return False
    return True


def is_foreground_release_container(layer: dict[str, Any], canvas_width: int, canvas_height: int) -> bool:
    layer_type = str(layer.get("type") or "")
    if layer_type not in {"raster", "shape"}:
        return False
    bbox = normalize_bbox(layer.get("bbox") or {})
    area = float(bbox["width"] * bbox["height"])
    canvas_area = max(1.0, float(canvas_width) * float(canvas_height))
    if area < canvas_area * 0.008 or area > canvas_area * 0.68:
        return False
    if bbox["width"] < 40 or bbox["height"] < 28:
        return False
    reason = str(layer.get("reason") or "")
    if layer_type == "shape":
        return any(token in reason for token in ("surface", "solid", "background"))
    return any(token in reason for token in ("foreground_object", "high_texture", "source_raster", "fallback_object"))


def select_missing_text_block(
    selected: dict[str, dict[str, Any]],
    block: dict[str, Any],
    container: dict[str, Any],
    *,
    reason: str,
    group: dict[str, Any] | None,
) -> None:
    existing = selected.get(block["id"])
    if existing is not None and release_reason_rank(existing["ownershipRepair"]["reason"]) >= release_reason_rank(reason):
        return
    selected[block["id"]] = {
        **block,
        "ownershipRepair": {
            "policy": "container_foreground_ownership_repair.v1",
            "reason": reason,
            "containerLayerId": container.get("id"),
            "containerLayerType": container.get("type"),
            "containerReason": container.get("reason"),
            "containerBBox": normalize_bbox(container.get("bbox") or {}),
            "groupId": group.get("id") if group else None,
            "groupPolicy": group.get("policy") if group else None,
            "source": "raw_ocr_block_missing_from_layer_stack",
        },
    }


def release_reason_rank(reason: str) -> int:
    return {
        "repeated_local_foreground_item": 30,
        "repeated_local_foreground_related_text": 20,
        "simple_control_foreground_text": 10,
    }.get(reason, 0)


def related_to_repeated_foreground_group(
    block: dict[str, Any],
    group: dict[str, Any],
    container_bbox: dict[str, int],
) -> bool:
    members = group.get("members") or []
    if not members:
        return False
    if any(block["id"] == member.get("ocrId") for member in members):
        return True

    axis = str(group.get("axis") or "x")
    centers = sorted(center_float(member["bbox"], axis) for member in members)
    gaps = [b - a for a, b in zip(centers, centers[1:]) if b > a]
    median_gap = sorted(gaps)[len(gaps) // 2] if gaps else max(float(container_bbox["width"]), float(container_bbox["height"]))
    block_main = center_float(block["bbox"], axis)
    member_widths = [float(member["bbox"].get("width") or 0) for member in members]
    member_heights = [float(member["bbox"].get("height") or 0) for member in members]
    main_size = max([float(block["bbox"].get("width" if axis == "x" else "height") or 0), *member_widths, *member_heights])
    main_threshold = max(42.0, min(median_gap * 0.42, main_size * 2.2))
    if min(abs(block_main - center) for center in centers) > main_threshold:
        return False

    group_bbox = group.get("bbox") or {}
    cross = "y" if axis == "x" else "x"
    block_cross = center_float(block["bbox"], cross)
    group_cross = center_float(group_bbox, cross)
    group_cross_size = float(group_bbox.get("height" if cross == "y" else "width") or 0)
    block_cross_size = float(block["bbox"].get("height" if cross == "y" else "width") or 0)
    container_cross_size = float(container_bbox["height" if cross == "y" else "width"])
    cross_threshold = min(
        max(72.0, group_cross_size * 2.6, block_cross_size * 2.8),
        max(72.0, container_cross_size * 0.38),
    )
    return abs(block_cross - group_cross) <= cross_threshold


def is_simple_control_foreground_text(
    block: dict[str, Any],
    container: dict[str, Any],
    canvas_width: int,
    canvas_height: int,
) -> bool:
    bbox = block["bbox"]
    container_bbox = normalize_bbox(container.get("bbox") or {})
    if ioa_float(bbox, container_bbox) < 0.82:
        return False
    width = float(container_bbox["width"])
    height = float(container_bbox["height"])
    aspect = width / max(1.0, height)
    short_side = float(min(canvas_width, canvas_height))
    if aspect < 2.2 or height > max(96.0, short_side * 0.16):
        return False
    text_area_ratio = area_float(bbox) / max(1.0, width * height)
    if text_area_ratio < 0.045 or text_area_ratio > 0.62:
        return False
    reason = str(container.get("reason") or "")
    layer_type = str(container.get("type") or "")
    if layer_type == "raster" and "foreground_object" in reason:
        return False
    center_x = center_float(bbox, "x")
    center_y = center_float(bbox, "y")
    container_center_x = container_bbox["x"] + width / 2.0
    container_center_y = container_bbox["y"] + height / 2.0
    return (
        abs(center_x - container_center_x) <= width * 0.32
        and abs(center_y - container_center_y) <= height * 0.34
    )


def to_float_bbox(bbox: dict[str, int]) -> dict[str, float]:
    return {
        "x": float(bbox["x"]),
        "y": float(bbox["y"]),
        "width": float(bbox["width"]),
        "height": float(bbox["height"]),
    }


def area_float(bbox: dict[str, Any]) -> float:
    return max(0.0, float(bbox.get("width") or 0)) * max(0.0, float(bbox.get("height") or 0))


def intersection_area_float(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax1 = float(a.get("x") or 0)
    ay1 = float(a.get("y") or 0)
    ax2 = ax1 + float(a.get("width") or 0)
    ay2 = ay1 + float(a.get("height") or 0)
    bx1 = float(b.get("x") or 0)
    by1 = float(b.get("y") or 0)
    bx2 = bx1 + float(b.get("width") or 0)
    by2 = by1 + float(b.get("height") or 0)
    return max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))


def ioa_float(inner: dict[str, Any], outer: dict[str, Any]) -> float:
    return intersection_area_float(inner, outer) / max(1.0, area_float(inner))


def iou(a: dict[str, Any], b: dict[str, Any]) -> float:
    overlap = intersection_area_float(a, b)
    if overlap <= 0:
        return 0.0
    return overlap / max(1.0, area_float(a) + area_float(b) - overlap)


def center_float(bbox: dict[str, Any], axis: str) -> float:
    return float(bbox.get(axis) or 0) + float(bbox.get("width" if axis == "x" else "height") or 0) / 2.0


def ensure_source_png(psdlike_dir: Path, output_dir: Path) -> Path:
    source = psdlike_dir / "source.png"
    if not source.exists():
        source_image = psdlike_dir / "input.png"
        source = source_image if source_image.exists() else source
    target = output_dir / "source.png"
    if source.exists():
        shutil.copy2(source, target)
        return target

    source_from_stack = find_source_from_layer_stack(psdlike_dir / "layer_stack.v1.json")
    if source_from_stack and source_from_stack.exists():
        shutil.copy2(source_from_stack, target)
        return target
    raise PSDLikeAdapterError("PSD-like output does not contain source.png and sourceImage is unavailable")


def find_source_from_layer_stack(layer_stack_path: Path) -> Path | None:
    try:
        data = json.loads(layer_stack_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = data.get("sourceImage")
    if isinstance(value, str) and value:
        return Path(value).expanduser().resolve()
    return None


def adapt_raster_layer(
    layer: dict[str, Any],
    psdlike_dir: Path,
    output_dir: Path,
    index: int,
    canvas_width: int,
    canvas_height: int,
    source_png: Path,
    source_layers: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    primitive_id = f"psd_raster_{index:04d}"
    bbox = normalize_bbox(layer["bbox"])
    source_asset = psdlike_dir / str(layer.get("asset") or "")
    if not source_asset.exists():
        raise PSDLikeAdapterError(f"Missing PSD-like raster asset for {layer.get('id')}: {source_asset}")
    crop_ref = f"crops/{primitive_id}.png"
    mask_ref = f"masks/{primitive_id}.png"
    repair = repair_raster_layer_bounds(
        layer=layer,
        source_png=source_png,
        bbox=bbox,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        source_layers=source_layers,
    )
    compile_hints: dict[str, Any] = {}
    if layer.get("syntheticForeground"):
        compile_hints["foregroundObjectRelease"] = {
            **(layer.get("ownershipRepair") or {}),
            "layerReason": layer.get("reason"),
        }
    if repair is None:
        shutil.copy2(source_asset, output_dir / crop_ref)
    else:
        bbox = repair["bbox"]
        repair["image"].save(output_dir / crop_ref)
        compile_hints["rasterBoundaryRepair"] = {
            "policy": "source_connected_component.v1",
            "originalBBox": repair["originalBBox"],
            "repairedBBox": bbox,
            "reason": repair["reason"],
        }
    write_rect_mask(output_dir / mask_ref, canvas_width, canvas_height, bbox)
    primitive = {
        "id": primitive_id,
        "primitiveType": "image_region",
        "bbox": bbox,
        "maskRef": mask_ref,
        "cropRef": crop_ref,
        "source": {
            "kind": "psdlike_raster",
            "sourceLayerId": layer.get("id"),
            "reason": layer.get("reason"),
            "syntheticForeground": bool(layer.get("syntheticForeground")),
        },
        "measurements": layer.get("scores") or {},
        "compileHints": compile_hints,
    }
    replay = base_replay_layer(layer, primitive_id, "image_region", bbox, crop_ref, mask_ref)
    return primitive, replay


def repair_raster_layer_bounds(
    *,
    layer: dict[str, Any],
    source_png: Path,
    bbox: dict[str, int],
    canvas_width: int,
    canvas_height: int,
    source_layers: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not should_try_raster_boundary_repair(layer, bbox, canvas_width, canvas_height):
        return None
    if not source_png.exists():
        return None

    padding = raster_boundary_search_padding(bbox)
    window = expand_bbox(bbox, padding, canvas_width, canvas_height)
    with Image.open(source_png) as image:
        source = image.convert("RGBA")
        local = source.crop((window["x"], window["y"], window["x"] + window["width"], window["y"] + window["height"]))
        arr = np.asarray(local.convert("RGB"), dtype=np.int16)

    if arr.size == 0:
        return None

    background = estimate_edge_background(arr)
    delta = np.linalg.norm(arr - background.reshape(1, 1, 3), axis=2)
    foreground = delta >= foreground_delta_threshold(delta)
    seed_box = {
        "x": bbox["x"] - window["x"],
        "y": bbox["y"] - window["y"],
        "width": bbox["width"],
        "height": bbox["height"],
    }
    component = connected_component_touching_seed(foreground, seed_box)
    if component is None:
        return None

    component_bbox = mask_bbox(component)
    if component_bbox is None:
        return None
    repaired = {
        "x": window["x"] + component_bbox["x"],
        "y": window["y"] + component_bbox["y"],
        "width": component_bbox["width"],
        "height": component_bbox["height"],
    }
    repaired = expand_bbox(repaired, 2, canvas_width, canvas_height)
    if not valid_repaired_raster_bbox(original=bbox, repaired=repaired, canvas_width=canvas_width, canvas_height=canvas_height):
        return None
    if overlaps_text_layer(repaired, source_layers):
        return None

    with Image.open(source_png) as image:
        source = image.convert("RGBA")
        crop = source.crop((repaired["x"], repaired["y"], repaired["x"] + repaired["width"], repaired["y"] + repaired["height"]))
    return {
        "bbox": repaired,
        "image": crop,
        "originalBBox": bbox,
        "reason": "foreground_pixels_continue_outside_psdlike_raster_bbox",
    }


def should_try_raster_boundary_repair(
    layer: dict[str, Any],
    bbox: dict[str, int],
    canvas_width: int,
    canvas_height: int,
) -> bool:
    reason = str(layer.get("reason") or "")
    if "background" in reason or "container" in reason:
        return False
    area = bbox["width"] * bbox["height"]
    canvas_area = max(1, canvas_width * canvas_height)
    if area < 120 or area > min(42_000, max(4_000, int(canvas_area * 0.04))):
        return False
    if bbox["width"] > max(96, canvas_width * 0.45):
        return False
    if bbox["height"] > max(64, canvas_height * 0.18):
        return False
    return True


def raster_boundary_search_padding(bbox: dict[str, int]) -> int:
    side = max(bbox["width"], bbox["height"])
    return max(12, min(96, int(round(side * 0.85))))


def foreground_delta_threshold(delta: np.ndarray) -> float:
    if delta.size == 0:
        return 32.0
    edge_values = np.concatenate(
        [
            delta[0, :].reshape(-1),
            delta[-1, :].reshape(-1),
            delta[:, 0].reshape(-1),
            delta[:, -1].reshape(-1),
        ],
        axis=0,
    )
    edge_noise = float(np.percentile(edge_values, 95)) if edge_values.size else 0.0
    return max(28.0, min(64.0, edge_noise * 1.8))


def connected_component_touching_seed(mask: np.ndarray, seed_box: dict[str, int]) -> np.ndarray | None:
    height, width = mask.shape[:2]
    x1 = max(0, seed_box["x"])
    y1 = max(0, seed_box["y"])
    x2 = min(width, seed_box["x"] + seed_box["width"])
    y2 = min(height, seed_box["y"] + seed_box["height"])
    if x1 >= x2 or y1 >= y2:
        return None
    seed = mask[y1:y2, x1:x2]
    if int(seed.sum()) < max(6, int(seed.size * 0.02)):
        return None

    visited = np.zeros(mask.shape, dtype=bool)
    component = np.zeros(mask.shape, dtype=bool)
    seed_points = np.argwhere(seed)
    stack = [(int(x1 + point[1]), int(y1 + point[0])) for point in seed_points]
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= width or y >= height:
            continue
        if visited[y, x] or not mask[y, x]:
            continue
        visited[y, x] = True
        component[y, x] = True
        for ny in (y - 1, y, y + 1):
            for nx in (x - 1, x, x + 1):
                if nx == x and ny == y:
                    continue
                if 0 <= nx < width and 0 <= ny < height and not visited[ny, nx] and mask[ny, nx]:
                    stack.append((nx, ny))
    if not component.any():
        return None
    return component


def mask_bbox(mask: np.ndarray) -> dict[str, int] | None:
    ys, xs = np.where(mask)
    if xs.size == 0 or ys.size == 0:
        return None
    x1 = int(xs.min())
    y1 = int(ys.min())
    x2 = int(xs.max()) + 1
    y2 = int(ys.max()) + 1
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}


def valid_repaired_raster_bbox(
    *,
    original: dict[str, int],
    repaired: dict[str, int],
    canvas_width: int,
    canvas_height: int,
) -> bool:
    growth_left = original["x"] - repaired["x"]
    growth_top = original["y"] - repaired["y"]
    growth_right = (repaired["x"] + repaired["width"]) - (original["x"] + original["width"])
    growth_bottom = (repaired["y"] + repaired["height"]) - (original["y"] + original["height"])
    if max(growth_left, growth_top, growth_right, growth_bottom) < 4:
        return False
    original_area = max(1, original["width"] * original["height"])
    repaired_area = repaired["width"] * repaired["height"]
    canvas_area = max(1, canvas_width * canvas_height)
    if repaired_area < original_area or repaired_area > original_area * 5.0:
        return False
    if repaired_area > min(60_000, max(8_000, int(canvas_area * 0.055))):
        return False
    if repaired["width"] > max(original["width"] * 2.8, 160):
        return False
    if repaired["height"] > max(original["height"] * 3.0, 160):
        return False
    return True


def overlaps_text_layer(bbox: dict[str, int], source_layers: list[dict[str, Any]]) -> bool:
    bbox_area = max(1, bbox["width"] * bbox["height"])
    for layer in source_layers:
        if layer.get("type") != "text":
            continue
        text_bbox = normalize_bbox(layer.get("bbox") or {})
        overlap = intersection_area(bbox, text_bbox)
        if overlap <= 0:
            continue
        text_area = max(1, text_bbox["width"] * text_bbox["height"])
        if overlap / bbox_area >= 0.08 or overlap / text_area >= 0.25:
            return True
    return False


def adapt_shape_layer(
    layer: dict[str, Any],
    source_png: Path,
    output_dir: Path,
    index: int,
    canvas_width: int,
    canvas_height: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    primitive_id = f"psd_shape_{index:04d}"
    bbox = normalize_bbox(layer["bbox"])
    crop_ref = f"crops/{primitive_id}.png"
    mask_ref = f"masks/{primitive_id}.png"
    style = layer.get("style") or {}
    fill = str(style.get("fill") or "#FFFFFF")
    editable_shape = should_emit_editable_shape(layer, bbox, canvas_width, canvas_height)
    if editable_shape:
        image = Image.new("RGBA", (bbox["width"], bbox["height"]), css_to_rgba(fill))
        image.save(output_dir / crop_ref)
        write_text_mask(output_dir / mask_ref, output_dir / crop_ref, canvas_width, canvas_height, bbox)
        primitive_type = "surface_region"
        compile_hints: dict[str, Any] = {}
    else:
        with Image.open(source_png) as source:
            source.convert("RGBA").crop(
                (
                    bbox["x"],
                    bbox["y"],
                    bbox["x"] + bbox["width"],
                    bbox["y"] + bbox["height"],
                )
            ).save(output_dir / crop_ref)
        write_rect_mask(output_dir / mask_ref, canvas_width, canvas_height, bbox)
        primitive_type = "image_region"
        compile_hints = {
            "shapeFallbackMode": "source_raster_crop",
            "shapeFallbackReason": "non_container_shape_requires_mask",
        }
    primitive = {
        "id": primitive_id,
        "primitiveType": primitive_type,
        "bbox": bbox,
        "maskRef": mask_ref,
        "cropRef": crop_ref,
        "source": {
            "kind": "psdlike_shape",
            "sourceLayerId": layer.get("id"),
            "reason": layer.get("reason"),
            "style": style,
        },
        "measurements": layer.get("scores") or {},
        "compileHints": compile_hints,
    }
    replay = base_replay_layer(layer, primitive_id, primitive_type, bbox, crop_ref, mask_ref)
    if editable_shape:
        replay = {
            **replay,
            "editableMode": "shape",
            "shapeStyle": style,
        }
    return primitive, replay


def should_emit_editable_shape(
    layer: dict[str, Any],
    bbox: dict[str, int],
    canvas_width: int,
    canvas_height: int,
) -> bool:
    reason = str(layer.get("reason") or "")
    if reason in {"background_surface_band", "local_container_surface"}:
        return True

    width = bbox["width"]
    height = bbox["height"]
    canvas_area = max(1, canvas_width * canvas_height)
    area_ratio = (width * height) / canvas_area
    width_ratio = width / max(1, canvas_width)
    height_ratio = height / max(1, canvas_height)
    aspect = width / max(1, height)

    if area_ratio >= 0.08 and (aspect >= 1.8 or aspect <= 0.56):
        return True
    if width_ratio >= 0.30 and height >= 32 and aspect >= 1.8:
        return True
    if height_ratio >= 0.12 and width >= 32 and aspect <= 0.56:
        return True
    return False


def adapt_text_layer(
    layer: dict[str, Any],
    source_png: Path,
    output_dir: Path,
    index: int,
    canvas_width: int,
    canvas_height: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    primitive_id = f"psd_text_{index:04d}"
    bbox = normalize_bbox(layer["bbox"])
    crop_ref = f"crops/{primitive_id}.png"
    mask_ref = f"masks/{primitive_id}.png"
    with Image.open(source_png) as source:
        source.convert("RGBA").crop(
            (
                bbox["x"],
                bbox["y"],
                bbox["x"] + bbox["width"],
                bbox["y"] + bbox["height"],
            )
        ).save(output_dir / crop_ref)
    write_rect_mask(output_dir / mask_ref, canvas_width, canvas_height, bbox)
    text = str(layer.get("text") or "")
    compile_hints: dict[str, Any] = {}
    if layer.get("syntheticForeground"):
        compile_hints["foregroundObjectRelease"] = {
            **(layer.get("ownershipRepair") or {}),
            "layerReason": layer.get("reason"),
        }
    primitive = {
        "id": primitive_id,
        "primitiveType": "text_region",
        "bbox": bbox,
        "maskRef": mask_ref,
        "cropRef": crop_ref,
        "source": {
            "kind": "ocr",
            "ocrBlockId": layer.get("id"),
            "text": text,
            "reason": layer.get("reason"),
            "psdlikeStyle": layer.get("style") or {},
            "confidence": layer.get("confidence"),
        },
        "measurements": layer.get("textFit") or {},
        "compileHints": compile_hints,
    }
    replay = base_replay_layer(layer, primitive_id, "text_region", bbox, crop_ref, mask_ref)
    return primitive, replay


def base_replay_layer(
    layer: dict[str, Any],
    primitive_id: str,
    role: str,
    bbox: dict[str, int],
    crop_ref: str,
    mask_ref: str,
) -> dict[str, Any]:
    replay = {
        "id": primitive_id,
        "sourcePrimitiveId": primitive_id,
        "sourceLayerId": layer.get("id"),
        "role": role,
        "nodeType": "rectangle",
        "bbox": bbox,
        "fillImage": f"./assets/{crop_ref}",
        "maskImage": f"./assets/{mask_ref}",
        "editableMode": "raster_crop",
        "z": int(layer.get("z") or 0),
    }
    if layer.get("syntheticForeground"):
        replay["foregroundObjectRelease"] = {
            **(layer.get("ownershipRepair") or {}),
            "layerReason": layer.get("reason"),
        }
    return replay


def normalize_bbox(raw: dict[str, Any]) -> dict[str, int]:
    x = int(round(float(raw.get("x") or 0)))
    y = int(round(float(raw.get("y") or 0)))
    width = max(1, int(round(float(raw.get("width") or 0))))
    height = max(1, int(round(float(raw.get("height") or 0))))
    return {"x": x, "y": y, "width": width, "height": height}


def expand_bbox(bbox: dict[str, int], px: int, canvas_width: int, canvas_height: int) -> dict[str, int]:
    x1 = max(0, bbox["x"] - px)
    y1 = max(0, bbox["y"] - px)
    x2 = min(canvas_width, bbox["x"] + bbox["width"] + px)
    y2 = min(canvas_height, bbox["y"] + bbox["height"] + px)
    return {"x": x1, "y": y1, "width": max(1, x2 - x1), "height": max(1, y2 - y1)}


def intersection_area(a: dict[str, int], b: dict[str, int]) -> int:
    x1 = max(a["x"], b["x"])
    y1 = max(a["y"], b["y"])
    x2 = min(a["x"] + a["width"], b["x"] + b["width"])
    y2 = min(a["y"] + a["height"], b["y"] + b["height"])
    return max(0, x2 - x1) * max(0, y2 - y1)


def write_rect_mask(path: Path, canvas_width: int, canvas_height: int, bbox: dict[str, int]) -> None:
    image = Image.new("L", (max(1, canvas_width), max(1, canvas_height)), 0)
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (
            bbox["x"],
            bbox["y"],
            bbox["x"] + bbox["width"] - 1,
            bbox["y"] + bbox["height"] - 1,
        ),
        fill=255,
    )
    image.save(path)


def write_text_mask(path: Path, crop_path: Path, canvas_width: int, canvas_height: int, bbox: dict[str, int]) -> None:
    crop = Image.open(crop_path).convert("RGB")
    arr = np.asarray(crop, dtype=np.int16)
    if arr.size == 0:
        write_rect_mask(path, canvas_width, canvas_height, bbox)
        return
    background = estimate_edge_background(arr)
    delta = np.linalg.norm(arr - background.reshape(1, 1, 3), axis=2)
    mask = delta >= 32.0
    if mask.sum() < max(2, int(mask.size * 0.01)):
        luminance = (arr[:, :, 0] * 0.2126 + arr[:, :, 1] * 0.7152 + arr[:, :, 2] * 0.0722)
        bg_luminance = float(background[0] * 0.2126 + background[1] * 0.7152 + background[2] * 0.0722)
        mask = np.abs(luminance - bg_luminance) >= 24.0
    if not mask.any():
        write_rect_mask(path, canvas_width, canvas_height, bbox)
        return
    local = Image.fromarray((mask.astype(np.uint8) * 255), "L")
    page = Image.new("L", (max(1, canvas_width), max(1, canvas_height)), 0)
    page.paste(local, (bbox["x"], bbox["y"]))
    page.save(path)


def estimate_edge_background(arr: np.ndarray) -> np.ndarray:
    height, width = arr.shape[:2]
    border = max(1, min(4, height // 4, width // 4))
    samples = np.concatenate(
        [
            arr[:border, :, :].reshape(-1, 3),
            arr[height - border :, :, :].reshape(-1, 3),
            arr[:, :border, :].reshape(-1, 3),
            arr[:, width - border :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    if samples.size == 0:
        return np.array([255, 255, 255], dtype=np.int16)
    return np.median(samples, axis=0).astype(np.int16)


def css_to_rgba(value: str) -> tuple[int, int, int, int]:
    value = value.strip()
    if value.startswith("#"):
        if len(value) == 4:
            return tuple(int(ch * 2, 16) for ch in value[1:]) + (255,)
        if len(value) == 7:
            return (
                int(value[1:3], 16),
                int(value[3:5], 16),
                int(value[5:7], 16),
                255,
            )
    return (255, 255, 255, 255)


def copy_psdlike_debug(psdlike_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "layer_stack.v1.json",
        "draft_runtime.dsl.v1_0.json",
        "preview.html",
        "preview_report.md",
        "draft_preview.png",
        "reconstructed_preview.png",
        "overlay.png",
        "raster_heatmap.png",
        "shape_heatmap.png",
        "ownership_report.v1.json",
        "hybrid_boundary_report.v1.json",
        "diagnostics.md",
        "input.ocr_blocks.v1.json",
        "psdlike.stdout.txt",
        "psdlike.stderr.txt",
    ):
        source = psdlike_dir / name
        if source.exists():
            shutil.copy2(source, target_dir / name)
    assets = psdlike_dir / "assets"
    if assets.exists():
        shutil.copytree(assets, target_dir / "assets", dirs_exist_ok=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
