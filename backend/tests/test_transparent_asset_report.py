from __future__ import annotations

from pathlib import Path

from app.png_tools import decode_png_pixels, encode_rgb_png
from app.transparent_asset_report import extract_m29_transparent_asset_report


def test_transparent_asset_empty_is_report_only(tmp_path: Path) -> None:
    report = transparent_report(tmp_path, source_objects=[], ocr_blocks=[], internal_candidates=[])

    assert report["summary"]["candidateCount"] == 0
    assert report["summary"]["allowedCount"] == 0
    assert report["summary"]["assetChanged"] is False
    assert report["meta"]["reportOnly"] is True
    assert report["meta"]["materializerConsumesAssets"] is False


def test_raster_icon_on_stable_background_allows_rgba_debug_asset(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_objects=[raster_icon("icon", [18, 18, 24, 24])],
        ocr_blocks=[],
        internal_candidates=[],
    )

    assert report["summary"]["candidateCount"] == 1
    assert report["summary"]["allowedCount"] == 1
    item = report["items"][0]
    assert item["decision"] == "allow"
    assert item["assetPath"]
    asset_path = tmp_path / "m29_transparent_assets" / item["assetPath"]
    assert asset_path.exists()
    pixels = decode_png_pixels(asset_path.read_bytes())
    assert pixels.width == 24
    assert pixels.height == 24
    assert item["alphaCoverage"] > 0.20
    assert item["largestComponentRatio"] > 0.90


def test_ocr_overlap_rejects_transparent_asset(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_objects=[raster_icon("icon", [18, 18, 24, 24])],
        ocr_blocks=[ocr_block("text", [18, 18, 24, 24])],
        internal_candidates=[],
    )

    item = report["items"][0]
    assert item["decision"] == "reject"
    assert "overlaps_ocr_text" in item["risks"]
    assert item["assetPath"] is None


def test_unstable_background_rejects_asset(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_png=make_icon_png(unstable_background=True),
        source_objects=[raster_icon("icon", [18, 18, 24, 24])],
        ocr_blocks=[],
        internal_candidates=[],
    )

    item = report["items"][0]
    assert item["decision"] == "reject"
    assert "unstable_background" in item["reasons"]


def test_edge_alpha_risk_rejects_background_block_asset(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_png=make_icon_png(edge_alpha_risk=True),
        source_objects=[raster_icon("icon", [18, 18, 24, 24])],
        ocr_blocks=[],
        internal_candidates=[],
    )

    item = report["items"][0]
    assert item["decision"] == "reject"
    assert "edge_alpha_risk" in item["reasons"]
    assert item["edgeAlphaCoverageGt32"] > 0.12
    assert item["assetPath"] is None


def test_high_confidence_m29_6_internal_icon_candidate_uses_same_alpha_gate(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_objects=[],
        ocr_blocks=[],
        internal_candidates=[internal_icon("internal_icon", [18, 18, 24, 24], confidence="high")],
    )

    assert report["summary"]["candidateCount"] == 1
    assert report["summary"]["allowedCount"] == 1
    item = report["items"][0]
    assert item["source"] == "m29_6_internal_icon_candidate"
    assert item["decision"] == "allow"


def test_medium_confidence_internal_icon_without_group_support_is_report_rejected(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_objects=[],
        ocr_blocks=[],
        internal_candidates=[internal_icon("internal_icon", [18, 18, 24, 24], confidence="medium")],
    )

    item = report["items"][0]
    assert item["decision"] == "reject"
    assert "internal_candidate_not_execution_supported" in item["risks"]


def test_group_supported_medium_internal_icon_uses_alpha_gate(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_objects=[],
        ocr_blocks=[],
        internal_candidates=[internal_icon("internal_icon", [18, 18, 24, 24], confidence="medium", group_supported=True)],
    )

    item = report["items"][0]
    assert item["decision"] == "allow"
    assert "group_supported_internal_candidate" in item["reasons"]
    assert "internal_candidate_not_execution_supported" not in item["risks"]


def test_anchored_group_supported_internal_icon_allows_soft_edge_glow(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_png=make_soft_edge_selected_icon_png(),
        source_objects=[media_region("media", [0, 0, 96, 72])],
        ocr_blocks=[ocr_block("label", [36, 58, 24, 8])],
        internal_candidates=[
            internal_icon(
                "internal_icon",
                [30, 18, 36, 34],
                confidence="high",
                group_supported=True,
                media_source_object_id="media",
                matched_ocr_box_id="label",
                anchor_relation="above_text",
                text_anchor=0.92,
                hero_penalty=0.12,
                text_overlap=0.02,
                raw_type="pixel_component",
                raw_subtype="non_ocr_foreground",
            )
        ],
    )

    item = report["items"][0]
    assert item["decision"] == "allow"
    assert item["alphaProfile"] == "anchored_soft_edge_icon"
    assert "anchored_soft_edge_alpha" in item["reasons"]
    assert item["edgeAlphaCoverageGt32"] > 0.12
    assert item["largestComponentRatio"] >= 0.90


def test_unanchored_internal_icon_with_soft_edge_still_rejects_edge_alpha_risk(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_png=make_soft_edge_selected_icon_png(),
        source_objects=[media_region("media", [0, 0, 96, 72])],
        ocr_blocks=[],
        internal_candidates=[internal_icon("internal_icon", [30, 18, 36, 34], confidence="high", media_source_object_id="media")],
    )

    item = report["items"][0]
    assert item["decision"] == "reject"
    assert item["alphaProfile"] == "default_icon"
    assert "edge_alpha_risk" in item["reasons"]


def test_internal_icon_uses_context_bbox_for_stable_action_strip_background(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_png=make_action_strip_png(),
        source_objects=[media_region("media", [0, 0, 96, 72])],
        ocr_blocks=[],
        internal_candidates=[internal_icon("internal_icon", [38, 28, 16, 16], confidence="high", media_source_object_id="media")],
    )

    item = report["items"][0]
    assert item["decision"] == "allow"
    assert item["bbox"] == [38, 28, 16, 16]
    assert item["analysisBbox"][2] > item["bbox"][2]
    assert item["analysisBbox"][3] > item["bbox"][3]
    assert item["backgroundCoverage"] >= 0.36
    asset_path = tmp_path / "m29_transparent_assets" / item["assetPath"]
    pixels = decode_png_pixels(asset_path.read_bytes())
    assert pixels.width == item["analysisBbox"][2]
    assert pixels.height == item["analysisBbox"][3]


def test_unstable_background_still_rejects_when_no_dominant_background_cluster(tmp_path: Path) -> None:
    report = transparent_report(
        tmp_path,
        source_png=make_no_dominant_background_png(),
        source_objects=[media_region("media", [0, 0, 96, 72])],
        ocr_blocks=[],
        internal_candidates=[internal_icon("internal_icon", [38, 28, 16, 16], confidence="high", media_source_object_id="media")],
    )

    item = report["items"][0]
    assert item["decision"] == "reject"
    assert "unstable_background" in item["reasons"]


def transparent_report(
    tmp_path: Path,
    *,
    source_png: bytes | None = None,
    source_objects: list[dict],
    ocr_blocks: list[dict],
    internal_candidates: list[dict],
) -> dict:
    result = extract_m29_transparent_asset_report(
        task_id="task_transparent_asset",
        source_png=source_png or make_icon_png(),
        ocr_document={"version": "0.1", "imageSize": {"width": 64, "height": 64}, "blocks": ocr_blocks},
        m292_document={"schemaName": "M292SourceUiPhysicalGraph", "schemaVersion": "0.1", "sourceObjects": source_objects},
        media_internal_report={
            "schemaName": "M29MediaInternalDecompositionReport",
            "schemaVersion": "0.1",
            "internalCandidates": internal_candidates,
        },
        output_dir=tmp_path / "m29_transparent_assets",
    )
    assert (tmp_path / "m29_transparent_assets" / "transparent_asset_report.json").exists()
    return result.report


def make_icon_png(*, unstable_background: bool = False, edge_alpha_risk: bool = False) -> bytes:
    rows = []
    for y in range(64):
        row = bytearray()
        for x in range(64):
            rgb = [255, 255, 255]
            if unstable_background and 18 <= x < 42 and 18 <= y < 42:
                rgb = [245, 245, 245] if (x + y) % 2 == 0 else [40, 80, 180]
            if edge_alpha_risk and x == 18 and 18 <= y < 42:
                rgb = [225, 225, 225]
            if 22 <= x < 38 and 22 <= y < 38:
                rgb = [0, 0, 0]
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(64, 64, rows)


def make_action_strip_png() -> bytes:
    rows = []
    for y in range(72):
        row = bytearray()
        for x in range(96):
            rgb = [49, 41, 30]
            if 38 <= x < 54 and 28 <= y < 44:
                rgb = [230, 198, 144]
            if 24 <= x < 32 and 14 <= y < 22:
                rgb = [232, 198, 145]
            if 64 <= x < 78 and 48 <= y < 56:
                rgb = [230, 198, 144]
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(96, 72, rows)


def make_no_dominant_background_png() -> bytes:
    colors = ([20, 40, 180], [230, 210, 80], [80, 190, 120], [190, 60, 160])
    rows = []
    for y in range(72):
        row = bytearray()
        for x in range(96):
            rgb = list(colors[((x // 3) + (y // 3)) % len(colors)])
            if 38 <= x < 54 and 28 <= y < 44:
                rgb = [0, 0, 0]
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(96, 72, rows)


def make_soft_edge_selected_icon_png() -> bytes:
    rows = []
    for y in range(72):
        row = bytearray()
        for x in range(96):
            rgb = [4, 20, 52]
            if (26 <= x < 70 and 14 <= y < 56) or (70 <= x < 78 and 24 <= y < 48) or (36 <= x < 64 and 56 <= y < 64):
                rgb = [8, 38, 78]
            if 30 <= x < 66 and 18 <= y < 52:
                rgb = [21, 106, 224]
            if 36 <= x < 60 and 24 <= y < 46:
                rgb = [126, 206, 255]
            row.extend(rgb)
        rows.append(bytes(row))
    return encode_rgb_png(96, 72, rows)


def raster_icon(object_id: str, bbox: list[int]) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": "raster_icon",
        "pixelOwner": "raster_icon",
        "replayDecision": "icon_replay",
        "sourceEvidence": {},
        "confidence": "high",
        "reasons": ["test"],
        "risks": [],
    }


def media_region(object_id: str, bbox: list[int]) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": "media_region",
        "pixelOwner": "preserve_raster",
        "replayDecision": "image_replay",
        "sourceEvidence": {},
        "confidence": "medium",
        "reasons": ["test"],
        "risks": ["contains_internal_text"],
    }


def ocr_block(block_id: str, bbox: list[int]) -> dict:
    return {"id": block_id, "text": "xx", "bbox": bbox, "confidence": 0.98}


def internal_icon(
    candidate_id: str,
    bbox: list[int],
    *,
    confidence: str,
    group_supported: bool = False,
    media_source_object_id: str = "media",
    matched_ocr_box_id: str = "",
    anchor_relation: str = "",
    text_anchor: float = 0.0,
    hero_penalty: float = 0.1,
    text_overlap: float = 0.0,
    raw_type: str = "symbol",
    raw_subtype: str = "icon",
) -> dict:
    return {
        "candidateId": candidate_id,
        "mediaSourceObjectId": media_source_object_id,
        "rawNodeId": "raw_icon",
        "rawType": raw_type,
        "rawSubtype": raw_subtype,
        "role": "internal_icon_candidate",
        "bbox": bbox,
        "candidateDecision": "accepted_report_candidate",
        "confidence": confidence,
        "score": 0.82,
        "scoreBreakdown": {"heroGraphicPenalty": hero_penalty, "textMaskOverlap": text_overlap, "textAnchorScore": text_anchor},
        "matchedOcrBoxId": matched_ocr_box_id,
        "anchorRelation": anchor_relation,
        "metrics": {},
        **({"groupSupportedExecution": True} if group_supported else {}),
    }
