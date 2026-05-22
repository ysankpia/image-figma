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


def m29_node(node_id: str, node_type: str, bbox: list[int], *, asset_path: str | None = None, style: dict | None = None) -> dict:
    data = {
        "id": node_id,
        "type": node_type,
        "subtype": "separator" if node_type == "shape" else "icon_candidate",
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
    return data


def ocr_document(blocks: list[dict]) -> dict:
    return {"version": "0.1", "taskId": "test", "provider": "test", "model": None, "imageSize": {"width": 80, "height": 60}, "coordinateSpace": "pixel", "blocks": blocks, "warnings": []}


def ocr_block(block_id: str, text: str, bbox: list[int]) -> dict:
    return {"id": block_id, "text": text, "bbox": bbox, "confidence": 0.95, "lineId": block_id, "blockId": block_id, "source": "test"}


def count_children(dsl: dict, role: str) -> int:
    return sum(1 for child in dsl["root"]["children"] if child.get("role") == role)
