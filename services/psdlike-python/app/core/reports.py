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


def write_diagnostics(output_path: Path, layer_stack: dict[str, Any]) -> None:
    diagnostics = layer_stack["diagnostics"]
    lines = [
        "# PSD-like Layer Decomposition Diagnostics",
        "",
        f"- source: `{layer_stack['sourceImage']}`",
        f"- ocr: `{layer_stack.get('ocr', '')}`",
        f"- canvas: {layer_stack['canvas']['width']}x{layer_stack['canvas']['height']}",
        f"- layers: {diagnostics['layerCount']}",
        f"- text layers: {diagnostics['textLayerCount']}",
        f"- raster layers: {diagnostics['rasterLayerCount']}",
        f"- shape layers: {diagnostics['shapeLayerCount']}",
        f"- surface shape layers: {diagnostics.get('surfaceShapeLayerCount', 0)}",
        f"- control surface shape layers: {diagnostics.get('controlSurfaceShapeLayerCount', 0)}",
        f"- page background: {diagnostics.get('pageBackground', '')}",
        f"- rejected candidates: {diagnostics['rejectedCandidateCount']}",
        f"- full page visible raster: {diagnostics['fullPageVisibleRaster']}",
        f"- tiny raster fragments: {diagnostics['tinyRasterFragments']}",
        f"- text overlap raster: {diagnostics['textOverlapRaster']}",
        f"- raw text overlap raster: {diagnostics['rawTextOverlapRaster']}",
        f"- raster text knockout: {diagnostics['rasterTextKnockoutCount']}",
        f"- text-owned raster suppressed: {diagnostics.get('textOwnedRasterSuppressedCount', 0)}",
        f"- raster covered text blocks: {diagnostics['rasterCoveredTextBlockCount']}",
        f"- missing assets: {diagnostics['missingAssetCount']}",
        "",
        "## Rejection Reasons",
        "",
    ]
    counts: dict[str, int] = {}
    for item in layer_stack.get("rejected", []):
        key = f"{item.get('kind')}:{item.get('reason')}"
        counts[key] = counts.get(key, 0) + 1
    if counts:
        for key, count in sorted(counts.items()):
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- none")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ownership_report(output_path: Path, layer_stack: dict[str, Any]) -> None:
    raster_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "raster"]
    text_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "text"]
    coverage_by_text: dict[str, list[dict[str, Any]]] = {layer["id"]: [] for layer in text_layers}

    for raster in raster_layers:
        ownership = raster.get("ownership", {})
        for block in ownership.get("coveredTextBlocks", []):
            text_id = str(block.get("id", ""))
            if text_id in coverage_by_text:
                coverage_by_text[text_id].append(
                    {
                        "rasterId": raster["id"],
                        "coverage": block.get("coverage", 0),
                    }
                )

    report = {
        "version": "psd_like_ownership_report.v1",
        "diagnostics": {
            "rasterLayerCount": len(raster_layers),
            "textLayerCount": len(text_layers),
            "visibleTextOwnershipConflict": layer_stack["diagnostics"]["textOverlapRaster"],
            "rasterTextKnockoutCount": layer_stack["diagnostics"]["rasterTextKnockoutCount"],
            "rasterCoveredTextBlockCount": layer_stack["diagnostics"]["rasterCoveredTextBlockCount"],
        },
        "rasterOwnership": [
            {
                "id": layer["id"],
                "bbox": layer["bbox"],
                "asset": layer.get("asset", ""),
                "ownership": layer.get("ownership", {}),
            }
            for layer in raster_layers
        ],
        "textCoverage": coverage_by_text,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
