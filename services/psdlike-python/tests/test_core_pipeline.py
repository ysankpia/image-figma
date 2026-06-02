from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from app.core.model_evidence import apply_model_evidence
from app.core.ocr import load_ocr_blocks
from app.core.pipeline import run_pipeline
from app.core.schema import BBox, OCRBlock, intersection_area, ioa, iou


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
    image_path, ocr_path = write_button_fixture(tmp_path)

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


def test_model_evidence_absent_keeps_pipeline_metadata_free(tmp_path: Path) -> None:
    image_path, ocr_path = write_button_fixture(tmp_path)

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    dsl = json.loads(result.dsl_path.read_text(encoding="utf-8"))

    assert result.semantic_evidence_path is None
    assert "semanticEvidence" not in layer_stack
    assert "semanticEvidence" not in dsl.get("meta", {})
    assert all(not layer.get("semanticTags") for layer in layer_stack["layers"])
    assert all(not child.get("meta", {}).get("semanticTags") for child in dsl["root"]["children"])


def test_model_evidence_textbutton_tags_existing_shape_without_visible_changes(tmp_path: Path) -> None:
    image_path, ocr_path = write_button_fixture(tmp_path)
    baseline = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "baseline")
    baseline_stack = json.loads(baseline.layer_stack_path.read_text(encoding="utf-8"))
    shape = next(layer for layer in baseline_stack["layers"] if layer["type"] == "shape")
    model_path = write_model_evidence(tmp_path, "TextButton", shape["bbox"], confidence=0.87)

    result = run_pipeline(
        image_path=image_path,
        ocr_path=ocr_path,
        out_dir=tmp_path / "model",
        model_evidence_path=model_path,
    )
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    dsl = json.loads(result.dsl_path.read_text(encoding="utf-8"))

    assert result.semantic_evidence_path is not None
    assert result.semantic_evidence_path.exists()
    assert visible_signature(layer_stack) == visible_signature(baseline_stack)
    assert layer_stack["diagnostics"]["semanticTagCount"] > 0
    tagged_shapes = [layer for layer in layer_stack["layers"] if layer["type"] == "shape" and layer.get("semanticTags")]
    assert tagged_shapes
    assert tagged_shapes[0]["semanticTags"][0]["tag"] == "TextButton"
    tagged_nodes = [child for child in dsl["root"]["children"] if child.get("meta", {}).get("semanticTags")]
    assert tagged_nodes
    assert dsl["meta"]["semanticEvidence"]["diagnostics"]["modelEvidencePresent"] is True


def test_model_text_detection_does_not_create_or_tag_text_layer(tmp_path: Path) -> None:
    image_path, ocr_path = write_button_fixture(tmp_path)
    baseline = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "baseline")
    baseline_stack = json.loads(baseline.layer_stack_path.read_text(encoding="utf-8"))
    text = next(layer for layer in baseline_stack["layers"] if layer["type"] == "text")
    model_path = write_model_evidence(tmp_path, "Text", text["bbox"], confidence=0.91)

    result = run_pipeline(
        image_path=image_path,
        ocr_path=ocr_path,
        out_dir=tmp_path / "model",
        model_evidence_path=model_path,
    )
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert visible_signature(layer_stack) == visible_signature(baseline_stack)
    assert layer_stack["diagnostics"]["textLayerCount"] == baseline_stack["diagnostics"]["textLayerCount"]
    assert not [layer for layer in layer_stack["layers"] if layer["type"] == "text" and layer.get("semanticTags")]


def test_model_image_detection_tags_existing_raster_without_new_asset(tmp_path: Path) -> None:
    layer_stack = manual_layer_stack()
    model_path = write_model_evidence(tmp_path, "Image", layer_stack["layers"][0]["bbox"], confidence=0.93)
    before = json.loads(json.dumps(layer_stack))

    semantic_path = apply_model_evidence(layer_stack, model_path, [], tmp_path / "semantic_evidence.v1.json")

    assert semantic_path is not None
    assert semantic_path.exists()
    assert layer_stack["diagnostics"]["semanticTagCount"] == 1
    assert layer_stack["layers"][0]["semanticTags"][0]["tag"] == "Image"
    assert visible_signature(layer_stack) == visible_signature(before)
    assert layer_stack["layers"][0]["asset"] == before["layers"][0]["asset"]


def test_malformed_model_evidence_is_ignored_without_crashing(tmp_path: Path) -> None:
    layer_stack = manual_layer_stack()
    bad_path = tmp_path / "bad_model_evidence.v1.json"
    bad_path.write_text("{bad json", encoding="utf-8")

    semantic_path = apply_model_evidence(layer_stack, bad_path, [], tmp_path / "semantic_evidence.v1.json")

    assert semantic_path is not None
    assert layer_stack["diagnostics"]["modelEvidencePresent"] is False
    assert "JSONDecodeError" in layer_stack["diagnostics"]["modelEvidenceIgnoredReason"]


def test_canvas_mismatch_model_evidence_is_ignored_without_crashing(tmp_path: Path) -> None:
    layer_stack = manual_layer_stack()
    model_path = tmp_path / "model_evidence.v1.json"
    model_path.write_text(
        json.dumps(
            {
                "version": "model_evidence.v1",
                "canvas": {"width": 999, "height": 100},
                "detections": [],
            }
        ),
        encoding="utf-8",
    )

    semantic_path = apply_model_evidence(layer_stack, model_path, [], tmp_path / "semantic_evidence.v1.json")

    assert semantic_path is not None
    assert layer_stack["diagnostics"]["modelEvidencePresent"] is False
    assert "canvas_mismatch" in layer_stack["diagnostics"]["modelEvidenceIgnoredReason"]


def test_semantic_tags_do_not_mutate_visible_layer_fields(tmp_path: Path) -> None:
    layer_stack = manual_layer_stack()
    before = visible_signature(layer_stack)
    model_path = write_model_evidence(tmp_path, "TextButton", layer_stack["layers"][1]["bbox"], confidence=0.76)

    apply_model_evidence(
        layer_stack,
        model_path,
        [OCRBlock(id="text_0001", text="OK", bbox=BBox(65, 45, 20, 14), confidence=0.99)],
        tmp_path / "semantic_evidence.v1.json",
    )

    assert visible_signature(layer_stack) == before
    assert layer_stack["layers"][1]["semanticTags"][0]["authority"] == "hint"


def write_button_fixture(tmp_path: Path) -> tuple[Path, Path]:
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
    return image_path, ocr_path


def write_model_evidence(tmp_path: Path, class_name: str, bbox: dict[str, int], confidence: float = 0.9) -> Path:
    path = tmp_path / f"{class_name}.model_evidence.v1.json"
    path.write_text(
        json.dumps(
            {
                "version": "model_evidence.v1",
                "canvas": {"width": 240, "height": 120},
                "detections": [
                    {
                        "id": "det_0001",
                        "className": class_name,
                        "classId": 1,
                        "confidence": confidence,
                        "bbox": bbox,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def manual_layer_stack() -> dict:
    return {
        "version": "layer_stack.v1",
        "sourceImage": "synthetic.png",
        "ocr": "",
        "canvas": {"width": 240, "height": 120},
        "pageBackground": "#ffffff",
        "layers": [
            {
                "id": "raster_0001",
                "type": "raster",
                "bbox": {"x": 20, "y": 20, "width": 80, "height": 70},
                "z": 20001,
                "asset": "assets/raster_0001.png",
                "style": {},
                "text": "do-not-touch",
                "reason": "foreground_object_on_surface",
            },
            {
                "id": "shape_0001",
                "type": "shape",
                "bbox": {"x": 50, "y": 36, "width": 120, "height": 42},
                "z": 12001,
                "style": {"fill": "#f5b428", "cornerRadius": 18},
                "reason": "ocr_anchored_control_surface",
            },
            {
                "id": "text_0001",
                "type": "text",
                "bbox": {"x": 65, "y": 45, "width": 20, "height": 14},
                "z": 30001,
                "text": "OK",
                "style": {"fill": "#111111", "fontSize": 14},
                "reason": "ocr_authority",
            },
        ],
        "diagnostics": {
            "layerCount": 3,
            "textLayerCount": 1,
            "rasterLayerCount": 1,
            "shapeLayerCount": 1,
            "missingAssetCount": 0,
            "shapeAssetCount": 0,
            "fullPageVisibleRaster": 0,
        },
    }


def visible_signature(layer_stack: dict) -> list[dict]:
    return [
        {
            "id": layer.get("id"),
            "type": layer.get("type"),
            "bbox": layer.get("bbox"),
            "z": layer.get("z"),
            "asset": layer.get("asset"),
            "style": layer.get("style"),
            "text": layer.get("text"),
        }
        for layer in layer_stack["layers"]
    ]
