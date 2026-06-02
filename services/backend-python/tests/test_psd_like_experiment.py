from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from tools.psd_like_layer_decomposition_experiment import (
    BBox,
    OCRBlock,
    build_layer_stack,
    build_draft_runtime_dsl,
    build_foreground_object_candidates,
    build_raster_candidates,
    build_shape_candidates,
    build_surface_candidates,
    build_text_mask,
    detect_ocr_anchored_control_surfaces,
    color_distance,
    compute_tile_maps,
    crop_raster_assets,
    estimate_inpaint_fill_for_candidate_text,
    estimate_text_background_for_box,
    estimate_background_color,
    exported_rejections,
    build_raster_ownership,
    infer_background_plate_candidates,
    infer_control_corner_radius,
    is_full_page_backing,
    promote_control_surfaces,
    promote_complex_shape_regions,
    sample_text_color,
    suppress_control_owned_rasters,
    suppress_text_owned_raster_fragments,
    write_preview_html,
    write_preview_report,
    write_draft_preview_png,
)


def test_raster_candidate_from_high_texture_region():
    rgb = np.full((80, 80, 3), 245, dtype=np.uint8)
    for y in range(16, 48):
        for x in range(16, 48):
            value = 30 if (x + y) % 2 == 0 else 220
            rgb[y, x] = (value, 80, 255 - value)

    text_mask = np.zeros((80, 80), dtype=bool)
    maps = compute_tile_maps(rgb, text_mask, tile_size=8)
    candidates, rejected = build_raster_candidates(
        maps=maps,
        text_mask=text_mask,
        ocr_blocks=[],
        width=80,
        height=80,
        tile_size=8,
        threshold=0.35,
        min_area=64,
        max_text_overlap=0.20,
    )

    assert rejected == []
    assert candidates
    assert candidates[0].kind == "raster"
    assert candidates[0].bbox.area >= 16 * 16


def test_ocr_mask_suppresses_text_only_raster():
    rgb = np.full((80, 80, 3), 245, dtype=np.uint8)
    rgb[20:36, 10:70] = (10, 10, 10)
    block = OCRBlock(id="text_0001", text="Hello", bbox=BBox(10, 20, 60, 16), confidence=0.99)
    text_mask = build_text_mask(80, 80, [block], padding=2)

    maps = compute_tile_maps(rgb, text_mask, tile_size=8)
    candidates, _ = build_raster_candidates(
        maps=maps,
        text_mask=text_mask,
        ocr_blocks=[block],
        width=80,
        height=80,
        tile_size=8,
        threshold=0.20,
        min_area=64,
        max_text_overlap=0.20,
    )

    assert candidates == []


def test_shape_candidate_from_solid_non_background_region():
    rgb = np.full((120, 120, 3), 245, dtype=np.uint8)
    rgb[24:88, 16:104] = (210, 230, 255)
    text_mask = np.zeros((120, 120), dtype=bool)
    maps = compute_tile_maps(rgb, text_mask, tile_size=8)

    shapes, _ = build_shape_candidates(
        maps=maps,
        text_mask=text_mask,
        raster_candidates=[],
        width=120,
        height=120,
        tile_size=8,
        threshold=0.70,
        min_area=512,
    )

    assert shapes
    assert shapes[0].kind == "shape"
    assert shapes[0].bbox.area >= 512


def test_background_color_uses_edge_dominant_cluster_not_corner_median():
    rgb = np.full((120, 120, 3), 255, dtype=np.uint8)
    rgb[:84, :] = (34, 34, 34)

    assert estimate_background_color(rgb) == (34, 34, 34)


def test_surface_candidate_from_large_stable_color_band():
    rgb = np.full((160, 120, 3), 255, dtype=np.uint8)
    rgb[:72, :] = (220, 120, 104)
    text_mask = np.zeros((160, 120), dtype=bool)
    maps = compute_tile_maps(rgb, text_mask, tile_size=8)

    surfaces, rejected = build_surface_candidates(
        maps=maps,
        text_mask=text_mask,
        width=120,
        height=160,
        tile_size=8,
        min_area=512,
    )

    assert any(item.reason == "background_surface_band" and item.bbox.y == 0 and item.bbox.height >= 64 for item in surfaces)
    assert all(item.get("reason") != "page_background" for item in rejected if item.get("bbox", {}).get("height", 0) < 150)


def test_background_plate_inferred_from_repeated_surface_bands():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    surfaces = [
        Candidate(
            id=f"surface_{index:04d}",
            kind="shape",
            bbox=box,
            score=0.9,
            scores={"fillR": 12, "fillG": 14, "fillB": 16},
            reason="background_surface_band",
        )
        for index, box in enumerate(
            [
                BBox(20, 20, 180, 40),
                BBox(24, 100, 172, 64),
                BBox(20, 220, 180, 80),
                BBox(20, 360, 180, 48),
            ],
            start=1,
        )
    ]

    plates = infer_background_plate_candidates(surfaces, width=220, height=440, page_background=(230, 230, 230))

    assert len(plates) == 1
    assert plates[0].reason == "inferred_background_plate_from_surface_bands"
    assert plates[0].bbox == BBox(20, 20, 180, 388)


def test_background_plate_not_inferred_from_page_color_or_sparse_bands():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    page_color_surfaces = [
        Candidate(
            id=f"surface_same_{index:04d}",
            kind="shape",
            bbox=box,
            score=0.9,
            scores={"fillR": 240, "fillG": 240, "fillB": 240},
            reason="background_surface_band",
        )
        for index, box in enumerate([BBox(0, 0, 220, 80), BBox(0, 160, 220, 80), BBox(0, 320, 220, 80)], start=1)
    ]
    sparse_surfaces = [
        Candidate(
            id=f"surface_sparse_{index:04d}",
            kind="shape",
            bbox=box,
            score=0.9,
            scores={"fillR": 20, "fillG": 20, "fillB": 20},
            reason="background_surface_band",
        )
        for index, box in enumerate([BBox(0, 0, 220, 80), BBox(0, 320, 220, 80)], start=1)
    ]

    assert infer_background_plate_candidates(page_color_surfaces, 220, 440, page_background=(245, 245, 245)) == []
    assert infer_background_plate_candidates(sparse_surfaces, 220, 440, page_background=(245, 245, 245)) == []


def test_single_color_page_does_not_create_visible_surface_backing():
    rgb = np.full((120, 120, 3), 240, dtype=np.uint8)
    text_mask = np.zeros((120, 120), dtype=bool)
    maps = compute_tile_maps(rgb, text_mask, tile_size=8)

    surfaces, rejected = build_surface_candidates(
        maps=maps,
        text_mask=text_mask,
        width=120,
        height=120,
        tile_size=8,
        min_area=512,
    )

    assert surfaces == []
    assert any(item["reason"] == "page_background" for item in rejected)


def test_text_color_uses_foreground_contrast_on_light_background():
    rgb = np.full((40, 80, 3), 255, dtype=np.uint8)
    rgb[14:24, 20:60] = (12, 12, 12)

    assert sample_text_color(rgb, BBox(10, 8, 60, 24)) == "#0c0c0c"


def test_text_color_uses_foreground_contrast_on_dark_or_colored_background():
    rgb = np.full((40, 80, 3), (220, 120, 104), dtype=np.uint8)
    rgb[14:24, 20:60] = (255, 255, 255)

    assert sample_text_color(rgb, BBox(10, 8, 60, 24)) == "#ffffff"


def test_foreground_object_candidate_from_smooth_object_on_surface():
    rgb = np.full((160, 160, 3), (220, 120, 104), dtype=np.uint8)
    rgb[48:112, 56:120] = (248, 246, 238)
    text_mask = np.zeros((160, 160), dtype=bool)
    maps = compute_tile_maps(rgb, text_mask, tile_size=8)
    surfaces, _ = build_surface_candidates(
        maps=maps,
        text_mask=text_mask,
        width=160,
        height=160,
        tile_size=8,
        min_area=512,
    )

    objects, rejected = build_foreground_object_candidates(
        maps=maps,
        text_mask=text_mask,
        ocr_blocks=[],
        surface_candidates=surfaces,
        width=160,
        height=160,
        tile_size=8,
        min_area=512,
        max_text_overlap=0.24,
    )

    assert rejected == []
    assert any(item.reason == "foreground_object_on_surface" and item.bbox.area >= 48 * 48 for item in objects)


def test_full_page_backing_guard():
    assert is_full_page_backing(BBox(0, 0, 100, 90), 100, 100) is True
    assert is_full_page_backing(BBox(10, 10, 20, 20), 100, 100) is False


def test_layer_stack_assets_only_for_raster(tmp_path: Path):
    image = Image.new("RGB", (50, 50), (255, 255, 255))
    rgb = np.asarray(image)
    raster = [BBox(5, 5, 20, 20)]
    from tools.psd_like_layer_decomposition_experiment import Candidate

    raster_candidates = [
        Candidate(
            id="raster_raw_0001",
            kind="raster",
            bbox=raster[0],
            score=0.9,
            scores={"textOverlap": 0.0, "raster": 0.9, "shape": 0.0},
            reason="test",
        )
    ]
    shape_candidates = [
        Candidate(
            id="shape_raw_0001",
            kind="shape",
            bbox=BBox(0, 0, 30, 30),
            score=0.8,
            scores={"textOverlap": 0.0, "raster": 0.0, "shape": 0.8},
            reason="test",
        )
    ]
    text_mask = np.zeros((50, 50), dtype=bool)
    ownership = build_raster_ownership(raster_candidates, [], text_mask)
    assets = crop_raster_assets(image, raster_candidates, tmp_path, text_mask=text_mask)
    stack = build_layer_stack(
        image_path=tmp_path / "source.png",
        ocr_path=None,
        image=image,
        rgb=rgb,
        ocr_blocks=[],
        raster_candidates=raster_candidates,
        shape_candidates=shape_candidates,
        asset_refs=assets,
        ownership=ownership,
        rejected=[],
        thresholds={"maxTextOverlap": 0.2},
    )

    raster_layers = [layer for layer in stack["layers"] if layer["type"] == "raster"]
    shape_layers = [layer for layer in stack["layers"] if layer["type"] == "shape"]
    assert raster_layers[0]["asset"] == "assets/raster_0001.png"
    assert (tmp_path / raster_layers[0]["asset"]).exists()
    assert "asset" not in shape_layers[0]
    assert stack["diagnostics"]["missingAssetCount"] == 0


def test_raster_asset_inpaints_ocr_text_pixels_instead_of_cutting_alpha(tmp_path: Path):
    from tools.psd_like_layer_decomposition_experiment import Candidate

    image = Image.new("RGB", (40, 40), (200, 40, 40))
    pixels = np.asarray(image).copy()
    pixels[10:20, 10:20] = (255, 255, 255)
    image = Image.fromarray(pixels, mode="RGB")
    candidate = Candidate(
        id="raster_raw_0001",
        kind="raster",
        bbox=BBox(0, 0, 40, 40),
        score=0.9,
        scores={"textOverlap": 0.1, "raster": 0.9, "shape": 0.0},
        reason="test",
    )
    block = OCRBlock(id="text_0001", text="T", bbox=BBox(10, 10, 10, 10), confidence=0.99)
    text_mask = build_text_mask(40, 40, [block], padding=0)
    ownership = build_raster_ownership([candidate], [block], text_mask)
    assets = crop_raster_assets(image, [candidate], tmp_path, text_mask=text_mask, ocr_blocks=[block], rgb=np.asarray(image))

    asset = Image.open(tmp_path / assets[candidate.id]).convert("RGBA")
    rgba = np.asarray(asset)

    assert ownership[candidate.id]["textKnockout"] is True
    assert ownership[candidate.id]["coveredTextBlockCount"] == 1
    assert tuple(rgba[12, 12, :3]) == (200, 40, 40)
    assert rgba[12, 12, 3] == 255
    assert tuple(rgba[2, 2, :3]) == (200, 40, 40)
    assert rgba[2, 2, 3] == 255


def test_text_background_estimation_uses_padded_button_fill():
    rgb = np.full((40, 100, 3), 245, dtype=np.uint8)
    rgb[8:32, 10:90] = (18, 102, 253)
    rgb[14:25, 34:66] = (255, 255, 255)

    bg = estimate_text_background_for_box(rgb, BBox(34, 14, 32, 11))

    assert np.linalg.norm(bg.astype(np.int16) - np.array([18, 102, 253], dtype=np.int16)) < 18


def test_inpaint_fill_uses_candidate_local_button_color_not_page_background():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    rgb = np.full((80, 160, 3), 245, dtype=np.uint8)
    rgb[28:56, 42:118] = (255, 132, 0)
    rgb[36:48, 62:98] = (255, 255, 255)
    candidate = Candidate(
        id="button",
        kind="raster",
        bbox=BBox(42, 28, 76, 28),
        score=0.9,
        scores={},
        reason="button",
    )
    block_box = BBox(62, 36, 36, 12)
    text_mask = np.zeros((80, 160), dtype=bool)
    text_mask[36:48, 62:98] = True

    fill = estimate_inpaint_fill_for_candidate_text(rgb, candidate, block_box, text_mask)

    assert color_distance(fill, np.array([255, 132, 0], dtype=np.uint8)) < 18
    assert color_distance(fill, np.array([245, 245, 245], dtype=np.uint8)) > 80


def test_control_surface_with_ocr_promotes_raster_to_shape():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    rgb = np.full((200, 200, 3), 245, dtype=np.uint8)
    rgb[80:108, 58:134] = (255, 132, 0)
    rgb[88:100, 78:114] = (255, 255, 255)
    block = OCRBlock(id="text_0001", text="确定", bbox=BBox(78, 88, 36, 12), confidence=0.99)
    text_mask = build_text_mask(200, 200, [block], padding=0)
    raster = Candidate(
        id="raster_button",
        kind="raster",
        bbox=BBox(58, 80, 76, 28),
        score=0.8,
        scores={"texture": 0.08, "entropy": 0.18, "dominant": 0.88, "textOverlap": 0.08},
        reason="high_texture_with_internal_text",
    )

    rasters, shapes, decisions = promote_control_surfaces([raster], [], [block], text_mask, rgb)

    assert rasters == []
    assert len(shapes) == 1
    assert shapes[0].reason == "editable_control_surface_from_raster"
    assert shapes[0].scores["fillR"] == 255
    assert decisions[0]["sourceRasterId"] == "raster_button"
    assert decisions[0]["coveredTextBlockIds"] == ["text_0001"]


def test_control_surface_preserves_non_text_icon_residual():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    rgb = np.full((300, 300, 3), 245, dtype=np.uint8)
    rgb[80:116, 44:156] = (18, 102, 253)
    rgb[91:105, 58:72] = (255, 255, 255)
    rgb[92:104, 92:128] = (255, 255, 255)
    block = OCRBlock(id="text_0001", text="签到", bbox=BBox(92, 92, 36, 12), confidence=0.99)
    text_mask = build_text_mask(300, 300, [block], padding=0)
    raster = Candidate(
        id="raster_button",
        kind="raster",
        bbox=BBox(44, 80, 112, 36),
        score=0.8,
        scores={"texture": 0.20, "entropy": 0.30, "dominant": 0.78, "textOverlap": 0.05, "raster": 0.5},
        reason="high_texture_with_internal_text",
    )

    rasters, shapes, decisions = promote_control_surfaces([raster], [], [block], text_mask, rgb)

    assert len(shapes) == 1
    assert len(rasters) == 1
    assert rasters[0].reason == "control_foreground_residual"
    assert rasters[0].bbox.x <= 60
    assert decisions[0]["residualRasterCount"] == 1


def test_control_corner_radius_infers_rounded_button_radius():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    image = Image.new("RGB", (140, 80), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 22, 120, 58), radius=18, fill=(18, 102, 253))
    rgb = np.asarray(image)
    shape = Candidate(
        id="control",
        kind="shape",
        bbox=BBox(20, 22, 100, 36),
        score=0.8,
        scores={"fillR": 18.0, "fillG": 102.0, "fillB": 253.0},
        reason="editable_control_surface_from_raster",
    )

    radius = infer_control_corner_radius(rgb, shape)

    assert 12 <= radius <= 18


def test_high_texture_text_region_does_not_promote_to_control_shape():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    rgb = np.full((200, 200, 3), 245, dtype=np.uint8)
    for y in range(72, 104):
        for x in range(60, 130):
            value = 30 if (x + y) % 2 == 0 else 230
            rgb[y, x] = (value, 80, 255 - value)
    rgb[82:94, 82:110] = (255, 255, 255)
    block = OCRBlock(id="text_0001", text="图文", bbox=BBox(82, 82, 28, 12), confidence=0.99)
    text_mask = build_text_mask(200, 200, [block], padding=0)
    raster = Candidate(
        id="raster_photo_text",
        kind="raster",
        bbox=BBox(60, 72, 70, 32),
        score=0.8,
        scores={"texture": 0.66, "entropy": 0.82, "dominant": 0.20, "textOverlap": 0.08},
        reason="high_texture_with_internal_text",
    )

    rasters, shapes, decisions = promote_control_surfaces([raster], [], [block], text_mask, rgb)

    assert rasters == [raster]
    assert shapes == []
    assert decisions == []


def test_ocr_anchored_yellow_button_creates_shape_without_button_raster(tmp_path: Path):
    from tools.psd_like_layer_decomposition_experiment import Candidate

    image = Image.new("RGB", (180, 100), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 30, 140, 64), radius=12, fill=(246, 196, 42))
    draw.rectangle((68, 40, 112, 54), fill=(20, 20, 20))
    rgb = np.asarray(image)
    block = OCRBlock(id="text_0001", text="确认支付", bbox=BBox(68, 38, 44, 18), confidence=0.99)
    text_mask = build_text_mask(180, 100, [block], padding=0)
    raster = Candidate(
        id="raster_button",
        kind="raster",
        bbox=BBox(40, 30, 100, 34),
        score=0.88,
        scores={"texture": 0.12, "entropy": 0.16, "dominant": 0.82, "textOverlap": 0.10},
        reason="button_like_raster",
    )

    controls, _ = detect_ocr_anchored_control_surfaces(rgb, [block], text_mask)
    suppression = suppress_control_owned_rasters([raster], controls)
    assets = crop_raster_assets(image, suppression.rasters, tmp_path, text_mask=text_mask, ocr_blocks=[block], rgb=rgb)
    ownership = build_raster_ownership(suppression.rasters, [block], text_mask)
    stack = build_layer_stack(
        image_path=tmp_path / "source.png",
        ocr_path=None,
        image=image,
        rgb=rgb,
        ocr_blocks=[block],
        raster_candidates=suppression.rasters,
        shape_candidates=controls,
        asset_refs=assets,
        ownership=ownership,
        rejected=suppression.suppressed,
        thresholds={"maxTextOverlap": 0.2},
    )

    assert len(controls) == 1
    assert controls[0].reason == "ocr_anchored_control_surface"
    assert suppression.rasters == []
    assert suppression.suppressed[0]["reason"] == "control_surface_owned_background"
    assert stack["diagnostics"]["ocrAnchoredControlSurfaceCount"] == 1
    assert stack["diagnostics"]["controlOwnedRasterSuppressedCount"] == 1
    assert stack["diagnostics"]["shapeAssetCount"] == 0
    assert [layer["type"] for layer in stack["layers"]] == ["shape", "text"]
    assert stack["layers"][0]["style"]["fill"].lower() == "#f6c42a"
    assert stack["layers"][0]["z"] >= 10000
    assert stack["layers"][1]["z"] >= 30000
    assert not list((tmp_path / "assets").glob("*.png")) if (tmp_path / "assets").exists() else True


def test_ocr_anchored_short_text_wide_pill_recovers_surface_width():
    image = Image.new("RGB", (260, 120), (248, 248, 248))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((32, 36, 220, 76), radius=20, fill=(80, 146, 76))
    draw.rectangle((104, 48, 148, 64), fill=(255, 255, 255))
    rgb = np.asarray(image)
    block = OCRBlock(id="text_0001", text="GO", bbox=BBox(104, 46, 44, 20), confidence=0.99)
    text_mask = build_text_mask(260, 120, [block], padding=0)

    controls, _ = detect_ocr_anchored_control_surfaces(rgb, [block], text_mask)

    assert controls
    assert controls[0].bbox.width >= 110
    assert controls[0].scores["outerRingDelta"] >= 18


def test_ocr_anchored_plain_text_does_not_create_control_surface():
    rgb = np.full((120, 180, 3), 248, dtype=np.uint8)
    rgb[42:58, 70:118] = (20, 20, 20)
    block = OCRBlock(id="text_0001", text="Plain", bbox=BBox(70, 40, 48, 20), confidence=0.99)
    text_mask = build_text_mask(180, 120, [block], padding=0)

    controls, _ = detect_ocr_anchored_control_surfaces(rgb, [block], text_mask)

    assert controls == []


def test_ocr_anchored_textured_photo_text_does_not_create_control_surface():
    rgb = np.full((140, 220, 3), 245, dtype=np.uint8)
    for y in range(30, 100):
        for x in range(30, 190):
            value = 40 if (x + y) % 2 == 0 else 220
            rgb[y, x] = (value, 90, 255 - value)
    rgb[58:74, 84:136] = (255, 255, 255)
    block = OCRBlock(id="text_0001", text="Photo", bbox=BBox(84, 56, 52, 20), confidence=0.99)
    text_mask = build_text_mask(220, 140, [block], padding=0)

    controls, _ = detect_ocr_anchored_control_surfaces(rgb, [block], text_mask)

    assert controls == []


def test_control_owned_raster_keeps_inner_icon_but_suppresses_edge_fragment():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    control = Candidate(
        id="control",
        kind="shape",
        bbox=BBox(40, 30, 120, 40),
        score=0.8,
        scores={"fillR": 240.0, "fillG": 180.0, "fillB": 40.0},
        reason="ocr_anchored_control_surface",
    )
    edge = Candidate(
        id="edge",
        kind="raster",
        bbox=BBox(42, 32, 14, 8),
        score=0.6,
        scores={},
        reason="control_foreground_residual",
    )
    icon = Candidate(
        id="icon",
        kind="raster",
        bbox=BBox(76, 42, 14, 14),
        score=0.7,
        scores={},
        reason="control_foreground_residual",
    )

    result = suppress_control_owned_rasters([edge, icon], [control])

    assert result.rasters == [icon]
    assert result.suppressed[0]["id"] == "edge"
    assert result.suppressed[0]["reason"] == "control_residual_edge_fragment"
    assert result.residual_suppressed_count == 1


def test_control_owned_raster_does_not_suppress_large_parent_region():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    control = Candidate(
        id="control",
        kind="shape",
        bbox=BBox(280, 160, 120, 40),
        score=0.8,
        scores={"fillR": 240.0, "fillG": 180.0, "fillB": 40.0},
        reason="ocr_anchored_control_surface",
    )
    parent_raster = Candidate(
        id="parent_raster",
        kind="raster",
        bbox=BBox(220, 120, 260, 180),
        score=0.7,
        scores={},
        reason="high_texture_region",
    )
    button_raster = Candidate(
        id="button_raster",
        kind="raster",
        bbox=BBox(278, 158, 124, 44),
        score=0.7,
        scores={},
        reason="button_like_raster",
    )

    result = suppress_control_owned_rasters([parent_raster, button_raster], [control])

    assert result.rasters == [parent_raster]
    assert [item["id"] for item in result.suppressed] == ["button_raster"]
    assert result.suppressed[0]["reason"] == "control_surface_owned_background"


def test_exported_rejections_keep_control_ownership_decisions_when_truncated():
    rejected = [{"kind": "shape", "reason": "too_small", "id": f"shape_{index:04d}"} for index in range(205)]
    rejected.append(
        {
            "kind": "control_owned_raster_suppressed",
            "id": "button_raster",
            "reason": "control_surface_owned_background",
        }
    )
    rejected.append(
        {
            "kind": "text_owned_raster_suppressed",
            "id": "text_fragment",
            "reason": "text_owned_thin_fragment",
        }
    )

    exported = exported_rejections(rejected, limit=200)

    assert len(exported) == 200
    assert exported[0]["kind"] == "control_owned_raster_suppressed"
    assert exported[0]["id"] == "button_raster"
    assert exported[1]["kind"] == "text_owned_raster_suppressed"
    assert exported[1]["id"] == "text_fragment"


def test_text_owned_raster_suppresses_thin_text_fragment():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    block = OCRBlock(id="text_0001", text="Total", bbox=BBox(40, 40, 96, 20), confidence=0.99)
    text_mask = build_text_mask(220, 120, [block], padding=0)
    fragment = Candidate(
        id="text_stroke_fragment",
        kind="raster",
        bbox=BBox(56, 48, 72, 8),
        score=0.7,
        scores={"textOverlap": 0.5, "texture": 0.9, "edge": 0.7},
        reason="foreground_object_on_surface",
    )

    kept, suppressed = suppress_text_owned_raster_fragments([fragment], [block], text_mask)

    assert kept == []
    assert suppressed[0]["id"] == "text_stroke_fragment"
    assert suppressed[0]["reason"] == "text_owned_thin_fragment"


def test_text_owned_raster_keeps_large_parent_region_with_text():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    block = OCRBlock(id="text_0001", text="Banner", bbox=BBox(90, 80, 120, 28), confidence=0.99)
    text_mask = build_text_mask(360, 220, [block], padding=0)
    parent = Candidate(
        id="parent_photo",
        kind="raster",
        bbox=BBox(40, 40, 280, 140),
        score=0.8,
        scores={"textOverlap": 0.04, "texture": 0.8, "edge": 0.6},
        reason="high_texture_with_internal_text",
    )

    kept, suppressed = suppress_text_owned_raster_fragments([parent], [block], text_mask)

    assert kept == [parent]
    assert suppressed == []


def test_complex_shape_region_promotes_to_single_raster():
    from tools.psd_like_layer_decomposition_experiment import Candidate

    shape = Candidate(
        id="shape_0001",
        kind="shape",
        bbox=BBox(0, 0, 220, 160),
        score=0.7,
        scores={"dominant": 0.65, "textOverlap": 0.02, "texture": 0.18, "edge": 0.14},
        reason="low_texture_solid_region",
    )
    rasters = [
        Candidate(
            id=f"raster_{index:04d}",
            kind="raster",
            bbox=BBox(10 + index * 30, 20, 20, 30),
            score=0.5,
            scores={"textOverlap": 0.0, "raster": 0.5, "shape": 0.0},
            reason="fragment",
        )
        for index in range(4)
    ]

    promoted_rasters, remaining_shapes, decisions = promote_complex_shape_regions(rasters, [shape])

    assert remaining_shapes == []
    assert len(promoted_rasters) == 1
    assert promoted_rasters[0].bbox == shape.bbox
    assert promoted_rasters[0].reason == "complex_visual_region_promoted_from_shape"
    assert decisions[0]["consumedRasterCount"] == 4


def test_draft_runtime_and_preview_are_mechanical_layer_stack_consumers(tmp_path: Path):
    from tools.psd_like_layer_decomposition_experiment import Candidate

    image = Image.new("RGB", (80, 80), (255, 255, 255))
    rgb = np.asarray(image)
    raster_candidate = Candidate(
        id="raster_raw_0001",
        kind="raster",
        bbox=BBox(10, 10, 20, 20),
        score=0.9,
        scores={"textOverlap": 0.0, "raster": 0.9, "shape": 0.0},
        reason="test_raster",
    )
    shape_candidate = Candidate(
        id="shape_raw_0001",
        kind="shape",
        bbox=BBox(0, 0, 60, 40),
        score=0.8,
        scores={"textOverlap": 0.0, "raster": 0.0, "shape": 0.8},
        reason="test_shape",
    )
    text = OCRBlock(id="text_0001", text="Hi", bbox=BBox(12, 44, 20, 12), confidence=0.99)
    text_mask = build_text_mask(80, 80, [text], padding=0)
    ownership = build_raster_ownership([raster_candidate], [text], text_mask)
    assets = crop_raster_assets(image, [raster_candidate], tmp_path, text_mask=text_mask)
    stack = build_layer_stack(
        image_path=tmp_path / "source.png",
        ocr_path=None,
        image=image,
        rgb=rgb,
        ocr_blocks=[text],
        raster_candidates=[raster_candidate],
        shape_candidates=[shape_candidate],
        asset_refs=assets,
        ownership=ownership,
        rejected=[],
        thresholds={"maxTextOverlap": 0.2},
    )
    dsl = build_draft_runtime_dsl(stack, rgb)
    write_preview_html(tmp_path / "preview.html", dsl)
    write_preview_report(tmp_path / "preview_report.md", dsl, stack)
    write_draft_preview_png(tmp_path / "draft_preview.png", dsl, tmp_path)

    children = dsl["root"]["children"]
    assert [child["type"] for child in children] == ["shape", "image", "text"]
    assert dsl["assets"][0]["url"] == "assets/raster_0001.png"

    html = (tmp_path / "preview.html").read_text(encoding="utf-8")
    report = (tmp_path / "preview_report.md").read_text(encoding="utf-8")
    preview = Image.open(tmp_path / "draft_preview.png")
    assert 'class="node raster"' in html
    assert 'class="node text"' in html
    assert "Hi" in html
    assert "- missing image refs: 0" in report
    assert preview.size == (80, 80)
