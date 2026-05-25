from __future__ import annotations

from pathlib import Path

import pytest

from app.plan_materializer import build_plan_driven_dsl
from app.png_tools import PngPixels, decode_png_pixels, encode_rgb_png, encode_rgba_png, read_png_metadata


def test_m29_plan_materializer_requires_m295_plan(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(80, 60))

    with pytest.raises(ValueError, match="M29.5 replay plan is required"):
        build_plan_driven_dsl(
            source_png=source.read_bytes(),
            source_image_path=str(source),
            m29_document=m29_document(tmp_path, nodes=[]),
            m292_document=m292_document([m292_object("text", [10, 10, 20, 10], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"])]),
            ocr_document=ocr_document([ocr_block("ocr_text", "Hi", [10, 10, 20, 10])]),
            output_dir=tmp_path / "out",
        )


def test_m29_plan_items_are_the_only_visible_materialization_order(tmp_path: Path) -> None:
    source = write_png(
        tmp_path / "source.png",
        make_png(120, 90, fill=(246, 246, 246), marks=[([10, 10, 80, 40], (40, 80, 120)), ([20, 22, 30, 10], (245, 245, 245))]),
    )
    m292 = m292_document(
        [
            m292_object("media", [10, 10, 80, 40], "media_region", "preserve_raster", "image_replay", m29_ids=["image_001"]),
            m292_object("text", [20, 22, 30, 10], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"]),
            m292_object("shape_unplanned", [70, 70, 20, 6], "separator", "shape_geometry", "shape_replay", m29_ids=["shape_001"]),
        ]
    )
    plan = m295_plan(
        [
            m295_item("plan_media", "media", [10, 10, 80, 40], "image_replay", "m29_image"),
            m295_item("plan_text", "text", [20, 22, 30, 10], "text_replay", "m29_text"),
        ]
    )

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("image_001", "image", [10, 10, 80, 40]), m29_node("shape_001", "shape", [70, 70, 20, 6])]),
        m292_document=m292,
        m295_replay_plan=plan,
        ocr_document=ocr_document([ocr_block("ocr_text", "Hi", [20, 22, 30, 10])]),
        output_dir=tmp_path / "out",
    )

    roles = [child.get("role") for child in result.dsl["root"]["children"]]
    assert "m29_image" in roles
    assert "m29_text" in roles
    assert "m29_shape" not in roles
    assert roles.index("m29_image") < roles.index("m29_text")
    assert result.report["summary"]["replayedImageCount"] == 1
    assert result.report["summary"]["replayedTextCount"] == 1


def test_m29_plan_materializer_samples_source_background_instead_of_fixed_white(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(100, 80, fill=(9, 13, 27), marks=[([25, 20, 50, 30], (40, 70, 120))]))

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[]),
        m292_document=m292_document([]),
        m295_replay_plan=m295_plan([]),
        output_dir=tmp_path / "out",
    )

    assert result.dsl["page"]["background"]["value"] != "#F7F8FA"
    assert result.dsl["root"]["style"]["fill"] != "#F7F8FA"
    assert result.dsl["page"]["background"]["value"] == "#090D1B"


def test_promoted_internal_icon_uses_m295_authorized_transparent_asset(tmp_path: Path) -> None:
    source = write_png(
        tmp_path / "source.png",
        make_png(80, 60, fill=(255, 255, 255), marks=[([20, 20, 16, 16], (0, 0, 0))]),
    )
    transparent_asset = tmp_path / "m29_transparent_assets" / "assets" / "transparent" / "promoted_icon.png"
    transparent_asset.parent.mkdir(parents=True, exist_ok=True)
    transparent_asset.write_bytes(encode_rgb_png(16, 16, [b"\x11\x22\x33" * 16 for _ in range(16)]))
    m292 = m292_document(
        [
            m292_object(
                "promoted_icon",
                [20, 20, 16, 16],
                "raster_icon",
                "raster_icon",
                "icon_replay",
                m29_ids=["raw_icon"],
                source_evidence={
                    "promotionSource": "m29_6_internal_icon_candidate",
                    "mediaSourceObjectId": "media",
                    "transparentAssetPath": "assets/transparent/promoted_icon.png",
                },
            ),
        ]
    )
    plan = m295_plan([m295_item("plan_icon", "promoted_icon", [20, 20, 16, 16], "icon_replay", "m29_symbol")])

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("raw_icon", "symbol", [20, 20, 16, 16])]),
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    symbol_asset = next(asset for asset in result.dsl["assets"] if asset.get("role") == "m29_symbol")
    assert (tmp_path / "out" / symbol_asset["url"]).read_bytes() == transparent_asset.read_bytes()
    symbol_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_symbol")
    assert symbol_node["meta"]["m29TransparentAssetPath"] == str(transparent_asset)


def test_copied_media_cleanup_requires_m295_cleanup_target(tmp_path: Path) -> None:
    source = write_png(
        tmp_path / "source.png",
        make_png(120, 90, fill=(240, 240, 240), marks=[([10, 10, 80, 50], (80, 100, 140)), ([30, 28, 20, 8], (0, 0, 0))]),
    )
    m292 = m292_document(
        [
            m292_object("media", [10, 10, 80, 50], "media_region", "preserve_raster", "image_replay", m29_ids=["image_001"]),
            m292_object("text", [30, 28, 20, 8], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"]),
        ]
    )
    plan = m295_plan(
        [
            m295_item("plan_media", "media", [10, 10, 80, 50], "image_replay", "m29_image"),
            m295_item(
                "plan_text",
                "text",
                [30, 28, 20, 8],
                "text_replay",
                "m29_text",
                cleanup_targets=[
                    {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"},
                    {"target": "copied_image_asset", "targetSourceObjectId": "media", "reason": "editable_text_contained_by_media"},
                ],
            ),
        ]
    )

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("image_001", "image", [10, 10, 80, 50])]),
        m292_document=m292,
        m295_replay_plan=plan,
        ocr_document=ocr_document([ocr_block("ocr_text", "Hi", [30, 28, 20, 8])]),
        output_dir=tmp_path / "out",
    )

    copied = copied_image_pixels(result.dsl, tmp_path / "out")
    assert copied.rows[20][20 * 3 : 20 * 3 + 3] != b"\x00\x00\x00"
    assert result.report["summary"]["copiedImageAssetTextErasedCount"] == 1

    no_cleanup_plan = m295_plan(
        [
            m295_item("plan_media", "media", [10, 10, 80, 50], "image_replay", "m29_image"),
            m295_item("plan_text", "text", [30, 28, 20, 8], "text_replay", "m29_text"),
        ]
    )
    result_without_cleanup = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("image_001", "image", [10, 10, 80, 50])]),
        m292_document=m292,
        m295_replay_plan=no_cleanup_plan,
        ocr_document=ocr_document([ocr_block("ocr_text", "Hi", [30, 28, 20, 8])]),
        output_dir=tmp_path / "out_no_cleanup",
    )
    copied_without_cleanup = copied_image_pixels(result_without_cleanup.dsl, tmp_path / "out_no_cleanup")
    assert copied_without_cleanup.rows[20][20 * 3 : 20 * 3 + 3] == b"\x00\x00\x00"
    assert result_without_cleanup.report["summary"]["copiedImageAssetTextErasedCount"] == 0


def test_promoted_internal_icon_cleans_parent_media_only_with_m295_target(tmp_path: Path) -> None:
    source = write_png(
        tmp_path / "source.png",
        make_png(120, 90, fill=(240, 240, 240), marks=[([10, 10, 80, 50], (80, 100, 140)), ([30, 28, 20, 16], (0, 0, 0))]),
    )
    transparent_asset = tmp_path / "m29_transparent_assets" / "assets" / "transparent" / "promoted_icon.png"
    transparent_asset.parent.mkdir(parents=True, exist_ok=True)
    transparent_asset.write_bytes(make_rgba_icon_asset(20, 16, alpha_box=[6, 4, 8, 8]))
    m292 = m292_document(
        [
            m292_object("media", [10, 10, 80, 50], "media_region", "preserve_raster", "image_replay", m29_ids=["image_001"]),
            m292_object(
                "promoted_icon",
                [30, 28, 20, 16],
                "raster_icon",
                "raster_icon",
                "icon_replay",
                m29_ids=["raw_icon"],
                source_evidence={
                    "promotionSource": "m29_6_internal_icon_candidate",
                    "mediaSourceObjectId": "media",
                    "transparentAssetPath": "assets/transparent/promoted_icon.png",
                },
            ),
        ]
    )
    authorized_plan = m295_plan(
        [
            m295_item("plan_media", "media", [10, 10, 80, 50], "image_replay", "m29_image"),
            m295_item(
                "plan_icon",
                "promoted_icon",
                [30, 28, 20, 16],
                "icon_replay",
                "m29_symbol",
                cleanup_targets=[
                    {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"},
                    {"target": "copied_image_asset", "targetSourceObjectId": "media", "reason": "promoted_internal_asset_contained_by_media"},
                ],
            ),
        ]
    )

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("image_001", "image", [10, 10, 80, 50]), m29_node("raw_icon", "symbol", [30, 28, 20, 16])]),
        m292_document=m292,
        m295_replay_plan=authorized_plan,
        output_dir=tmp_path / "out_icon_cleanup",
    )

    copied = copied_image_pixels(result.dsl, tmp_path / "out_icon_cleanup")
    assert copied.rows[22][30 * 3 : 30 * 3 + 3] != b"\x00\x00\x00"
    assert copied.rows[18][20 * 3 : 20 * 3 + 3] == b"\x00\x00\x00"
    assert result.report["summary"]["copiedImageAssetInternalErasedCount"] == 1

    unauthorized_plan = m295_plan(
        [
            m295_item("plan_media", "media", [10, 10, 80, 50], "image_replay", "m29_image"),
            m295_item("plan_icon", "promoted_icon", [30, 28, 20, 16], "icon_replay", "m29_symbol"),
        ]
    )
    result_without_cleanup = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("image_001", "image", [10, 10, 80, 50]), m29_node("raw_icon", "symbol", [30, 28, 20, 16])]),
        m292_document=m292,
        m295_replay_plan=unauthorized_plan,
        output_dir=tmp_path / "out_icon_no_cleanup",
    )
    copied_without_cleanup = copied_image_pixels(result_without_cleanup.dsl, tmp_path / "out_icon_no_cleanup")
    assert copied_without_cleanup.rows[22][30 * 3 : 30 * 3 + 3] == b"\x00\x00\x00"
    assert result_without_cleanup.report["summary"]["copiedImageAssetInternalErasedCount"] == 0


def test_fallback_erasure_requires_m295_fallback_cleanup_target(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(80, 60, fill=(240, 240, 240), marks=[([20, 20, 20, 10], (0, 0, 0))]))
    m292 = m292_document([m292_object("text", [20, 20, 20, 10], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"])])

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[]),
        m292_document=m292,
        m295_replay_plan=m295_plan([m295_item("plan_text", "text", [20, 20, 20, 10], "text_replay", "m29_text")]),
        ocr_document=ocr_document([ocr_block("ocr_text", "Hi", [20, 20, 20, 10])]),
        output_dir=tmp_path / "out",
    )

    fallback_asset = next(asset for asset in result.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_pixels = decode_png_pixels((tmp_path / "out" / fallback_asset["url"]).read_bytes())
    assert fallback_pixels.rows[22][22 * 3 : 22 * 3 + 3] == b"\x00\x00\x00"
    assert result.report["summary"]["fallbackErasedBBoxCount"] == 0


def test_shape_replay_uses_only_source_geometry_fit_radius(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(100, 80, fill=(248, 248, 248), marks=[([20, 20, 50, 24], (235, 235, 235))]))
    m292 = m292_document([m292_object("shape", [20, 20, 50, 24], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_001"])])
    plan = m295_plan([m295_item("plan_shape", "shape", [20, 20, 50, 24], "shape_replay", "m29_shape")])

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(
            tmp_path,
            nodes=[
                m29_node(
                    "shape_001",
                    "shape",
                    [20, 20, 50, 24],
                    geometry={"kind": "rounded_rect", "confidence": "high", "params": {"radius": 7}},
                )
            ],
        ),
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    shape = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_shape")
    assert shape["style"]["radius"] == 7
    assert shape["meta"]["m29ShapeStyleSource"] == "shape_geometry_fit"


def test_shape_replay_does_not_invent_radius_without_geometry_fit(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(100, 80, fill=(248, 248, 248), marks=[([20, 20, 50, 24], (235, 235, 235))]))
    m292 = m292_document([m292_object("shape", [20, 20, 50, 24], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_001"])])
    plan = m295_plan([m295_item("plan_shape", "shape", [20, 20, 50, 24], "shape_replay", "m29_shape")])

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("shape_001", "shape", [20, 20, 50, 24])]),
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    shape = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_shape")
    assert "radius" not in shape["style"]
    assert shape["meta"]["m29ShapeStyleSource"] == "sampled_fill_only"


def test_shape_replay_samples_missing_fill_from_source_pixels(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(100, 80, fill=(12, 14, 22), marks=[([20, 20, 50, 24], (42, 48, 62))]))
    m292 = m292_document([m292_object("shape", [20, 20, 50, 24], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_001"])])
    plan = m295_plan([m295_item("plan_shape", "shape", [20, 20, 50, 24], "shape_replay", "m29_shape")])

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("shape_001", "shape", [20, 20, 50, 24])]),
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    shape = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_shape")
    assert shape["style"]["fill"] == "#2A303E"
    assert shape["style"]["fill"] != "#F7F8FA"


def test_shape_replay_uses_source_shape_inference_overrides(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(120, 90, fill=(240, 240, 240), marks=[([20, 20, 80, 30], (82, 148, 76)), ([44, 28, 32, 8], (255, 255, 255))]))
    m292 = m292_document(
        [
            m292_object(
                "shape",
                [20, 20, 80, 30],
                "control_background",
                "shape_geometry",
                "shape_replay",
                m29_ids=["unknown_button"],
                source_evidence={"shapeFillOverride": "#52944C", "shapeRadiusOverride": 15},
            )
        ]
    )
    plan = m295_plan([m295_item("plan_shape", "shape", [20, 20, 80, 30], "shape_replay", "m29_shape")])

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("unknown_button", "unknown", [20, 20, 80, 30])]),
        m292_document=m292,
        m295_replay_plan=plan,
        output_dir=tmp_path / "out",
    )

    shape = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_shape")
    assert shape["style"]["fill"] == "#52944C"
    assert shape["style"]["radius"] == 15
    assert shape["meta"]["m29ShapeStyleSource"] == "source_shape_inference"


def test_shape_background_cleans_parent_media_only_with_m295_target(tmp_path: Path) -> None:
    source = write_png(
        tmp_path / "source.png",
        make_png(120, 90, fill=(240, 240, 240), marks=[([10, 10, 90, 60], (40, 80, 120)), ([30, 28, 42, 20], (82, 148, 76))]),
    )
    m292 = m292_document(
        [
            m292_object("media", [10, 10, 90, 60], "media_region", "preserve_raster", "image_replay", m29_ids=["image_001"]),
            m292_object(
                "shape",
                [30, 28, 42, 20],
                "control_background",
                "shape_geometry",
                "shape_replay",
                m29_ids=["unknown_button"],
                source_evidence={"shapeFillOverride": "#52944C", "shapeRadiusOverride": 10},
            ),
        ]
    )
    authorized_plan = m295_plan(
        [
            m295_item("plan_media", "media", [10, 10, 90, 60], "image_replay", "m29_image"),
            m295_item(
                "plan_shape",
                "shape",
                [30, 28, 42, 20],
                "shape_replay",
                "m29_shape",
                cleanup_targets=[
                    {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"},
                    {"target": "copied_image_asset", "targetSourceObjectId": "media", "reason": "shape_background_contained_by_media"},
                ],
            ),
        ]
    )

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("image_001", "image", [10, 10, 90, 60]), m29_node("unknown_button", "unknown", [30, 28, 42, 20])]),
        m292_document=m292,
        m295_replay_plan=authorized_plan,
        output_dir=tmp_path / "out_shape_cleanup",
    )

    copied = copied_image_pixels(result.dsl, tmp_path / "out_shape_cleanup")
    assert copied.rows[18][20 * 3 : 20 * 3 + 3] != b"\x52\x94\x4c"
    assert copied.rows[0][0:3] == b"(\x50\x78"
    assert result.report["summary"]["copiedImageAssetShapeErasedCount"] == 1

    unauthorized_plan = m295_plan(
        [
            m295_item("plan_media", "media", [10, 10, 90, 60], "image_replay", "m29_image"),
            m295_item("plan_shape", "shape", [30, 28, 42, 20], "shape_replay", "m29_shape"),
        ]
    )
    result_without_cleanup = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("image_001", "image", [10, 10, 90, 60]), m29_node("unknown_button", "unknown", [30, 28, 42, 20])]),
        m292_document=m292,
        m295_replay_plan=unauthorized_plan,
        output_dir=tmp_path / "out_shape_no_cleanup",
    )

    copied_without_cleanup = copied_image_pixels(result_without_cleanup.dsl, tmp_path / "out_shape_no_cleanup")
    assert copied_without_cleanup.rows[18][20 * 3 : 20 * 3 + 3] == b"\x52\x94\x4c"
    assert result_without_cleanup.report["summary"]["copiedImageAssetShapeErasedCount"] == 0


def test_controlled_structure_materialization_groups_contiguous_high_confidence_members(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(140, 90, fill=(248, 248, 248), marks=[([20, 20, 40, 20], (235, 235, 235)), ([70, 20, 40, 20], (20, 20, 20))]))
    m292 = m292_document(
        [
            m292_object("shape", [20, 20, 40, 20], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_001"]),
            m292_object("text", [70, 20, 40, 20], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"]),
        ]
    )
    plan = m295_plan(
        [
            m295_item("plan_shape", "shape", [20, 20, 40, 20], "shape_replay", "m29_shape"),
            m295_item("plan_text", "text", [70, 20, 40, 20], "text_replay", "m29_text"),
        ]
    )

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("shape_001", "shape", [20, 20, 40, 20])]),
        m292_document=m292,
        m295_replay_plan=plan,
        ocr_document=ocr_document([ocr_block("ocr_text", "Label", [70, 20, 40, 20])]),
        sibling_group_report=sibling_group_report(
            [
                sibling_group(
                    "m29_sibling_group_0001",
                    ["shape", "text"],
                    [20, 20, 90, 20],
                    score=0.91,
                    confidence="high",
                )
            ]
        ),
        layout_energy_report=layout_energy_report([layout_energy_candidate("m29_sibling_group_0001", ["shape", "text"], [20, 20, 90, 20])]),
        auto_layout_permission_report=auto_layout_permission_report([auto_layout_permission("m29_sibling_group_0001", ["shape", "text"], [20, 20, 90, 20])]),
        output_dir=tmp_path / "out",
    )

    group = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m29_controlled_structure_group")
    assert group["style"]["fill"] is None
    assert group["meta"]["autoLayoutCreated"] is False
    assert group["layout"] == {"x": 20, "y": 20, "width": 90, "height": 20}
    assert [child["role"] for child in group["children"]] == ["m29_shape", "m29_text"]
    assert group["children"][0]["layout"]["x"] == 0
    assert group["children"][1]["layout"]["x"] == 50
    assert result.report["summary"]["controlledStructureGroupCount"] == 1
    assert result.report["summary"]["controlledStructureMaterializationChanged"] is True
    assert result.report["controlledStructureMaterialization"]["summary"]["acceptedGroupCount"] == 1


def test_controlled_structure_materialization_keeps_flat_output_without_reports(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_png(140, 90, fill=(248, 248, 248), marks=[([20, 20, 40, 20], (235, 235, 235)), ([70, 20, 40, 20], (20, 20, 20))]))
    m292 = m292_document(
        [
            m292_object("shape", [20, 20, 40, 20], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_001"]),
            m292_object("text", [70, 20, 40, 20], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"]),
        ]
    )

    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("shape_001", "shape", [20, 20, 40, 20])]),
        m292_document=m292,
        m295_replay_plan=m295_plan(
            [
                m295_item("plan_shape", "shape", [20, 20, 40, 20], "shape_replay", "m29_shape"),
                m295_item("plan_text", "text", [70, 20, 40, 20], "text_replay", "m29_text"),
            ]
        ),
        ocr_document=ocr_document([ocr_block("ocr_text", "Label", [70, 20, 40, 20])]),
        output_dir=tmp_path / "out",
    )

    assert not any(child.get("role") == "m29_controlled_structure_group" for child in result.dsl["root"]["children"])
    assert result.report["summary"]["controlledStructureGroupCount"] == 0


def test_controlled_structure_materialization_rejects_non_contiguous_members(tmp_path: Path) -> None:
    source = write_png(
        tmp_path / "source.png",
        make_png(180, 90, fill=(248, 248, 248), marks=[([20, 20, 30, 20], (235, 235, 235)), ([70, 20, 30, 20], (210, 210, 210)), ([120, 20, 30, 20], (0, 0, 0))]),
    )
    m292 = m292_document(
        [
            m292_object("shape_a", [20, 20, 30, 20], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_001"]),
            m292_object("shape_b", [70, 20, 30, 20], "control_background", "shape_geometry", "shape_replay", m29_ids=["shape_002"]),
            m292_object("text", [120, 20, 30, 20], "editable_ui_text", "editable_text", "text_replay", ocr_ids=["ocr_text"]),
        ]
    )
    result = build_plan_driven_dsl(
        source_png=source.read_bytes(),
        source_image_path=str(source),
        m29_document=m29_document(tmp_path, nodes=[m29_node("shape_001", "shape", [20, 20, 30, 20]), m29_node("shape_002", "shape", [70, 20, 30, 20])]),
        m292_document=m292,
        m295_replay_plan=m295_plan(
            [
                m295_item("plan_shape_a", "shape_a", [20, 20, 30, 20], "shape_replay", "m29_shape"),
                m295_item("plan_shape_b", "shape_b", [70, 20, 30, 20], "shape_replay", "m29_shape"),
                m295_item("plan_text", "text", [120, 20, 30, 20], "text_replay", "m29_text"),
            ]
        ),
        ocr_document=ocr_document([ocr_block("ocr_text", "C", [120, 20, 30, 20])]),
        sibling_group_report=sibling_group_report([sibling_group("m29_sibling_group_0001", ["shape_a", "text"], [20, 20, 130, 20], score=0.92, confidence="high")]),
        layout_energy_report=layout_energy_report([layout_energy_candidate("m29_sibling_group_0001", ["shape_a", "text"], [20, 20, 130, 20])]),
        auto_layout_permission_report=auto_layout_permission_report([auto_layout_permission("m29_sibling_group_0001", ["shape_a", "text"], [20, 20, 130, 20])]),
        output_dir=tmp_path / "out",
    )

    assert result.report["summary"]["controlledStructureGroupCount"] == 0
    rejected = result.report["controlledStructureMaterialization"]["rejectedGroups"]
    assert rejected[0]["reason"] == "member_z_order_not_contiguous"


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


def make_rgba_icon_asset(width: int, height: int, *, alpha_box: list[int]) -> bytes:
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            alpha = 255 if alpha_box[0] <= x < alpha_box[0] + alpha_box[2] and alpha_box[1] <= y < alpha_box[1] + alpha_box[3] else 0
            row.extend([17, 34, 51, alpha])
        rows.append(bytes(row))
    return encode_rgba_png(width, height, rows)


def m29_document(tmp_path: Path, *, nodes: list[dict]) -> dict:
    m29_dir = tmp_path / "m29"
    m29_dir.mkdir(parents=True, exist_ok=True)
    return {
        "version": "0.1",
        "sourceImage": str(tmp_path / "source.png"),
        "sourceM29NodesJson": str(m29_dir / "nodes.json"),
        "imageSize": {"width": 100, "height": 80},
        "nodes": nodes,
        "relations": [],
        "blocked": [],
        "debug": {},
        "warnings": [],
        "meta": {"counts": {}},
    }


def m29_node(node_id: str, node_type: str, bbox: list[int], *, subtype: str | None = None, geometry: dict | None = None) -> dict:
    data = {
        "id": node_id,
        "type": node_type,
        "subtype": subtype or ("separator" if node_type == "shape" else "bitmap_candidate"),
        "bbox": bbox,
        "confidence": 0.9,
        "source": f"{node_type}_detector",
        "sourceOrder": 0,
        "layerHint": "content",
        "reasons": ["test"],
        "metrics": {"colorCount": 1, "textureScore": 0.01, "edgeScore": 0, "fillRatio": 1, "aspectRatio": bbox[2] / bbox[3], "brightness": 200, "meanRgb": [0, 0, 0]},
    }
    if geometry is not None:
        data["geometry"] = geometry
    return data


def ocr_document(blocks: list[dict]) -> dict:
    return {"version": "0.1", "taskId": "test", "provider": "test", "model": None, "imageSize": {"width": 80, "height": 60}, "coordinateSpace": "pixel", "blocks": blocks, "warnings": []}


def ocr_block(block_id: str, text: str, bbox: list[int]) -> dict:
    return {"id": block_id, "text": text, "bbox": bbox, "confidence": 0.95, "lineId": block_id, "blockId": block_id, "source": "test"}


def m292_document(objects: list[dict]) -> dict:
    return {
        "schemaName": "M292SourceUiPhysicalGraph",
        "schemaVersion": "0.1",
        "summary": {"sourceObjectCount": len(objects)},
        "sourceObjects": objects,
    }


def m292_object(
    object_id: str,
    bbox: list[int],
    visual_kind: str,
    pixel_owner: str,
    replay_decision: str,
    *,
    m29_ids: list[str] | None = None,
    ocr_ids: list[str] | None = None,
    source_evidence: dict | None = None,
) -> dict:
    evidence = {
        "ocrBoxIds": ocr_ids or [],
        "m29NodeIds": m29_ids or [],
        "blockedIds": [],
        "localBackgroundConfidence": 0.9,
        "textOverlapRatio": 0.0,
        "mediaContainmentRatio": 0.0,
    }
    if source_evidence:
        evidence.update(source_evidence)
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "sourceEvidence": evidence,
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
        "pixelOwner": "editable_text",
        "cleanupTargets": cleanup_targets or [],
        "suppressedSourceObjectIds": [],
        "relationEdgeIds": [],
        "clusterIds": [],
        "confidence": "high",
        "reasons": ["test_plan"],
        "risks": [],
    }


def copied_image_pixels(dsl: dict, output_dir: Path) -> PngPixels:
    image_node = next(child for child in dsl["root"]["children"] if child.get("role") == "m29_image")
    asset_id = image_node["source"]["assetId"]
    asset = next(item for item in dsl["assets"] if item.get("assetId") == asset_id)
    return decode_png_pixels((output_dir / asset["url"]).read_bytes())


def sibling_group_report(groups: list[dict]) -> dict:
    return {
        "schemaName": "M29SiblingGroupCandidateReport",
        "schemaVersion": "0.1",
        "summary": {"siblingGroupCandidateCount": len(groups)},
        "siblingGroupCandidates": groups,
    }


def sibling_group(group_id: str, members: list[str], bbox: list[int], *, score: float, confidence: str) -> dict:
    return {
        "id": group_id,
        "source": "relation_component",
        "groupPattern": "row_like",
        "memberSourceObjectIds": members,
        "memberPlanItemIds": [f"plan_{member}" for member in members],
        "memberFinalReplayActions": ["shape_replay" if "shape" in member else "text_replay" for member in members],
        "edgeIds": ["edge_001"],
        "bbox": bbox,
        "score": score,
        "confidence": confidence,
        "metrics": {"memberCount": len(members)},
        "reasons": ["test_sibling_group"],
        "risks": [],
    }


def layout_energy_report(candidates: list[dict]) -> dict:
    return {
        "schemaName": "M29LayoutEnergyReport",
        "schemaVersion": "0.1",
        "summary": {"layoutEnergyCandidateCount": len(candidates)},
        "layoutEnergyCandidates": candidates,
    }


def layout_energy_candidate(source_candidate_id: str, members: list[str], bbox: list[int]) -> dict:
    return {
        "id": f"{source_candidate_id}_energy",
        "subjectId": "m29_layout_subject_0001",
        "subjectType": "sibling_group",
        "sourceCandidateId": source_candidate_id,
        "bestModel": "row",
        "confidence": "high",
        "energy": 0.12,
        "memberSourceObjectIds": members,
        "bbox": bbox,
        "risks": [],
    }


def auto_layout_permission_report(items: list[dict]) -> dict:
    return {
        "schemaName": "M29AutoLayoutPermissionReport",
        "schemaVersion": "0.1",
        "summary": {"permissionItemCount": len(items), "allowCandidateCount": len(items)},
        "permissionItems": items,
    }


def auto_layout_permission(source_candidate_id: str, members: list[str], bbox: list[int]) -> dict:
    return {
        "id": f"{source_candidate_id}_permission",
        "layoutEnergyCandidateId": f"{source_candidate_id}_energy",
        "subjectId": "m29_layout_subject_0001",
        "subjectType": "sibling_group",
        "sourceCandidateId": source_candidate_id,
        "permission": "allow_candidate",
        "recommendedModel": "row",
        "recommendedAxis": "horizontal",
        "energy": 0.12,
        "confidence": "high",
        "threshold": 0.32,
        "memberSourceObjectIds": members,
        "bbox": bbox,
        "reasons": ["test_permission"],
        "risks": [],
    }
