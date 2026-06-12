import argparse
import json

import numpy as np
from PIL import Image, ImageDraw

from tools.psd_like_layer_decomposition_experiment import BBox, Candidate, OCRBlock, build_text_mask
from tools.psd_like_v2_vector_surface_experiment import (
    extract_vector_surfaces,
    filter_raster_fallbacks,
    infer_corner_radius,
    run,
)


def rgb_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"))


def test_ocr_text_on_plain_page_does_not_create_surface():
    image = Image.new("RGB", (240, 160), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 68, 130, 84), fill=(25, 25, 25))
    block = OCRBlock(id="text_0001", text="Plain", bbox=BBox(70, 68, 60, 16), confidence=0.99)
    text_mask = build_text_mask(image.width, image.height, [block], padding=3)

    surfaces = extract_vector_surfaces(rgb_array(image), [block], text_mask)

    assert surfaces == []


def test_solid_rounded_button_with_ocr_creates_vector_surface():
    image = Image.new("RGB", (260, 180), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((54, 62, 206, 112), radius=18, fill=(38, 120, 244))
    draw.rectangle((103, 78, 157, 96), fill=(255, 255, 255))
    block = OCRBlock(id="text_0001", text="Submit", bbox=BBox(103, 78, 54, 18), confidence=0.99)
    text_mask = build_text_mask(image.width, image.height, [block], padding=3)

    surfaces = extract_vector_surfaces(rgb_array(image), [block], text_mask)

    assert len(surfaces) == 1
    surface = surfaces[0]
    assert surface.contained_text_ids == ["text_0001"]
    assert surface.bbox.x <= 56
    assert surface.bbox.y <= 64
    assert surface.bbox.x2 >= 204
    assert surface.bbox.y2 >= 110
    assert surface.corner_radius >= 8


def test_high_texture_photo_with_text_is_not_vector_surface():
    image = Image.new("RGB", (260, 180), (245, 245, 245))
    arr = np.asarray(image).copy()
    for y in range(46, 134):
        for x in range(34, 226):
            value = (x * 17 + y * 31) % 255
            arr[y, x] = (value, 255 - value, (x * y) % 255)
    arr[82:102, 96:164] = (255, 255, 255)
    image = Image.fromarray(arr, mode="RGB")
    block = OCRBlock(id="text_0001", text="Photo", bbox=BBox(96, 82, 68, 20), confidence=0.99)
    text_mask = build_text_mask(image.width, image.height, [block], padding=3)

    surfaces = extract_vector_surfaces(rgb_array(image), [block], text_mask)

    assert surfaces == []


def test_full_page_background_is_rejected_as_visible_surface():
    image = Image.new("RGB", (220, 160), (32, 118, 220))
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 70, 150, 88), fill=(255, 255, 255))
    block = OCRBlock(id="text_0001", text="Hero", bbox=BBox(70, 70, 80, 18), confidence=0.99)
    text_mask = build_text_mask(image.width, image.height, [block], padding=3)

    surfaces = extract_vector_surfaces(rgb_array(image), [block], text_mask)

    assert surfaces == []


def test_corner_radius_inference_distinguishes_round_and_square():
    rounded = Image.new("RGB", (120, 80), (245, 245, 245))
    draw = ImageDraw.Draw(rounded)
    draw.rounded_rectangle((20, 20, 100, 60), radius=14, fill=(40, 150, 90))
    square = Image.new("RGB", (120, 80), (245, 245, 245))
    draw = ImageDraw.Draw(square)
    draw.rectangle((20, 20, 100, 60), fill=(40, 150, 90))
    fill = np.array([40, 150, 90], dtype=np.uint8)

    rounded_radius = infer_corner_radius(rgb_array(rounded), BBox(20, 20, 80, 40), fill)
    square_radius = infer_corner_radius(rgb_array(square), BBox(20, 20, 80, 40), fill)

    assert rounded_radius >= 8
    assert square_radius == 0


def test_v2_run_outputs_shape_and_text_for_button_without_button_asset(tmp_path):
    image = Image.new("RGB", (260, 180), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((54, 62, 206, 112), radius=18, fill=(38, 120, 244))
    draw.rectangle((103, 78, 157, 96), fill=(255, 255, 255))
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
                        "text": "Submit",
                        "bbox": {"x": 103, "y": 78, "width": 54, "height": 18},
                        "confidence": 0.99,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    layer_stack = run(
        argparse.Namespace(
            image=str(image_path),
            ocr=str(ocr_path),
            out=str(tmp_path / "out"),
            allow_missing_ocr=False,
            text_padding=3,
            ocr_min_confidence=0.70,
            vector_min_area=480,
            tile_size=8,
            raster_threshold=0.42,
            raster_min_area=512,
            max_text_overlap=0.04,
        )
    )
    dsl = json.loads((tmp_path / "out" / "draft_runtime.v2.dsl.v1_0.json").read_text(encoding="utf-8"))

    assert layer_stack["diagnostics"]["shapeLayerCount"] == 1
    assert layer_stack["diagnostics"]["rasterLayerCount"] == 0
    assert layer_stack["diagnostics"]["textLayerCount"] == 1
    assert dsl["assets"] == []
    assert [node["type"] for node in dsl["root"]["children"]].count("shape") == 1
    assert [node["type"] for node in dsl["root"]["children"]].count("text") == 1


def test_raster_fallback_rejects_vector_owned_control_background():
    text_mask = np.zeros((180, 260), dtype=bool)
    control_shape = Candidate(
        id="shape_surface_0001",
        kind="shape",
        bbox=BBox(54, 62, 152, 50),
        score=0.95,
        scores={"role": "control_surface"},
        reason="vector_surface",
    )
    raster = Candidate(
        id="raster_0001",
        kind="raster",
        bbox=BBox(60, 68, 120, 32),
        score=0.8,
        scores={"textOverlap": 0.0},
        reason="high_texture_low_text_overlap",
    )

    accepted, rejected = filter_raster_fallbacks([raster], [control_shape], text_mask, 260, 180, 0.04)

    assert accepted == []
    assert rejected[0]["reason"] == "vector_control_owned_background"
