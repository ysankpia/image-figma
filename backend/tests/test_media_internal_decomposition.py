from __future__ import annotations

from pathlib import Path

from app.media_internal_decomposition import extract_m29_media_internal_decomposition_report
from app.png_tools import encode_rgb_png


def test_media_internal_decomposition_empty_is_report_only(tmp_path: Path) -> None:
    report = media_report(tmp_path, source_objects=[], raw_nodes=[], ocr_blocks=[])

    assert report["summary"]["compositeMediaCount"] == 0
    assert report["summary"]["internalCandidateCount"] == 0
    assert report["summary"]["dslChanged"] is False
    assert report["summary"]["assetChanged"] is False
    assert report["summary"]["createdVisibleNodeCount"] == 0
    assert report["meta"]["reportOnly"] is True


def test_composite_media_with_internal_ocr_and_symbol_reports_candidate(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_objects=[source_object("media", [0, 0, 240, 140], risks=["contains_internal_text"])],
        raw_nodes=[raw_symbol("icon", [94, 48, 28, 28], fill_ratio=0.62)],
        ocr_blocks=[ocr_block("label", [88, 86, 42, 16])],
    )

    assert report["summary"]["compositeMediaCount"] == 1
    assert report["summary"]["textMaskCount"] == 1
    assert report["summary"]["internalCandidateCount"] == 1
    candidate = report["internalCandidates"][0]
    assert candidate["role"] == "internal_icon_candidate"
    assert candidate["candidateDecision"] == "accepted_report_candidate"
    assert candidate["matchedOcrBoxId"] == "label"
    assert candidate["scoreBreakdown"]["textAnchorScore"] > 0


def test_text_mask_rejects_raw_component_overlapping_internal_ocr(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_objects=[source_object("media", [0, 0, 240, 140])],
        raw_nodes=[raw_symbol("glyph_piece", [91, 87, 30, 12])],
        ocr_blocks=[ocr_block("label", [88, 86, 42, 16])],
    )

    candidate = report["internalCandidates"][0]
    assert candidate["candidateDecision"] == "rejected_fragment"
    assert "overlaps_internal_text_mask" in candidate["risks"]
    assert report["rejectedFragments"][0]["reason"] == "overlaps_internal_text_mask"


def test_large_hero_fragment_is_rejected(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_objects=[source_object("media", [0, 0, 300, 180])],
        raw_nodes=[raw_symbol("hero", [76, 25, 150, 90], texture=0.32, color_count=80, fill_ratio=0.28)],
        ocr_blocks=[ocr_block("label", [40, 146, 50, 18])],
    )

    candidate = report["internalCandidates"][0]
    assert candidate["candidateDecision"] == "rejected_fragment"
    assert "large_media_fragment" in candidate["risks"] or "hero_or_texture_fragment" in candidate["risks"]


def test_repeated_icon_label_row_builds_matched_group_without_text_literal_rule(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_objects=[source_object("media", [0, 0, 360, 160])],
        raw_nodes=[
            raw_symbol("icon_a", [38, 55, 28, 28]),
            raw_symbol("icon_b", [138, 55, 28, 28]),
            raw_symbol("icon_c", [238, 55, 28, 28]),
        ],
        ocr_blocks=[
            ocr_block("text_a", [34, 95, 36, 16]),
            ocr_block("text_b", [134, 95, 36, 16]),
            ocr_block("text_c", [234, 95, 36, 16]),
        ],
    )

    assert report["summary"]["matchedInternalGroupCount"] == 1
    group = report["matchedInternalGroups"][0]
    assert group["role"] == "action_row"
    assert group["layoutModel"] == "row"
    assert len(group["items"]) == 3
    assert report["meta"]["noSpecializedTextFilenameThemeOrFixedBboxRules"] is True


def test_ocr_anchor_foreground_uses_multiple_relations_not_only_above_text(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_png=make_anchor_relation_png(),
        source_objects=[source_object("media", [0, 0, 180, 140])],
        raw_nodes=[],
        ocr_blocks=[ocr_block("label", [78, 62, 24, 14])],
    )

    candidates = [
        item
        for item in report["internalCandidates"]
        if item["rawType"] == "pixel_component" and item["candidateDecision"] == "accepted_report_candidate"
    ]
    relations = {item["anchorRelation"] for item in candidates}
    assert {"above_text", "below_text", "left_of_text", "right_of_text"}.issubset(relations)
    assert all("ocr_anchor_foreground_component" in item["reasons"] for item in candidates)


def test_non_ocr_foreground_component_inside_media_reports_candidate(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_png=make_non_ocr_foreground_png(),
        source_objects=[source_object("media", [0, 0, 220, 140])],
        raw_nodes=[],
        ocr_blocks=[],
    )

    candidates = [
        item
        for item in report["internalCandidates"]
        if item["rawSubtype"] == "non_ocr_foreground" and item["candidateDecision"] == "accepted_report_candidate"
    ]
    assert candidates
    assert any(contained_bbox([146, 48, 28, 24], item["bbox"]) for item in candidates)
    assert all("non_ocr_internal_foreground_component" in item["reasons"] for item in candidates)
    assert all(item["matchedOcrBoxId"] is None for item in candidates)
    assert report["meta"]["noSpecializedTextFilenameThemeOrFixedBboxRules"] is True


def test_non_ocr_foreground_still_respects_internal_text_mask(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_png=make_non_ocr_foreground_png(),
        source_objects=[source_object("media", [0, 0, 220, 140])],
        raw_nodes=[],
        ocr_blocks=[ocr_block("label", [146, 48, 28, 24])],
    )

    accepted = [
        item
        for item in report["internalCandidates"]
        if item["rawSubtype"] == "non_ocr_foreground" and item["candidateDecision"] == "accepted_report_candidate"
    ]
    assert not any(overlaps_bbox(item["bbox"], [146, 48, 28, 24]) for item in accepted)


def test_non_ocr_large_hero_foreground_is_rejected_not_promoted(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_png=make_non_ocr_foreground_png(hero=True),
        source_objects=[source_object("media", [0, 0, 220, 140])],
        raw_nodes=[],
        ocr_blocks=[],
    )

    rejected = [
        item
        for item in report["internalCandidates"]
        if item["rawSubtype"] == "non_ocr_foreground" and item["candidateDecision"] == "rejected_fragment"
    ]
    assert rejected
    assert any("large_media_fragment" in item["risks"] or "hero_or_texture_fragment" in item["risks"] for item in rejected)


def test_action_row_group_support_marks_medium_candidates_without_text_literal_rule(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_objects=[source_object("media", [0, 0, 420, 180])],
        raw_nodes=[
            raw_symbol("icon_a", [42, 55, 26, 24], color_count=86, fill_ratio=0.36),
            raw_symbol("icon_b", [142, 55, 26, 24], color_count=86, fill_ratio=0.36),
            raw_symbol("icon_c", [242, 55, 26, 24], color_count=86, fill_ratio=0.36),
        ],
        ocr_blocks=[
            ocr_block("text_a", [38, 95, 36, 16]),
            ocr_block("text_b", [138, 95, 36, 16]),
            ocr_block("text_c", [238, 95, 36, 16]),
        ],
    )

    assert report["summary"]["matchedInternalGroupCount"] == 1
    supported = [item for item in report["internalCandidates"] if item.get("groupSupportedExecution") is True]
    assert supported
    assert all(item["confidence"] in {"high", "medium"} for item in supported)


def test_single_control_row_icon_text_geometry_supports_execution_without_repetition(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_objects=[source_object("media", [0, 0, 240, 120])],
        raw_nodes=[raw_symbol("icon", [42, 42, 36, 34], color_count=12, fill_ratio=0.68)],
        ocr_blocks=[ocr_block("label", [104, 46, 54, 20])],
    )

    candidate = next(item for item in report["internalCandidates"] if item["rawNodeId"] == "icon")
    assert candidate["candidateDecision"] == "accepted_report_candidate"
    assert candidate["matchedOcrBoxId"] == "label"
    assert candidate["anchorRelation"] == "left_of_text"
    assert candidate["controlRowSupportedExecution"] is True
    assert "single_control_row_icon_text_geometry" in candidate["reasons"]
    assert candidate.get("groupSupportedExecution") is not True


def test_large_hero_fragment_does_not_get_single_control_row_execution_support(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_objects=[source_object("media", [0, 0, 300, 180])],
        raw_nodes=[raw_symbol("hero", [34, 34, 138, 86], texture=0.22, color_count=56, fill_ratio=0.42)],
        ocr_blocks=[ocr_block("label", [190, 62, 48, 18])],
    )

    candidate = next(item for item in report["internalCandidates"] if item["rawNodeId"] == "hero")
    assert candidate.get("controlRowSupportedExecution") is not True


def test_fragmented_icon_parts_with_same_text_anchor_get_union_candidate(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_objects=[source_object("media", [0, 0, 520, 180])],
        raw_nodes=[
            raw_symbol("icon_a", [42, 55, 30, 34], color_count=22, fill_ratio=0.50),
            raw_symbol("icon_b", [162, 54, 30, 34], color_count=22, fill_ratio=0.50),
            raw_symbol("icon_c_top", [281, 54, 30, 17], color_count=22, fill_ratio=0.42),
            raw_symbol("icon_c_bottom", [280, 69, 32, 17], color_count=22, fill_ratio=0.42),
            raw_symbol("icon_d", [402, 55, 30, 34], color_count=22, fill_ratio=0.50),
        ],
        ocr_blocks=[
            ocr_block("text_a", [38, 108, 38, 16]),
            ocr_block("text_b", [158, 108, 38, 16]),
            ocr_block("text_c", [278, 108, 38, 16]),
            ocr_block("text_d", [398, 108, 38, 16]),
        ],
    )

    merged = [
        item
        for item in report["internalCandidates"]
        if "merged_anchor_icon_fragments" in item["reasons"] and item["matchedOcrBoxId"] == "text_c"
    ]
    assert merged
    assert merged[0]["candidateDecision"] == "accepted_report_candidate"
    assert merged[0]["bbox"] == [280, 54, 32, 32]
    assert merged[0]["groupSupportedExecution"] is True
    assert len(merged[0]["sourceFragmentCandidateIds"]) == 2
    group_items = [item for group in report["matchedInternalGroups"] for item in group["items"]]
    assert {item["ocrBoxId"] for item in group_items} == {"text_a", "text_b", "text_c", "text_d"}


def test_near_media_bottom_label_can_anchor_internal_icon_candidate(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_png=make_selected_tab_png(),
        source_objects=[source_object("media", [0, 30, 260, 100])],
        raw_nodes=[],
        ocr_blocks=[ocr_block("tab_label", [108, 118, 44, 24])],
    )

    anchored = [
        item
        for item in report["internalCandidates"]
        if item["candidateDecision"] == "accepted_report_candidate"
        and item.get("matchedOcrBoxId") == "tab_label"
        and item.get("anchorRelation") == "above_text"
    ]
    assert anchored
    assert any("ocr_anchor_foreground_component" in item["reasons"] for item in anchored)


def test_separator_inside_media_is_rejected_not_icon(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_objects=[source_object("media", [0, 0, 240, 140])],
        raw_nodes=[raw_shape("separator", [120, 50, 1, 50], subtype="separator")],
        ocr_blocks=[ocr_block("label", [88, 86, 42, 16])],
    )

    candidate = report["internalCandidates"][0]
    assert candidate["role"] == "internal_separator_candidate"
    assert candidate["candidateDecision"] == "rejected_fragment"
    assert "separator_not_icon" in candidate["risks"]


def test_scaled_pixel_anchor_component_is_not_rejected_by_1x_area_cap(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_png=make_scaled_anchor_png(),
        source_objects=[source_object("media", [0, 0, 600, 360])],
        raw_nodes=[],
        ocr_blocks=[ocr_block("large_label", [250, 300, 90, 42])],
        image_size={"width": 600, "height": 360},
    )

    anchored = [
        item
        for item in report["internalCandidates"]
        if item["candidateDecision"] == "accepted_report_candidate"
        and item["rawType"] == "pixel_component"
        and item["matchedOcrBoxId"] == "large_label"
    ]
    assert anchored
    assert any(item["bbox"][2] >= 72 and item["bbox"][3] >= 68 for item in anchored)
    assert report["meta"]["scaleProfile"]["scale_basis_px"] > 24


def test_many_small_non_ocr_components_are_not_limited_to_top_six(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_png=make_many_small_components_png(),
        source_objects=[source_object("media", [0, 0, 170, 120])],
        raw_nodes=[],
        ocr_blocks=[],
        image_size={"width": 170, "height": 120},
    )

    components = [item for item in report["internalCandidates"] if item["rawSubtype"] == "non_ocr_foreground"]
    assert len(components) >= 8
    assert sum(1 for item in components if item["candidateDecision"] == "accepted_report_candidate") >= 8


def test_selected_indicator_pixel_component_reports_marker_role_not_icon(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_png=make_selected_marker_component_png(),
        source_objects=[source_object("media", [0, 0, 260, 160])],
        raw_nodes=[],
        ocr_blocks=[ocr_block("tab_label", [96, 80, 68, 24])],
        image_size={"width": 260, "height": 160},
    )

    selected = [
        item
        for item in report["internalCandidates"]
        if item["candidateDecision"] == "accepted_report_candidate"
        and item["role"] == "selected_marker_candidate"
        and item["matchedOcrBoxId"] == "tab_label"
    ]
    assert selected
    assert all(item["rawType"] == "pixel_component" for item in selected)


def test_repeated_small_non_ocr_components_report_table_marker_role(tmp_path: Path) -> None:
    report = media_report(
        tmp_path,
        source_png=make_table_marker_components_png(),
        source_objects=[source_object("media", [0, 0, 240, 180])],
        raw_nodes=[],
        ocr_blocks=[],
        image_size={"width": 240, "height": 180},
    )

    markers = [
        item
        for item in report["internalCandidates"]
        if item["candidateDecision"] == "accepted_report_candidate" and item["role"] == "table_marker_candidate"
    ]
    assert len(markers) >= 3
    assert all("repeated_small_marker_geometry" in item["reasons"] for item in markers)


def media_report(
    tmp_path: Path,
    *,
    source_png: bytes | None = None,
    source_objects: list[dict],
    raw_nodes: list[dict],
    ocr_blocks: list[dict],
    image_size: dict[str, int] | None = None,
) -> dict:
    image_size = image_size or {"width": 400, "height": 300}
    result = extract_m29_media_internal_decomposition_report(
        task_id="task_media_internal",
        source_png=source_png,
        m29_document={"version": "0.1", "imageSize": image_size, "nodes": raw_nodes, "blocked": []},
        ocr_document={"version": "0.1", "imageSize": image_size, "blocks": ocr_blocks},
        m292_document={"schemaName": "M292SourceUiPhysicalGraph", "schemaVersion": "0.1", "sourceObjects": source_objects},
        m2931_report={"schemaName": "M2931RegionRelationGraphReport", "schemaVersion": "0.1", "edges": []},
        m295_report={"schemaName": "M295ReplayPlan", "schemaVersion": "0.1", "planItems": []},
        output_dir=tmp_path / "m29_media_internal_decomposition",
    )
    assert (tmp_path / "m29_media_internal_decomposition" / "media_internal_decomposition_report.json").exists()
    return result.report


def source_object(object_id: str, bbox: list[int], *, risks: list[str] | None = None) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": "media_region",
        "pixelOwner": "preserve_raster",
        "replayDecision": "image_replay",
        "sourceEvidence": {},
        "confidence": "medium",
        "reasons": ["test"],
        "risks": risks or [],
    }


def ocr_block(block_id: str, bbox: list[int]) -> dict:
    return {
        "id": block_id,
        "text": "xx",
        "bbox": bbox,
        "confidence": 0.96,
        "lineId": f"{block_id}_line",
        "blockId": f"{block_id}_block",
    }


def raw_symbol(
    node_id: str,
    bbox: list[int],
    *,
    texture: float = 0.08,
    color_count: int = 18,
    fill_ratio: float = 0.56,
) -> dict:
    return raw_node(node_id, bbox, "symbol", "foreground", texture=texture, color_count=color_count, fill_ratio=fill_ratio)


def raw_shape(node_id: str, bbox: list[int], *, subtype: str = "rect") -> dict:
    return raw_node(node_id, bbox, "shape", subtype, texture=0.04, color_count=4, fill_ratio=1.0)


def raw_node(
    node_id: str,
    bbox: list[int],
    node_type: str,
    subtype: str,
    *,
    texture: float,
    color_count: int,
    fill_ratio: float,
) -> dict:
    return {
        "id": node_id,
        "type": node_type,
        "subtype": subtype,
        "bbox": bbox,
        "confidence": 0.82,
        "source": "test",
        "sourceOrder": 1,
        "layerHint": "content",
        "reasons": ["test"],
        "metrics": {
            "colorCount": color_count,
            "textureScore": texture,
            "edgeScore": 0.1,
            "fillRatio": fill_ratio,
            "aspectRatio": round(bbox[2] / bbox[3], 4),
            "brightness": 120,
            "meanRgb": [80, 120, 200],
        },
    }


def make_anchor_relation_png() -> bytes:
    rows = []
    icon_color = [20, 80, 220]
    icon_boxes = [
        [80, 34, 18, 18],
        [80, 96, 18, 18],
        [42, 60, 18, 18],
        [120, 60, 18, 18],
    ]
    for y in range(140):
        row = bytearray()
        for x in range(180):
            rgb = [255, 255, 255]
            if any(box[0] <= x < box[0] + box[2] and box[1] <= y < box[1] + box[3] for box in icon_boxes):
                rgb = icon_color
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(180, 140, rows)


def make_non_ocr_foreground_png(*, hero: bool = False) -> bytes:
    rows = []
    for y in range(140):
        row = bytearray()
        for x in range(220):
            rgb = [18, 22, 38]
            if 146 <= x < 174 and 48 <= y < 72:
                rgb = [40, 150, 240]
            if hero and 44 <= x < 176 and 30 <= y < 112:
                rgb = [20 + (x + y) % 70, 90 + (x * 3 + y) % 120, 150 + (x + y * 2) % 90]
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(220, 140, rows)


def make_selected_tab_png() -> bytes:
    rows = []
    for y in range(160):
        row = bytearray()
        for x in range(260):
            rgb = [5, 12, 26]
            if 96 <= x < 164 and 54 <= y < 108:
                rgb = [28, 118, 255]
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(260, 160, rows)


def make_scaled_anchor_png() -> bytes:
    rows = []
    for y in range(360):
        row = bytearray()
        for x in range(600):
            rgb = [8, 12, 24]
            if 260 <= x < 340 and 160 <= y < 240:
                rgb = [30, 128, 255]
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(600, 360, rows)


def make_many_small_components_png() -> bytes:
    boxes = [[10 + column * 38, 16 + row * 42, 12, 12] for row in range(2) for column in range(4)]
    rows = []
    for y in range(120):
        row = bytearray()
        for x in range(170):
            rgb = [12, 16, 30]
            if any(box[0] <= x < box[0] + box[2] and box[1] <= y < box[1] + box[3] for box in boxes):
                rgb = [42, 160, 242]
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(170, 120, rows)


def make_selected_marker_component_png() -> bytes:
    rows = []
    for y in range(160):
        row = bytearray()
        for x in range(260):
            rgb = [5, 12, 26]
            if 102 <= x < 158 and 118 <= y < 128:
                rgb = [42, 96, 255]
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(260, 160, rows)


def make_table_marker_components_png() -> bytes:
    boxes = [[26, 28 + row * 44, 10, 10] for row in range(3)]
    rows = []
    for y in range(180):
        row = bytearray()
        for x in range(240):
            rgb = [14, 18, 32]
            if any(box[0] <= x < box[0] + box[2] and box[1] <= y < box[1] + box[3] for box in boxes):
                rgb = [46, 170, 116]
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(240, 180, rows)


def contained_bbox(inner: list[int], outer: list[int]) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[0] + outer[2] >= inner[0] + inner[2] and outer[1] + outer[3] >= inner[1] + inner[3]


def overlaps_bbox(left: list[int], right: list[int]) -> bool:
    return max(left[0], right[0]) < min(left[0] + left[2], right[0] + right[2]) and max(left[1], right[1]) < min(left[1] + left[3], right[1] + right[3])
