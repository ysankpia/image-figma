from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from app.core.layers import build_layer_stack
from app.core.model_evidence import apply_model_evidence
from app.core.media_text import assign_media_owned_text_blocks
from app.core.ocr import load_ocr_blocks
from app.core.pipeline import PipelineOptions, run_pipeline
from app.core.runtime import wire_runtime_namespace
from app.core.schema import BBox, Candidate, OCRBlock, intersection_area, ioa, iou
from app.core.style import TextStyleContext, sample_text_color_with_diagnostics
from app.core.controls import suppress_container_parent_shapes, suppress_control_owned_shapes


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


def test_low_confidence_model_control_does_not_change_visible_layers(tmp_path: Path) -> None:
    image_path, ocr_path = write_plain_text_fixture(tmp_path)
    baseline = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "baseline")
    baseline_stack = json.loads(baseline.layer_stack_path.read_text(encoding="utf-8"))
    model_path = write_model_evidence(tmp_path, "TextButton", {"x": 32, "y": 36, "width": 112, "height": 36}, confidence=0.42)

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "model", model_evidence_path=model_path)
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert visible_signature(layer_stack) == visible_signature(baseline_stack)
    assert layer_stack["diagnostics"]["modelControlAcceptedCount"] == 0
    assert layer_stack["diagnostics"]["modelControlRejectedReasons"]["below_control_trigger_confidence"] == 1


def test_high_confidence_model_control_still_requires_physical_gate(tmp_path: Path) -> None:
    image_path, ocr_path = write_plain_text_fixture(tmp_path)
    model_path = write_model_evidence(tmp_path, "TextButton", {"x": 32, "y": 36, "width": 112, "height": 36}, confidence=0.91)

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "model", model_evidence_path=model_path)
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert layer_stack["diagnostics"]["modelControlSearchWindowCount"] == 1
    assert layer_stack["diagnostics"]["modelControlAcceptedCount"] == 0
    assert not [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape" and layer.get("reason") == "model_assisted_control_surface"
    ]


def test_valid_model_control_emits_shape_and_keeps_text_above(tmp_path: Path) -> None:
    image_path, ocr_path = write_model_control_fixture(tmp_path)
    model_path = write_model_evidence(
        tmp_path,
        "TextButton",
        {"x": 50, "y": 42, "width": 140, "height": 40},
        confidence=0.88,
        canvas={"width": 400, "height": 300},
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "model", model_evidence_path=model_path)
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    model_shapes = [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape" and layer.get("reason") == "model_assisted_control_surface"
    ]
    text_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "text"]
    assert model_shapes
    assert layer_stack["diagnostics"]["modelControlAcceptedCount"] >= 1
    assert all(text_layers[0]["z"] > shape["z"] for shape in model_shapes)
    assert layer_stack["semanticEvidence"]["diagnostics"]["modelOwnershipDecisionCount"] >= 1
    assert (result.out_dir / "semantic_evidence_report.md").exists()
    tags_summary = json.loads((result.out_dir / "semantic_tags_summary.json").read_text(encoding="utf-8"))
    ownership_decisions = json.loads((result.out_dir / "model_ownership_decisions.v1.json").read_text(encoding="utf-8"))
    assert tags_summary["diagnostics"]["modelOwnershipDecisionCount"] >= 1
    assert ownership_decisions["summary"]["acceptedCount"] >= 1


def test_model_image_detection_with_no_texture_is_rejected(tmp_path: Path) -> None:
    image_path = write_plain_media_fixture(tmp_path)
    model_path = write_model_evidence(
        tmp_path,
        "Image",
        {"x": 36, "y": 34, "width": 80, "height": 46},
        confidence=0.90,
        canvas={"width": 200, "height": 160},
    )

    result = run_pipeline(image_path=image_path, out_dir=tmp_path / "model", model_evidence_path=model_path)
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert layer_stack["diagnostics"]["modelMediaSearchWindowCount"] == 1
    assert layer_stack["diagnostics"]["modelMediaAcceptedCount"] == 0
    assert layer_stack["diagnostics"]["modelMediaRejectedCount"] == 1
    assert layer_stack["diagnostics"]["modelMediaRejectedReasons"]["missing_local_media_component"] == 1


def test_model_icon_detection_with_texture_can_add_raster(tmp_path: Path) -> None:
    image_path = write_texture_icon_fixture(tmp_path)
    model_path = write_model_evidence(
        tmp_path,
        "Icon",
        {"x": 48, "y": 48, "width": 24, "height": 24},
        confidence=0.86,
        canvas={"width": 200, "height": 160},
    )

    result = run_pipeline(
        image_path=image_path,
        out_dir=tmp_path / "model",
        model_evidence_path=model_path,
        options=PipelineOptions(raster_min_area=2000),
    )
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    dsl = json.loads(result.dsl_path.read_text(encoding="utf-8"))

    model_rasters = [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "raster" and layer.get("reason") == "model_assisted_media_refinement"
    ]
    assert model_rasters
    assert layer_stack["diagnostics"]["modelMediaAddedRasterCount"] >= 1
    assert layer_stack["diagnostics"]["modelAssistedMediaRasterCount"] >= 1
    assert layer_stack["diagnostics"]["missingAssetCount"] == 0
    assert layer_stack["diagnostics"]["fullPageVisibleRaster"] == 0
    asset_ids = {asset["assetId"] for asset in dsl.get("assets", [])}
    assert asset_ids


def test_model_image_detection_overlapping_control_is_rejected(tmp_path: Path) -> None:
    image_path, ocr_path = write_model_control_fixture(tmp_path)
    model_path = write_model_evidence(
        tmp_path,
        "Image",
        {"x": 50, "y": 42, "width": 140, "height": 40},
        confidence=0.91,
        canvas={"width": 400, "height": 300},
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "model", model_evidence_path=model_path)
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert layer_stack["diagnostics"]["controlSurfaceShapeLayerCount"] >= 1
    assert layer_stack["diagnostics"]["modelMediaAcceptedCount"] == 0
    assert layer_stack["diagnostics"]["modelMediaRejectedReasons"]["overlaps_accepted_control"] == 1


def test_model_media_candidate_can_own_internal_ocr_after_physical_gate() -> None:
    block = OCRBlock(id="text_0001", text="SALE", bbox=BBox(72, 70, 42, 14), confidence=0.98)
    text_mask = blank_text_mask(220, 180, [block])
    raster = Candidate(
        id="model_media_det_0001",
        kind="raster",
        bbox=BBox(20, 30, 170, 112),
        score=0.82,
        scores={"texture": 0.58, "edge": 0.48, "entropy": 0.46, "unique": 0.38, "textOverlap": 0.03},
        reason="model_assisted_media_refinement",
    )

    media_owned_ids, decisions = assign_media_owned_text_blocks(
        raster_candidates=[raster],
        ocr_blocks=[block],
        text_mask=text_mask,
        image_width=220,
        image_height=180,
    )

    assert media_owned_ids == {"text_0001"}
    assert decisions[0]["ownerRasterId"] == "model_media_det_0001"


def test_chart_tick_near_graphic_line_does_not_create_control_shape(tmp_path: Path) -> None:
    image_path = tmp_path / "chart_ticks.png"
    image = Image.new("RGB", (320, 220), "white")
    draw = ImageDraw.Draw(image)
    for text, y in [("18万", 54), ("12万", 92), ("6万", 130), ("0", 168)]:
        draw.text((252, y), text, fill=(30, 30, 30))
    draw.line((210, 50, 286, 176), fill=(64, 116, 249), width=4)
    image.save(image_path)
    ocr_path = write_ocr_artifact(
        tmp_path,
        "chart_ticks.ocr_blocks.v1.json",
        [
            ("text_0001", "18万", 252, 54, 28, 12),
            ("text_0002", "12万", 252, 92, 28, 12),
            ("text_0003", "6万", 252, 130, 22, 12),
            ("text_0004", "0", 252, 168, 10, 12),
        ],
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert not [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape" and layer.get("reason") == "ocr_anchored_control_surface"
    ]
    assert layer_stack["diagnostics"]["controlTextRoleRejectedCount"] >= 1


def test_numeric_button_with_closed_boundary_remains_shape(tmp_path: Path) -> None:
    image_path = tmp_path / "numeric_button.png"
    image = Image.new("RGB", (260, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((72, 34, 188, 82), radius=20, fill=(38, 94, 247))
    draw.text((114, 51), "24", fill=(255, 255, 255))
    image.save(image_path)
    ocr_path = write_ocr_artifact(tmp_path, "numeric_button.ocr_blocks.v1.json", [("text_0001", "24", 114, 51, 18, 12)])

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape" and layer.get("reason") == "ocr_anchored_control_surface"
    ]


def test_large_dark_data_card_does_not_promote_to_control(tmp_path: Path) -> None:
    image_path = tmp_path / "dark_card.png"
    image = Image.new("RGB", (360, 220), (0, 2, 11))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 38, 332, 150), fill=(2, 8, 20))
    draw.text((48, 62), "Total", fill=(180, 188, 204))
    draw.text((48, 94), "186,745.23", fill=(245, 247, 255))
    draw.text((48, 126), "$1,335,567.98", fill=(160, 168, 184))
    image.save(image_path)
    ocr_path = write_ocr_artifact(
        tmp_path,
        "dark_card.ocr_blocks.v1.json",
        [
            ("text_0001", "Total", 48, 62, 42, 14),
            ("text_0002", "186,745.23", 48, 94, 100, 18),
            ("text_0003", "$1,335,567.98", 48, 126, 128, 14),
        ],
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert not [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape"
        and layer.get("reason") in {"ocr_anchored_control_surface", "editable_control_surface_from_raster"}
        and layer["bbox"]["width"] > 220
    ]


def test_model_control_inherits_chart_tick_rejection(tmp_path: Path) -> None:
    image_path = tmp_path / "model_chart_tick.png"
    image = Image.new("RGB", (320, 220), "white")
    draw = ImageDraw.Draw(image)
    for text, y in [("18万", 54), ("12万", 92), ("6万", 130), ("0", 168)]:
        draw.text((252, y), text, fill=(30, 30, 30))
    draw.line((210, 50, 286, 176), fill=(64, 116, 249), width=4)
    image.save(image_path)
    ocr_path = write_ocr_artifact(
        tmp_path,
        "model_chart_tick.ocr_blocks.v1.json",
        [
            ("text_0001", "18万", 252, 54, 28, 12),
            ("text_0002", "12万", 252, 92, 28, 12),
            ("text_0003", "6万", 252, 130, 22, 12),
            ("text_0004", "0", 252, 168, 10, 12),
        ],
    )
    model_path = write_model_evidence(
        tmp_path,
        "TextButton",
        {"x": 244, "y": 48, "width": 58, "height": 34},
        confidence=0.91,
        canvas={"width": 320, "height": 220},
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out", model_evidence_path=model_path)
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert layer_stack["diagnostics"]["modelControlAcceptedCount"] == 0
    assert layer_stack["diagnostics"]["modelControlRejectedReasons"]["chart_tick_like_surface_not_control"] >= 1


def test_multi_text_container_surface_does_not_create_overlapping_controls(tmp_path: Path) -> None:
    image_path = tmp_path / "multi_text_container.png"
    image = Image.new("RGB", (360, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((36, 42, 324, 150), radius=18, fill=(42, 124, 212))
    draw.text((62, 62), "Title", fill=(255, 255, 255))
    draw.text((62, 92), "Issuer", fill=(235, 245, 255))
    draw.text((62, 122), "3301****", fill=(235, 245, 255))
    image.save(image_path)
    ocr_path = write_ocr_artifact(
        tmp_path,
        "multi_text_container.ocr_blocks.v1.json",
        [
            ("text_0001", "Title", 62, 62, 34, 12),
            ("text_0002", "Issuer", 62, 92, 42, 12),
            ("text_0003", "3301****", 62, 122, 66, 12),
        ],
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    control_shapes = [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape" and layer.get("scores", {}).get("confirmedControlSurface", 0) >= 1
    ]
    assert not control_shapes
    assert layer_stack["diagnostics"]["localSurfaceContainerCount"] >= 1


def test_model_control_without_pixel_surface_is_rejected(tmp_path: Path) -> None:
    image_path, ocr_path = write_plain_text_fixture(tmp_path)
    model_path = write_model_evidence(
        tmp_path,
        "TextButton",
        {"x": 52, "y": 42, "width": 92, "height": 36},
        confidence=0.94,
        canvas={"width": 240, "height": 120},
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out", model_evidence_path=model_path)
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert layer_stack["diagnostics"]["modelControlAcceptedCount"] == 0
    assert not [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape" and layer.get("reason") == "model_assisted_control_surface"
    ]


def test_solid_text_button_misdetected_as_image_does_not_add_edge_raster(tmp_path: Path) -> None:
    image_path = tmp_path / "solid_button_as_image.png"
    image = Image.new("RGB", (260, 140), (250, 250, 250))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((80, 48, 180, 92), radius=20, fill=(35, 92, 247))
    draw.text((111, 60), "办理", fill=(255, 255, 255))
    image.save(image_path)
    ocr_path = write_ocr_artifact(tmp_path, "solid_button_as_image.ocr_blocks.v1.json", [("text_0001", "办理", 111, 60, 42, 22)])
    model_path = write_model_evidence(
        tmp_path,
        "Image",
        {"x": 78, "y": 46, "width": 104, "height": 48},
        confidence=0.84,
        canvas={"width": 260, "height": 140},
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out", model_evidence_path=model_path)
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape" and layer.get("scores", {}).get("confirmedControlSurface", 0.0) >= 1.0
    ]
    assert not [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "raster" and layer.get("reason") == "model_assisted_media_refinement"
    ]
    assert layer_stack["diagnostics"]["modelMediaRejectedReasons"].get(
        "control_like_solid_text_surface", 0
    ) + layer_stack["diagnostics"]["modelMediaRejectedReasons"].get("overlaps_accepted_control", 0) >= 1
    text = next(layer for layer in layer_stack["layers"] if layer["type"] == "text")
    control = next(
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape" and layer.get("scores", {}).get("confirmedControlSurface", 0.0) >= 1.0
    )
    text_center_y = text["bbox"]["y"] + text["bbox"]["height"] / 2
    control_center_y = control["bbox"]["y"] + control["bbox"]["height"] / 2
    assert abs(text_center_y - control_center_y) <= 1.5
    assert text["textFit"]["ownerBboxRecentered"] == 1
    assert layer_stack["diagnostics"]["textOwnerBboxRecenteredCount"] >= 1


def test_control_owned_shape_fragment_is_suppressed() -> None:
    control = Candidate(
        "control",
        "shape",
        BBox(80, 48, 100, 44),
        0.9,
        {"confirmedControlSurface": 1.0, "fillR": 35.0, "fillG": 92.0, "fillB": 247.0},
        "ocr_anchored_control_surface",
    )
    fragment = Candidate(
        "fragment",
        "shape",
        BBox(70, 42, 110, 54),
        0.4,
        {},
        "low_texture_solid_region",
    )

    kept, suppressed = suppress_control_owned_shapes([fragment, control])

    assert [item.id for item in kept] == ["control"]
    assert suppressed[0]["kind"] == "control_owned_shape_suppressed"
    assert suppressed[0]["reason"] == "control_surface_parent_shape_fragment"


def test_container_parent_shape_is_suppressed_by_sibling_surfaces() -> None:
    parent = Candidate("parent", "shape", BBox(24, 80, 360, 120), 0.5, {}, "low_texture_solid_region")
    children = [
        Candidate(f"card_{index}", "shape", BBox(40 + index * 112, 96, 96, 72), 0.8, {"surfaceRoleContainer": 1.0}, "local_container_surface")
        for index in range(3)
    ]

    kept, suppressed = suppress_container_parent_shapes([parent, *children])

    assert [item.id for item in kept] == [child.id for child in children]
    assert suppressed[0]["kind"] == "container_parent_shape_suppressed"
    assert suppressed[0]["reason"] == "container_children_own_surface"
    assert suppressed[0]["childSurfaceCount"] == 3


def test_multi_text_sibling_cards_materialize_as_container_surfaces(tmp_path: Path) -> None:
    image_path = tmp_path / "sibling_cards.png"
    image = Image.new("RGB", (520, 420), (18, 20, 24))
    draw = ImageDraw.Draw(image)
    colors = [(54, 88, 139), (47, 110, 75), (38, 75, 127)]
    rows: list[tuple[str, str, int, int, int, int]] = []
    for index, (x, color) in enumerate(zip((32, 188, 344), colors), start=1):
        draw.rounded_rectangle((x, 62, x + 132, 154), radius=8, fill=color)
        draw.text((x + 12, 80), f"Card {index}", fill=(250, 250, 250))
        draw.text((x + 12, 108), f"Issuer {index}", fill=(235, 245, 255))
        rows.append((f"text_{index}_a", f"Card {index}", x + 12, 80, 54, 16))
        rows.append((f"text_{index}_b", f"Issuer {index}", x + 12, 108, 72, 16))
    image.save(image_path)
    ocr_path = write_ocr_artifact(tmp_path, "sibling_cards.ocr_blocks.v1.json", rows)

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    container_shapes = [
        layer for layer in layer_stack["layers"] if layer["type"] == "shape" and layer.get("reason") == "local_container_surface"
    ]
    control_shapes = [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape" and layer.get("scores", {}).get("confirmedControlSurface", 0.0) >= 1.0
    ]

    assert len(container_shapes) == 3
    assert not control_shapes
    assert layer_stack["diagnostics"]["containerSurfaceShapeLayerCount"] == 3


def test_container_surface_does_not_trigger_control_raster_suppression(tmp_path: Path) -> None:
    image_path = tmp_path / "container_with_texture.png"
    image = Image.new("RGB", (360, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((36, 42, 324, 152), radius=18, fill=(38, 118, 204))
    for x in range(210, 294, 8):
        draw.line((x, 64, x + 24, 132), fill=(16, 76, 170), width=3)
    draw.text((62, 62), "Title", fill=(255, 255, 255))
    draw.text((62, 94), "Issuer", fill=(235, 245, 255))
    draw.text((62, 126), "3301****", fill=(235, 245, 255))
    image.save(image_path)
    ocr_path = write_ocr_artifact(
        tmp_path,
        "container_with_texture.ocr_blocks.v1.json",
        [
            ("text_0001", "Title", 62, 62, 34, 12),
            ("text_0002", "Issuer", 62, 94, 42, 12),
            ("text_0003", "3301****", 62, 126, 66, 12),
        ],
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))

    assert layer_stack["diagnostics"]["localSurfaceContainerCount"] >= 1
    assert layer_stack["diagnostics"]["controlOwnedRasterSuppressedCount"] == 0


def test_adjacent_chip_controls_are_not_deduped_together(tmp_path: Path) -> None:
    image_path = tmp_path / "chips.png"
    image = Image.new("RGB", (260, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((36, 40, 104, 76), radius=14, fill=(230, 241, 255))
    draw.rounded_rectangle((116, 40, 186, 76), radius=14, fill=(230, 241, 255))
    draw.text((58, 51), "A", fill=(20, 20, 20))
    draw.text((140, 51), "B", fill=(20, 20, 20))
    image.save(image_path)
    ocr_path = write_ocr_artifact(
        tmp_path,
        "chips.ocr_blocks.v1.json",
        [
            ("text_0001", "A", 58, 51, 10, 12),
            ("text_0002", "B", 140, 51, 10, 12),
        ],
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    control_shapes = [
        layer
        for layer in layer_stack["layers"]
        if layer["type"] == "shape" and layer.get("scores", {}).get("confirmedControlSurface", 0) >= 1
    ]

    assert len(control_shapes) == 2


def test_control_text_uses_owner_surface_for_contrast_color_and_font(tmp_path: Path) -> None:
    image_path = tmp_path / "owner_text_color.png"
    image = Image.new("RGB", (280, 140), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((80, 40, 200, 84), radius=18, fill=(31, 91, 247))
    draw.text((121, 55), "确认", fill=(255, 255, 255))
    image.save(image_path)
    ocr_path = write_ocr_artifact(tmp_path, "owner_text_color.ocr_blocks.v1.json", [("text_0001", "确认", 121, 55, 38, 14)])

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    text = next(layer for layer in layer_stack["layers"] if layer["type"] == "text")

    assert text["style"]["fontFamily"] == "PingFang SC"
    assert text["style"]["fontWeight"] == 500
    assert text["style"]["color"].lower() in {"#ffffff", "#fefefe", "#fbfbfb"}
    assert text["textFit"]["textColorSource"] == "owner_surface_contrast_sample"
    assert text["textFit"]["textOwnerRole"] == "control_surface"
    assert layer_stack["diagnostics"]["textOwnerAwareColorCount"] >= 1


def test_text_foreground_sample_prefers_small_high_contrast_strokes(tmp_path: Path) -> None:
    image_path = tmp_path / "foreground_bucket.png"
    image = Image.new("RGB", (80, 80), (76, 60, 35))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 60, 60), fill=(105, 83, 52))
    draw.rectangle((38, 38, 42, 42), fill=(255, 255, 255))
    image.save(image_path)
    ocr_path = write_ocr_artifact(tmp_path, "foreground_bucket.ocr_blocks.v1.json", [("text_0001", "A", 20, 20, 40, 40)])

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    text = next(layer for layer in layer_stack["layers"] if layer["type"] == "text")

    assert text["style"]["color"].lower() == "#ffffff"
    assert text["textFit"]["textColorSource"] in {"local_contrast_sample", "owner_surface_contrast_sample"}


def test_text_color_bucket_encoding_keeps_rgb_channels_separate(tmp_path: Path) -> None:
    image_path = tmp_path / "foreground_bucket_channels.png"
    image = Image.new("RGB", (96, 72), (32, 64, 96))
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 18, 80, 54), fill=(32, 64, 96))
    draw.rectangle((34, 30, 62, 42), fill=(240, 248, 255))
    draw.rectangle((16, 18, 80, 22), fill=(224, 64, 96))
    image.save(image_path)
    ocr_path = write_ocr_artifact(tmp_path, "foreground_bucket_channels.ocr_blocks.v1.json", [("text_0001", "OK", 16, 18, 64, 36)])

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    text = next(layer for layer in layer_stack["layers"] if layer["type"] == "text")

    assert text["style"]["color"].lower() in {"#f0f8ff", "#eff8ff", "#f0f7ff"}


def test_text_color_uses_ocr_box_background_when_owner_fill_is_wrong() -> None:
    wire_runtime_namespace()
    rgb = np.full((80, 120, 3), (252, 252, 252), dtype=np.uint8)
    rgb[24:58, 28:92] = np.array([35, 92, 247], dtype=np.uint8)
    rgb[36:44, 48:72] = np.array([255, 255, 255], dtype=np.uint8)
    context = TextStyleContext(
        owner_bbox=BBox(28, 24, 64, 34),
        owner_fill=(230, 240, 253),
        owner_role="container_surface",
        owner_reason="low_texture_solid_region",
    )

    sample = sample_text_color_with_diagnostics(rgb, BBox(42, 30, 40, 24), context)

    assert sample.source == "ocr_box_dominant_background_contrast_sample"
    assert sample.color.lower() == "#ffffff"


def test_latin_numeric_text_uses_inter_font_family(tmp_path: Path) -> None:
    image_path = tmp_path / "latin_text.png"
    image = Image.new("RGB", (180, 80), "white")
    draw = ImageDraw.Draw(image)
    draw.text((24, 28), "web-01", fill=(20, 20, 20))
    image.save(image_path)
    ocr_path = write_ocr_artifact(tmp_path, "latin_text.ocr_blocks.v1.json", [("text_0001", "web-01", 24, 28, 58, 16)])

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    text = next(layer for layer in layer_stack["layers"] if layer["type"] == "text")

    assert text["style"]["fontFamily"] == "Inter"
    assert text["style"]["fontWeight"] == 400


def test_same_row_similar_action_text_font_sizes_are_harmonized(tmp_path: Path) -> None:
    image_path = tmp_path / "row_actions.png"
    image = Image.new("RGB", (420, 120), (18, 20, 24))
    draw = ImageDraw.Draw(image)
    for x in (30, 160, 290):
        draw.rounded_rectangle((x, 36, x + 104, 78), radius=8, fill=(31, 41, 56))
        draw.text((x + 20, 48), "在线办理", fill=(63, 148, 250))
    image.save(image_path)
    ocr_path = write_ocr_artifact(
        tmp_path,
        "row_actions.ocr_blocks.v1.json",
        [
            ("text_0001", "在线办理", 50, 47, 72, 22),
            ("text_0002", "在线办理", 180, 47, 75, 26),
            ("text_0003", "在线办理", 310, 47, 73, 24),
        ],
    )

    result = run_pipeline(image_path=image_path, ocr_path=ocr_path, out_dir=tmp_path / "out")
    layer_stack = json.loads(result.layer_stack_path.read_text(encoding="utf-8"))
    texts = [layer for layer in layer_stack["layers"] if layer["type"] == "text"]
    sizes = {layer["style"]["fontSize"] for layer in texts}

    assert len(sizes) == 1
    assert layer_stack["diagnostics"]["textRowHarmonizedCount"] >= 1


def test_media_owned_text_still_not_emitted_as_visible_text(tmp_path: Path) -> None:
    block = OCRBlock(id="text_0001", text="SALE", bbox=BBox(72, 70, 42, 14), confidence=0.98)
    image = Image.new("RGB", (220, 180), "white")
    image_path = tmp_path / "media_owned_style.png"
    image.save(image_path)

    layer_stack = build_layer_stack(
        image_path=image_path,
        ocr_path=None,
        image=image,
        rgb=np.asarray(image),
        ocr_blocks=[block],
        raster_candidates=[],
        shape_candidates=[],
        asset_refs={},
        ownership={},
        rejected=[],
        thresholds={"maxTextOverlap": 0.24},
        media_owned_text_ids={"text_0001"},
    )

    assert not [layer for layer in layer_stack["layers"] if layer["type"] == "text"]
    assert layer_stack["diagnostics"]["visibleTextLayerCount"] == 0


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


def write_ocr_artifact(tmp_path: Path, name: str, rows: list[tuple[str, str, int, int, int, int]]) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "version": "ocr_blocks.v1",
                "blocks": [
                    {
                        "id": row[0],
                        "text": row[1],
                        "bbox": {"x": row[2], "y": row[3], "width": row[4], "height": row[5]},
                        "confidence": 1.0,
                    }
                    for row in rows
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def write_plain_text_fixture(tmp_path: Path) -> tuple[Path, Path]:
    image_path = tmp_path / "plain_text.png"
    image = Image.new("RGB", (240, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.text((64, 52), "OK", fill=(20, 20, 20))
    image.save(image_path)

    ocr_path = tmp_path / "plain_text.ocr_blocks.v1.json"
    ocr_path.write_text(
        json.dumps(
            {
                "version": "ocr_blocks.v1",
                "blocks": [
                    {
                        "id": "text_0001",
                        "text": "OK",
                        "bbox": {"x": 64, "y": 52, "width": 18, "height": 12},
                        "confidence": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return image_path, ocr_path


def write_model_control_fixture(tmp_path: Path) -> tuple[Path, Path]:
    image_path = tmp_path / "model_control.png"
    image = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((50, 42, 190, 82), radius=18, fill=(245, 180, 40))
    draw.text((92, 53), "OK", fill=(20, 20, 20))
    image.save(image_path)

    ocr_path = tmp_path / "model_control.ocr_blocks.v1.json"
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


def write_plain_media_fixture(tmp_path: Path) -> Path:
    image_path = tmp_path / "plain_media.png"
    Image.new("RGB", (200, 160), "white").save(image_path)
    return image_path


def write_texture_icon_fixture(tmp_path: Path) -> Path:
    image_path = tmp_path / "texture_icon.png"
    image = Image.new("RGB", (200, 160), "white")
    draw = ImageDraw.Draw(image)
    for y in range(48, 72, 4):
        for x in range(48, 72, 4):
            fill = (30, 30, 30) if ((x + y) // 4) % 2 == 0 else (30, 180, 120)
            draw.rectangle((x, y, x + 3, y + 3), fill=fill)
    image.save(image_path)
    return image_path


def blank_text_mask(width: int, height: int, blocks: list[OCRBlock]):
    import numpy as np

    mask = np.zeros((height, width), dtype=bool)
    for block in blocks:
        mask[block.bbox.y : block.bbox.y2, block.bbox.x : block.bbox.x2] = True
    return mask


def write_model_evidence(
    tmp_path: Path,
    class_name: str,
    bbox: dict[str, int],
    confidence: float = 0.9,
    canvas: dict[str, int] | None = None,
) -> Path:
    path = tmp_path / f"{class_name}.model_evidence.v1.json"
    canvas = canvas or {"width": 240, "height": 120}
    path.write_text(
        json.dumps(
            {
                "version": "model_evidence.v1",
                "canvas": canvas,
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
