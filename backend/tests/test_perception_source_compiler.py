from __future__ import annotations

from pathlib import Path

from app.m29_replay_plan import build_m295_replay_plan
from app.perception_source_compiler import extract_perception_source_compiler_report
from app.png_tools import PngPixels, encode_rgb_png
from app.region_relation_graph_report import extract_m2931_region_relation_graph_report


def test_model_text_container_candidate_compiles_to_control_shape_and_m295_cleanup(tmp_path: Path) -> None:
    source = make_png(
        240,
        160,
        fill=(248, 248, 248),
        marks=[
            ([20, 30, 180, 44], (82, 148, 76)),
            ([72, 44, 82, 14], (255, 255, 255)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_control",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_cta", "Action", [72, 42, 82, 18])]),
        perception_model_report=perception_report([candidate("model_button", [20, 30, 200, 74], 0.86)]),
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 240, 160], "media_region", "preserve_raster", "image_replay"),
                m292_object("text", [72, 42, 82, 18], "editable_ui_text", "editable_text", "text_replay", source_evidence={"ocrBoxIds": ["ocr_cta"]}),
            ]
        ),
        output_dir=tmp_path / "compiler",
    )

    shape = only_compiled(result.report, "control_background")
    assert shape["bbox"] == [20, 30, 180, 44]
    assert shape["pixelOwner"] == "shape_geometry"
    assert shape["replayDecision"] == "shape_replay"
    assert shape["sourceEvidence"]["ocrBoxIds"] == ["ocr_cta"]
    assert shape["sourceEvidence"]["perceptionCandidateId"] == "model_button"
    assert shape["sourceEvidence"]["mediaSourceObjectId"] == "media"
    assert shape["sourceEvidence"]["foregroundClaimId"] == "model_button:foreground_claim"
    assert shape["sourceEvidence"]["shapeFillOverride"] == "#52944C"
    assert shape["sourceEvidence"]["claimMaskKind"] == "bbox"
    assert "shapeRadiusOverride" not in shape["sourceEvidence"]

    relation = extract_m2931_region_relation_graph_report(
        task_id="task_compiler_control",
        m292_document=result.m292_document,
        output_dir=tmp_path / "m29_3_1",
    ).report
    replay = build_m295_replay_plan(
        task_id="task_compiler_control",
        m292_document=result.m292_document,
        m2931_report=relation,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    ).report
    shape_item = next(item for item in replay["planItems"] if item["sourceObjectId"] == shape["id"])
    assert shape_item["finalReplayAction"] == "shape_replay"
    assert {
        "target": "copied_image_asset",
        "targetSourceObjectId": "media",
        "reason": "foreground_claim_removed_from_residual_media",
        "foregroundClaimId": "model_button:foreground_claim",
        "maskKind": "bbox",
    } in shape_item["cleanupTargets"]


def test_model_rounded_button_uses_pixel_proven_radius_and_mask_radius(tmp_path: Path) -> None:
    source = make_png(240, 160, fill=(248, 248, 248))
    draw_rounded_rect(source, 20, 30, 180, 44, 12, (82, 148, 76))
    source = paint_marks(source, [([72, 44, 82, 14], (255, 255, 255))])
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_rounded_control",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_cta", "Action", [72, 42, 82, 18])]),
        perception_model_report=perception_report([candidate("model_button", [20, 30, 200, 74], 0.86)]),
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 240, 160], "media_region", "preserve_raster", "image_replay"),
                m292_object("text", [72, 42, 82, 18], "editable_ui_text", "editable_text", "text_replay", source_evidence={"ocrBoxIds": ["ocr_cta"]}),
            ]
        ),
        output_dir=tmp_path / "compiler",
    )

    shape = only_compiled(result.report, "control_background")
    assert shape["sourceEvidence"]["claimMaskKind"] == "rounded_rect"
    assert shape["sourceEvidence"]["shapeRadiusOverride"] == 12
    relation = extract_m2931_region_relation_graph_report(
        task_id="task_compiler_rounded_control",
        m292_document=result.m292_document,
        output_dir=tmp_path / "m29_3_1",
    ).report
    replay = build_m295_replay_plan(
        task_id="task_compiler_rounded_control",
        m292_document=result.m292_document,
        m2931_report=relation,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    ).report
    shape_item = next(item for item in replay["planItems"] if item["sourceObjectId"] == shape["id"])
    assert {
        "target": "copied_image_asset",
        "targetSourceObjectId": "media",
        "reason": "foreground_claim_removed_from_residual_media",
        "foregroundClaimId": "model_button:foreground_claim",
        "maskKind": "rounded_rect",
        "maskRadius": 12,
    } in shape_item["cleanupTargets"]


def test_compact_non_text_candidate_compiles_to_source_crop_icon(tmp_path: Path) -> None:
    source = make_png(160, 120, fill=(248, 248, 248), marks=[([42, 32, 24, 24], (40, 90, 220)), ([88, 36, 44, 16], (20, 20, 20))])
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_icon",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_label", "Login", [88, 36, 44, 16])]),
        perception_model_report=perception_report([candidate("model_icon", [42, 32, 66, 56], 0.77)]),
        m292_document=m292_document([m292_object("media", [0, 0, 160, 120], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    icon = only_compiled(result.report, "raster_icon")
    assert icon["bbox"] == [42, 32, 24, 24]
    assert icon["pixelOwner"] == "raster_icon"
    assert icon["replayDecision"] == "icon_replay"
    assert icon["sourceEvidence"]["perceptionCandidateId"] == "model_icon"
    assert icon["sourceEvidence"]["controlRowSourceCropEligible"] is True

    relation = extract_m2931_region_relation_graph_report(
        task_id="task_compiler_icon",
        m292_document=result.m292_document,
        output_dir=tmp_path / "m29_3_1",
    ).report
    replay = build_m295_replay_plan(
        task_id="task_compiler_icon",
        m292_document=result.m292_document,
        m2931_report=relation,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    ).report
    assert next(item for item in replay["planItems"] if item["sourceObjectId"] == icon["id"])["finalReplayAction"] == "icon_replay"


def test_geometry_control_candidate_is_not_suppressed_by_parent_media_duplicate(tmp_path: Path) -> None:
    source = make_png(
        260,
        600,
        fill=(20, 24, 68),
        marks=[
            ([30, 280, 200, 42], (45, 48, 102)),
            ([52, 292, 28, 18], (255, 255, 255)),
            ([96, 294, 78, 14], (255, 255, 255)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_media_button",
        source_png=png_bytes(source),
        ocr_document=ocr_document([]),
        perception_model_report=perception_report([candidate("model_full_button", [30, 280, 230, 322], 0.44)]),
        m292_document=m292_document([m292_object("media_button", [30, 280, 200, 42], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    shape = only_compiled(result.report, "control_background")
    assert shape["bbox"] == [30, 280, 200, 42]
    assert shape["sourceEvidence"]["mediaSourceObjectId"] == "media_button"
    assert shape["sourceEvidence"]["internalRole"] == "internal_control_background"
    assert shape["sourceEvidence"]["controlInferenceReasons"] == ["perception_candidate_control_geometry"]


def test_text_candidate_near_equal_to_parent_media_remains_report_only(tmp_path: Path) -> None:
    source = make_png(
        320,
        220,
        fill=(245, 248, 255),
        marks=[
            ([24, 32, 272, 120], (95, 155, 240)),
            ([54, 60, 140, 28], (255, 255, 255)),
            ([54, 96, 110, 18], (255, 255, 255)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_media_text_region",
        source_png=png_bytes(source),
        ocr_document=ocr_document(
            [
                ocr_block("ocr_title", "Banner title", [54, 60, 140, 28]),
                ocr_block("ocr_subtitle", "Subtitle", [54, 96, 110, 18]),
            ]
        ),
        perception_model_report=perception_report([candidate("model_banner", [24, 32, 296, 152], 0.44)]),
        m292_document=m292_document(
            [
                m292_object("media_banner", [20, 28, 280, 128], "media_region", "preserve_raster", "image_replay"),
                m292_object("text_title", [54, 60, 140, 28], "editable_ui_text", "editable_text", "text_replay", source_evidence={"ocrBoxIds": ["ocr_title"]}),
            ]
        ),
        output_dir=tmp_path / "compiler",
    )

    assert result.report["summary"]["compiledSourceObjectCount"] == 0
    assert result.report["rejectedCandidates"][0]["reason"] in {
        "large_perception_candidate_preserved_as_media_residual",
        "near_equal_parent_media_candidate",
    }


def test_large_text_content_region_is_not_compiled_as_control_background(tmp_path: Path) -> None:
    source = make_png(
        360,
        900,
        fill=(248, 248, 248),
        marks=[
            ([28, 260, 304, 170], (255, 255, 255)),
            ([52, 288, 130, 22], (20, 20, 20)),
            ([52, 324, 180, 18], (80, 80, 80)),
            ([52, 360, 170, 18], (80, 80, 80)),
            ([52, 396, 130, 18], (80, 80, 80)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_large_card",
        source_png=png_bytes(source),
        ocr_document=ocr_document(
            [
                ocr_block("ocr_title", "Card title", [52, 288, 130, 22]),
                ocr_block("ocr_line_1", "Line one", [52, 324, 180, 18]),
                ocr_block("ocr_line_2", "Line two", [52, 360, 170, 18]),
                ocr_block("ocr_line_3", "Line three", [52, 396, 130, 18]),
            ]
        ),
        perception_model_report=perception_report([candidate("model_content_card", [28, 260, 332, 430], 0.41)]),
        m292_document=m292_document([]),
        output_dir=tmp_path / "compiler",
    )

    assert result.report["summary"]["compiledSourceObjectCount"] == 0
    assert result.report["rejectedCandidates"][0]["reason"] == "content_region_too_large_for_control_background"


def test_complex_single_line_text_control_compiles_to_selectable_image_crop(tmp_path: Path) -> None:
    source = make_png(
        360,
        900,
        fill=(16, 18, 42),
        marks=[
            ([48, 310, 264, 100], (28, 24, 58)),
            ([118, 348, 124, 20], (248, 248, 248)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_tall_single_line_control",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_button", "Continue", [118, 348, 124, 20])]),
        perception_model_report=perception_report([candidate("model_tall_button", [48, 310, 312, 410], 0.46)]),
        m292_document=m292_document([m292_object("media", [0, 0, 360, 900], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    control = only_compiled(result.report, "media_region")
    assert control["bbox"] == [48, 310, 264, 100]
    assert control["pixelOwner"] == "preserve_raster"
    assert control["replayDecision"] == "image_replay"
    assert control["sourceEvidence"]["ocrBoxIds"] == ["ocr_button"]
    assert control["sourceEvidence"]["internalRole"] == "internal_control_raster_background"
    assert control["sourceEvidence"]["mediaSourceObjectId"] == "media"
    assert control["sourceEvidence"]["controlInferenceReasons"] == ["perception_candidate_complex_text_control_raster_crop"]


def test_multi_item_navigation_container_does_not_become_raster_owner(tmp_path: Path) -> None:
    source = make_png(
        420,
        420,
        fill=(248, 248, 248),
        marks=[
            ([20, 80, 380, 112], (255, 255, 255)),
            ([52, 100, 24, 24], (80, 80, 80)),
            ([132, 100, 24, 24], (80, 80, 80)),
            ([212, 100, 24, 24], (20, 170, 86)),
            ([292, 100, 24, 24], (80, 80, 80)),
            ([48, 154, 34, 18], (80, 80, 80)),
            ([128, 154, 34, 18], (80, 80, 80)),
            ([208, 154, 34, 18], (20, 170, 86)),
            ([288, 154, 34, 18], (80, 80, 80)),
        ],
    )
    base_objects = [
        m292_object("icon_home", [52, 100, 24, 24], "raster_icon", "raster_icon", "icon_replay"),
        m292_object("icon_category", [132, 100, 24, 24], "raster_icon", "raster_icon", "icon_replay"),
        m292_object("icon_order", [212, 100, 24, 24], "raster_icon", "raster_icon", "icon_replay"),
        m292_object("icon_profile", [292, 100, 24, 24], "raster_icon", "raster_icon", "icon_replay"),
        m292_object("text_home", [48, 154, 34, 18], "editable_ui_text", "editable_text", "text_replay", source_evidence={"ocrBoxIds": ["ocr_home"]}),
        m292_object("text_category", [128, 154, 34, 18], "editable_ui_text", "editable_text", "text_replay", source_evidence={"ocrBoxIds": ["ocr_category"]}),
        m292_object("text_order", [208, 154, 34, 18], "editable_ui_text", "editable_text", "text_replay", source_evidence={"ocrBoxIds": ["ocr_order"]}),
        m292_object("text_profile", [288, 154, 34, 18], "editable_ui_text", "editable_text", "text_replay", source_evidence={"ocrBoxIds": ["ocr_profile"]}),
    ]
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_multi_item_nav",
        source_png=png_bytes(source),
        ocr_document=ocr_document(
            [
                ocr_block("ocr_home", "Home", [48, 154, 34, 18]),
                ocr_block("ocr_category", "Cat", [128, 154, 34, 18]),
                ocr_block("ocr_order", "Order", [208, 154, 34, 18]),
                ocr_block("ocr_profile", "Mine", [288, 154, 34, 18]),
            ]
        ),
        perception_model_report=perception_report([candidate("model_bottom_nav", [20, 80, 400, 192], 0.44)]),
        m292_document=m292_document(base_objects),
        output_dir=tmp_path / "compiler",
    )

    assert not [
        item
        for item in result.report["compiledSourceObjects"]
        if item["visualKind"] == "media_region"
        and item["sourceEvidence"].get("internalRole") == "internal_control_raster_background"
    ]
    rejected_candidate_ids = {item["candidateId"] for item in result.report["rejectedCandidates"]}
    assert "model_bottom_nav" in rejected_candidate_ids

    relation = extract_m2931_region_relation_graph_report(
        task_id="task_compiler_multi_item_nav",
        m292_document=result.m292_document,
        output_dir=tmp_path / "m29_3_1",
    ).report
    replay = build_m295_replay_plan(
        task_id="task_compiler_multi_item_nav",
        m292_document=result.m292_document,
        m2931_report=relation,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    ).report
    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in replay["planItems"]}
    assert actions["icon_home"] == "icon_replay"
    assert actions["icon_category"] == "icon_replay"
    assert actions["icon_order"] == "icon_replay"
    assert actions["icon_profile"] == "icon_replay"
    assert actions["text_home"] == "text_replay"
    assert actions["text_category"] == "text_replay"
    assert actions["text_order"] == "text_replay"
    assert actions["text_profile"] == "text_replay"


def test_geometry_control_candidate_compiles_without_complete_ocr_containment(tmp_path: Path) -> None:
    source = make_png(
        320,
        700,
        fill=(248, 248, 248),
        marks=[
            ([48, 296, 224, 48], (33, 88, 190)),
            ([78, 312, 24, 16], (255, 255, 255)),
            ([124, 312, 98, 16], (255, 255, 255)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_geometry_control",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_outside", "Continue", [124, 351, 98, 16])]),
        perception_model_report=perception_report([candidate("model_button_bg", [48, 296, 272, 344], 0.39)]),
        m292_document=m292_document([m292_object("media", [0, 0, 320, 700], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    shape = only_compiled(result.report, "control_background")
    assert shape["bbox"] == [48, 296, 224, 48]
    assert shape["sourceEvidence"]["ocrBoxIds"] == []
    assert shape["sourceEvidence"]["controlInferenceReasons"] == ["perception_candidate_control_geometry"]
    assert shape["sourceEvidence"]["shapeFillOverride"] == "#2158BE"


def test_low_score_icon_candidate_compiles_only_inside_compiled_control(tmp_path: Path) -> None:
    source = make_png(
        320,
        700,
        fill=(248, 248, 248),
        marks=[
            ([48, 296, 224, 48], (33, 88, 190)),
            ([78, 312, 24, 16], (255, 255, 255)),
            ([124, 312, 98, 16], (255, 255, 255)),
            ([280, 40, 18, 18], (20, 20, 20)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_control_child_icon",
        source_png=png_bytes(source),
        ocr_document=ocr_document([]),
        perception_model_report=perception_report(
            [
                candidate("model_button_bg", [48, 296, 272, 344], 0.42),
                candidate("model_button_icon", [76, 310, 104, 330], 0.11),
                candidate("model_loose_low_score_fragment", [280, 40, 298, 58], 0.11),
            ]
        ),
        m292_document=m292_document([m292_object("media", [0, 0, 320, 700], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    shape = only_compiled(result.report, "control_background")
    icon = only_compiled(result.report, "raster_icon")
    assert icon["sourceEvidence"]["parentControlSourceObjectId"] == shape["id"]
    assert icon["sourceEvidence"]["iconInferenceReasons"] == ["perception_candidate_inside_compiled_control"]
    rejected = {item["candidateId"]: item["reason"] for item in result.report["rejectedCandidates"]}
    assert rejected["model_loose_low_score_fragment"] == "insufficient_ownership_evidence"


def test_low_score_control_child_icon_cannot_claim_text_pixels(tmp_path: Path) -> None:
    source = make_png(
        320,
        700,
        fill=(248, 248, 248),
        marks=[
            ([48, 296, 224, 48], (33, 88, 190)),
            ([78, 312, 24, 16], (255, 255, 255)),
            ([124, 312, 98, 16], (255, 255, 255)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_child_icon_text_overlap",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_label", "Continue", [124, 312, 98, 16])]),
        perception_model_report=perception_report(
            [
                candidate("model_button_bg", [48, 296, 272, 344], 0.42),
                candidate("model_text_sized_icon", [112, 304, 236, 336], 0.11),
            ]
        ),
        m292_document=m292_document([m292_object("media", [0, 0, 320, 700], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    shape = only_compiled(result.report, "control_background")
    assert shape["sourceEvidence"]["controlInferenceReasons"] == ["perception_candidate_contains_ocr_text"]
    icons = [item for item in result.report["compiledSourceObjects"] if item["visualKind"] == "raster_icon"]
    assert len(icons) == 1
    assert icons[0]["bbox"] == [78, 312, 24, 16]
    assert icons[0]["sourceEvidence"]["parentControlSourceObjectId"] == shape["id"]
    assert icons[0]["sourceEvidence"]["iconInferenceReasons"] == ["inferred_leading_icon_inside_compiled_control"]
    rejected = {item["candidateId"]: item["reason"] for item in result.report["rejectedCandidates"]}
    assert rejected["model_text_sized_icon"] == "control_child_icon_text_overlap_risk"


def test_low_score_control_child_icon_allows_edge_text_overlap_inside_parent_control(tmp_path: Path) -> None:
    source = make_png(
        320,
        700,
        fill=(248, 248, 248),
        marks=[
            ([48, 296, 224, 48], (33, 88, 190)),
            ([86, 310, 30, 30], (255, 255, 255)),
            ([112, 312, 84, 16], (255, 255, 255)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_child_icon_edge_overlap",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_label", "Transfer", [112, 312, 84, 16])]),
        perception_model_report=perception_report(
            [
                candidate("model_button_bg", [48, 296, 272, 344], 0.42),
                candidate("model_icon_edge_touch", [86, 310, 118, 340], 0.09),
            ]
        ),
        m292_document=m292_document([m292_object("media", [0, 0, 320, 700], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    shape = only_compiled(result.report, "control_background")
    icons = [item for item in result.report["compiledSourceObjects"] if item["visualKind"] == "raster_icon"]
    assert len(icons) == 1
    assert icons[0]["bbox"] == [86, 310, 32, 30]
    assert icons[0]["sourceEvidence"]["parentControlSourceObjectId"] == shape["id"]
    assert icons[0]["sourceEvidence"]["iconInferenceReasons"] == ["perception_candidate_inside_compiled_control"]
    assert not any(item["candidateId"] == "model_icon_edge_touch" for item in result.report["rejectedCandidates"])


def test_low_score_icon_candidate_compiles_inside_complex_control_image_crop(tmp_path: Path) -> None:
    source = make_png(
        360,
        900,
        fill=(16, 18, 42),
        marks=[
            ([48, 310, 264, 100], (28, 24, 58)),
            ([74, 336, 44, 44], (40, 110, 230)),
            ([146, 348, 124, 20], (248, 248, 248)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_complex_control_child_icon",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_button", "Continue", [146, 348, 124, 20])]),
        perception_model_report=perception_report(
            [
                candidate("model_tall_button", [48, 310, 312, 410], 0.46),
                candidate("model_button_icon", [74, 336, 118, 380], 0.12),
            ]
        ),
        m292_document=m292_document([m292_object("media", [0, 0, 360, 900], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    control = only_compiled(result.report, "media_region")
    icon = only_compiled(result.report, "raster_icon")
    assert control["sourceEvidence"]["internalRole"] == "internal_control_raster_background"
    assert icon["sourceEvidence"]["parentControlSourceObjectId"] == control["id"]
    assert icon["sourceEvidence"]["iconInferenceReasons"] == ["perception_candidate_inside_compiled_control"]


def test_low_risk_unknown_candidate_compiles_to_selectable_raster_crop(tmp_path: Path) -> None:
    source = make_png(
        240,
        180,
        fill=(18, 20, 42),
        marks=[
            ([68, 56, 48, 28], (55, 90, 220)),
            ([88, 64, 28, 14], (210, 230, 255)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_selectable_crop",
        source_png=png_bytes(source),
        ocr_document=ocr_document([]),
        perception_model_report=perception_report([candidate("model_unknown_ui", [60, 48, 132, 96], 0.22)]),
        m292_document=m292_document([m292_object("media", [0, 0, 240, 180], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    crop = only_compiled(result.report, "media_region")
    assert crop["id"] == "m292_perception_selectable_crop_0001"
    assert crop["bbox"] == [60, 48, 72, 48]
    assert crop["pixelOwner"] == "preserve_raster"
    assert crop["replayDecision"] == "image_replay"
    assert crop["sourceEvidence"]["internalRole"] == "internal_selectable_raster_crop"
    assert crop["sourceEvidence"]["cleanupEligible"] is False
    assert crop["sourceEvidence"]["controlInferenceReasons"] == ["perception_candidate_selectable_raster_crop_fallback"]

    relation = extract_m2931_region_relation_graph_report(
        task_id="task_compiler_selectable_crop",
        m292_document=result.m292_document,
        output_dir=tmp_path / "m29_3_1",
    ).report
    replay = build_m295_replay_plan(
        task_id="task_compiler_selectable_crop",
        m292_document=result.m292_document,
        m2931_report=relation,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    ).report
    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in replay["planItems"]}
    assert actions["media"] == "image_replay"
    assert actions[crop["id"]] == "image_replay"
    crop_item = next(item for item in replay["planItems"] if item["sourceObjectId"] == crop["id"])
    assert crop_item["targetRole"] == "m29_image"
    assert not any(target.get("target") == "copied_image_asset" for target in crop_item["cleanupTargets"])


def test_text_only_model_candidate_does_not_become_selectable_raster_crop(tmp_path: Path) -> None:
    source = make_png(
        240,
        180,
        fill=(248, 248, 248),
        marks=[([82, 62, 64, 18], (20, 20, 20))],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_text_candidate_no_crop",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_text", "Label", [82, 62, 64, 18])]),
        perception_model_report=perception_report([candidate("model_text_only", [82, 62, 146, 80], 0.16)]),
        m292_document=m292_document([m292_object("text", [82, 62, 64, 18], "editable_ui_text", "editable_text", "text_replay", source_evidence={"ocrBoxIds": ["ocr_text"]})]),
        output_dir=tmp_path / "compiler",
    )

    assert result.report["summary"]["compiledSourceObjectCount"] == 0
    rejected = {item["candidateId"]: item["reason"] for item in result.report["rejectedCandidates"]}
    assert rejected["model_text_only"] in {
        "duplicate_or_near_equal_existing_source_object",
        "insufficient_ownership_evidence",
    }


def test_vertical_label_tile_infers_icon_above_text_without_replaying_whole_tile(tmp_path: Path) -> None:
    source = make_png(
        360,
        220,
        fill=(14, 18, 34),
        marks=[
            ([54, 42, 96, 112], (18, 26, 48)),
            ([82, 58, 40, 32], (30, 190, 245)),
            ([78, 122, 48, 24], (230, 236, 245)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_vertical_action_tile",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_action", "充值", [78, 122, 48, 24])]),
        perception_model_report=perception_report([candidate("model_action_tile", [54, 42, 150, 154], 0.48)]),
        m292_document=m292_document([m292_object("media", [0, 0, 360, 220], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    icons = [item for item in result.report["compiledSourceObjects"] if item["visualKind"] == "raster_icon"]
    controls = [item for item in result.report["compiledSourceObjects"] if item["visualKind"] == "control_background"]
    assert len(icons) == 1
    assert controls == []
    assert icons[0]["bbox"] == [82, 58, 40, 32]
    assert icons[0]["sourceEvidence"]["labelAnchorOcrBoxId"] == "ocr_action"
    assert icons[0]["sourceEvidence"]["iconInferenceReasons"] == ["inferred_icon_above_ocr_label_inside_model_tile"]


def test_control_candidate_infers_missing_leading_icon_from_pixels_left_of_text(tmp_path: Path) -> None:
    source = make_png(
        360,
        220,
        fill=(246, 246, 246),
        marks=[
            ([42, 80, 276, 56], (255, 255, 255)),
            ([72, 98, 24, 20], (30, 100, 220)),
            ([126, 100, 142, 16], (30, 30, 30)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_missing_leading_icon",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_label", "Continue", [126, 100, 142, 16])]),
        perception_model_report=perception_report([candidate("model_button", [42, 80, 318, 136], 0.74)]),
        m292_document=m292_document([m292_object("media", [0, 0, 360, 220], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    compiled = result.report["compiledSourceObjects"]
    control = next(item for item in compiled if item["visualKind"] == "control_background")
    icons = [item for item in compiled if item["visualKind"] == "raster_icon"]
    assert len(icons) == 1
    assert icons[0]["bbox"] == [72, 98, 24, 20]
    assert icons[0]["sourceEvidence"]["parentControlSourceObjectId"] == control["id"]
    assert icons[0]["sourceEvidence"]["iconInferenceReasons"] == ["inferred_leading_icon_inside_compiled_control"]
    assert icons[0]["sourceEvidence"]["leadingIconSource"] == "control_pixels_left_of_ocr_text"


def test_control_text_child_candidate_does_not_block_missing_leading_icon_inference(tmp_path: Path) -> None:
    source = make_png(
        360,
        220,
        fill=(246, 246, 246),
        marks=[
            ([42, 80, 276, 56], (255, 255, 255)),
            ([72, 98, 24, 20], (30, 100, 220)),
            ([126, 100, 142, 16], (30, 30, 30)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_text_child_not_icon",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_label", "Continue", [126, 100, 142, 16])]),
        perception_model_report=perception_report(
            [
                candidate("model_button", [42, 80, 318, 136], 0.74),
                candidate("model_text_candidate", [124, 96, 270, 120], 0.12),
            ]
        ),
        m292_document=m292_document([m292_object("media", [0, 0, 360, 220], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    icons = [item for item in result.report["compiledSourceObjects"] if item["visualKind"] == "raster_icon"]
    assert len(icons) == 1
    assert icons[0]["bbox"] == [72, 98, 24, 20]
    assert icons[0]["sourceEvidence"]["derivedFromPerceptionCandidateId"] == "model_button"
    assert icons[0]["sourceEvidence"]["iconInferenceReasons"] == ["inferred_leading_icon_inside_compiled_control"]
    rejected = {item["candidateId"]: item["reason"] for item in result.report["rejectedCandidates"]}
    assert rejected["model_text_candidate"] == "control_child_icon_text_overlap_risk"


def test_control_candidate_does_not_infer_leading_icon_without_foreground_pixels(tmp_path: Path) -> None:
    source = make_png(
        360,
        220,
        fill=(246, 246, 246),
        marks=[
            ([42, 80, 276, 56], (255, 255, 255)),
            ([126, 100, 142, 16], (30, 30, 30)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_no_missing_leading_icon",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_label", "Continue", [126, 100, 142, 16])]),
        perception_model_report=perception_report([candidate("model_button", [42, 80, 318, 136], 0.74)]),
        m292_document=m292_document([m292_object("media", [0, 0, 360, 220], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    assert len([item for item in result.report["compiledSourceObjects"] if item["visualKind"] == "raster_icon"]) == 0


def test_tiny_stable_circle_candidate_compiles_to_shape_not_icon(tmp_path: Path) -> None:
    source = make_png(120, 90, fill=(248, 248, 248), marks=[([40, 30, 10, 10], (45, 115, 235))])
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_circle",
        source_png=png_bytes(source),
        ocr_document=ocr_document([]),
        perception_model_report=perception_report([candidate("model_dot", [40, 30, 50, 40], 0.72)]),
        m292_document=m292_document([m292_object("media", [0, 0, 120, 90], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    shape = only_compiled(result.report, "control_background")
    assert shape["bbox"] == [40, 30, 10, 10]
    assert shape["pixelOwner"] == "shape_geometry"
    assert shape["replayDecision"] == "shape_replay"
    assert shape["sourceEvidence"]["internalRole"] == "internal_circle_control"
    assert shape["sourceEvidence"]["claimMaskKind"] == "circle"
    assert shape["sourceEvidence"]["shapeRadiusOverride"] == 5


def test_large_model_candidate_remains_report_only_not_source_ownership(tmp_path: Path) -> None:
    source = make_png(300, 200, fill=(30, 40, 80), marks=[([40, 50, 220, 100], (80, 120, 180))])
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_hero",
        source_png=png_bytes(source),
        ocr_document=ocr_document([]),
        perception_model_report=perception_report([candidate("model_hero", [0, 0, 300, 200], 0.91)]),
        m292_document=m292_document([m292_object("media", [0, 0, 300, 200], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    assert result.report["summary"]["compiledSourceObjectCount"] == 0
    assert result.report["summary"]["sourceOwnershipChanged"] is False
    assert result.report["rejectedCandidates"][0]["reason"] == "large_perception_candidate_preserved_as_media_residual"
    assert len(result.m292_document["sourceObjects"]) == 1


def only_compiled(report: dict, visual_kind: str) -> dict:
    matches = [item for item in report["compiledSourceObjects"] if item["visualKind"] == visual_kind]
    assert len(matches) == 1
    return matches[0]


def perception_report(candidates: list[dict]) -> dict:
    return {
        "schemaName": "M29PerceptionModelReport",
        "schemaVersion": "0.1",
        "summary": {"candidateCount": len(candidates), "reportOnly": True},
        "candidates": candidates,
    }


def candidate(candidate_id: str, bbox: list[float], score: float) -> dict:
    return {
        "candidateId": candidate_id,
        "sourceProvider": "test_model",
        "roleHint": "unknown_ui_object",
        "bbox": bbox,
        "score": score,
        "decision": "report_only",
        "replayAuthorized": False,
        "cleanupAuthorized": False,
    }


def m292_document(objects: list[dict]) -> dict:
    return {
        "schemaName": "M292SourceUiPhysicalGraph",
        "schemaVersion": "0.1",
        "sourceObjects": objects,
        "summary": {"sourceObjectCount": len(objects)},
        "meta": {},
    }


def m292_object(
    object_id: str,
    bbox: list[int],
    visual_kind: str,
    pixel_owner: str,
    replay_decision: str,
    *,
    confidence: str = "high",
    source_evidence: dict | None = None,
) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "sourceEvidence": source_evidence or {},
        "confidence": confidence,
        "reasons": ["test"],
        "risks": [],
    }


def ocr_document(blocks: list[dict]) -> dict:
    return {"version": "0.1", "taskId": "test", "provider": "test", "model": None, "imageSize": {"width": 80, "height": 60}, "coordinateSpace": "pixel", "blocks": blocks, "warnings": []}


def ocr_block(block_id: str, text: str, bbox: list[int], *, confidence: float = 0.95) -> dict:
    return {"id": block_id, "text": text, "bbox": bbox, "confidence": confidence, "lineId": block_id, "blockId": block_id, "source": "test"}


def make_png(width: int, height: int, *, fill: tuple[int, int, int] = (250, 250, 250), marks: list[tuple[list[int], tuple[int, int, int]]] | None = None) -> PngPixels:
    rows = [bytearray(bytes(fill) * width) for _ in range(height)]
    for bbox, color in marks or []:
        x, y, w, h = bbox
        for row_index in range(y, y + h):
            for column in range(x, x + w):
                rows[row_index][column * 3 : column * 3 + 3] = bytes(color)
    return PngPixels(width=width, height=height, rows=[bytes(row) for row in rows])


def paint_marks(pixels: PngPixels, marks: list[tuple[list[int], tuple[int, int, int]]]) -> PngPixels:
    rows = [bytearray(row) for row in pixels.rows]
    for bbox, color in marks:
        x, y, w, h = bbox
        for row_index in range(y, y + h):
            for column in range(x, x + w):
                rows[row_index][column * 3 : column * 3 + 3] = bytes(color)
    return PngPixels(width=pixels.width, height=pixels.height, rows=[bytes(row) for row in rows])


def draw_rounded_rect(canvas: PngPixels, x: int, y: int, width: int, height: int, radius: int, color: tuple[int, int, int]) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    color_bytes = bytes(color)
    radius = max(0, min(radius, min(width, height) // 2))
    for row_index in range(y, min(canvas.height, y + height)):
        for column in range(x, min(canvas.width, x + width)):
            local_x = column - x
            local_y = row_index - y
            cx = radius if local_x < radius else width - radius - 1 if local_x >= width - radius else local_x
            cy = radius if local_y < radius else height - radius - 1 if local_y >= height - radius else local_y
            if (local_x - cx) * (local_x - cx) + (local_y - cy) * (local_y - cy) <= radius * radius:
                rows[row_index][column * 3 : column * 3 + 3] = color_bytes
    canvas.rows[:] = [bytes(row) for row in rows]


def png_bytes(pixels: PngPixels) -> bytes:
    return encode_rgb_png(pixels.width, pixels.height, pixels.rows)
