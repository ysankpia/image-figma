from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.png_tools import PngPixels, encode_rgb_png, read_png_metadata
from app.reconstruction_ui_tree import extract_m31_reconstruction_ui_tree, find_m31_forbidden_terms


def test_m31_builds_root_primitive_refs_units_and_fallbacks(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(160, 120))
    ocr = ocr_document()
    m29 = m29_document()
    before = copy.deepcopy(m29)
    result = run_m31(tmp_path, source, ocr, m29)

    tree = result.tree
    report = result.report
    assert tree["schemaName"] == "M31ReconstructionUiTree"
    assert tree["root"]["bbox"] == [0, 0, 160, 120]
    assert len(tree["primitiveRefs"]) == len(m29["nodes"]) + 1
    assert report["summary"]["m29NodeCount"] == len(m29["nodes"])
    assert report["summary"]["primitiveRefCount"] == len(m29["nodes"]) + 1
    assert report["summary"]["ownedPrimitiveCount"] == len(m29["nodes"]) + 1
    assert report["summary"]["orphanPrimitiveCount"] == 0
    assert report["summary"]["rootLeafPrimitiveCount"] == 0
    assert report["summary"]["unitFallbackCoverage"] == 1.0
    assert report["summary"]["createdDetectionBBoxCount"] == 0
    assert report["summary"]["permissionViolationCount"] == 0
    assert m29 == before

    for unit in units(tree):
        fallback = unit["fallback"]
        assert fallback["cropBBox"] == unit["bbox"]
        asset = next(item for item in tree["assets"] if item["id"] == fallback["assetId"])
        metadata = read_png_metadata((result.output_dir / asset["path"]).read_bytes())
        assert metadata is not None
        assert metadata.width == unit["bbox"][2]
        assert metadata.height == unit["bbox"][3]


def test_container_like_shape_owns_inner_primitives(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(160, 120))
    result = run_m31(tmp_path, source, ocr_document(), m29_document())

    container_unit = next(unit for unit in units(result.tree) if unit["unitKind"] == "container_backed_unit")
    assert container_unit["visualKind"] == "card_like"
    assert container_unit["bboxDerivation"] == "container_from_m29_shape"
    assert set(container_unit["sourceRefs"]["m29NodeIds"]) == {"shape_card", "text_title", "image_thumb"}


def test_unmatched_ocr_box_becomes_text_primitive_ref(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(160, 120))
    result = run_m31(tmp_path, source, ocr_document(), m29_document())

    ocr_ref = next(ref for ref in result.tree["primitiveRefs"] if ref["sourceKind"] == "ocr_text_box")
    assert ocr_ref["sourceId"] == "ocr_label"
    assert ocr_ref["primitiveType"] == "text"
    assert ocr_ref["sourceRefs"]["ocrTextBoxId"] == "ocr_label"
    assert ocr_ref["ownerUnitId"] is not None


def test_row_aligned_primitives_become_media_text_unit(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(160, 120))
    result = run_m31(tmp_path, source, ocr_document(), m29_document(include_container=False, include_repeated=False))

    media_unit = next(unit for unit in units(result.tree) if unit["visualKind"] == "media_text_block")
    assert media_unit["unitKind"] == "media_text_unit"
    assert media_unit["bboxDerivation"] == "row_cluster_from_alignment"
    assert set(media_unit["sourceRefs"]["m29NodeIds"]) == {"text_title", "image_thumb"}


def test_same_size_spacing_units_become_repeated_group(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(160, 120))
    result = run_m31(tmp_path, source, ocr_document(), m29_document())

    repeated = [node for node in result.tree["nodes"] if node["kind"] == "repeated_group"]
    assert len(repeated) == 1
    assert repeated[0]["visualKind"] == "matrix"
    assert len(repeated[0]["children"]) == 3
    assert result.report["summary"]["repeatedGroupCount"] == 1


def test_out_of_bounds_primitive_goes_to_review_bucket(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(160, 120))
    m29 = m29_document()
    m29["nodes"].append(m29_node("shape_bad", "shape", [150, 112, 40, 20], subtype="separator", layer_hint="content"))

    result = run_m31(tmp_path, source, ocr_document(), m29)

    assert result.report["summary"]["reviewBucketCount"] == 1
    assert result.report["summary"]["orphanPrimitiveCount"] == 0
    assert result.tree["reviewBuckets"][0]["reason"] == "out_of_bounds"
    bad_ref = next(ref for ref in result.tree["primitiveRefs"] if ref["sourceId"] == "shape_bad")
    assert bad_ref["ownerUnitId"] is None
    assert bad_ref["reviewBucketId"] == result.tree["reviewBuckets"][0]["id"]


def test_forbidden_terms_are_absent_from_tree_and_report(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(160, 120))
    result = run_m31(tmp_path, source, ocr_document(), m29_document())

    serialized = json.dumps({"tree": result.tree, "report": result.report}, ensure_ascii=False).lower()
    for term in [
        "bottom_nav",
        "tab",
        "toolbar",
        "ecommerce",
        "education",
        "wallet",
        "coupon",
        "merchant",
        "product",
        "course",
        "recoverable_icon",
        "promotable_icon",
        "icon_recovery",
        "restore",
    ]:
        assert term not in find_m31_forbidden_terms(serialized)
    assert result.report["summary"]["forbiddenHitCount"] == 0


def test_development_profile_writes_overlay_and_production_skips_it(tmp_path: Path) -> None:
    source = write_png(tmp_path / "source.png", make_canvas(160, 120))
    dev = run_m31(tmp_path / "dev", source, ocr_document(), m29_document(), profile="development")
    prod = run_m31(tmp_path / "prod", source, ocr_document(), m29_document(), profile="production")

    assert (dev.output_dir / "m31_reconstruction_tree_overlay.png").exists()
    assert not (prod.output_dir / "m31_reconstruction_tree_overlay.png").exists()


def test_invalid_review_reason_is_rejected(tmp_path: Path) -> None:
    from app.reconstruction_ui_tree import add_review_bucket

    with pytest.raises(ValueError, match="not allowed"):
        add_review_bucket(dummy_context(tmp_path), "bad_reason", [])


def run_m31(tmp_path: Path, source: Path, ocr: dict, m29: dict, *, profile: str = "development"):
    output_dir = tmp_path / "m31"
    ocr_json = tmp_path / "ocr.json"
    m29_json = tmp_path / "nodes.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    ocr_json.parent.mkdir(parents=True, exist_ok=True)
    ocr_json.write_text(json.dumps(ocr, ensure_ascii=False, indent=2), encoding="utf-8")
    m29_json.write_text(json.dumps(m29, ensure_ascii=False, indent=2), encoding="utf-8")
    return extract_m31_reconstruction_ui_tree(
        source_image_path=str(source),
        ocr_document=ocr,
        ocr_json_path=str(ocr_json),
        m29_document=m29,
        m29_nodes_json_path=str(m29_json),
        output_dir=output_dir,
        profile=profile,
    )


def units(tree: dict) -> list[dict]:
    return [node for node in tree["nodes"] if node.get("kind") == "reconstruction_unit"]


def ocr_document() -> dict:
    return {
        "version": "0.1",
        "taskId": "task_test",
        "provider": "fake",
        "model": None,
        "imageSize": {"width": 160, "height": 120},
        "coordinateSpace": "pixel",
        "blocks": [
            {"id": "ocr_title", "text": "Title", "bbox": [20, 20, 42, 12], "confidence": 0.95, "lineId": "line_1", "blockId": "block_1"},
            {"id": "ocr_label", "text": "Label", "bbox": [18, 90, 24, 10], "confidence": 0.92, "lineId": "line_2", "blockId": "block_2"},
        ],
        "warnings": [],
        "meta": {},
        "status": "completed",
        "error": None,
    }


def m29_document(*, include_container: bool = True, include_repeated: bool = True) -> dict:
    nodes = [
        m29_node("text_title", "text", [20, 20, 42, 12], subtype="line", layer_hint="content", text="Title"),
        m29_node("image_thumb", "image", [70, 16, 34, 26], subtype="raster", layer_hint="content"),
    ]
    relations = []
    if include_container:
        nodes.insert(0, m29_node("shape_card", "shape", [12, 10, 108, 44], subtype="card_background", layer_hint="container"))
        relations = [
            {"parentId": "shape_card", "childId": "text_title", "type": "contains", "confidence": 0.96, "reasons": ["contained_bbox"]},
            {"parentId": "shape_card", "childId": "image_thumb", "type": "contains", "confidence": 0.96, "reasons": ["contained_bbox"]},
        ]
    if include_repeated:
        nodes.extend(
            [
                m29_node("symbol_a", "symbol", [20, 78, 12, 12], subtype="compact", layer_hint="content"),
                m29_node("symbol_b", "symbol", [52, 78, 12, 12], subtype="compact", layer_hint="content"),
                m29_node("symbol_c", "symbol", [84, 78, 12, 12], subtype="compact", layer_hint="content"),
            ]
        )
    return {
        "version": "0.1",
        "sourceImage": "source.png",
        "imageSize": {"width": 160, "height": 120},
        "nodes": nodes,
        "relations": relations,
        "blocked": [],
        "debug": {},
        "warnings": [],
        "meta": {"counts": {}},
    }


def m29_node(
    node_id: str,
    node_type: str,
    bbox: list[int],
    *,
    subtype: str,
    layer_hint: str,
    text: str | None = None,
) -> dict:
    index = sum(ord(char) for char in node_id)
    node = {
        "id": node_id,
        "type": node_type,
        "subtype": subtype,
        "bbox": bbox,
        "confidence": 0.9,
        "source": "test",
        "sourceOrder": index,
        "layerHint": layer_hint,
        "reasons": ["test_fixture"],
        "metrics": {
            "colorCount": 1,
            "textureScore": 0.0,
            "edgeScore": 0.0,
            "fillRatio": 1.0,
            "aspectRatio": bbox[2] / bbox[3],
            "brightness": 240,
            "meanRgb": [240, 240, 240],
        },
    }
    if text is not None:
        node["text"] = text
    return node


def write_png(path: Path, pixels: PngPixels) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_rgb_png(pixels.width, pixels.height, pixels.rows))
    return path


def make_canvas(width: int, height: int, fill: tuple[int, int, int] = (250, 250, 250)) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])


def dummy_context(tmp_path: Path):
    from app.reconstruction_ui_tree import TreeBuildContext

    pixels = make_canvas(8, 8)
    return TreeBuildContext(
        source_png=encode_rgb_png(8, 8, pixels.rows),
        pixels=pixels,
        output_dir=tmp_path,
        primitive_refs=[],
        source_nodes=[],
        relations=[],
        warnings=[],
    )
