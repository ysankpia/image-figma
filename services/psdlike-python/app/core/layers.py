from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Mechanical migration from PSD-like V1 oracle. Keep behavior changes out of this stage.


def exported_rejections(rejected: list[dict[str, Any]], limit: int = 200) -> list[dict[str, Any]]:
    if len(rejected) <= limit:
        return rejected
    priority_kinds = {"control_owned_raster_suppressed", "text_owned_raster_suppressed", "media_owned_text"}
    priority = [item for item in rejected if item.get("kind") in priority_kinds]
    remaining = [item for item in rejected if item.get("kind") not in priority_kinds]
    return (priority + remaining)[:limit]


def build_layer_stack(
    image_path: Path,
    ocr_path: Path | None,
    image: Image.Image,
    rgb: np.ndarray,
    ocr_blocks: list[OCRBlock],
    raster_candidates: list[Candidate],
    shape_candidates: list[Candidate],
    asset_refs: dict[str, str],
    ownership: dict[str, dict[str, Any]],
    rejected: list[dict[str, Any]],
    thresholds: dict[str, Any],
    media_owned_text_ids: set[str] | None = None,
    media_owned_text_decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    layers: list[dict[str, Any]] = []
    media_owned_text_ids = media_owned_text_ids or set()
    media_owned_text_decisions = media_owned_text_decisions or []
    page_background_rgb = estimate_background_color(rgb)

    for index, shape in enumerate(shape_candidates, start=1):
        if shape.reason == "inferred_background_plate_from_surface_bands":
            z = 10000 + index
        elif shape.reason == "background_surface_band":
            z = 11000 + index
        else:
            z = 12000 + index
        layers.append(
            {
                "id": f"shape_{index:04d}",
                "type": "shape",
                "bbox": shape.bbox.to_dict(),
                "z": z,
                "style": shape_style(rgb, shape),
                "scores": shape.scores,
                "reason": shape.reason,
            }
        )

    for index, raster in enumerate(raster_candidates, start=1):
        layers.append(
            {
                "id": f"raster_{index:04d}",
                "type": "raster",
                "bbox": raster.bbox.to_dict(),
                "z": 20000 + index,
                "asset": asset_refs.get(raster.id, ""),
                "scores": raster.scores,
                "ownership": ownership.get(raster.id, {}),
                "reason": raster.reason,
            }
        )

    visible_ocr_blocks = [block for block in ocr_blocks if block.id not in media_owned_text_ids]
    for index, block in enumerate(visible_ocr_blocks, start=1):
        context = text_style_context_for_block(block, layers, page_background_rgb)
        text_style = estimate_text_style(rgb, block.bbox, block.text, context)
        text_bbox = owner_aware_text_bbox(block.bbox, text_style["diagnostics"], context)
        layers.append(
            {
                "id": block.id or f"text_{index:04d}",
                "type": "text",
                "bbox": text_bbox.to_dict(),
                "z": 30000 + index,
                "text": block.text,
                "style": text_style["style"],
                "textFit": text_style["diagnostics"],
                "confidence": round(block.confidence, 4),
                "reason": "ocr_authority",
            }
        )
    harmonize_text_layers(layers)

    page_area = image.width * image.height
    full_page_raster = sum(1 for item in raster_candidates if is_full_page_backing(item.bbox, image.width, image.height))
    tiny_raster = sum(1 for item in raster_candidates if item.bbox.area < 400)
    raw_text_overlap_raster = sum(1 for item in raster_candidates if item.scores.get("textOverlap", 0.0) > thresholds["maxTextOverlap"])
    raster_text_knockout = sum(1 for item in raster_candidates if ownership.get(item.id, {}).get("textKnockout"))
    covered_text_blocks = sum(int(ownership.get(item.id, {}).get("coveredTextBlockCount", 0)) for item in raster_candidates)
    visible_text_overlap = sum(1 for item in raster_candidates if ownership.get(item.id, {}).get("visibleTextOwnershipConflict"))
    missing_assets = sum(1 for item in layers if item["type"] == "raster" and not item.get("asset"))
    surface_shapes = sum(1 for item in shape_candidates if item.reason == "background_surface_band")
    background_plates = sum(1 for item in shape_candidates if item.reason == "inferred_background_plate_from_surface_bands")
    container_surfaces = sum(1 for item in shape_candidates if item.reason == "local_container_surface")
    control_surfaces = sum(1 for item in shape_candidates if item.scores.get("confirmedControlSurface", 0.0) >= 1.0)
    ocr_control_surfaces = sum(
        1
        for item in shape_candidates
        if item.reason == "ocr_anchored_control_surface" and item.scores.get("confirmedControlSurface", 0.0) >= 1.0
    )
    model_control_surfaces = sum(
        1
        for item in shape_candidates
        if item.reason == "model_assisted_control_surface" and item.scores.get("confirmedControlSurface", 0.0) >= 1.0
    )
    model_media_rasters = sum(
        1 for item in raster_candidates if item.reason in {"model_assisted_media_refinement", "model_assisted_media_merge"}
    )
    control_owned_raster_suppressed = sum(1 for item in rejected if item.get("kind") == "control_owned_raster_suppressed")
    control_owned_shape_suppressed = sum(1 for item in rejected if item.get("kind") == "control_owned_shape_suppressed")
    container_parent_shape_suppressed = sum(1 for item in rejected if item.get("kind") == "container_parent_shape_suppressed")
    control_residual_suppressed = sum(1 for item in rejected if item.get("reason", "").startswith("control_residual_"))
    text_owned_raster_suppressed = sum(1 for item in rejected if item.get("kind") == "text_owned_raster_suppressed")
    media_owned_text_count = len(media_owned_text_ids)
    media_text_owner_raster_count = len({str(item.get("ownerRasterId", "")) for item in media_owned_text_decisions if item.get("ownerRasterId")})
    text_fit_shrink_count = sum(1 for item in layers if item["type"] == "text" and item.get("textFit", {}).get("shrink", 0) > 0)
    dark_control_surfaces = sum(
        1
        for item in shape_candidates
        if item.scores.get("darkControlSurface", 0.0) >= 1.0 and item.scores.get("confirmedControlSurface", 0.0) >= 1.0
    )
    shape_asset_count = sum(1 for item in layers if item["type"] == "shape" and item.get("asset"))
    page_background = color_hex(page_background_rgb)
    text_style_owner_context_count = sum(
        1 for item in layers if item["type"] == "text" and item.get("textFit", {}).get("textOwnerRole") not in {"", "unknown"}
    )
    text_owner_aware_color_count = sum(
        1 for item in layers if item["type"] == "text" and item.get("textFit", {}).get("textColorSource") == "owner_surface_contrast_sample"
    )
    text_fallback_color_count = sum(
        1 for item in layers if item["type"] == "text" and item.get("textFit", {}).get("textColorSource") == "fallback_contrast"
    )
    text_font_family_cjk_count = sum(
        1 for item in layers if item["type"] == "text" and item.get("style", {}).get("fontFamily") == "PingFang SC"
    )
    text_font_weight_medium_count = sum(
        1 for item in layers if item["type"] == "text" and int(item.get("style", {}).get("fontWeight", 0)) >= 500
    )
    text_row_harmonized_count = sum(
        1 for item in layers if item["type"] == "text" and item.get("textFit", {}).get("rowHarmonized", 0) > 0
    )
    text_fit_owner_aware_count = sum(
        1 for item in layers if item["type"] == "text" and item.get("textFit", {}).get("ownerAwareFit", 0) > 0
    )
    text_owner_bbox_recentered_count = sum(
        1 for item in layers if item["type"] == "text" and item.get("textFit", {}).get("ownerBboxRecentered", 0) > 0
    )

    return {
        "version": "layer_stack.v1",
        "sourceImage": str(image_path),
        "ocr": str(ocr_path) if ocr_path else "",
        "canvas": {"width": image.width, "height": image.height},
        "pageBackground": page_background,
        "layers": sorted(layers, key=lambda item: item["z"]),
        "diagnostics": {
            "layerCount": len(layers),
            "ocrTextCount": len(ocr_blocks),
            "textLayerCount": len(visible_ocr_blocks),
            "visibleTextLayerCount": len(visible_ocr_blocks),
            "mediaOwnedTextBlockCount": media_owned_text_count,
            "mediaTextOwnerRasterCount": media_text_owner_raster_count,
            "textFitShrinkCount": text_fit_shrink_count,
            "textStyleOwnerContextCount": text_style_owner_context_count,
            "textOwnerAwareColorCount": text_owner_aware_color_count,
            "textFallbackColorCount": text_fallback_color_count,
            "textFontFamilyCjkCount": text_font_family_cjk_count,
            "textFontWeightMediumCount": text_font_weight_medium_count,
            "textRowHarmonizedCount": text_row_harmonized_count,
            "textFitOwnerAwareCount": text_fit_owner_aware_count,
            "textOwnerBboxRecenteredCount": text_owner_bbox_recentered_count,
            "darkControlSurfaceCount": dark_control_surfaces,
            "rasterLayerCount": len(raster_candidates),
            "modelAssistedMediaRasterCount": model_media_rasters,
            "shapeLayerCount": len(shape_candidates),
            "surfaceShapeLayerCount": surface_shapes,
            "backgroundPlateLayerCount": background_plates,
            "containerSurfaceShapeLayerCount": container_surfaces,
            "controlSurfaceShapeLayerCount": control_surfaces,
            "ocrAnchoredControlSurfaceCount": ocr_control_surfaces,
            "modelAssistedControlSurfaceCount": model_control_surfaces,
            "controlOwnedRasterSuppressedCount": control_owned_raster_suppressed,
            "controlOwnedShapeSuppressedCount": control_owned_shape_suppressed,
            "containerParentShapeSuppressedCount": container_parent_shape_suppressed,
            "controlResidualSuppressedCount": control_residual_suppressed,
            "textOwnedRasterSuppressedCount": text_owned_raster_suppressed,
            "shapeAssetCount": shape_asset_count,
            "pageBackground": page_background,
            "rejectedCandidateCount": len(rejected),
            "fullPageVisibleRaster": full_page_raster,
            "tinyRasterFragments": tiny_raster,
            "textOverlapRaster": visible_text_overlap,
            "rawTextOverlapRaster": raw_text_overlap_raster,
            "rasterTextKnockoutCount": raster_text_knockout,
            "rasterCoveredTextBlockCount": covered_text_blocks,
            "missingAssetCount": missing_assets,
            "pageArea": page_area,
        },
        "thresholds": thresholds,
        "mediaOwnedText": media_owned_text_decisions,
        "rejected": exported_rejections(rejected + media_owned_text_decisions),
    }


def text_style_context_for_block(block: OCRBlock, layers: list[dict[str, Any]], page_background: np.ndarray) -> TextStyleContext:
    control_context = best_shape_context(block, layers, confirmed_control=True)
    if control_context is not None:
        return control_context
    surface_context = best_shape_context(block, layers, confirmed_control=False)
    if surface_context is not None:
        return surface_context
    raster_context = best_raster_context(block, layers)
    if raster_context is not None:
        return raster_context
    return TextStyleContext(owner_fill=tuple(int(v) for v in page_background), owner_role="page_background", owner_reason="page_background")


def best_shape_context(block: OCRBlock, layers: list[dict[str, Any]], confirmed_control: bool) -> TextStyleContext | None:
    best: tuple[float, dict[str, Any], BBox] | None = None
    for layer in layers:
        if layer.get("type") != "shape":
            continue
        scores = layer.get("scores") or {}
        is_control = scores.get("confirmedControlSurface", 0.0) >= 1.0
        if confirmed_control != is_control:
            continue
        box = bbox_from_dict(layer.get("bbox") or {})
        if box is None or box.area <= 0:
            continue
        coverage = ioa(block.bbox, box)
        if coverage < (0.45 if is_control else 0.70) and not bbox_center_inside(block.bbox, box):
            continue
        area_penalty = box.area / max(1, block.bbox.area)
        score = coverage * 4.0 + (1.0 if bbox_center_inside(block.bbox, box) else 0.0) - min(1.5, area_penalty / 500.0)
        if best is None or score > best[0]:
            best = (score, layer, box)
    if best is None:
        return None
    _, layer, box = best
    fill = rgb_tuple_from_hex(str((layer.get("style") or {}).get("fill") or ""))
    return TextStyleContext(
        owner_bbox=box,
        owner_fill=fill,
        owner_reason=str(layer.get("reason") or ""),
        owner_role="control_surface" if confirmed_control else "container_surface",
        owner_id=str(layer.get("id") or ""),
    )


def best_raster_context(block: OCRBlock, layers: list[dict[str, Any]]) -> TextStyleContext | None:
    best: tuple[float, dict[str, Any], BBox] | None = None
    for layer in layers:
        if layer.get("type") != "raster":
            continue
        box = bbox_from_dict(layer.get("bbox") or {})
        if box is None or box.area <= 0:
            continue
        coverage = ioa(block.bbox, box)
        if coverage < 0.85:
            continue
        score = coverage - min(0.4, box.area / max(1, block.bbox.area) / 5000.0)
        if best is None or score > best[0]:
            best = (score, layer, box)
    if best is None:
        return None
    _, layer, box = best
    return TextStyleContext(owner_bbox=box, owner_reason=str(layer.get("reason") or ""), owner_role="media_surface", owner_id=str(layer.get("id") or ""))


def bbox_from_dict(value: dict[str, Any]) -> BBox | None:
    try:
        return BBox(int(value["x"]), int(value["y"]), int(value["width"]), int(value["height"]))
    except Exception:
        return None


def bbox_center_inside(inner: BBox, outer: BBox) -> bool:
    cx = inner.x + inner.width / 2
    cy = inner.y + inner.height / 2
    return outer.x <= cx <= outer.x2 and outer.y <= cy <= outer.y2


def rgb_tuple_from_hex(value: str) -> tuple[int, int, int] | None:
    if not value.startswith("#"):
        return None
    text = value[1:]
    if len(text) == 3:
        text = "".join(char + char for char in text)
    if len(text) != 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None


def owner_aware_text_bbox(box: BBox, diagnostics: dict[str, Any], context: TextStyleContext) -> BBox:
    owner = context.owner_bbox
    if owner is None or context.owner_role != "control_surface":
        return box
    line_height = int(diagnostics.get("lineHeight") or diagnostics.get("measuredHeight") or box.height)
    measured_width = int(diagnostics.get("measuredWidth") or box.width)
    measured_height = int(diagnostics.get("measuredHeight") or line_height)
    target_height = max(1, min(owner.height, max(line_height, measured_height, int(round(box.height * 0.72)))))
    horizontal_padding = max(4, int(round(owner.height * 0.20)))
    max_width = max(1, owner.width - horizontal_padding * 2)
    target_width = max(box.width, measured_width)
    target_width = max(1, min(max_width, target_width))
    center_x = box.x + box.width / 2
    center_y = owner.y + owner.height / 2
    min_x = owner.x + horizontal_padding
    max_x = owner.x2 - horizontal_padding - target_width
    x = int(round(center_x - target_width / 2))
    if max_x >= min_x:
        x = max(min_x, min(max_x, x))
    else:
        x = owner.x + max(0, (owner.width - target_width) // 2)
    y = int(round(center_y - target_height / 2))
    y = max(owner.y, min(owner.y2 - target_height, y))
    if x == box.x and y == box.y and target_width == box.width and target_height == box.height:
        return box
    diagnostics["ownerBboxRecentered"] = 1
    diagnostics["originalBBox"] = box.to_dict()
    diagnostics["ownerBBox"] = owner.to_dict()
    diagnostics["targetWidth"] = target_width
    diagnostics["targetHeight"] = target_height
    return BBox(x, y, target_width, target_height)


def harmonize_text_layers(layers: list[dict[str, Any]]) -> None:
    text_layers = [layer for layer in layers if layer.get("type") == "text" and layer.get("style", {}).get("fontSize")]
    rows: list[list[dict[str, Any]]] = []
    for layer in sorted(text_layers, key=lambda item: (item["bbox"]["y"] + item["bbox"]["height"] / 2, item["bbox"]["x"])):
        box = layer["bbox"]
        center = box["y"] + box["height"] / 2
        placed = False
        for row in rows:
            first = row[0]["bbox"]
            first_center = first["y"] + first["height"] / 2
            tolerance = max(8.0, min(float(first["height"]), float(box["height"])) * 0.42)
            if abs(center - first_center) <= tolerance:
                row.append(layer)
                placed = True
                break
        if not placed:
            rows.append([layer])
    for row in rows:
        harmonize_text_row(row)


def harmonize_text_row(row: list[dict[str, Any]]) -> None:
    if len(row) < 3:
        return
    clusters: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for layer in row:
        style = layer.get("style") or {}
        key = (
            str(style.get("fontFamily") or ""),
            color_family(str(style.get("color") or "")),
        )
        clusters.setdefault(key, []).append(layer)
    for items in clusters.values():
        if len(items) < 3:
            continue
        sizes = [int(item["style"]["fontSize"]) for item in items]
        mode = row_font_size_mode(sizes)
        threshold = max(3, min(6, round(mode * 0.18)))
        eligible = [item for item in items if abs(int(item["style"]["fontSize"]) - mode) <= threshold]
        if len(eligible) < 2:
            continue
        for item in eligible:
            old_size = int(item["style"]["fontSize"])
            if old_size == mode:
                continue
            item["style"]["fontSize"] = mode
            item["style"]["lineHeight"] = max(8, min(120, math.ceil(mode * 1.12)))
            fit = item.setdefault("textFit", {})
            fit["rowHarmonized"] = 1
            fit["rowOriginalFontSize"] = old_size
            fit["fontSize"] = mode
            fit["lineHeight"] = item["style"]["lineHeight"]


def row_font_size_mode(sizes: list[int]) -> int:
    counts: dict[int, int] = {}
    for size in sizes:
        counts[size] = counts.get(size, 0) + 1
    best_count = max(counts.values())
    candidates = [size for size, count in counts.items() if count == best_count]
    if best_count > 1:
        return int(round(float(np.median(candidates))))
    return int(round(float(np.median(sizes))))


def color_family(value: str) -> str:
    rgb = rgb_tuple_from_hex(value)
    if rgb is None:
        return "unknown"
    r, g, b = rgb
    if max(rgb) - min(rgb) < 28:
        return "neutral"
    if b >= r + 28 and b >= g + 16:
        return "blue"
    if g >= r + 18 and g >= b + 18:
        return "green"
    if r >= g + 18 and r >= b + 18:
        return "red_or_orange"
    return "chromatic"
