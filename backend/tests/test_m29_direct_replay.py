from __future__ import annotations

from pathlib import Path

from app.m29_direct_replay import M29DirectReplayOptions, build_m29_direct_replay_dsl
from app.png_tools import PngPixels, decode_png_pixels, encode_rgb_png, read_png_metadata


def test_ocr_text_suppresses_overlapping_m29_symbol(tmp_path: Path) -> None:
    source = make_png(80, 60, fill=(250, 250, 250), marks=[([10, 10, 20, 10], (0, 0, 0))])
    source_path = write_png(tmp_path / "source.png", source)
    m29_dir = tmp_path / "m29"
    symbol = write_png(m29_dir / "assets" / "symbols" / "symbol_001.png", make_png(20, 10, fill=(0, 0, 0)))
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node("symbol_001", "symbol", [10, 10, 20, 10], asset_path=str(symbol.relative_to(m29_dir))),
        ],
    )
    ocr = ocr_document([ocr_block("ocr_text_001", "Hi", [10, 10, 20, 10])])

    result = build_m29_direct_replay_dsl(
        source_png=source_path.read_bytes(),
        source_image_path=str(source_path),
        m29_document=m29,
        ocr_document=ocr,
        output_dir=tmp_path / "out",
    )

    assert result.dsl["root"]["id"] == "m29_direct_root"
    assert {asset["assetId"] for asset in result.dsl["assets"]} >= {
        "m29_direct_asset_original",
        "m29_direct_asset_fallback",
    }
    assert count_children(result.dsl, "m29_direct_text") == 1
    assert count_children(result.dsl, "m29_direct_symbol") == 0
    assert result.report["summary"]["skippedReasons"]["overlapped_by_ocr_text"] == 1


def test_m29_image_replay_copies_asset_and_keeps_lineage(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(100, 80))
    m29_dir = tmp_path / "m29"
    asset = write_png(m29_dir / "assets" / "images" / "image_001.png", make_png(30, 20, fill=(10, 80, 120)))
    m29 = m29_document(tmp_path, nodes=[m29_node("image_001", "image", [20, 15, 30, 20], asset_path=str(asset.relative_to(m29_dir)))])

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        output_dir=tmp_path / "out",
    )

    image_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_direct_image")
    asset_id = image_node["source"]["assetId"]
    dsl_asset = next(asset for asset in result.dsl["assets"] if asset.get("assetId") == asset_id)
    assert image_node["meta"]["sourceM29NodeId"] == "image_001"
    assert (tmp_path / "out" / dsl_asset["url"]).exists()
    assert result.report["summary"]["replayedImageCount"] == 1


def test_fallback_erases_replayed_bboxes_without_mutating_source(tmp_path: Path) -> None:
    source_pixels = make_png(80, 60, fill=(240, 240, 240), marks=[([20, 20, 20, 10], (0, 0, 0))])
    source = write_png(tmp_path / "source.png", source_pixels)
    original_bytes = source.read_bytes()
    m29 = m29_document(tmp_path, nodes=[m29_node("shape_001", "shape", [20, 20, 20, 10], style={"fill": "#000000"})])

    result = build_m29_direct_replay_dsl(
        source_png=original_bytes,
        source_image_path=str(source),
        m29_document=m29,
        output_dir=tmp_path / "out",
    )

    assert source.read_bytes() == original_bytes
    fallback_asset = next(asset for asset in result.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_pixels = decode_png_pixels((tmp_path / "out" / fallback_asset["url"]).read_bytes())
    assert fallback_pixels.rows[22][22 * 3 : 22 * 3 + 3] != b"\x00\x00\x00"
    assert result.report["summary"]["fallbackErasedBBoxCount"] == 1


def test_blocked_primitives_are_report_only(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(80, 60))
    m29 = m29_document(tmp_path, nodes=[], blocked=[{"id": "blocked_001", "bbox": [10, 10, 20, 10], "source": "symbol_detector", "reasons": ["inside_image_primitive"]}])

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        output_dir=tmp_path / "out",
    )

    assert result.report["summary"]["skippedBlockedCount"] == 1
    assert not any(str(child.get("role", "")).startswith("m29_direct") for child in result.dsl["root"]["children"])


def test_node_budget_prevents_layer_explosion(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(200, 120))
    nodes = [m29_node(f"symbol_{index:03d}", "symbol", [index * 3, 10, 2, 8]) for index in range(1, 10)]
    m29 = m29_document(tmp_path, nodes=nodes)

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        output_dir=tmp_path / "out",
        options=M29DirectReplayOptions(max_total_visible_nodes=3, min_symbol_area=1),
    )

    assert result.report["summary"]["visibleNodeCount"] == 3
    assert result.report["summary"]["maxTotalVisibleNodesExceeded"] is True
    assert result.report["summary"]["skippedReasons"]["node_budget_exceeded"] == 6


def test_m292_document_controls_direct_replay_decisions(tmp_path: Path) -> None:
    source = write_png(
        tmp_path / "source.png",
        make_png(
            100,
            80,
            fill=(248, 248, 248),
            marks=[([10, 10, 20, 10], (0, 0, 0)), ([50, 10, 20, 10], (0, 0, 0)), ([10, 40, 8, 8], (20, 20, 20)), ([23, 40, 8, 8], (20, 20, 20))],
        ),
    )
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node("symbol_001", "symbol", [10, 40, 8, 8]),
            m29_node("symbol_002", "symbol", [23, 40, 8, 8]),
            m29_node("shape_001", "shape", [50, 10, 20, 10], style={"fill": "#000000"}),
        ],
    )
    m292 = {
        "summary": {"sourceObjectCount": 4, "editableTextCount": 1, "preservedRasterTextCount": 1},
        "sourceObjects": [
            m292_object("m292_text", [10, 10, 20, 10], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"]),
            m292_object("m292_preserve", [50, 10, 20, 10], "preserve_raster_text", "preserve_raster", "preserve_in_parent_raster"),
            m292_object("m292_icon", [10, 40, 21, 8], "raster_icon", "raster_icon", "icon_replay", m29_ids=["symbol_001", "symbol_002"]),
            m292_object("m292_shape", [60, 55, 18, 4], "separator", "shape_geometry", "shape_replay", m29_ids=["shape_001"]),
        ],
    }

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_text", "Hi", [10, 10, 20, 10])]),
        m292_document=m292,
        output_dir=tmp_path / "out",
    )

    assert count_children(result.dsl, "m29_direct_text") == 1
    assert count_children(result.dsl, "m29_direct_symbol") == 1
    assert count_children(result.dsl, "m29_direct_shape") == 1
    assert result.report["summary"]["fallbackErasedBBoxCount"] == 3
    assert result.report["summary"]["skippedReasons"]["preserve_in_parent_raster"] == 1
    assert result.report["summary"]["m292SourcePhysicalGraph"]["sourceObjectCount"] == 4
    icon = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_direct_symbol")
    assert icon["layout"]["width"] == 21
    assert icon["meta"]["sourceM292ObjectId"] == "m292_icon"
    assert icon["meta"]["sourceM29NodeIds"] == ["symbol_001", "symbol_002"]


def test_m295_recovered_raster_foreground_replays_as_symbol_crop(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(100, 80, fill=(248, 248, 248), marks=[([30, 30, 28, 28], (80, 30, 160))]))
    m292 = {
        "summary": {"sourceObjectCount": 2},
        "sourceObjects": [
            m292_object("m292_recovered_icon", [30, 30, 28, 28], "raster_icon", "raster_icon", "icon_replay"),
            m292_object("m292_diagnostic", [70, 30, 16, 16], "unknown", "diagnostic_only", "skip"),
        ],
    }
    plan = m295_plan(
        [
            m295_item("plan_icon", "m292_recovered_icon", [30, 30, 28, 28], "icon_replay", "m29_direct_symbol"),
            m295_item("plan_diag", "m292_diagnostic", [70, 30, 16, 16], "diagnostic_only", None),
        ]
    )

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[]),
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    assert count_children(result.dsl, "m29_direct_symbol") == 1
    assert count_children(result.dsl, "m29_direct_shape") == 0
    assert result.report["summary"]["skippedReasons"]["diagnostic_only"] == 1
    symbol = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_direct_symbol")
    assert symbol["layout"]["width"] == 28
    assert symbol["meta"]["sourceM295PlanItemId"] == "plan_icon"


def test_m292_preserve_raster_text_is_not_erased_from_fallback(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(80, 60, fill=(240, 240, 240), marks=[([20, 20, 18, 8], (0, 0, 0))]))
    original_pixel = source.read_bytes()
    m292 = {
        "summary": {"sourceObjectCount": 1},
        "sourceObjects": [
            m292_object("m292_art", [20, 20, 18, 8], "preserve_raster_text", "preserve_raster", "preserve_in_parent_raster"),
        ],
    }

    result = build_m29_direct_replay_dsl(
        source_png=original_pixel,
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[]),
        ocr_document=ocr_document([ocr_block("ocr_art", "ART", [20, 20, 18, 8])]),
        m292_document=m292,
        output_dir=tmp_path / "out",
    )

    fallback_asset = next(asset for asset in result.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_pixels = decode_png_pixels((tmp_path / "out" / fallback_asset["url"]).read_bytes())
    assert fallback_pixels.rows[22][22 * 3 : 22 * 3 + 3] == b"\x00\x00\x00"
    assert result.report["summary"]["fallbackErasedBBoxCount"] == 0


def test_m292_editable_text_inside_copied_image_asset_is_erased_from_asset_only(tmp_path: Path) -> None:
    source_pixels = make_png(
        120,
        90,
        fill=(245, 245, 245),
        marks=[([10, 10, 80, 50], (220, 220, 220)), ([30, 25, 20, 8], (0, 0, 0))],
    )
    source = write_png(tmp_path / "source.png", source_pixels)
    source_bytes = source.read_bytes()
    m29_dir = tmp_path / "m29"
    raw_asset = write_png(m29_dir / "assets" / "images" / "image_001.png", make_png(80, 50, fill=(220, 220, 220), marks=[([20, 15, 20, 8], (0, 0, 0))]))
    raw_asset_bytes = raw_asset.read_bytes()
    m29 = m29_document(
        tmp_path,
        nodes=[m29_node("image_001", "image", [10, 10, 80, 50], asset_path=str(raw_asset.relative_to(m29_dir)))],
    )
    m292 = {
        "summary": {"sourceObjectCount": 2},
        "sourceObjects": [
            m292_object("m292_image", [10, 10, 80, 50], "media_region", "preserve_raster", "image_replay", m29_ids=["image_001"]),
            m292_object("m292_text", [30, 25, 20, 8], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"]),
        ],
    }

    result = build_m29_direct_replay_dsl(
        source_png=source_bytes,
        source_image_path=str(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_text", "TEXT", [30, 25, 20, 8])]),
        m292_document=m292,
        output_dir=tmp_path / "out",
    )

    copied_pixels = copied_image_pixels(result.dsl, tmp_path / "out")
    assert copied_pixels.rows[17][25 * 3 : 25 * 3 + 3] != b"\x00\x00\x00"
    assert source.read_bytes() == source_bytes
    assert raw_asset.read_bytes() == raw_asset_bytes
    assert result.report["summary"]["copiedImageAssetTextErasedCount"] == 1


def test_m292_preserved_text_inside_copied_image_asset_is_not_erased(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(120, 90, fill=(245, 245, 245)))
    m29_dir = tmp_path / "m29"
    raw_asset = write_png(m29_dir / "assets" / "images" / "image_001.png", make_png(80, 50, fill=(220, 220, 220), marks=[([20, 15, 20, 8], (0, 0, 0))]))
    raw_asset_bytes = raw_asset.read_bytes()
    m29 = m29_document(
        tmp_path,
        nodes=[m29_node("image_001", "image", [10, 10, 80, 50], asset_path=str(raw_asset.relative_to(m29_dir)))],
    )
    m292 = {
        "summary": {"sourceObjectCount": 2},
        "sourceObjects": [
            m292_object("m292_image", [10, 10, 80, 50], "media_region", "preserve_raster", "image_replay", m29_ids=["image_001"]),
            m292_object("m292_art", [30, 25, 20, 8], "preserve_raster_text", "preserve_raster", "preserve_in_parent_raster", ocr_ids=["ocr_art"]),
        ],
    }

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_art", "ART", [30, 25, 20, 8])]),
        m292_document=m292,
        output_dir=tmp_path / "out",
    )

    copied_pixels = copied_image_pixels(result.dsl, tmp_path / "out")
    assert copied_pixels.rows[17][25 * 3 : 25 * 3 + 3] == b"\x00\x00\x00"
    assert raw_asset.read_bytes() == raw_asset_bytes
    assert result.report["summary"]["copiedImageAssetTextErasedCount"] == 0
    assert result.report["summary"]["fallbackErasedBBoxCount"] == 1


def test_m292_editable_text_outside_copied_image_asset_is_not_erased_from_asset(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(120, 90, fill=(245, 245, 245), marks=[([95, 25, 15, 8], (0, 0, 0))]))
    m29_dir = tmp_path / "m29"
    raw_asset = write_png(m29_dir / "assets" / "images" / "image_001.png", make_png(80, 50, fill=(220, 220, 220), marks=[([20, 15, 20, 8], (0, 0, 0))]))
    raw_asset_bytes = raw_asset.read_bytes()
    m29 = m29_document(
        tmp_path,
        nodes=[m29_node("image_001", "image", [10, 10, 80, 50], asset_path=str(raw_asset.relative_to(m29_dir)))],
    )
    m292 = {
        "summary": {"sourceObjectCount": 2},
        "sourceObjects": [
            m292_object("m292_image", [10, 10, 80, 50], "media_region", "preserve_raster", "image_replay", m29_ids=["image_001"]),
            m292_object("m292_text", [95, 25, 15, 8], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"]),
        ],
    }

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_text", "OUT", [95, 25, 15, 8])]),
        m292_document=m292,
        output_dir=tmp_path / "out",
    )

    copied_pixels = copied_image_pixels(result.dsl, tmp_path / "out")
    assert copied_pixels.rows[17][25 * 3 : 25 * 3 + 3] == b"\x00\x00\x00"
    assert raw_asset.read_bytes() == raw_asset_bytes
    assert result.report["summary"]["copiedImageAssetTextErasedCount"] == 0


def test_m295_replay_plan_controls_visible_nodes(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(120, 90, fill=(245, 245, 245), marks=[([10, 10, 20, 8], (0, 0, 0)), ([50, 10, 20, 8], (0, 0, 0))]))
    m292 = {
        "summary": {"sourceObjectCount": 2},
        "sourceObjects": [
            m292_object("m292_keep", [10, 10, 20, 8], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_keep"]),
            m292_object("m292_suppress", [50, 10, 20, 8], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_suppress"]),
        ],
    }
    plan = m295_plan(
        [
            m295_item("plan_keep", "m292_keep", [10, 10, 20, 8], "text_replay", "m29_direct_text"),
            m295_item("plan_suppress", "m292_suppress", [50, 10, 20, 8], "suppress_duplicate", None),
        ]
    )

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[]),
        ocr_document=ocr_document([ocr_block("ocr_keep", "KEEP", [10, 10, 20, 8]), ocr_block("ocr_suppress", "DROP", [50, 10, 20, 8])]),
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    assert count_children(result.dsl, "m29_direct_text") == 1
    text_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_direct_text")
    assert text_node["content"]["text"] == "KEEP"
    assert text_node["meta"]["sourceM295PlanItemId"] == "plan_keep"
    assert text_node["meta"]["m295FinalReplayAction"] == "text_replay"
    assert result.report["summary"]["skippedReasons"]["suppress_duplicate"] == 1
    assert result.report["summary"]["m295ReplayPlan"]["plannedVisibleNodeCount"] == 1


def test_m295_plan_cleanup_targets_drive_copied_image_asset_erasure(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(120, 90, fill=(245, 245, 245), marks=[([10, 10, 80, 50], (220, 220, 220)), ([30, 25, 20, 8], (0, 0, 0))]))
    m29_dir = tmp_path / "m29"
    raw_asset = write_png(m29_dir / "assets" / "images" / "image_001.png", make_png(80, 50, fill=(220, 220, 220), marks=[([20, 15, 20, 8], (0, 0, 0))]))
    m29 = m29_document(
        tmp_path,
        nodes=[m29_node("image_001", "image", [10, 10, 80, 50], asset_path=str(raw_asset.relative_to(m29_dir)))],
    )
    m292 = {
        "summary": {"sourceObjectCount": 2},
        "sourceObjects": [
            m292_object("m292_image", [10, 10, 80, 50], "media_region", "preserve_raster", "image_replay", m29_ids=["image_001"]),
            m292_object("m292_text", [30, 25, 20, 8], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"]),
        ],
    }
    plan = m295_plan(
        [
            m295_item("plan_image", "m292_image", [10, 10, 80, 50], "image_replay", "m29_direct_image"),
            m295_item(
                "plan_text",
                "m292_text",
                [30, 25, 20, 8],
                "text_replay",
                "m29_direct_text",
                cleanup_targets=[
                    {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"},
                    {"target": "copied_image_asset", "targetSourceObjectId": "m292_image", "reason": "editable_text_contained_by_media"},
                ],
            ),
        ]
    )

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_text", "TEXT", [30, 25, 20, 8])]),
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    copied_pixels = copied_image_pixels(result.dsl, tmp_path / "out")
    assert copied_pixels.rows[17][25 * 3 : 25 * 3 + 3] != b"\x00\x00\x00"
    assert result.report["summary"]["copiedImageAssetTextErasedCount"] == 1
    roles = [child.get("role") for child in result.dsl["root"]["children"]]
    assert roles.index("m29_direct_image") < roles.index("m29_direct_text")


def test_m295_plan_without_asset_cleanup_target_does_not_erase_copied_image(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(120, 90, fill=(245, 245, 245), marks=[([10, 10, 80, 50], (220, 220, 220)), ([30, 25, 20, 8], (0, 0, 0))]))
    m29_dir = tmp_path / "m29"
    raw_asset = write_png(m29_dir / "assets" / "images" / "image_001.png", make_png(80, 50, fill=(220, 220, 220), marks=[([20, 15, 20, 8], (0, 0, 0))]))
    m29 = m29_document(
        tmp_path,
        nodes=[m29_node("image_001", "image", [10, 10, 80, 50], asset_path=str(raw_asset.relative_to(m29_dir)))],
    )
    m292 = {
        "summary": {"sourceObjectCount": 2},
        "sourceObjects": [
            m292_object("m292_image", [10, 10, 80, 50], "media_region", "preserve_raster", "image_replay", m29_ids=["image_001"]),
            m292_object("m292_text", [30, 25, 20, 8], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"]),
        ],
    }
    plan = m295_plan(
        [
            m295_item("plan_image", "m292_image", [10, 10, 80, 50], "image_replay", "m29_direct_image"),
            m295_item("plan_text", "m292_text", [30, 25, 20, 8], "text_replay", "m29_direct_text"),
        ]
    )

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_text", "TEXT", [30, 25, 20, 8])]),
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    copied_pixels = copied_image_pixels(result.dsl, tmp_path / "out")
    assert copied_pixels.rows[17][25 * 3 : 25 * 3 + 3] == b"\x00\x00\x00"
    assert result.report["summary"]["copiedImageAssetTextErasedCount"] == 0


def test_m295_shape_replay_preserves_geometry_fit_radius(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(140, 90, fill=(245, 245, 245), marks=[([20, 20, 90, 32], (235, 235, 235))]))
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node(
                "shape_001",
                "shape",
                [20, 20, 90, 32],
                style={"fill": "#EEEEEE"},
                geometry={"kind": "rounded_rect", "confidence": "high", "params": {"radius": 7}, "metrics": {}, "evidence": ["test"]},
            )
        ],
    )
    m292 = {
        "summary": {"sourceObjectCount": 1},
        "sourceObjects": [m292_object("m292_shape", [20, 20, 90, 32], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_001"])],
    }
    plan = m295_plan([m295_item("plan_shape", "m292_shape", [20, 20, 90, 32], "shape_replay", "m29_direct_shape")])

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    shape = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_direct_shape")
    assert shape["style"]["radius"] == 7
    assert shape["meta"]["m29DirectShapeStyleSource"] == "shape_geometry_fit"
    assert shape["meta"]["m29DirectShapeRadius"] == 7


def test_m295_low_contrast_support_shape_uses_geometry_fit_radius(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(180, 100, fill=(248, 248, 248), marks=[([30, 30, 120, 40], (238, 238, 238))]))
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node(
                "shape_support_001",
                "shape",
                [30, 30, 120, 40],
                subtype="low_contrast_support",
                style={"fill": "#EEEEEE"},
                geometry={"kind": "pill", "confidence": "high", "params": {"radius": 20}, "metrics": {}, "evidence": ["test"]},
            )
        ],
    )
    m292 = {
        "summary": {"sourceObjectCount": 1},
        "sourceObjects": [m292_object("m292_support", [30, 30, 120, 40], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_support_001"])],
    }
    plan = m295_plan([m295_item("plan_support", "m292_support", [30, 30, 120, 40], "shape_replay", "m29_direct_shape")])

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    shape = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_direct_shape")
    assert shape["style"]["radius"] == 20
    assert shape["meta"]["m29DirectShapeStyleSource"] == "shape_geometry_fit"
    assert shape["meta"]["m29DirectShapeRadius"] == 20


def test_m295_text_support_background_shape_uses_geometry_fit_radius(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(180, 100, fill=(248, 248, 248), marks=[([42, 32, 84, 26], (255, 232, 235))]))
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node(
                "shape_text_support_001",
                "shape",
                [42, 32, 84, 26],
                subtype="text_support_background",
                style={"fill": "#FFE8EB"},
                geometry={"kind": "pill", "confidence": "high", "params": {"radius": 13}, "metrics": {}, "evidence": ["text_support_background_region"]},
            )
        ],
    )
    m292 = {
        "summary": {"sourceObjectCount": 1},
        "sourceObjects": [m292_object("m292_text_support", [42, 32, 84, 26], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_text_support_001"])],
    }
    plan = m295_plan([m295_item("plan_text_support", "m292_text_support", [42, 32, 84, 26], "shape_replay", "m29_direct_shape")])

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    shape = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_direct_shape")
    assert shape["style"]["fill"] == "#FFE8EB"
    assert shape["style"]["radius"] == 13
    assert shape["meta"]["sourceM29NodeIds"] == ["shape_text_support_001"]
    assert shape["meta"]["m29DirectShapeStyleSource"] == "shape_geometry_fit"
    assert shape["meta"]["m29DirectShapeRadius"] == 13


def test_m292_shape_replay_preserves_geometry_fit_radius_without_m295_plan(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(140, 90, fill=(245, 245, 245), marks=[([20, 20, 90, 32], (235, 235, 235))]))
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node(
                "shape_001",
                "shape",
                [20, 20, 90, 32],
                style={"fill": "#EEEEEE"},
                geometry={"kind": "rounded_rect", "confidence": "medium", "params": {"radius": 6}, "metrics": {}, "evidence": ["test"]},
            )
        ],
    )
    m292 = {
        "summary": {"sourceObjectCount": 1},
        "sourceObjects": [m292_object("m292_shape", [20, 20, 90, 32], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_001"])],
    }

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        m292_document=m292,
        output_dir=tmp_path / "out",
    )

    shape = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_direct_shape")
    assert shape["style"]["radius"] == 6
    assert shape["meta"]["m29DirectShapeStyleSource"] == "shape_geometry_fit"


def test_low_contrast_support_rect_geometry_does_not_invent_radius(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(180, 100, fill=(248, 248, 248), marks=[([20, 0, 140, 40], (238, 238, 238))]))
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node(
                "shape_support_001",
                "shape",
                [20, 0, 140, 40],
                subtype="low_contrast_support",
                style={"fill": "#EEEEEE"},
                geometry={"kind": "rect", "confidence": "medium", "params": {}, "metrics": {}, "evidence": ["test"]},
            )
        ],
    )
    m292 = {
        "summary": {"sourceObjectCount": 1},
        "sourceObjects": [m292_object("m292_support", [20, 0, 140, 40], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_support_001"])],
    }
    plan = m295_plan([m295_item("plan_support", "m292_support", [20, 0, 140, 40], "shape_replay", "m29_direct_shape")])

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    shape = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_direct_shape")
    assert "radius" not in shape["style"]
    assert shape["meta"]["m29DirectShapeStyleSource"] == "sampled_fill_only"


def test_shape_replay_without_raw_radius_does_not_invent_radius(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(140, 90, fill=(245, 245, 245), marks=[([20, 20, 90, 32], (235, 235, 235))]))
    m29 = m29_document(tmp_path, nodes=[m29_node("shape_001", "shape", [20, 20, 90, 32])])
    m292 = {
        "summary": {"sourceObjectCount": 1},
        "sourceObjects": [m292_object("m292_shape", [20, 20, 90, 32], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_001"])],
    }

    result = build_m29_direct_replay_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29,
        m292_document=m292,
        output_dir=tmp_path / "out",
    )

    shape = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_direct_shape")
    assert "radius" not in shape["style"]
    assert shape["meta"]["m29DirectShapeStyleSource"] == "sampled_fill_only"


def make_png(width: int, height: int, *, fill: tuple[int, int, int] = (250, 250, 250), marks: list[tuple[list[int], tuple[int, int, int]]] | None = None) -> PngPixels:
    rows = [bytearray(bytes(fill) * width) for _ in range(height)]
    for bbox, color in marks or []:
        x, y, w, h = bbox
        for row_index in range(y, y + h):
            for column in range(x, x + w):
                rows[row_index][column * 3 : column * 3 + 3] = bytes(color)
    return PngPixels(width=width, height=height, rows=[bytes(row) for row in rows])


def write_png(path: Path, pixels: PngPixels) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_rgb_png(pixels.width, pixels.height, pixels.rows))
    assert read_png_metadata(path.read_bytes()) is not None
    return path


def m29_document(tmp_path: Path, *, nodes: list[dict], blocked: list[dict] | None = None) -> dict:
    m29_dir = tmp_path / "m29"
    m29_dir.mkdir(parents=True, exist_ok=True)
    return {
        "version": "0.1",
        "sourceImage": str(tmp_path / "source.png"),
        "sourceM29NodesJson": str(m29_dir / "nodes.json"),
        "imageSize": {"width": 100, "height": 80},
        "nodes": nodes,
        "relations": [],
        "blocked": blocked or [],
        "debug": {},
        "warnings": [],
        "meta": {"counts": {}},
    }


def m29_node(
    node_id: str,
    node_type: str,
    bbox: list[int],
    *,
    asset_path: str | None = None,
    style: dict | None = None,
    subtype: str | None = None,
    geometry: dict | None = None,
) -> dict:
    data = {
        "id": node_id,
        "type": node_type,
        "subtype": subtype or ("separator" if node_type == "shape" else "icon_candidate"),
        "bbox": bbox,
        "confidence": 0.9,
        "source": f"{node_type}_detector",
        "sourceOrder": 0,
        "layerHint": "content",
        "reasons": ["solid_fill"] if node_type == "shape" else ["test"],
        "metrics": {"colorCount": 1, "textureScore": 0.01, "edgeScore": 0, "fillRatio": 1, "aspectRatio": bbox[2] / bbox[3], "brightness": 200, "meanRgb": [0, 0, 0]},
    }
    if asset_path:
        data["assetPath"] = asset_path
    if style:
        data["style"] = style
    if geometry:
        data["geometry"] = geometry
    return data


def ocr_document(blocks: list[dict]) -> dict:
    return {"version": "0.1", "taskId": "test", "provider": "test", "model": None, "imageSize": {"width": 80, "height": 60}, "coordinateSpace": "pixel", "blocks": blocks, "warnings": []}


def ocr_block(block_id: str, text: str, bbox: list[int]) -> dict:
    return {"id": block_id, "text": text, "bbox": bbox, "confidence": 0.95, "lineId": block_id, "blockId": block_id, "source": "test"}


def count_children(dsl: dict, role: str) -> int:
    return sum(1 for child in dsl["root"]["children"] if child.get("role") == role)


def copied_image_pixels(dsl: dict, output_dir: Path) -> PngPixels:
    image_node = next(child for child in dsl["root"]["children"] if child.get("role") == "m29_direct_image")
    asset_id = image_node["source"]["assetId"]
    asset = next(item for item in dsl["assets"] if item.get("assetId") == asset_id)
    return decode_png_pixels((output_dir / asset["url"]).read_bytes())


def m292_object(
    object_id: str,
    bbox: list[int],
    visual_kind: str,
    pixel_owner: str,
    replay_decision: str,
    *,
    m29_ids: list[str] | None = None,
    ocr_ids: list[str] | None = None,
) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "sourceEvidence": {
            "ocrBoxIds": ocr_ids or [],
            "m29NodeIds": m29_ids or [],
            "blockedIds": [],
            "localBackgroundConfidence": 0.9,
            "textOverlapRatio": 0.0,
            "mediaContainmentRatio": 0.0,
        },
        "confidence": "high",
        "reasons": ["test"],
        "risks": [],
    }


def m295_plan(items: list[dict]) -> dict:
    return {
        "schemaName": "M295ReplayPlan",
        "schemaVersion": "0.1",
        "summary": {"plannedVisibleNodeCount": sum(1 for item in items if item["finalReplayAction"] in {"text_replay", "image_replay", "icon_replay", "shape_replay"})},
        "planItems": items,
    }


def m295_item(
    item_id: str,
    source_object_id: str,
    bbox: list[int],
    action: str,
    target_role: str | None,
    *,
    cleanup_targets: list[dict] | None = None,
) -> dict:
    return {
        "id": item_id,
        "sourceObjectId": source_object_id,
        "bbox": bbox,
        "finalReplayAction": action,
        "targetRole": target_role,
        "pixelOwner": "editable_text" if action == "text_replay" else "preserve_raster",
        "cleanupTargets": cleanup_targets or [],
        "suppressedSourceObjectIds": [],
        "relationEdgeIds": [],
        "clusterIds": ["cluster_test"],
        "confidence": "high",
        "reasons": ["test"],
        "risks": [],
    }
