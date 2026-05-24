from __future__ import annotations

from pathlib import Path

from app.png_tools import PngPixels, encode_rgb_png, read_png_metadata
from app.source_ui_physical_graph import M292SourcePhysicalOptions, extract_source_ui_physical_graph


def test_high_confidence_ocr_text_becomes_editable_text_replay(tmp_path: Path) -> None:
    source = make_png(120, 80, fill=(248, 248, 248), marks=[([20, 20, 28, 10], (20, 20, 20))])
    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29_document(tmp_path, nodes=[]),
        ocr_document=ocr_document([ocr_block("ocr_001", "Hello", [20, 20, 28, 10], confidence=0.98)]),
        output_dir=tmp_path / "m29_2",
    )

    obj = only_object(result, "editable_ui_text")
    assert obj["pixelOwner"] == "editable_text"
    assert obj["replayDecision"] == "text_replay"
    assert obj["sourceEvidence"]["ocrBoxIds"] == ["ocr_001"]
    assert result["summary"]["editableTextCount"] == 1


def test_ocr_text_inside_large_textured_media_is_preserved_as_raster(tmp_path: Path) -> None:
    source = make_textured_png(220, 140, [10, 10, 150, 80])
    m29 = m29_document(tmp_path, nodes=[m29_node("image_001", "image", [10, 10, 150, 80], metrics={"colorCount": 80, "textureScore": 0.4})])

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_art", "SALE", [24, 28, 72, 42])]),
        output_dir=tmp_path / "m29_2",
    )

    text = only_object(result, "preserve_raster_text")
    assert text["pixelOwner"] == "preserve_raster"
    assert text["replayDecision"] == "preserve_in_parent_raster"
    assert text["sourceEvidence"]["mediaContainmentRatio"] >= 0.98
    assert result["summary"]["mediaRegionCount"] == 1
    assert result["summary"]["preservedRasterTextCount"] == 1


def test_small_media_overlay_label_remains_editable_text(tmp_path: Path) -> None:
    source = make_textured_png(220, 140, [10, 10, 150, 80])
    m29 = m29_document(tmp_path, nodes=[m29_node("image_001", "image", [10, 10, 150, 80], metrics={"colorCount": 80, "textureScore": 0.4})])

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_badge", "1/9", [118, 66, 24, 14])]),
        output_dir=tmp_path / "m29_2",
    )

    text = only_object(result, "editable_ui_text")
    assert text["pixelOwner"] == "editable_text"
    assert text["replayDecision"] == "text_replay"
    assert text["sourceEvidence"]["mediaContainmentRatio"] >= 0.98


def test_adjacent_symbol_fragments_merge_into_one_raster_icon(tmp_path: Path) -> None:
    source = make_png(120, 80, fill=(250, 250, 250), marks=[([10, 20, 8, 8], (30, 30, 30)), ([23, 20, 8, 8], (30, 30, 30))])
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node("symbol_001", "symbol", [10, 20, 8, 8]),
            m29_node("symbol_002", "symbol", [23, 20, 8, 8]),
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([]),
        output_dir=tmp_path / "m29_2",
        options=M292SourcePhysicalOptions(icon_cluster_gap=6),
    )

    icon = only_object(result, "raster_icon")
    assert icon["bbox"] == [10, 20, 21, 8]
    assert icon["pixelOwner"] == "raster_icon"
    assert icon["replayDecision"] == "icon_replay"
    assert icon["sourceEvidence"]["m29NodeIds"] == ["symbol_001", "symbol_002"]
    assert result["summary"]["rasterIconCount"] == 1


def test_simple_shape_replays_but_complex_shape_is_diagnostic(tmp_path: Path) -> None:
    source = make_png(160, 100, fill=(248, 248, 248), marks=[([10, 10, 80, 20], (235, 235, 235)), ([110, 12, 22, 22], (60, 60, 120))])
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node("shape_bg", "shape", [10, 10, 80, 20], subtype="card_background", metrics={"colorCount": 1, "textureScore": 0.01}),
            m29_node("shape_blur", "shape", [110, 12, 22, 22], subtype="complex_blob", metrics={"colorCount": 48, "textureScore": 0.32}),
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([]),
        output_dir=tmp_path / "m29_2",
    )

    shape = only_object(result, "card_background")
    diagnostic = only_object(result, "shadow_or_blur")
    assert shape["pixelOwner"] == "shape_geometry"
    assert shape["replayDecision"] == "shape_replay"
    assert diagnostic["pixelOwner"] == "diagnostic_only"
    assert diagnostic["replayDecision"] == "skip"


def test_low_contrast_support_shape_replays_as_control_background(tmp_path: Path) -> None:
    source = make_png(160, 100, fill=(248, 248, 248), marks=[([20, 20, 100, 32], (238, 238, 238))])
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node("shape_support_001", "shape", [20, 20, 100, 32], subtype="low_contrast_support", metrics={"colorCount": 1, "textureScore": 0.02}),
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([]),
        output_dir=tmp_path / "m29_2",
    )

    shape = only_object(result, "control_background")
    assert shape["pixelOwner"] == "shape_geometry"
    assert shape["replayDecision"] == "shape_replay"
    assert shape["sourceEvidence"]["m29NodeIds"] == ["shape_support_001"]


def test_text_support_background_shape_replays_as_control_background(tmp_path: Path) -> None:
    source = make_png(160, 100, fill=(248, 248, 248), marks=[([30, 30, 84, 26], (255, 232, 235))])
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node("shape_text_support_001", "shape", [30, 30, 84, 26], subtype="text_support_background", metrics={"colorCount": 1, "textureScore": 0.02}),
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_tag", "tag", [42, 36, 60, 14])]),
        output_dir=tmp_path / "m29_2",
    )

    shape = only_object(result, "control_background")
    text = only_object(result, "editable_ui_text")
    assert shape["pixelOwner"] == "shape_geometry"
    assert shape["replayDecision"] == "shape_replay"
    assert shape["sourceEvidence"]["m29NodeIds"] == ["shape_text_support_001"]
    assert shape["sourceEvidence"]["textOverlapRatio"] > 0
    assert text["replayDecision"] == "text_replay"


def test_small_textured_circle_shape_replays_as_raster_icon_not_shape(tmp_path: Path) -> None:
    source = make_png(120, 90, fill=(248, 248, 248), marks=[([24, 24, 36, 36], (120, 80, 40))])
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node(
                "shape_avatar_like",
                "shape",
                [24, 24, 36, 36],
                subtype="badge_background",
                metrics={"colorCount": 112, "textureScore": 0.24, "edgeScore": 0.36, "fillRatio": 0.76},
            ),
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([]),
        output_dir=tmp_path / "m29_2",
    )

    icon = only_object(result, "raster_icon")
    assert icon["bbox"] == [24, 24, 36, 36]
    assert icon["pixelOwner"] == "raster_icon"
    assert icon["replayDecision"] == "icon_replay"
    assert "small_textured_foreground_shape" in icon["reasons"]
    assert not [item for item in result["sourceObjects"] if item["pixelOwner"] == "shape_geometry"]


def test_geometry_circle_fit_does_not_override_complex_foreground_ownership(tmp_path: Path) -> None:
    source = make_png(120, 90, fill=(248, 248, 248), marks=[([24, 24, 36, 36], (120, 80, 40))])
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node(
                "shape_circle_fit",
                "shape",
                [24, 24, 36, 36],
                subtype="small_ellipse",
                metrics={"colorCount": 96, "textureScore": 0.26, "edgeScore": 0.34, "fillRatio": 0.76},
                geometry={"kind": "circle", "confidence": "high", "params": {"radius": 18}, "metrics": {"fitError": 0.02}, "evidence": ["mask_fit"]},
            ),
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([]),
        output_dir=tmp_path / "m29_2",
    )

    icon = only_object(result, "raster_icon")
    assert icon["pixelOwner"] == "raster_icon"
    assert icon["replayDecision"] == "icon_replay"
    assert icon["sourceEvidence"]["m29NodeIds"] == ["shape_circle_fit"]
    assert "small_textured_foreground_shape" in icon["reasons"]
    assert not [item for item in result["sourceObjects"] if item["pixelOwner"] == "shape_geometry"]


def test_low_texture_badge_shape_still_replays_as_shape(tmp_path: Path) -> None:
    source = make_png(120, 90, fill=(248, 248, 248), marks=[([24, 24, 36, 20], (235, 235, 235))])
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node("shape_badge", "shape", [24, 24, 36, 20], subtype="badge_background", metrics={"colorCount": 2, "textureScore": 0.02, "edgeScore": 0.04}),
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([]),
        output_dir=tmp_path / "m29_2",
    )

    shape = only_object(result, "control_background")
    assert shape["pixelOwner"] == "shape_geometry"
    assert shape["replayDecision"] == "shape_replay"


def test_blocked_complex_small_foreground_recovers_as_raster_icon(tmp_path: Path) -> None:
    source = make_png(120, 90, fill=(248, 248, 248), marks=[([40, 28, 32, 32], (90, 40, 160))])
    m29 = m29_document(
        tmp_path,
        nodes=[],
        blocked=[
            {
                "id": "blocked_icon",
                "bbox": [40, 28, 32, 32],
                "source": "symbol_detector",
                "reasons": ["symbol_color_too_high", "symbol_texture_too_high", "symbol_edge_too_high", "weak_symbol_metrics"],
                "metrics": {"colorCount": 80, "textureScore": 0.32, "edgeScore": 0.42, "fillRatio": 0.70},
            }
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([]),
        output_dir=tmp_path / "m29_2",
    )

    icon = only_object(result, "raster_icon")
    assert icon["pixelOwner"] == "raster_icon"
    assert icon["replayDecision"] == "icon_replay"
    assert icon["sourceEvidence"]["blockedIds"] == ["blocked_icon"]


def test_blocked_complex_foreground_overlapping_ocr_stays_diagnostic(tmp_path: Path) -> None:
    source = make_png(120, 90, fill=(248, 248, 248), marks=[([40, 28, 32, 20], (20, 20, 20))])
    m29 = m29_document(
        tmp_path,
        nodes=[],
        blocked=[
            {
                "id": "blocked_text",
                "bbox": [40, 28, 32, 20],
                "source": "symbol_detector",
                "reasons": ["symbol_color_too_high", "weak_symbol_metrics"],
                "metrics": {"colorCount": 80, "textureScore": 0.32, "edgeScore": 0.42, "fillRatio": 0.70},
            }
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_text", "Text", [38, 26, 36, 24])]),
        output_dir=tmp_path / "m29_2",
    )

    diagnostic = only_object(result, "unknown")
    assert diagnostic["pixelOwner"] == "diagnostic_only"
    assert diagnostic["replayDecision"] == "skip"
    assert result["summary"]["rasterIconCount"] == 0


def test_symbol_inside_media_is_not_separately_replayed(tmp_path: Path) -> None:
    source = make_textured_png(180, 120, [20, 20, 110, 70])
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node("image_001", "image", [20, 20, 110, 70], metrics={"colorCount": 80, "textureScore": 0.4}),
            m29_node("symbol_inside", "symbol", [45, 40, 16, 16]),
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([]),
        output_dir=tmp_path / "m29_2",
    )

    assert result["summary"]["mediaRegionCount"] == 1
    assert result["summary"]["rasterIconCount"] == 0
    assert not [obj for obj in result["sourceObjects"] if obj["sourceEvidence"]["m29NodeIds"] == ["symbol_inside"]]


def test_large_image_like_unknown_becomes_preserved_media_region(tmp_path: Path) -> None:
    source = make_textured_png(240, 180, [20, 20, 170, 120])
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node(
                "unknown_chart_like",
                "unknown",
                [20, 20, 170, 120],
                subtype="image_like_low_confidence",
                metrics={"colorCount": 70, "textureScore": 0.24, "edgeScore": 0.33},
            ),
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([]),
        output_dir=tmp_path / "m29_2",
    )

    media = only_object(result, "media_region")
    assert media["pixelOwner"] == "preserve_raster"
    assert media["replayDecision"] == "image_replay"
    assert media["sourceEvidence"]["m29NodeIds"] == ["unknown_chart_like"]
    assert "large_image_like_region" in media["reasons"]
    assert "low_confidence_media_region" in media["risks"]


def test_high_iou_duplicate_keeps_higher_priority_candidate(tmp_path: Path) -> None:
    source = make_png(140, 100)
    m29 = m29_document(
        tmp_path,
        nodes=[
            m29_node("shape_001", "shape", [20, 20, 42, 18], subtype="card_background", metrics={"colorCount": 1, "textureScore": 0.01}),
        ],
    )

    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29,
        ocr_document=ocr_document([ocr_block("ocr_001", "Text", [20, 20, 42, 18])]),
        output_dir=tmp_path / "m29_2",
    )

    assert len(result["sourceObjects"]) == 1
    assert result["sourceObjects"][0]["visualKind"] == "editable_ui_text"
    assert result["sourceObjects"][0]["replayDecision"] == "text_replay"


def test_report_files_and_overlay_are_written(tmp_path: Path) -> None:
    source = make_png(80, 60)
    result = extract_source_ui_physical_graph(
        source_png=png_bytes(source),
        m29_document=m29_document(tmp_path, nodes=[]),
        ocr_document=ocr_document([]),
        output_dir=tmp_path / "m29_2",
    )

    assert result["schemaName"] == "M292SourceUiPhysicalGraph"
    assert result["summary"]["dslChanged"] is False
    assert result["summary"]["assetChanged"] is False
    assert (tmp_path / "m29_2" / "source_ui_physical_graph.json").exists()
    assert read_png_metadata((tmp_path / "m29_2" / "source_ui_physical_graph_overlay.png").read_bytes()) is not None


def only_object(result: dict, visual_kind: str) -> dict:
    matches = [item for item in result["sourceObjects"] if item["visualKind"] == visual_kind]
    assert len(matches) == 1
    return matches[0]


def make_png(width: int, height: int, *, fill: tuple[int, int, int] = (250, 250, 250), marks: list[tuple[list[int], tuple[int, int, int]]] | None = None) -> PngPixels:
    rows = [bytearray(bytes(fill) * width) for _ in range(height)]
    for bbox, color in marks or []:
        x, y, w, h = bbox
        for row_index in range(y, y + h):
            for column in range(x, x + w):
                rows[row_index][column * 3 : column * 3 + 3] = bytes(color)
    return PngPixels(width=width, height=height, rows=[bytes(row) for row in rows])


def make_textured_png(width: int, height: int, media_bbox: list[int]) -> PngPixels:
    rows = [bytearray(bytes((248, 248, 248)) * width) for _ in range(height)]
    x, y, w, h = media_bbox
    for row_index in range(y, y + h):
        for column in range(x, x + w):
            rgb = ((column * 5 + row_index * 3) % 255, (column * 7) % 255, (row_index * 9) % 255)
            rows[row_index][column * 3 : column * 3 + 3] = bytes(rgb)
    return PngPixels(width=width, height=height, rows=[bytes(row) for row in rows])


def png_bytes(pixels: PngPixels) -> bytes:
    return encode_rgb_png(pixels.width, pixels.height, pixels.rows)


def m29_document(tmp_path: Path, *, nodes: list[dict], blocked: list[dict] | None = None) -> dict:
    return {
        "version": "0.1",
        "sourceImage": str(tmp_path / "source.png"),
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
    subtype: str | None = None,
    metrics: dict | None = None,
    geometry: dict | None = None,
) -> dict:
    node = {
        "id": node_id,
        "type": node_type,
        "subtype": subtype or ("separator" if node_type == "shape" else "icon_candidate"),
        "bbox": bbox,
        "confidence": 0.9,
        "source": f"{node_type}_detector",
        "sourceOrder": 0,
        "layerHint": "content",
        "reasons": ["test"],
        "metrics": {
            "colorCount": (metrics or {}).get("colorCount", 1),
            "textureScore": (metrics or {}).get("textureScore", 0.01),
            "edgeScore": (metrics or {}).get("edgeScore", 0),
            "fillRatio": (metrics or {}).get("fillRatio", 1),
            "aspectRatio": bbox[2] / bbox[3],
            "brightness": (metrics or {}).get("brightness", 200),
            "meanRgb": (metrics or {}).get("meanRgb", [0, 0, 0]),
        },
    }
    if geometry is not None:
        node["geometry"] = geometry
    return node


def ocr_document(blocks: list[dict]) -> dict:
    return {"version": "0.1", "taskId": "test", "provider": "test", "model": None, "imageSize": {"width": 80, "height": 60}, "coordinateSpace": "pixel", "blocks": blocks, "warnings": []}


def ocr_block(block_id: str, text: str, bbox: list[int], *, confidence: float = 0.95) -> dict:
    return {"id": block_id, "text": text, "bbox": bbox, "confidence": confidence, "lineId": block_id, "blockId": block_id, "source": "test"}
