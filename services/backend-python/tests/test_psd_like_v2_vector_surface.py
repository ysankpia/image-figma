import numpy as np
from PIL import Image, ImageDraw

from tools.psd_like_layer_decomposition_experiment import BBox, OCRBlock, build_text_mask
from tools.psd_like_v2_vector_surface_experiment import (
    extract_vector_surfaces,
    infer_corner_radius,
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
