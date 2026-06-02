from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from app.core.ocr import load_ocr_blocks
from app.core.pipeline import run_pipeline
from app.core.schema import BBox, intersection_area, ioa, iou


def test_bbox_geometry() -> None:
    a = BBox(10, 10, 20, 20)
    b = BBox(20, 20, 20, 20)
    assert intersection_area(a, b) == 100
    assert round(iou(a, b), 4) == round(100 / 700, 4)
    assert ioa(BBox(12, 12, 4, 4), a) == 1.0


def test_load_ocr_blocks_filters_confidence_and_clamps(tmp_path: Path) -> None:
    artifact = {
        "version": "ocr_blocks.v1",
        "blocks": [
            {"id": "keep", "text": "OK", "bbox": {"x": 5, "y": 5, "width": 40, "height": 16}, "confidence": 0.9},
            {"id": "drop", "text": "LOW", "bbox": {"x": 1, "y": 1, "width": 20, "height": 12}, "confidence": 0.2},
            {"id": "empty", "text": "", "bbox": {"x": 1, "y": 1, "width": 20, "height": 12}, "confidence": 1.0},
        ],
    }
    path = tmp_path / "ocr.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    blocks = load_ocr_blocks(path, 100, 50, 0.7)
    assert [block.id for block in blocks] == ["keep"]
    assert blocks[0].bbox == BBox(5, 5, 40, 16)


def test_pipeline_outputs_button_shape_text_and_assets(tmp_path: Path) -> None:
    image_path = tmp_path / "button.png"
    image = Image.new("RGB", (240, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((50, 42, 190, 82), radius=18, fill=(245, 180, 40))
    draw.text((92, 53), "OK", fill=(20, 20, 20))
    image.save(image_path)

    ocr_path = tmp_path / "ocr_blocks.v1.json"
    ocr_path.write_text(
        json.dumps(
            {
                "version": "ocr_blocks.v1",
                "blocks": [
                    {
                        "id": "text_0001",
                        "text": "OK",
                        "bbox": {"x": 92, "y": 53, "width": 18, "height": 12},
                        "confidence": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=out_dir)
    assert result.layer_stack_path.exists()
    assert result.dsl_path.exists()
    assert result.preview_html_path.exists()
    assert result.diagnostics_path.exists()
    assert result.diagnostics["missingAssetCount"] == 0
    assert result.diagnostics["shapeAssetCount"] == 0
    assert result.diagnostics["fullPageVisibleRaster"] == 0

    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    text_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "text"]
    shape_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "shape"]
    raster_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "raster"]
    assert len(text_layers) == 1
    assert shape_layers
    assert all(not layer.get("asset") for layer in shape_layers)
    assert all(text_layers[0]["z"] > layer["z"] for layer in shape_layers + raster_layers)

    dsl = json.loads(result.dsl_path.read_text(encoding="utf-8"))
    asset_paths = {asset["assetId"]: asset.get("path") or asset.get("url") for asset in dsl.get("assets", [])}
    for child in dsl["root"]["children"]:
        if child["type"] == "image":
            asset_id = child["image"]["assetId"]
            assert asset_id in asset_paths
            assert (out_dir / asset_paths[asset_id]).exists()
