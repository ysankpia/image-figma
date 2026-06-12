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


def build_draft_runtime_dsl(layer_stack: dict[str, Any], rgb: np.ndarray) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []

    for layer in sorted(layer_stack["layers"], key=lambda item: (item["z"], item["bbox"]["y"], item["bbox"]["x"], item["id"])):
        layer_type = layer["type"]
        bbox = layer["bbox"]
        node: dict[str, Any] = {
            "id": layer["id"],
            "type": "image" if layer_type == "raster" else layer_type,
            "name": layer_name(layer),
            "bbox": bbox,
            "z": layer["z"],
            "meta": {
                "source": "psd_like_layer_stack",
                "reason": layer.get("reason", ""),
            },
        }
        if layer.get("semanticTags"):
            node["meta"]["semanticTags"] = layer["semanticTags"]

        if layer_type == "raster":
            asset_id = f"asset_{layer['id']}"
            node["image"] = {"assetId": asset_id, "mode": "fill"}
            node["meta"]["ownership"] = layer.get("ownership", {})
            assets.append(
                {
                    "assetId": asset_id,
                    "type": "image",
                    "url": layer.get("asset", ""),
                    "path": layer.get("asset", ""),
                    "format": "png",
                    "width": bbox["width"],
                    "height": bbox["height"],
                    "meta": {"sourceLayerId": layer["id"]},
                }
            )
        elif layer_type == "shape":
            node["style"] = layer.get("style", {})
        elif layer_type == "text":
            text = str(layer.get("text", ""))
            if not text.strip():
                continue
            node["text"] = {"characters": text}
            box = BBox(int(bbox["x"]), int(bbox["y"]), int(bbox["width"]), int(bbox["height"]))
            node["style"] = layer.get("style") or estimate_text_style(rgb, box, text)["style"]
            node["meta"]["textFit"] = layer.get("textFit", {})

        children.append(node)

    canvas = layer_stack["canvas"]
    background = str(layer_stack.get("pageBackground") or color_hex(estimate_background_color(rgb)))
    payload = {
        "version": "1.0",
        "kind": "draft_runtime",
        "taskId": "psd_like_experiment",
        "page": {
            "name": "PSD-like Draft Experiment",
            "width": canvas["width"],
            "height": canvas["height"],
            "background": background,
        },
        "root": {
            "id": "root",
            "type": "frame",
            "name": "PSD-like Draft",
            "bbox": {"x": 0, "y": 0, "width": canvas["width"], "height": canvas["height"]},
            "children": children,
        },
        "assets": assets,
        "meta": {
            "pipeline": "psd_like_layer_decomposition_experiment.v1",
            "sourceImage": layer_stack.get("sourceImage", ""),
            "diagnostics": layer_stack.get("diagnostics", {}),
        },
    }
    if layer_stack.get("semanticEvidence"):
        payload["meta"]["semanticEvidence"] = layer_stack["semanticEvidence"]
    return payload


def layer_name(layer: dict[str, Any]) -> str:
    if layer["type"] == "text":
        text = str(layer.get("text", "")).strip()
        return text[:32] if text else layer["id"]
    if layer["type"] == "raster":
        return f"Raster {layer['id']}"
    return f"Shape {layer['id']}"
