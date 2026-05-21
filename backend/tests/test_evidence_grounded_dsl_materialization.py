from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.evidence_grounded_dsl_materialization import (
    M30Options,
    materialize_evidence_grounded_dsl,
)
from app.mixed_symbol_text_conflict_audit import FORBIDDEN_CONTRACT_TERMS, find_forbidden_contract_terms
from app.png_tools import PngPixels, encode_rgb_png, read_png_metadata, decode_png_pixels
from scripts.run_m30_evidence_grounded_dsl_materialization import resolve_mode


def test_bootstrap_dsl_from_m29_creates_fallback_and_materialized_nodes(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(120, 100))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir)
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    children = result.dsl["root"]["children"]
    assert any(child["id"] == "fallback_full_image" for child in children)
    assert count_children(result.dsl, "m30_text_member") == 1
    assert count_children(result.dsl, "m30_text_cover") == 1
    assert count_children(result.dsl, "m30_shape_candidate") == 1
    assert count_children(result.dsl, "m30_visual_asset") == 1
    assert not any(child.get("type") == "icon" for child in children)
    assert result.report.summary["createdNewBBoxCount"] == 0
    assert result.report.summary["permissionViolationCount"] == 0
    assert result.report.summary["fallbackPreserved"] is True
    assert result.report.summary["textCoverCandidateCount"] == 1
    assert result.report.summary["materializedTextCoverCount"] == 1
    assert read_png_metadata((tmp_path / "m30" / "m30_materialization_preview.png").read_bytes()).width == 120


def test_augment_existing_dsl_preserves_base_and_appends_nodes(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(120, 100))
    base_dsl = base_dsl_document()
    before = copy.deepcopy(base_dsl)
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir)
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="augment-existing-dsl",
        base_dsl=base_dsl,
        base_dsl_path="/tmp/base_dsl.json",
    )

    assert base_dsl == before
    child_ids = {child["id"] for child in result.dsl["root"]["children"]}
    assert {"original_ref", "fallback_full_image"} <= child_ids
    assert len(result.dsl["root"]["children"]) > len(before["root"]["children"])
    assert result.report.source_base_dsl == "/tmp/base_dsl.json"


def test_text_nodes_keep_source_trace(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(100, 80))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir, visual_assets=[], shape_candidates=[])
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    text_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m30_text_member")
    assert text_node["content"]["text"] == "Hello"
    assert text_node["meta"]["sourceTextMemberId"] == "text_member_0001"
    assert text_node["meta"]["sourceTextBoxId"] == "ocr_001"
    assert text_node["meta"]["sourceEvidenceNodeId"] == "evidence_text_001"
    assert text_node["meta"]["sourceBBox"] == [10, 10, 40, 12]


def test_stable_background_text_member_generates_text_cover_shape(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(100, 80, fill=(250, 250, 250)))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir, visual_assets=[], shape_candidates=[])
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    cover_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m30_text_cover")
    assert cover_node["type"] == "shape"
    assert cover_node["layout"] == {"x": 10, "y": 10, "width": 40, "height": 12}
    assert cover_node["style"]["fill"] == "#FAFAFA"
    assert cover_node["meta"]["sourceKind"] == "m30_text_cover"
    assert cover_node["meta"]["sourceTextMemberId"] == "text_member_0001"
    assert cover_node["meta"]["sourceTextNodeId"].startswith("m30_text_")
    assert result.report.materialized_text_cover_nodes[0].kind == "text_cover"


def test_text_cover_layer_order_keeps_text_above_cover(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(120, 100))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir)
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    roles = [child.get("role") for child in result.dsl["root"]["children"]]
    assert roles.index("fallback_region") < roles.index("m30_shape_candidate")
    assert roles.index("m30_shape_candidate") < roles.index("m30_visual_asset")
    assert roles.index("m30_visual_asset") < roles.index("m30_text_cover")
    assert roles.index("m30_text_cover") < roles.index("m30_text_member")


def test_unstable_background_skips_text_cover(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_noisy_text_edge_canvas(100, 80, [10, 10, 40, 12]))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir, visual_assets=[], shape_candidates=[])
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
        options=M30Options(text_cover_background_tolerance=1, text_cover_min_sample_confidence=0.99),
    )

    assert count_children(result.dsl, "m30_text_cover") == 0
    assert result.report.summary["materializedTextCoverCount"] == 0
    assert result.report.summary["skippedTextCoverReasons"]["unstable_background_sample"] == 1


def test_high_risk_text_member_skips_text_cover(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(100, 80))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir, visual_assets=[], shape_candidates=[], text_risks=["unresolved_boundary"])
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert count_children(result.dsl, "m30_text_member") == 1
    assert count_children(result.dsl, "m30_text_cover") == 0
    assert result.report.summary["skippedTextCoverReasons"]["high_risk_text_member"] == 1


def test_visual_asset_overlap_skips_text_cover(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(120, 100))
    m2905_dir = tmp_path / "m29_0_5"
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0002.png", make_canvas(40, 12))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[
            visual_asset("visual_asset_0002", [10, 10, 40, 12], str(visual_asset_path.relative_to(m2905_dir))),
        ],
        shape_candidates=[],
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
        options=M30Options(text_editability_enabled=False),
    )

    assert count_children(result.dsl, "m30_visual_asset") == 1
    assert count_children(result.dsl, "m30_text_cover") == 0
    assert result.report.summary["skippedTextCoverReasons"]["unsafe_visual_overlap"] == 1


def test_graphic_text_over_visual_asset_is_preserved_in_fallback_by_default(tmp_path: Path) -> None:
    canvas = make_canvas(120, 100, fill=(240, 240, 240))
    rows = [bytearray(row) for row in canvas.rows]
    for row_index in range(11, 16):
        for column in range(12, 22):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x00\x00\x00"
    source = write_png(tmp_path / "source.png", PngPixels(width=120, height=100, rows=[bytes(row) for row in rows]))
    m2905_dir = tmp_path / "m29_0_5"
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0002.png", make_canvas(40, 12))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[
            visual_asset("visual_asset_0002", [10, 10, 40, 12], str(visual_asset_path.relative_to(m2905_dir))),
        ],
        shape_candidates=[],
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        m2902_document=m2902_document_with_text_box("ocr_001", [10, 10, 40, 12], "Graphic"),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert count_children(result.dsl, "m30_text_member") == 0
    assert count_children(result.dsl, "m30_text_cover") == 0
    assert result.report.summary["materializedTextCount"] == 0
    assert result.report.summary["preservedGraphicTextCount"] == 1
    assert result.report.summary["editableTextCount"] == 0
    assert result.report.summary["createdNewBBoxCount"] == 0
    preserved = result.report.to_dict()["preservedGraphicTextItems"][0]
    assert preserved["decision"] == "graphic_text_preserve_in_fallback"
    assert "image_embedded_text" in preserved["reasons"]
    skipped_reasons = {item.reason for item in result.report.skipped_items}
    assert "graphic_text_preserve_in_fallback" in skipped_reasons

    fallback_asset = next(asset for asset in result.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_path = tmp_path / "m30" / fallback_asset["url"]
    fallback_pixels = decode_png_pixels(fallback_path.read_bytes())
    for row_index in range(11, 16):
        for column in range(12, 22):
            offset = column * 3
            assert list(fallback_pixels.rows[row_index][offset : offset + 3]) == [0, 0, 0]


def test_rotated_ocr_text_is_preserved_as_evidence_but_not_materialized_text(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(120, 100))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir, visual_assets=[], shape_candidates=[])
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)
    m2902 = m2902_document_with_text_box(
        "ocr_001",
        [10, 10, 40, 12],
        "Graphic",
        meta={"angle": 12.5, "polygon": [[10, 10], [50, 18], [47, 30], [7, 22]]},
    )

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        m2902_document=m2902,
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert count_children(result.dsl, "m30_text_member") == 0
    assert result.report.summary["preservedGraphicTextCount"] == 1
    preserved = result.report.to_dict()["preservedGraphicTextItems"][0]
    assert preserved["sourceTextBoxId"] == "ocr_001"
    assert preserved["metrics"]["angle"] == 12.5
    assert "rotated_or_skewed_text" in preserved["reasons"]


def test_aligned_text_row_overrides_light_ocr_angle_noise(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(360, 160))
    m2905_dir = tmp_path / "m29_0_5"
    members = [
        text_member("text_member_0001", [24, 42, 54, 24], "Alpha", source_text_box_id="ocr_001"),
        text_member("text_member_0002", [132, 41, 56, 25], "Beta", source_text_box_id="ocr_002"),
        text_member("text_member_0003", [244, 42, 58, 24], "Gamma", source_text_box_id="ocr_003"),
    ]
    m2905 = m2905_document(m2905_dir, visual_assets=[], shape_candidates=[], text_members=members)
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)
    m2902 = m2902_document_with_text_boxes(
        [
            {"id": "ocr_001", "bbox": [24, 42, 54, 24], "text": "Alpha", "meta": {"angle": 0.0}},
            {"id": "ocr_002", "bbox": [132, 41, 56, 25], "text": "Beta", "meta": {"angle": 4.8}},
            {"id": "ocr_003", "bbox": [244, 42, 58, 24], "text": "Gamma", "meta": {"angle": 0.0}},
        ]
    )

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        m2902_document=m2902,
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert count_children(result.dsl, "m30_text_member") == 3
    decisions = {item["sourceTextBoxId"]: item for item in result.report.to_dict()["textEditabilityDecisions"]}
    assert decisions["ocr_002"]["decision"] == "editable_text"
    assert "aligned_text_row" in decisions["ocr_002"]["reasons"]
    assert "rotated_or_skewed_text" in decisions["ocr_002"]["metrics"]["preserveSignals"]
    assert "aligned_text_row" in decisions["ocr_002"]["metrics"]["editableCounterSignals"]


def test_compact_overlay_badge_overrides_image_embedded_text(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(420, 320, fill=(245, 245, 245)))
    m2905_dir = tmp_path / "m29_0_5"
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0002.png", make_canvas(280, 190))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[visual_asset("visual_asset_0002", [40, 70, 280, 190], str(visual_asset_path.relative_to(m2905_dir)))],
        shape_candidates=[],
        text_members=[text_member("text_member_0001", [54, 84, 58, 24], "Label", source_text_box_id="ocr_001")],
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        m2902_document=m2902_document_with_text_box("ocr_001", [54, 84, 58, 24], "Label", meta={"angle": 0.0}),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert count_children(result.dsl, "m30_text_member") == 1
    decision = result.report.to_dict()["textEditabilityDecisions"][0]
    assert decision["decision"] == "editable_text"
    assert "compact_overlay_badge" in decision["reasons"]
    assert "image_embedded_text" in decision["metrics"]["preserveSignals"]
    assert "compact_overlay_badge" in decision["metrics"]["editableCounterSignals"]


def test_large_center_media_text_remains_preserved(tmp_path: Path) -> None:
    canvas = make_canvas(420, 320, fill=(245, 245, 245))
    rows = [bytearray(row) for row in canvas.rows]
    for row_index in range(110, 150):
        for column in range(115, 305):
            rows[row_index][column * 3 : column * 3 + 3] = bytes(((column * 7) % 255, (row_index * 5) % 255, 80))
    source = write_png(tmp_path / "source.png", PngPixels(width=420, height=320, rows=[bytes(row) for row in rows]))
    m2905_dir = tmp_path / "m29_0_5"
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0002.png", make_canvas(320, 210))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[visual_asset("visual_asset_0002", [50, 70, 320, 210], str(visual_asset_path.relative_to(m2905_dir)))],
        shape_candidates=[],
        text_members=[text_member("text_member_0001", [115, 110, 190, 40], "Poster", source_text_box_id="ocr_001")],
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        m2902_document=m2902_document_with_text_box("ocr_001", [115, 110, 190, 40], "Poster", meta={"angle": 0.0}),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert count_children(result.dsl, "m30_text_member") == 0
    decision = result.report.to_dict()["preservedGraphicTextItems"][0]
    assert decision["decision"] == "graphic_text_preserve_in_fallback"
    assert "image_embedded_text" in decision["reasons"]
    assert "compact_overlay_badge" not in decision["metrics"]["editableCounterSignals"]


def test_metadata_text_cluster_overrides_light_ocr_angle_noise(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(900, 520))
    m2905_dir = tmp_path / "m29_0_5"
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0002.png", make_canvas(20, 20))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[visual_asset("visual_asset_0002", [222, 102, 20, 20], str(visual_asset_path.relative_to(m2905_dir)))],
        shape_candidates=[],
        text_members=[
            text_member("text_member_0001", [246, 100, 58, 24], "Place", source_text_box_id="ocr_001"),
        ],
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)
    m2902 = m2902_document_with_text_boxes(
        [
            {"id": "ocr_001", "bbox": [246, 100, 58, 24], "text": "Place", "meta": {"angle": 4.4}},
        ]
    )

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        m2902_document=m2902,
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    decisions = {item["sourceTextBoxId"]: item for item in result.report.to_dict()["textEditabilityDecisions"]}
    assert decisions["ocr_001"]["decision"] == "editable_text"
    assert "metadata_text_cluster" in decisions["ocr_001"]["reasons"]
    assert "rotated_or_skewed_text" in decisions["ocr_001"]["metrics"]["preserveSignals"]
    assert "metadata_text_cluster" in decisions["ocr_001"]["metrics"]["editableCounterSignals"]


def test_plain_ocr_text_remains_editable_text_candidate(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(120, 100))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir, visual_assets=[], shape_candidates=[])
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        m2902_document=m2902_document_with_text_box("ocr_001", [10, 10, 40, 12], "Hello", meta={"angle": 0.2}),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    text_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m30_text_member")
    assert text_node["content"]["text"] == "Hello"
    assert text_node["meta"]["textEditabilityDecision"] == "editable_text"
    assert result.report.summary["editableTextCount"] == 1
    assert result.report.summary["preservedGraphicTextCount"] == 0
    decisions = result.report.to_dict()["textEditabilityDecisions"]
    assert decisions[0]["decision"] == "editable_text"
    assert decisions[0]["reasons"] == ["source_evidence_trace"]


def test_editable_text_samples_foreground_color_from_source_pixels(tmp_path: Path) -> None:
    canvas = make_canvas(120, 100, fill=(22, 119, 255))
    rows = [bytearray(row) for row in canvas.rows]
    for row_index in range(13, 18):
        for column in range(14, 28):
            rows[row_index][column * 3 : column * 3 + 3] = b"\xff\xff\xff"
    source = write_png(tmp_path / "source.png", PngPixels(width=120, height=100, rows=[bytes(row) for row in rows]))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir, visual_assets=[], shape_candidates=[])
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        m2902_document=m2902_document_with_text_box("ocr_001", [10, 10, 40, 12], "Hello", meta={"angle": 0.0}),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    text_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m30_text_member")
    assert text_node["style"]["color"] == "#FFFFFF"
    assert text_node["meta"]["textForegroundColorSource"] == "sampled_foreground"
    assert text_node["meta"]["textForegroundBackgroundColor"] == "#1677FF"
    assert result.report.summary["sampledTextForegroundCount"] == 1
    assert result.report.summary["defaultContrastTextForegroundCount"] == 0
    assert result.report.summary["defaultTextColorFallbackCount"] == 0


def test_text_foreground_sampling_falls_back_to_contrast_color(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(120, 100, fill=(18, 28, 46)))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir, visual_assets=[], shape_candidates=[])
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    text_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m30_text_member")
    assert text_node["style"]["color"] == "#FFFFFF"
    assert text_node["meta"]["textForegroundColorSource"] == "default_contrast"
    assert result.report.summary["defaultContrastTextForegroundCount"] == 1


def test_text_symbol_leakage_cleanup_trims_leading_q_and_uses_cleaned_bbox(tmp_path: Path) -> None:
    rows = [bytearray(bytes((255, 255, 255)) * 120) for _ in range(48)]
    for row_index in range(16, 28):
        for column in range(12, 24):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x00\x00\x00"
    for row_index in range(16, 28):
        for column in range(32, 84):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x11\x18\x27"
    source = write_png(tmp_path / "source.png", PngPixels(width=120, height=48, rows=[bytes(row) for row in rows]))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[],
        shape_candidates=[],
        text_members=[text_member("text_member_0001", [10, 12, 90, 20], "Q春日穿搭灵感")],
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    text_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m30_text_member")
    assert text_node["content"]["text"] == "春日穿搭灵感"
    assert text_node["layout"] == {"x": 32, "y": 12, "width": 68, "height": 20}
    assert text_node["style"]["color"] == "#111827"
    assert text_node["meta"]["textSymbolLeakageDecision"] == "trimmed_leading_symbol"
    assert text_node["meta"]["originalText"] == "Q春日穿搭灵感"
    assert text_node["meta"]["cleanedText"] == "春日穿搭灵感"
    assert text_node["meta"]["originalBBox"] == [10, 12, 90, 20]
    assert text_node["meta"]["cleanedBBox"] == [32, 12, 68, 20]
    assert text_node["meta"]["protectedSymbolBBox"] == [10, 12, 14, 20]
    assert text_node["meta"]["gapBBox"] == [24, 12, 8, 20]
    assert result.report.materialized_text_nodes[0].bbox == [32, 12, 68, 20]
    assert result.report.summary["trimmedTextSymbolLeakageCount"] == 1
    assert result.report.summary["textSymbolLeakageReasonCounts"]["projection_gap_after_symbol"] == 1
    decisions = result.report.to_dict()["textSymbolLeakageDecisions"]
    assert decisions[0]["decision"] == "trimmed_leading_symbol"

    fallback_asset = next(asset for asset in result.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_pixels = decode_png_pixels((tmp_path / "m30" / fallback_asset["url"]).read_bytes())
    for row_index in range(16, 28):
        for column in range(12, 24):
            offset = column * 3
            assert fallback_pixels.rows[row_index][offset : offset + 3] == b"\x00\x00\x00"
    for row_index in range(16, 28):
        for column in range(32, 84):
            offset = column * 3
            assert fallback_pixels.rows[row_index][offset : offset + 3] == b"\xff\xff\xff"


def test_text_symbol_leakage_cleanup_does_not_trim_q_without_projection_gap(tmp_path: Path) -> None:
    rows = [bytearray(bytes((255, 255, 255)) * 120) for _ in range(48)]
    for row_index in range(16, 28):
        for column in range(12, 84):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x11\x18\x27"
    source = write_png(tmp_path / "source.png", PngPixels(width=120, height=48, rows=[bytes(row) for row in rows]))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[],
        shape_candidates=[],
        text_members=[text_member("text_member_0001", [10, 12, 90, 20], "Q版穿搭")],
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    text_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m30_text_member")
    assert text_node["content"]["text"] == "Q版穿搭"
    assert text_node["layout"] == {"x": 10, "y": 12, "width": 90, "height": 20}
    assert "textSymbolLeakageDecision" not in text_node["meta"]
    assert result.report.summary["trimmedTextSymbolLeakageCount"] == 0
    assert result.report.to_dict()["textSymbolLeakageDecisions"] == []


def test_text_symbol_leakage_cleanup_does_not_trim_single_q(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(80, 40, fill=(255, 255, 255)))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[],
        shape_candidates=[],
        text_members=[text_member("text_member_0001", [10, 10, 20, 16], "Q")],
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    text_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m30_text_member")
    assert text_node["content"]["text"] == "Q"
    assert "textSymbolLeakageDecision" not in text_node["meta"]


def test_text_symbol_leakage_cleanup_can_be_disabled(tmp_path: Path) -> None:
    rows = [bytearray(bytes((255, 255, 255)) * 120) for _ in range(48)]
    for row_index in range(16, 28):
        for column in range(12, 24):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x00\x00\x00"
    for row_index in range(16, 28):
        for column in range(32, 84):
            rows[row_index][column * 3 : column * 3 + 3] = b"\x11\x18\x27"
    source = write_png(tmp_path / "source.png", PngPixels(width=120, height=48, rows=[bytes(row) for row in rows]))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[],
        shape_candidates=[],
        text_members=[text_member("text_member_0001", [10, 12, 90, 20], "Q春日穿搭灵感")],
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
        options=M30Options(text_symbol_leakage_cleanup_enabled=False),
    )

    text_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m30_text_member")
    assert text_node["content"]["text"] == "Q春日穿搭灵感"
    assert text_node["layout"] == {"x": 10, "y": 12, "width": 90, "height": 20}


def test_unreliable_shape_and_unsafe_visual_are_skipped(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(120, 100))
    m2905_dir = tmp_path / "m29_0_5"
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0001.png", make_canvas(18, 18))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[
            visual_asset("visual_asset_0001", [60, 10, 18, 18], str(visual_asset_path.relative_to(m2905_dir)), text_overlap=0.2, risks=["high_text_overlap"])
        ],
        shape_candidates=[
            shape_candidate("shape_0001", [10, 40, 50, 20], color=None),
        ],
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert count_children(result.dsl, "m30_shape_candidate") == 0
    assert count_children(result.dsl, "m30_visual_asset") == 0
    reasons = {item.reason for item in result.report.skipped_items}
    assert {"missing_reliable_fill", "unsafe_text_overlap"} <= reasons


def test_low_overlap_large_accepted_image_materializes_with_raw_lineage(tmp_path: Path) -> None:
    canvas = make_canvas(420, 320, fill=(240, 240, 240))
    rows = [bytearray(row) for row in canvas.rows]
    for r in range(30, 210):
        for c in range(40, 280):
            rows[r][c * 3 : c * 3 + 3] = b"\x15\x44\x66"
    source = write_png(tmp_path / "source.png", PngPixels(width=420, height=320, rows=[bytes(row) for row in rows]))
    m2905_dir = tmp_path / "m29_0_5"
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0001.png", make_canvas(240, 180, fill=(20, 60, 90)))
    m2903_json = write_json(tmp_path / "m29_0_3" / "visual_evidence.json", m2903_document("accepted_image_003", "m29_image_003", [40, 30, 240, 180]))
    m2904_json = write_json(tmp_path / "m29_0_4" / "visual_object_candidates.json", m2904_document("evidence_0004", "accepted_image_003", [40, 30, 240, 180]))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[
            visual_asset(
                "visual_asset_0001",
                [40, 30, 240, 180],
                str(visual_asset_path.relative_to(m2905_dir)),
                text_overlap=0.015,
                asset_use="image_asset",
                visual_kind="image_like",
                source_evidence_ids=["evidence_0004"],
            )
        ],
        shape_candidates=[],
        text_members=[],
        source_m2903=str(m2903_json),
        source_m2904=str(m2904_json),
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    image_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "m30_visual_asset")
    meta = image_node["meta"]
    assert image_node["layout"] == {"x": 40, "y": 30, "width": 240, "height": 180}
    assert meta["m30AcceptedImageMaterialization"] is True
    assert meta["sourceEvidenceNodeIds"] == ["evidence_0004", "accepted_image_003", "m29_image_003", "image_003"]
    assert meta["sourceM2904EvidenceNodeIds"] == ["evidence_0004"]
    assert meta["sourceM2903ItemIds"] == ["accepted_image_003"]
    assert meta["sourceM2903SourceEvidenceIds"] == ["m29_image_003"]
    assert meta["sourceM29NodeIds"] == ["image_003"]
    assert meta["acceptedImageTextOverlapRatio"] == 0.015
    assert result.report.summary["materializedAcceptedImageCount"] == 1
    materialized = result.report.materialized_image_nodes[0]
    assert {"accepted_image_low_text_overlap", "raw_m29_lineage_recovered"} <= set(materialized.reasons)

    fallback_asset = next(asset for asset in result.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_pixels = decode_png_pixels((tmp_path / "m30" / fallback_asset["url"]).read_bytes())
    for r in range(40, 60):
        for c in range(50, 70):
            offset = c * 3
            assert list(fallback_pixels.rows[r][offset : offset + 3]) == [240, 240, 240]


def test_large_accepted_image_policy_keeps_high_overlap_risk_and_missing_lineage_blocked(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(420, 320))
    m2905_dir = tmp_path / "m29_0_5"
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0001.png", make_canvas(240, 180))
    m2903_json = write_json(tmp_path / "m29_0_3" / "visual_evidence.json", m2903_document("accepted_image_003", "m29_image_003", [40, 30, 240, 180]))
    m2904_json = write_json(tmp_path / "m29_0_4" / "visual_object_candidates.json", m2904_document("evidence_0004", "accepted_image_003", [40, 30, 240, 180]))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[
            visual_asset("visual_asset_high_overlap", [40, 30, 240, 180], str(visual_asset_path.relative_to(m2905_dir)), text_overlap=0.03, asset_use="image_asset", visual_kind="image_like", source_evidence_ids=["evidence_0004"]),
            visual_asset("visual_asset_high_risk", [40, 30, 240, 180], str(visual_asset_path.relative_to(m2905_dir)), text_overlap=0.01, risks=["high_text_overlap"], asset_use="image_asset", visual_kind="image_like", source_evidence_ids=["evidence_0004"]),
            visual_asset("visual_asset_missing_lineage", [40, 30, 240, 180], str(visual_asset_path.relative_to(m2905_dir)), text_overlap=0.01, asset_use="image_asset", visual_kind="image_like", source_evidence_ids=["evidence_missing"]),
        ],
        shape_candidates=[],
        text_members=[],
        source_m2903=str(m2903_json),
        source_m2904=str(m2904_json),
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert count_children(result.dsl, "m30_visual_asset") == 0
    skipped = {item.id: item.reason for item in result.report.skipped_items if item.source_kind == "m2905_visual_asset"}
    assert skipped == {
        "visual_asset_high_overlap": "unsafe_text_overlap",
        "visual_asset_high_risk": "unsafe_text_overlap",
        "visual_asset_missing_lineage": "unsafe_text_overlap",
    }


def test_small_icon_visual_asset_does_not_use_accepted_image_policy(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(120, 100))
    m2905_dir = tmp_path / "m29_0_5"
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0001.png", make_canvas(18, 18))
    m2903_json = write_json(tmp_path / "m29_0_3" / "visual_evidence.json", m2903_document("accepted_image_003", "m29_image_003", [60, 10, 18, 18]))
    m2904_json = write_json(tmp_path / "m29_0_4" / "visual_object_candidates.json", m2904_document("evidence_0004", "accepted_image_003", [60, 10, 18, 18]))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[
            visual_asset("visual_asset_0001", [60, 10, 18, 18], str(visual_asset_path.relative_to(m2905_dir)), text_overlap=0.01, source_evidence_ids=["evidence_0004"])
        ],
        shape_candidates=[],
        text_members=[],
        source_m2903=str(m2903_json),
        source_m2904=str(m2904_json),
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert count_children(result.dsl, "m30_visual_asset") == 0
    assert next(item for item in result.report.skipped_items if item.id == "visual_asset_0001").reason == "unsafe_text_overlap"


def test_audit_only_references_never_become_visible_children(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(100, 80))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir)
    m2905["objects"] = [
        {
            "id": "refined_0001",
            "combinedAssetUse": "audit_only",
            "bbox": [1, 1, 10, 10],
        }
    ]
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert result.report.audit_only_references
    assert result.report.summary["visibleAuditOnlyChildCount"] == 0
    serialized_children = json.dumps(result.dsl["root"]["children"], ensure_ascii=False)
    assert "m2913_audit" not in serialized_children
    assert "m29032_review" not in serialized_children
    assert "mixed_symbol_text_candidate" not in serialized_children


def test_m29_inputs_are_not_rewritten_and_no_new_bbox_is_emitted(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(120, 100))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir)
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)
    before = m2905_json.read_bytes()

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=json.loads(m2905_json.read_text(encoding="utf-8")),
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    assert m2905_json.read_bytes() == before
    source_bboxes = {
        tuple(item["bbox"])
        for key in ("textMembers", "shapeCandidates", "visualAssets")
        for item in m2905.get(key, [])
        if item.get("bbox")
    }
    emitted_bboxes = {
        tuple(item.bbox)
        for item in [
            *result.report.materialized_text_nodes,
            *result.report.materialized_text_cover_nodes,
            *result.report.materialized_shape_nodes,
            *result.report.materialized_image_nodes,
        ]
    }
    assert emitted_bboxes <= source_bboxes
    assert result.report.summary["createdNewBBoxCount"] == 0


def test_forbidden_terms_absent_from_output(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(100, 80))
    m2905_dir = tmp_path / "m29_0_5"
    m2905 = m2905_document(m2905_dir)
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    output_text = json.dumps({"dsl": result.dsl, "report": result.report.to_dict()}, ensure_ascii=False).lower()
    for term in FORBIDDEN_CONTRACT_TERMS:
        assert term not in find_forbidden_contract_terms(output_text)


def test_invalid_cli_mode_input_combination_fails_fast() -> None:
    with pytest.raises(ValueError, match="requires --base-dsl"):
        resolve_mode("augment-existing-dsl", None)
    with pytest.raises(ValueError, match="cannot be combined"):
        resolve_mode("bootstrap-dsl-from-m29", Path("/tmp/base.json"))
    assert resolve_mode("", Path("/tmp/base.json")) == "augment-existing-dsl"
    assert resolve_mode("", None) == "bootstrap-dsl-from-m29"


def m2905_document(
    root: Path,
    *,
    visual_assets: list[dict] | None = None,
    shape_candidates: list[dict] | None = None,
    text_risks: list[str] | None = None,
    text_members: list[dict] | None = None,
    source_m2903: str | None = None,
    source_m2904: str | None = None,
) -> dict:
    visual_asset_path = write_png(root / "assets" / "visual_assets" / "visual_asset_0001.png", make_canvas(18, 18))
    return {
        "schemaName": "M2905TextAwareVisualObjectRefinementDocument",
        "schemaVersion": "0.1",
        "sourceImage": "synthetic.png",
        "sourceM2903VisualEvidenceJson": source_m2903,
        "sourceM2904VisualObjectCandidatesJson": source_m2904,
        "objects": [],
        "visualAssets": visual_assets if visual_assets is not None else [visual_asset("visual_asset_0001", [60, 10, 18, 18], str(visual_asset_path.relative_to(root)))],
        "shapeCandidates": shape_candidates if shape_candidates is not None else [shape_candidate("shape_0001", [10, 40, 50, 20], color="#AABBCC")],
        "textMembers": text_members if text_members is not None else [
            {
                "id": "text_member_0001",
                "sourceObjectId": "object_001",
                "source": "m2902_text_box",
                "sourceEvidenceNodeId": "evidence_text_001",
                "sourceTextBoxId": "ocr_001",
                "bbox": [10, 10, 40, 12],
                "textPreview": "Hello",
                "text": "Hello",
                "confidence": 0.96,
                "risks": text_risks or [],
                "reasons": ["text_member_from_existing_object_member"],
                "previewAssetPath": None,
            }
        ],
    }


def text_member(id: str, bbox: list[int], text: str, risks: list[str] | None = None, source_text_box_id: str = "ocr_001") -> dict:
    return {
        "id": id,
        "sourceObjectId": "object_001",
        "source": "m2902_text_box",
        "sourceEvidenceNodeId": "evidence_text_001",
        "sourceTextBoxId": source_text_box_id,
        "bbox": bbox,
        "textPreview": text,
        "text": text,
        "confidence": 0.96,
        "risks": risks or [],
        "reasons": ["text_member_from_existing_object_member"],
        "previewAssetPath": None,
    }


def visual_asset(
    id: str,
    bbox: list[int],
    asset_path: str,
    *,
    text_overlap: float = 0.0,
    risks: list[str] | None = None,
    asset_use: str = "icon_asset",
    visual_kind: str = "icon_like",
    source_evidence_ids: list[str] | None = None,
) -> dict:
    return {
        "id": id,
        "sourceObjectId": "object_001",
        "sourceEvidenceNodeIds": source_evidence_ids if source_evidence_ids is not None else ["evidence_visual_001"],
        "bbox": bbox,
        "visualKind": visual_kind,
        "assetUse": asset_use,
        "decision": "candidate",
        "assetPath": asset_path,
        "textOverlapRatio": text_overlap,
        "metrics": None,
        "risks": risks or [],
        "reasons": ["icon_asset_from_existing_member_bbox"],
    }


def m2903_document(item_id: str, source_evidence_id: str, bbox: list[int]) -> dict:
    return {
        "schemaName": "M2903VisualEvidenceDocument",
        "schemaVersion": "0.1",
        "items": [
            {
                "id": item_id,
                "source": "m29_image",
                "sourceEvidenceId": source_evidence_id,
                "visualKind": "accepted_image",
                "decision": "accepted",
                "bbox": bbox,
            }
        ],
    }


def m2904_document(evidence_id: str, source_id: str, bbox: list[int]) -> dict:
    return {
        "schemaName": "M2904VisualObjectCandidateDocument",
        "schemaVersion": "0.1",
        "evidenceNodes": [
            {
                "id": evidence_id,
                "sourceId": source_id,
                "bbox": bbox,
            }
        ],
    }


def m2902_document_with_text_box(id: str, bbox: list[int], text: str, meta: dict | None = None) -> dict:
    return m2902_document_with_text_boxes([{"id": id, "bbox": bbox, "text": text, "meta": meta}])


def m2902_document_with_text_boxes(items: list[dict]) -> dict:
    text_boxes = []
    for raw in items:
        item = {
            "id": raw["id"],
            "bbox": raw["bbox"],
            "text": raw["text"],
            "confidence": raw.get("confidence", 0.96),
            "source": "ocr",
            "kind": "line",
        }
        if raw.get("meta") is not None:
            item["meta"] = raw["meta"]
        text_boxes.append(item)
    return {
        "schemaName": "M2902TextMaskedMediaAuditDocument",
        "schemaVersion": "0.1",
        "textBoxes": text_boxes,
    }


def shape_candidate(id: str, bbox: list[int], *, color: str | None) -> dict:
    return {
        "id": id,
        "sourceObjectId": "object_001",
        "sourceEvidenceNodeIds": ["evidence_shape_001"],
        "bbox": bbox,
        "assetUse": "shape_candidate",
        "decision": "candidate",
        "metrics": None,
        "color": color,
        "textOverlapRatio": 0.0,
        "reasons": ["shape_like_member"],
        "risks": [],
        "previewAssetPath": None,
    }


def base_dsl_document() -> dict:
    return {
        "version": "0.1",
        "taskId": "base_task",
        "page": {"name": "base", "width": 120, "height": 100, "background": {"type": "color", "value": "#FFFFFF"}},
        "assets": [
            {"assetId": "asset_original", "type": "image", "role": "original", "url": "source.png", "format": "png"},
            {"assetId": "asset_banner", "type": "image", "role": "fallback_region", "url": "source.png", "format": "png"},
        ],
        "root": {
            "id": "root",
            "type": "frame",
            "role": "screen",
            "layout": {"x": 0, "y": 0, "width": 120, "height": 100},
            "children": [
                {"id": "original_ref", "type": "image", "role": "original_reference", "layout": {"x": 0, "y": 0, "width": 120, "height": 100}, "source": {"assetId": "asset_original"}},
                {"id": "fallback_full_image", "type": "image", "role": "fallback_region", "layout": {"x": 0, "y": 0, "width": 120, "height": 100}, "source": {"assetId": "asset_banner"}},
            ],
        },
        "meta": {"notes": "base"},
    }


def write_png(path: Path, canvas: PngPixels) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_rgb_png(canvas.width, canvas.height, canvas.rows))
    return path


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def make_canvas(width: int, height: int, fill: tuple[int, int, int] = (240, 240, 240)) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])


def make_noisy_text_edge_canvas(width: int, height: int, bbox: list[int]) -> PngPixels:
    rows = [bytearray(row) for row in make_canvas(width, height).rows]
    x, y, box_width, box_height = bbox
    colors = [bytes((220, 220, 220)), bytes((255, 255, 255))]
    for column in range(x, x + box_width):
        for row_index in (y, y + box_height - 1):
            rows[row_index][column * 3 : column * 3 + 3] = colors[column % 2]
    for row_index in range(y, y + box_height):
        for column in (x, x + box_width - 1):
            rows[row_index][column * 3 : column * 3 + 3] = colors[row_index % 2]
    return PngPixels(width=width, height=height, rows=[bytes(row) for row in rows])


def count_children(dsl: dict, role: str) -> int:
    return sum(1 for child in dsl["root"]["children"] if child.get("role") == role)


def test_mask_bboxes_injection_into_fallback_regions(tmp_path: Path) -> None:
    canvas = make_canvas(120, 100, fill=(240, 240, 240))
    # Write some black pixels where the text is located [10, 10, 40, 12]
    rows = [bytearray(row) for row in canvas.rows]
    for r in range(11, 16):
        for c in range(12, 22):
            rows[r][c * 3 : c * 3 + 3] = b"\x00\x00\x00"
    source = write_png(tmp_path / "source.png", PngPixels(width=120, height=100, rows=[bytes(row) for row in rows]))
    m2905_dir = tmp_path / "m29_0_5"
    
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0001.png", make_canvas(10, 10))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[
            visual_asset("visual_asset_0001", [15, 15, 10, 10], str(visual_asset_path.relative_to(m2905_dir))),
        ],
        shape_candidates=[]
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    fallback_node = next(child for child in result.dsl["root"]["children"] if child.get("role") == "fallback_region")
    assert "maskBBoxes" not in fallback_node.get("meta", {})

    fallback_asset = next(asset for asset in result.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_path = tmp_path / "m30" / fallback_asset["url"]
    assert fallback_path.exists()
    
    fallback_pixels = decode_png_pixels(fallback_path.read_bytes())
    for r in range(11, 16):
        for c in range(12, 22):
            offset = c * 3
            assert list(fallback_pixels.rows[r][offset : offset + 3]) == [240, 240, 240]


def test_shape_erasure_from_fallback_images(tmp_path: Path) -> None:
    canvas = make_canvas(120, 100, fill=(240, 240, 240))
    # Write some black pixels where the shape is located [10, 40, 50, 20]
    rows = [bytearray(row) for row in canvas.rows]
    for r in range(41, 46):
        for c in range(12, 22):
            rows[r][c * 3 : c * 3 + 3] = b"\x00\x00\x00"
    source = write_png(tmp_path / "source.png", PngPixels(width=120, height=100, rows=[bytes(row) for row in rows]))
    m2905_dir = tmp_path / "m29_0_5"
    
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[],
        shape_candidates=[
            shape_candidate("shape_0001", [10, 40, 50, 20], color="#000000"),
        ]
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    # 1. Test shape erasure enabled
    result_enabled = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30_enabled",
        mode="bootstrap-dsl-from-m29",
        options=M30Options(shape_erasure_enabled=True),
    )
    fallback_asset_enabled = next(asset for asset in result_enabled.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_path_enabled = tmp_path / "m30_enabled" / fallback_asset_enabled["url"]
    fallback_pixels_enabled = decode_png_pixels(fallback_path_enabled.read_bytes())
    for r in range(41, 46):
        for c in range(12, 22):
            offset = c * 3
            assert list(fallback_pixels_enabled.rows[r][offset : offset + 3]) == [240, 240, 240]

    # 2. Test shape erasure disabled
    result_disabled = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30_disabled",
        mode="bootstrap-dsl-from-m29",
        options=M30Options(shape_erasure_enabled=False),
    )
    fallback_asset_disabled = next(asset for asset in result_disabled.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_path_disabled = tmp_path / "m30_disabled" / fallback_asset_disabled["url"]
    fallback_pixels_disabled = decode_png_pixels(fallback_path_disabled.read_bytes())
    for r in range(41, 46):
        for c in range(12, 22):
            offset = c * 3
            assert list(fallback_pixels_disabled.rows[r][offset : offset + 3]) == [0, 0, 0]


def test_image_erasure_from_fallback_images(tmp_path: Path) -> None:
    canvas = make_canvas(120, 100, fill=(240, 240, 240))
    # Write some black pixels where the visual asset (image) is located [60, 10, 18, 18]
    rows = [bytearray(row) for row in canvas.rows]
    for r in range(11, 16):
        for c in range(62, 72):
            rows[r][c * 3 : c * 3 + 3] = b"\x00\x00\x00"
    source = write_png(tmp_path / "source.png", PngPixels(width=120, height=100, rows=[bytes(row) for row in rows]))
    m2905_dir = tmp_path / "m29_0_5"
    
    visual_asset_path = write_png(m2905_dir / "assets" / "visual_assets" / "visual_asset_0001.png", make_canvas(18, 18))
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[
            visual_asset("visual_asset_0001", [60, 10, 18, 18], str(visual_asset_path.relative_to(m2905_dir))),
        ],
        shape_candidates=[]
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    # 1. Test image erasure enabled
    result_enabled = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30_enabled",
        mode="bootstrap-dsl-from-m29",
        options=M30Options(image_erasure_enabled=True),
    )
    fallback_asset_enabled = next(asset for asset in result_enabled.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_path_enabled = tmp_path / "m30_enabled" / fallback_asset_enabled["url"]
    fallback_pixels_enabled = decode_png_pixels(fallback_path_enabled.read_bytes())
    for r in range(11, 16):
        for c in range(62, 72):
            offset = c * 3
            assert list(fallback_pixels_enabled.rows[r][offset : offset + 3]) == [240, 240, 240]

    # 2. Test image erasure disabled
    result_disabled = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30_disabled",
        mode="bootstrap-dsl-from-m29",
        options=M30Options(image_erasure_enabled=False),
    )
    fallback_asset_disabled = next(asset for asset in result_disabled.dsl["assets"] if asset.get("role") == "fallback_region")
    fallback_path_disabled = tmp_path / "m30_disabled" / fallback_asset_disabled["url"]
    fallback_pixels_disabled = decode_png_pixels(fallback_path_disabled.read_bytes())
    for r in range(11, 16):
        for c in range(62, 72):
            offset = c * 3
            assert list(fallback_pixels_disabled.rows[r][offset : offset + 3]) == [0, 0, 0]


def test_text_font_size_harmonization(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(300, 200))
    m2905_dir = tmp_path / "m29_0_5"
    
    # We create 3 text elements:
    # 1. "Alpha" at y=50, height=22 (initial font size round(22*0.82) = 18)
    # 2. "Beta" at y=52, height=18 (initial font size round(18*0.82) = 15)
    # 3. "Gamma" at y=52, height=18 (initial font size round(18*0.82) = 15)
    # These three are horizontally aligned (y_centers: 61, 61, 61) and have similar initial sizes (18, 15, 15).
    # Since difference <= 3, they should be harmonized to their median: 15.
    
    # We also add another element in the same row that has a very different size:
    # 4. "10:00" at y=55, height=10 (initial font size round(10*0.82) = 8).
    # This element should not be harmonized (difference to 15 is 7 > 3).
    
    # And another element on a completely different row:
    # 5. "Section" at y=120, height=20 (initial font size round(20*0.82) = 16).
    # This should not be harmonized with the first row.
    
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[],
        shape_candidates=[],
        text_members=[
            text_member("text_0001", [10, 50, 40, 22], "Alpha"),
            text_member("text_0002", [60, 52, 40, 18], "Beta"),
            text_member("text_0003", [110, 52, 40, 18], "Gamma"),
            text_member("text_0004", [200, 55, 30, 10], "10:00"),
            text_member("text_0005", [10, 120, 80, 20], "Section"),
        ]
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    children = result.dsl["root"]["children"]
    text_nodes = {c["name"]: c for c in children if c.get("type") == "text" and c.get("role") == "m30_text_member"}
    
    # Assert harmonization worked on the first row
    assert text_nodes["M30 Text / text_0001"]["style"]["fontSize"] == 15
    assert text_nodes["M30 Text / text_0002"]["style"]["fontSize"] == 15
    assert text_nodes["M30 Text / text_0003"]["style"]["fontSize"] == 15
    
    # Assert the small element in same row was not harmonized
    assert text_nodes["M30 Text / text_0004"]["style"]["fontSize"] == 8
    
    # Assert the element in the other row was not harmonized
    assert text_nodes["M30 Text / text_0005"]["style"]["fontSize"] == 16


def test_text_font_size_harmonization_mode_snapping(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(1000, 300))
    m2905_dir = tmp_path / "m29_0_5"
    
    # We create a horizontal tab bar row with multiple noisy sizes:
    # 1. "Primary" (height 46 -> fs 38)
    # 2. "Alpha" (height 36 -> fs 30)
    # 3. "Beta" (height 36 -> fs 30)
    # 4. "Gamma" (height 36 -> fs 30)
    # 5. "Delta" (height 42 -> fs 34)
    # 6. "Epsilon" (height 36 -> fs 30)
    # 7. "Zeta" (height 31 -> fs 25)
    # 8. "More" (height 25 -> fs 20)
    # Mode is 30. Adaptive threshold is max(3, min(6, round(30 * 0.18))) = 5.
    # Snapping range is [25, 35].
    # Expected: "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta" snap to 30.
    # "Primary" (38) and "More" (20) remain unchanged.
    
    m2905 = m2905_document(
        m2905_dir,
        visual_assets=[],
        shape_candidates=[],
        text_members=[
            text_member("text_0001", [32, 167, 78, 46], "Primary"),
            text_member("text_0002", [152, 171, 63, 36], "Alpha"),
            text_member("text_0003", [263, 171, 63, 36], "Beta"),
            text_member("text_0004", [375, 173, 61, 36], "Gamma"),
            text_member("text_0005", [483, 168, 64, 42], "Delta"),
            text_member("text_0006", [594, 173, 59, 36], "Epsilon"),
            text_member("text_0007", [703, 175, 57, 31], "Zeta"),
            text_member("text_0008", [796, 177, 25, 25], "More"),
        ]
    )
    m2905_json = write_json(m2905_dir / "refined_visual_objects.json", m2905)

    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source),
        m2905_document=m2905,
        m2905_json_path=str(m2905_json),
        output_dir=tmp_path / "m30",
        mode="bootstrap-dsl-from-m29",
    )

    children = result.dsl["root"]["children"]
    text_nodes = {c["name"]: c for c in children if c.get("type") == "text" and c.get("role") == "m30_text_member"}
    
    # Mode-snapped elements should all be 30
    assert text_nodes["M30 Text / text_0002"]["style"]["fontSize"] == 30
    assert text_nodes["M30 Text / text_0003"]["style"]["fontSize"] == 30
    assert text_nodes["M30 Text / text_0004"]["style"]["fontSize"] == 30
    assert text_nodes["M30 Text / text_0005"]["style"]["fontSize"] == 30
    assert text_nodes["M30 Text / text_0006"]["style"]["fontSize"] == 30
    assert text_nodes["M30 Text / text_0007"]["style"]["fontSize"] == 30
    
    # Non-snapped elements
    assert text_nodes["M30 Text / text_0001"]["style"]["fontSize"] == 36 # max capped at 36
    assert text_nodes["M30 Text / text_0008"]["style"]["fontSize"] == 20
