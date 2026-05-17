from __future__ import annotations

import json
from pathlib import Path

from app.png_tools import PngMetadata, PngPixels, decode_png_pixels, encode_rgb_png, read_png_metadata
from app.ui_visual_extraction import M28Candidate, M28RawMask, build_overlay_png, build_preview_sheet
from app.ui_visual_extraction import classify_visual_objects, crop_pixels, validate_m28_document


def test_m28_classifies_image_assets_and_blocks_internal_masks(tmp_path) -> None:
    image, pixels = synthetic_commerce_pixels()
    masks = [
        M28RawMask("sam2_mask_001", [30, 160, 810, 285], 120000, 0.90, 0.92),
        M28RawMask("sam2_mask_002", [400, 220, 120, 100], 12000, 0.90, 0.92),
        M28RawMask("sam2_mask_003", [70, 1578, 46, 46], 1500, 0.90, 0.92),
        M28RawMask("sam2_mask_004", [180, 1080, 70, 22], 1200, 0.90, 0.92),
    ]

    candidates, blocked = classify_visual_objects(masks, pixels, image)

    assert any(item.kind == "image_asset" and "hero_banner" in item.reasons for item in candidates)
    assert any("inside_image_asset" in item.reasons for item in blocked)
    assert any(item.kind == "icon_candidate" for item in candidates)
    assert not any(item.bbox == [180, 1080, 70, 22] for item in candidates)


def test_m28_blocks_text_line_and_red_digit_like_masks() -> None:
    image, pixels = synthetic_commerce_pixels()
    masks = [
        M28RawMask("sam2_mask_001", [40, 40, 760, 4], 3000, 0.88, 0.90),
        M28RawMask("sam2_mask_002", [710, 600, 72, 52], 2200, 0.88, 0.90),
        M28RawMask("sam2_mask_003", [70, 1578, 46, 46], 1500, 0.90, 0.92),
    ]

    candidates, _blocked = classify_visual_objects(masks, pixels, image)

    assert not any(item.bbox == [40, 40, 760, 4] for item in candidates)
    assert not any(item.bbox == [710, 600, 72, 52] for item in candidates)


def test_m28_overlay_preview_and_crop_outputs_are_readable(tmp_path) -> None:
    image, pixels = synthetic_commerce_pixels()
    candidate = M28Candidate("icon_candidate", [70, 1578, 46, 46], 0.82, ["sam2_mask_001"], ["icon_sized_visual"])
    blocked = M28Candidate("icon_candidate", [400, 220, 120, 100], 0.7, ["sam2_mask_002"], ["inside_image_asset"])

    crop = crop_pixels(pixels, candidate.bbox)
    crop_meta = read_png_metadata(crop)
    assert crop_meta is not None
    assert [crop_meta.width, crop_meta.height] == candidate.bbox[2:4]

    overlay = build_overlay_png(pixels, image, [candidate], [blocked])
    overlay_pixels = decode_png_pixels(overlay)
    assert read_png_metadata(overlay) == image

    (tmp_path / "icons").mkdir()
    (tmp_path / "images").mkdir()
    (tmp_path / "controls").mkdir()
    (tmp_path / "icons" / "m28_icon_001.png").write_bytes(crop)
    preview = build_preview_sheet(pixels, overlay_pixels, [candidate], tmp_path)
    assert read_png_metadata(preview) is not None


def test_m28_validation_rejects_missing_assets(tmp_path) -> None:
    image, _pixels = synthetic_commerce_pixels()
    document = type(
        "Doc",
        (),
        {
            "version": "0.1",
            "icons": [
                type(
                    "Item",
                    (),
                    {
                        "id": "m28_icon_001",
                        "bbox": [1, 1, 20, 20],
                        "assetPath": str(tmp_path / "missing.png"),
                    },
                )()
            ],
            "imageAssets": [],
            "controls": [],
            "blocked": [],
            "overlayPath": str(tmp_path / "overlay.png"),
            "previewSheetPath": str(tmp_path / "preview.png"),
        },
    )()

    try:
        validate_m28_document(document, image)
    except ValueError as error:
        assert "asset missing" in str(error)
    else:
        raise AssertionError("validate_m28_document should reject missing item assets")


def test_m28_document_json_shape_from_smoke_fixture(tmp_path) -> None:
    image, pixels = synthetic_commerce_pixels()
    overlay = build_overlay_png(pixels, image, [], [])
    overlay_path = tmp_path / "m28_visual_extraction_overlay.png"
    preview_path = tmp_path / "m28_visual_extraction_preview_sheet.png"
    overlay_path.write_bytes(overlay)
    preview_path.write_bytes(overlay)
    payload = {
        "version": "0.1",
        "sourceImage": "/tmp/input.png",
        "imageSize": {"width": image.width, "height": image.height},
        "sam": {"device": "cpu", "rawMaskCount": 0, "inferenceMs": 0},
        "icons": [],
        "imageAssets": [],
        "controls": [],
        "blocked": [],
        "overlayPath": str(overlay_path),
        "previewSheetPath": str(preview_path),
        "meta": {"iconCount": 0, "imageAssetCount": 0, "controlCount": 0, "blockedCount": 0},
    }
    assert json.loads(json.dumps(payload))["version"] == "0.1"


def synthetic_commerce_pixels() -> tuple[PngMetadata, PngPixels]:
    width, height = 853, 1844
    rows = [bytearray(b"\xFA\xFA\xFA" * width) for _ in range(height)]

    fill(rows, width, [23, 162, 807, 288], (236, 245, 210))
    fill(rows, width, [400, 220, 140, 110], (220, 35, 24))
    fill(rows, width, [560, 210, 180, 170], (60, 150, 42))
    fill(rows, width, [28, 485, 107, 96], (110, 200, 75))
    fill(rows, width, [164, 485, 107, 96], (240, 170, 40))
    fill(rows, width, [300, 485, 107, 96], (210, 80, 80))
    fill(rows, width, [437, 485, 107, 96], (80, 100, 110))
    fill(rows, width, [573, 485, 107, 96], (210, 150, 35))
    fill(rows, width, [710, 485, 107, 96], (80, 150, 230))
    fill(rows, width, [70, 1578, 46, 46], (250, 250, 250))
    stroke(rows, width, [82, 1590, 22, 22], (20, 20, 20))
    fill(rows, width, [180, 1080, 70, 22], (245, 30, 30))
    fill(rows, width, [185, 1085, 12, 12], (255, 255, 255))
    fill(rows, width, [710, 600, 72, 52], (250, 250, 250))
    stroke(rows, width, [715, 612, 58, 18], (245, 35, 35))

    data = encode_rgb_png(width, height, [bytes(row) for row in rows])
    pixels = decode_png_pixels(data)
    metadata = read_png_metadata(data)
    assert metadata is not None
    return metadata, pixels


def fill(rows: list[bytearray], image_width: int, bbox: list[int], color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    x, y, width, height = bbox
    for row_index in range(y, min(len(rows), y + height)):
        row = rows[row_index]
        for column in range(x, min(image_width, x + width)):
            offset = column * 3
            row[offset : offset + 3] = color_bytes


def stroke(rows: list[bytearray], image_width: int, bbox: list[int], color: tuple[int, int, int]) -> None:
    x, y, width, height = bbox
    fill(rows, image_width, [x, y, width, 3], color)
    fill(rows, image_width, [x, y + height - 3, width, 3], color)
    fill(rows, image_width, [x, y, 3, height], color)
    fill(rows, image_width, [x + width - 3, y, 3, height], color)
