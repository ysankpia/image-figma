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
        text_style = estimate_text_style(rgb, block.bbox, block.text)
        layers.append(
            {
                "id": block.id or f"text_{index:04d}",
                "type": "text",
                "bbox": block.bbox.to_dict(),
                "z": 30000 + index,
                "text": block.text,
                "style": text_style["style"],
                "textFit": text_style["diagnostics"],
                "confidence": round(block.confidence, 4),
                "reason": "ocr_authority",
            }
        )

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
    control_surfaces = sum(
        1
        for item in shape_candidates
        if item.reason in {"editable_control_surface_from_raster", "ocr_anchored_control_surface", "model_assisted_control_surface"}
    )
    ocr_control_surfaces = sum(1 for item in shape_candidates if item.reason == "ocr_anchored_control_surface")
    model_control_surfaces = sum(1 for item in shape_candidates if item.reason == "model_assisted_control_surface")
    control_owned_raster_suppressed = sum(1 for item in rejected if item.get("kind") == "control_owned_raster_suppressed")
    control_residual_suppressed = sum(1 for item in rejected if item.get("reason", "").startswith("control_residual_"))
    text_owned_raster_suppressed = sum(1 for item in rejected if item.get("kind") == "text_owned_raster_suppressed")
    media_owned_text_count = len(media_owned_text_ids)
    media_text_owner_raster_count = len({str(item.get("ownerRasterId", "")) for item in media_owned_text_decisions if item.get("ownerRasterId")})
    text_fit_shrink_count = sum(1 for item in layers if item["type"] == "text" and item.get("textFit", {}).get("shrink", 0) > 0)
    dark_control_surfaces = sum(1 for item in shape_candidates if item.scores.get("darkControlSurface", 0.0) >= 1.0)
    shape_asset_count = sum(1 for item in layers if item["type"] == "shape" and item.get("asset"))
    page_background = color_hex(estimate_background_color(rgb))

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
            "darkControlSurfaceCount": dark_control_surfaces,
            "rasterLayerCount": len(raster_candidates),
            "shapeLayerCount": len(shape_candidates),
            "surfaceShapeLayerCount": surface_shapes,
            "backgroundPlateLayerCount": background_plates,
            "controlSurfaceShapeLayerCount": control_surfaces,
            "ocrAnchoredControlSurfaceCount": ocr_control_surfaces,
            "modelAssistedControlSurfaceCount": model_control_surfaces,
            "controlOwnedRasterSuppressedCount": control_owned_raster_suppressed,
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
