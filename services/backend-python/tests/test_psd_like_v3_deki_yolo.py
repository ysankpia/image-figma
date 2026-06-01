from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from tools.psd_like_layer_decomposition_experiment import BBox, Candidate, OCRBlock, build_text_mask, compute_tile_maps
from tools.psd_like_v3_deki_yolo_experiment import (
    DekiYoloCandidate,
    deki_imageview_to_raster_candidates,
    deki_view_to_shape_candidates,
    load_deki_yolo_candidates,
    merge_deki_rasters,
    run,
)


def test_load_deki_yolo_candidates_normalizes_boxes_and_records_unknown_class(tmp_path: Path):
    artifact = {
        "version": "deki_yolo_candidates.v1",
        "modelPath": "/tmp/model.pt",
        "sourceImage": "/tmp/source.png",
        "canvas": {"width": 100, "height": 80},
        "candidates": [
            {
                "id": "raw_1",
                "classId": 1,
                "className": "ImageView",
                "bbox": {"x": -5, "y": 10, "width": 30, "height": 20},
                "confidence": 0.91,
            },
            {
                "id": "raw_2",
                "classId": 99,
                "className": "Alien",
                "bbox": {"x": 0, "y": 0, "width": 10, "height": 10},
                "confidence": 0.8,
            },
        ],
    }
    path = tmp_path / "deki.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")

    candidates, diagnostics, _ = load_deki_yolo_candidates(path, width=100, height=80)

    assert len(candidates) == 1
    assert candidates[0].bbox == BBox(0, 10, 25, 20)
    assert diagnostics[0]["reason"] == "unknown_class"


def test_deki_text_is_diagnostic_only_and_does_not_create_text_layer(tmp_path: Path):
    image = Image.new("RGB", (160, 120), (245, 245, 245))
    image_path = tmp_path / "source.png"
    image.save(image_path)
    ocr_path = tmp_path / "ocr.json"
    ocr_path.write_text(json.dumps({"version": "ocr_blocks.v1", "blocks": []}), encoding="utf-8")
    deki_path = tmp_path / "deki.json"
    deki_path.write_text(
        json.dumps(
            {
                "version": "deki_yolo_candidates.v1",
                "modelPath": "/tmp/model.pt",
                "sourceImage": str(image_path),
                "canvas": {"width": 160, "height": 120},
                "candidates": [
                    {
                        "id": "yolo_0001",
                        "classId": 2,
                        "className": "Text",
                        "bbox": {"x": 20, "y": 20, "width": 80, "height": 18},
                        "confidence": 0.99,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    stack = run(_args(image_path, ocr_path, deki_path, tmp_path / "out"))

    assert stack["diagnostics"]["textLayerCount"] == 0
    assert stack["diagnostics"]["dekiTextDiagnosticCount"] == 1


def test_deki_view_with_contained_ocr_button_creates_shape_when_experimental_gate_is_enabled(tmp_path: Path):
    image = Image.new("RGB", (220, 160), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((50, 60, 170, 100), radius=18, fill=(18, 102, 253))
    draw.rectangle((88, 74, 132, 88), fill=(255, 255, 255))
    image_path = tmp_path / "button.png"
    image.save(image_path)
    ocr_path = tmp_path / "ocr.json"
    ocr_path.write_text(
        json.dumps(
            {
                "version": "ocr_blocks.v1",
                "blocks": [
                    {
                        "id": "text_0001",
                        "text": "确定",
                        "bbox": {"x": 88, "y": 74, "width": 44, "height": 14},
                        "confidence": 0.99,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    deki_path = tmp_path / "deki.json"
    deki_path.write_text(
        json.dumps(
            {
                "version": "deki_yolo_candidates.v1",
                "modelPath": "/tmp/model.pt",
                "sourceImage": str(image_path),
                "canvas": {"width": 220, "height": 160},
                "candidates": [
                    {
                        "id": "yolo_0001",
                        "classId": 0,
                        "className": "View",
                        "bbox": {"x": 50, "y": 60, "width": 120, "height": 40},
                        "confidence": 0.93,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    out = tmp_path / "out"
    args = _args(image_path, ocr_path, deki_path, out)
    args.enable_deki_view_shapes = True
    stack = run(args)
    dsl = json.loads((out / "draft_runtime.v3.dsl.v1_0.json").read_text(encoding="utf-8"))

    deki_shapes = [layer for layer in stack["layers"] if layer["reason"] == "deki_yolo_view_control_surface"]
    assert len(deki_shapes) == 1
    assert deki_shapes[0]["style"]["fill"] == "#1266fd"
    assert deki_shapes[0]["style"].get("cornerRadius", 0) > 0
    assert stack["diagnostics"]["textLayerCount"] == 1
    assert dsl["assets"] == []
    assert [child["type"] for child in dsl["root"]["children"]].count("text") == 1
    assert [child["type"] for child in dsl["root"]["children"]].count("image") == 0


def test_deki_imageview_with_low_text_overlap_creates_raster_candidate():
    rgb = np.full((120, 160, 3), 245, dtype=np.uint8)
    rgb[30:70, 40:88] = (20, 80, 200)
    text_mask = np.zeros((120, 160), dtype=bool)
    maps = compute_tile_maps(rgb, text_mask, tile_size=8)
    candidates, rejected = deki_imageview_to_raster_candidates(
        yolo_candidates=[
            DekiYoloCandidate("yolo_0001", 1, "ImageView", BBox(40, 30, 48, 40), 0.92),
        ],
        maps=maps,
        text_mask=text_mask,
        ocr_blocks=[],
        width=160,
        height=120,
        tile_size=8,
    )

    assert rejected == []
    assert len(candidates) == 1
    assert candidates[0].reason == "deki_yolo_imageview"


def test_deki_imageview_covering_ocr_is_suppressed():
    rgb = np.full((120, 160, 3), 245, dtype=np.uint8)
    block = OCRBlock("text_0001", "Hello", BBox(42, 36, 44, 16), 0.99)
    text_mask = build_text_mask(160, 120, [block], padding=0)
    maps = compute_tile_maps(rgb, text_mask, tile_size=8)
    candidates, rejected = deki_imageview_to_raster_candidates(
        yolo_candidates=[
            DekiYoloCandidate("yolo_0001", 1, "ImageView", BBox(36, 30, 60, 34), 0.92),
        ],
        maps=maps,
        text_mask=text_mask,
        ocr_blocks=[block],
        width=160,
        height=120,
        tile_size=8,
    )

    assert candidates == []
    assert rejected[0]["reason"] in {"covers_ocr_text", "contains_multiple_ocr_blocks", "text_overlap_score"}


def test_deki_raster_is_diagnostic_only_in_v3_p0():
    v1 = Candidate("raster_0001", "raster", BBox(20, 20, 60, 60), 0.72, {"textOverlap": 0.0}, "v1")
    deki = Candidate("deki_raster_0001", "raster", BBox(22, 22, 56, 56), 0.90, {"textOverlap": 0.0}, "deki_yolo_imageview")

    merged, decisions = merge_deki_rasters([v1], [deki])

    assert len(merged) == 1
    assert merged[0].id == "raster_0001"
    assert decisions[0]["kind"] == "deki_raster_diagnostic_only"


def test_deki_view_is_diagnostic_only_by_default(tmp_path: Path):
    image = Image.new("RGB", (220, 160), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((50, 60, 170, 100), radius=18, fill=(18, 102, 253))
    draw.rectangle((88, 74, 132, 88), fill=(255, 255, 255))
    image_path = tmp_path / "button.png"
    image.save(image_path)
    ocr_path = tmp_path / "ocr.json"
    ocr_path.write_text(
        json.dumps(
            {
                "version": "ocr_blocks.v1",
                "blocks": [
                    {
                        "id": "text_0001",
                        "text": "确定",
                        "bbox": {"x": 88, "y": 74, "width": 44, "height": 14},
                        "confidence": 0.99,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    deki_path = tmp_path / "deki.json"
    deki_path.write_text(
        json.dumps(
            {
                "version": "deki_yolo_candidates.v1",
                "modelPath": "/tmp/model.pt",
                "sourceImage": str(image_path),
                "canvas": {"width": 220, "height": 160},
                "candidates": [
                    {
                        "id": "yolo_0001",
                        "classId": 0,
                        "className": "View",
                        "bbox": {"x": 50, "y": 60, "width": 120, "height": 40},
                        "confidence": 0.93,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    stack = run(_args(image_path, ocr_path, deki_path, tmp_path / "out"))

    assert [layer for layer in stack["layers"] if layer["reason"] == "deki_yolo_view_control_surface"] == []
    assert stack["diagnostics"]["dekiViewShapePassCount"] == 1
    assert stack["diagnostics"]["dekiViewShapeAcceptedCount"] == 0


def test_text_z_is_always_higher_than_raster_and_shape(tmp_path: Path):
    image = Image.new("RGB", (220, 160), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 70, 70), fill=(20, 80, 200))
    draw.rounded_rectangle((80, 90, 170, 124), radius=14, fill=(255, 132, 0))
    draw.rectangle((108, 100, 142, 112), fill=(255, 255, 255))
    image_path = tmp_path / "source.png"
    image.save(image_path)
    ocr_path = tmp_path / "ocr.json"
    ocr_path.write_text(
        json.dumps(
            {
                "version": "ocr_blocks.v1",
                "blocks": [
                    {
                        "id": "text_0001",
                        "text": "Go",
                        "bbox": {"x": 108, "y": 100, "width": 34, "height": 12},
                        "confidence": 0.99,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    deki_path = tmp_path / "deki.json"
    deki_path.write_text(
        json.dumps(
            {
                "version": "deki_yolo_candidates.v1",
                "modelPath": "/tmp/model.pt",
                "sourceImage": str(image_path),
                "canvas": {"width": 220, "height": 160},
                "candidates": [
                    {
                        "id": "yolo_0001",
                        "classId": 1,
                        "className": "ImageView",
                        "bbox": {"x": 20, "y": 20, "width": 50, "height": 50},
                        "confidence": 0.9,
                    },
                    {
                        "id": "yolo_0002",
                        "classId": 0,
                        "className": "View",
                        "bbox": {"x": 80, "y": 90, "width": 90, "height": 34},
                        "confidence": 0.9,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    args = _args(image_path, ocr_path, deki_path, tmp_path / "out")
    args.enable_deki_view_shapes = True
    stack = run(args)
    shape_z = [layer["z"] for layer in stack["layers"] if layer["type"] == "shape"]
    raster_z = [layer["z"] for layer in stack["layers"] if layer["type"] == "raster"]
    text_z = [layer["z"] for layer in stack["layers"] if layer["type"] == "text"]

    assert shape_z
    assert raster_z
    assert text_z
    assert max(shape_z) < min(raster_z)
    assert max(raster_z) < min(text_z)


def _args(image_path: Path, ocr_path: Path, deki_path: Path, out_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        image=str(image_path),
        ocr=str(ocr_path),
        deki_json=str(deki_path),
        out=str(out_dir),
        allow_missing_ocr=True,
        allow_missing_deki=True,
        tile_size=8,
        text_padding=3,
        ocr_min_confidence=0.70,
        raster_threshold=0.42,
        shape_threshold=0.62,
        raster_min_area=512,
        shape_min_area=1200,
        surface_min_area=2400,
        max_text_overlap=0.24,
    )
