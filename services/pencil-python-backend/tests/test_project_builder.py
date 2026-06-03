from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageDraw

from app.config import Settings
from app.exporter.single_page import SinglePageExportOptions, export_single_page
from app.hybrid_boundary import build_hybrid_boundary_artifact
from app.jsonio import read_json
from app.psdlike_adapter import adapt_psdlike_to_pencil_evidence
from app.project_builder import export_project, file_sha256
from app.types import ExportRequest, PageInput


def test_project_builder_exports_three_mode_project_zip(tmp_path: Path) -> None:
    fake_m29extract = write_fake_m29extract(tmp_path)
    image_a = write_image(tmp_path / "a.png", (90, 60), "#1f2937")
    image_b = write_image(tmp_path / "b.png", (80, 100), "#ffffff")
    out_dir = tmp_path / "out"

    manifest = export_project(
        ExportRequest(
            inputs=[
                PageInput(id="a", path=image_a, original_name="a.png"),
                PageInput(id="b", path=image_b, original_name="b.png"),
            ],
            out_dir=out_dir,
            project_name="Unit Project",
            mode="all",
            columns="2",
            include_debug=True,
            ocr_provider="none",
        ),
        settings=Settings(
            addr="127.0.0.1:0",
            storage_root=tmp_path / "storage",
            m29extract_path=fake_m29extract,
            psdlike_root=tmp_path / "psdlike",
            psdlike_tile_size=8,
            max_upload_bytes=1024 * 1024,
            max_files=20,
            max_workers=1,
            cors_allow_origins=["*"],
            ocr_provider="none",
        ),
    )

    assert manifest["pageCount"] == 2
    assert manifest["modes"] == ["clean-editable", "visual-fidelity", "visual-ocr"]
    assert (out_dir / "project.zip").exists()
    for mode in manifest["modes"]:
        design = read_json(out_dir / mode / "design.pen")
        assert len(design["children"]) == 2
        ids = collect_ids(design["children"])
        assert len(ids) == len(set(ids))
        serialized = json.dumps(design)
        assert "source.png" not in serialized
        assert "raw-crops" not in serialized
        assert "masks/" not in serialized
        assert "./assets/visible/page_0001/" in serialized
        for node in collect_nodes(design["children"]):
            assert "strokeWidth" not in node
            stroke = node.get("stroke")
            if stroke is not None:
                assert isinstance(stroke, dict)
                assert "fill" in stroke
                assert "thickness" in stroke
        image_fills = collect_image_fills(design["children"])
        image_urls = [fill["url"] for fill in image_fills]
        for fill in image_fills:
            url = fill["url"]
            assert fill["enabled"] is True
            assert url.startswith("./assets/visible/")
            assert not url.startswith("../")
            assert "/../" not in url
            assert not Path(url).is_absolute()
            assert (out_dir / mode / url.removeprefix("./")).exists()
        image_basenames = [Path(url).name for url in image_urls]
        assert len(image_basenames) == len(set(image_basenames))
        assert all(name.startswith((f"{mode}__page_0001__", f"{mode}__page_0002__")) for name in image_basenames)
        mode_manifest = read_json(out_dir / mode / "manifest.json")
        asset_urls = [item["url"] for item in mode_manifest["assets"]]
        asset_basenames = [Path(url).name for url in asset_urls]
        assert len(asset_basenames) == len(set(asset_basenames))
        assert all(name.startswith((f"{mode}__page_0001__", f"{mode}__page_0002__")) for name in asset_basenames)

    all_project_basenames: list[str] = []
    for mode in manifest["modes"]:
        design = read_json(out_dir / mode / "design.pen")
        all_project_basenames.extend(Path(url).name for url in collect_image_urls(design["children"]))
    assert len(all_project_basenames) == len(set(all_project_basenames))

    visual_ocr_manifest = read_json(out_dir / "work" / "page_0001" / "single_page_export" / "visual-ocr" / "manifest.json")
    assert visual_ocr_manifest["visibleOcrText"] is True
    assert visual_ocr_manifest["cropTextRegions"] is False
    assert visual_ocr_manifest["textNodes"] == 1
    assert visual_ocr_manifest["cropTextNodes"] == 0
    assert visual_ocr_manifest["textKnockoutCropNodes"] >= 1
    assert {item["decision"] for item in visual_ocr_manifest["textDecisions"]} == {"editable_text"}
    visual_ocr_design = read_json(out_dir / "visual-ocr" / "design.pen")
    text_node = next(node for node in collect_nodes(visual_ocr_design["children"]) if node.get("type") == "text")
    text_metadata = text_node["metadata"]
    original_bbox = text_metadata["originalBBox"]
    safe_bbox = text_metadata["safeBBox"]
    assert text_metadata["safeBoundsPolicy"] == "pencil_text_safe_bounds.v1"
    assert text_node["x"] == original_bbox["x"]
    assert text_node["width"] > original_bbox["width"]
    assert text_node["height"] > original_bbox["height"]
    assert text_node["width"] == safe_bbox["width"]
    assert text_node["height"] == safe_bbox["height"]

    visual_fidelity_manifest = read_json(out_dir / "work" / "page_0001" / "single_page_export" / "visual-fidelity" / "manifest.json")
    assert visual_fidelity_manifest["visibleOcrText"] is False
    assert visual_fidelity_manifest["cropTextRegions"] is True
    assert visual_fidelity_manifest["textNodes"] == 0
    assert visual_fidelity_manifest["cropTextNodes"] == 1
    assert visual_fidelity_manifest["textKnockoutCropNodes"] == 0

    with ZipFile(out_dir / "project.zip") as archive:
        names = set(archive.namelist())
    assert "manifest.json" in names
    assert "clean-editable/design.pen" in names
    assert "visual-fidelity/design.pen" in names
    assert "visual-ocr/design.pen" in names
    assert "debug/report.md" in names


def test_project_builder_reuses_existing_psdlike_batch_artifact(tmp_path: Path) -> None:
    image = write_image(tmp_path / "screen.png", (120, 80), "#f5f7fb")
    psdlike_root = tmp_path / "psdlike_batch"
    case_dir = write_fake_psdlike_output(psdlike_root / "case_0001_cached")
    input_manifest = {
        "version": "psdlike_python_service_input_manifest.v1",
        "cases": [
            {
                "caseId": "case_0001_cached",
                "sourcePath": str(image),
                "sha256": file_sha256(image),
            }
        ],
    }
    (psdlike_root / "input_manifest.v1.json").write_text(json.dumps(input_manifest), encoding="utf-8")
    out_dir = tmp_path / "out"

    manifest = export_project(
        ExportRequest(
            inputs=[PageInput(id="page_0001", path=image, original_name=image.name)],
            out_dir=out_dir,
            project_name="Reuse PSD-like",
            mode="visual-ocr",
            columns="1",
            include_debug=True,
            ocr_provider="none",
            boundary_source="psdlike",
            psdlike_artifacts_root=psdlike_root,
        ),
        settings=Settings(
            addr="127.0.0.1:0",
            storage_root=tmp_path / "storage",
            m29extract_path=None,
            psdlike_root=tmp_path / "missing_psdlike_runner",
            psdlike_tile_size=8,
            max_upload_bytes=1024 * 1024,
            max_files=20,
            max_workers=1,
            cors_allow_origins=["*"],
            ocr_provider="none",
        ),
    )

    assert manifest["boundarySource"] == "psdlike"
    assert manifest["psdlikeArtifactsRoot"] == str(psdlike_root)
    assert (out_dir / "project.zip").exists()
    assert (out_dir / "work" / "page_0001" / "psdlike" / "layer_stack.v1.json").exists()
    assert read_json(out_dir / "work" / "page_0001" / "psdlike" / "layer_stack.v1.json") == read_json(case_dir / "layer_stack.v1.json")
    design = read_json(out_dir / "visual-ocr" / "design.pen")
    assert any(node.get("type") == "text" and node.get("content") == "测试" for node in collect_nodes(design["children"]))


def test_psdlike_adapter_exports_shapes_as_editable_and_rasters_as_assets(tmp_path: Path) -> None:
    psdlike_dir = write_fake_psdlike_output(tmp_path / "psdlike")
    evidence_dir = tmp_path / "evidence"
    adapt_psdlike_to_pencil_evidence(psdlike_dir, evidence_dir)

    evidence = read_json(evidence_dir / "m29_physical_evidence.v1.json")
    replay = read_json(evidence_dir / "m29-pencil-replay.v1.json")
    assert evidence["diagnostics"]["boundarySource"] == "psdlike"
    assert {item["primitiveType"] for item in evidence["primitives"]} == {"image_region", "surface_region", "text_region"}
    assert any(item.get("editableMode") == "shape" for item in replay["layers"])

    export_dir = tmp_path / "single"
    export_single_page(
        SinglePageExportOptions(
            input_dir=evidence_dir,
            out=export_dir,
            name="PSD-like Unit",
            mode="all",
            include_debug_pen=True,
        )
    )
    clean_manifest = read_json(export_dir / "production" / "manifest.json")
    visual_manifest = read_json(export_dir / "visual-fidelity" / "manifest.json")
    assert clean_manifest["shapeNodes"] == 1
    assert clean_manifest["textNodes"] == 1
    assert clean_manifest["cropNodes"] == 1
    assert visual_manifest["cropTextNodes"] == 1
    clean_design = read_json(export_dir / "production" / "design.pen")
    serialized = json.dumps(clean_design)
    assert "source.png" not in serialized
    assert "raw-crops" not in serialized
    assert "masks/" not in serialized
    shape_node = next(
        node
        for node in collect_nodes(clean_design["children"])
        if (node.get("metadata") or {}).get("type") == "psdlike_editable_shape"
    )
    assert shape_node["stroke"] == {"align": "inside", "thickness": 1, "fill": "#e5e7eb"}
    assert "strokeWidth" not in shape_node


def test_single_page_empty_transparent_evidence_falls_back_to_source_raster(tmp_path: Path) -> None:
    evidence_dir = write_empty_transparent_evidence(tmp_path / "transparent")
    export_dir = tmp_path / "single"

    export_single_page(
        SinglePageExportOptions(
            input_dir=evidence_dir,
            out=export_dir,
            name="Transparent Unit",
            mode="all",
            include_debug_pen=True,
        )
    )

    for mode_dir in ("production", "visual-fidelity", "visual-ocr"):
        manifest = read_json(export_dir / mode_dir / "manifest.json")
        design = read_json(export_dir / mode_dir / "design.pen")
        frame = design["children"][0]
        assert frame["fill"] == "#FFFFFF"
        assert frame["metadata"]["sourceFallback"] is True
        assert manifest["sourceFallbackNodes"] == 1
        assert manifest["cropNodes"] == 1
        assert len(manifest["assets"]) == 1
        assert manifest["assets"][0]["visibleAssetSource"] == "source_full_raster"
        assert manifest["assets"][0]["sourceHasAlpha"] is True
        assert "source.png" not in json.dumps(design)

        nodes = collect_nodes(design["children"])
        image_node = next(node for node in nodes if (node.get("metadata") or {}).get("visibleAssetSource") == "source_full_raster")
        fill = image_node["fill"]
        assert fill["enabled"] is True
        assert fill["url"] == "./assets/visible/source_full.png"
        asset_path = export_dir / mode_dir / fill["url"].removeprefix("./")
        assert asset_path.exists()
        with Image.open(asset_path) as image:
            assert image.mode == "RGBA"
            assert image.size == (28, 28)
            assert image.getchannel("A").getextrema()[0] < 255


def test_visual_text_inside_local_raster_stays_raster_owned(tmp_path: Path) -> None:
    evidence_dir = write_fake_visual_text_evidence(tmp_path / "visual_text")
    export_dir = tmp_path / "single"

    export_single_page(
        SinglePageExportOptions(
            input_dir=evidence_dir,
            out=export_dir,
            name="Visual Text Unit",
            mode="all",
            include_debug_pen=True,
        )
    )

    for mode_dir in ("production", "visual-ocr"):
        manifest = read_json(export_dir / mode_dir / "manifest.json")
        design = read_json(export_dir / mode_dir / "design.pen")
        decisions = {item["primitiveId"]: item for item in manifest["textDecisions"]}

        assert decisions["prim_price"]["decision"] == "crop"
        assert decisions["prim_price"]["reason"] == "text_inside_raster_owner"
        assert decisions["prim_price"]["ownerPrimitiveId"] == "prim_media"
        assert decisions["prim_digit"]["decision"] == "crop"
        assert decisions["prim_digit"]["reason"] == "promo_text_cluster_preserved_as_raster"
        assert decisions["prim_digit"]["clusterId"] == decisions["prim_discount"]["clusterId"]
        assert decisions["prim_coupon"]["clusterId"] == decisions["prim_discount"]["clusterId"]
        assert manifest["visualTextCropNodes"] == 4
        assert manifest["textNodes"] == 0
        assert manifest["textKnockoutCropNodes"] == 0
        assert "¥518.5" not in json.dumps(design, ensure_ascii=False)
        assert "\"9\"" not in json.dumps(design, ensure_ascii=False)

    visual_fidelity_manifest = read_json(export_dir / "visual-fidelity" / "manifest.json")
    assert visual_fidelity_manifest["textNodes"] == 0
    assert visual_fidelity_manifest["cropTextNodes"] == 4


def test_psdlike_adapter_rasterizes_small_mask_required_shapes(tmp_path: Path) -> None:
    psdlike_dir = write_fake_small_shape_output(tmp_path / "small_shape")
    evidence_dir = tmp_path / "evidence"
    adapt_psdlike_to_pencil_evidence(psdlike_dir, evidence_dir)

    evidence = read_json(evidence_dir / "m29_physical_evidence.v1.json")
    replay = read_json(evidence_dir / "m29-pencil-replay.v1.json")
    small_shape = next(item for item in evidence["primitives"] if item["source"].get("sourceLayerId") == "shape_icon")
    small_replay = next(item for item in replay["layers"] if item.get("sourceLayerId") == "shape_icon")
    assert small_shape["primitiveType"] == "image_region"
    assert small_shape["compileHints"]["shapeFallbackMode"] == "source_raster_crop"
    assert small_replay["editableMode"] == "raster_crop"

    export_dir = tmp_path / "single"
    export_single_page(
        SinglePageExportOptions(
            input_dir=evidence_dir,
            out=export_dir,
            name="Small Shape Unit",
            mode="all",
            include_debug_pen=True,
        )
    )
    clean_manifest = read_json(export_dir / "production" / "manifest.json")
    assert clean_manifest["shapeNodes"] == 1
    assert clean_manifest["cropNodes"] == 1


def test_psdlike_adapter_repairs_truncated_local_raster_from_source(tmp_path: Path) -> None:
    psdlike_dir = write_fake_truncated_raster_output(tmp_path / "truncated_raster")
    evidence_dir = tmp_path / "evidence"
    adapt_psdlike_to_pencil_evidence(psdlike_dir, evidence_dir)

    evidence = read_json(evidence_dir / "m29_physical_evidence.v1.json")
    raster = next(item for item in evidence["primitives"] if item["source"].get("sourceLayerId") == "raster_icon")
    assert raster["bbox"]["x"] <= 68
    assert raster["bbox"]["y"] <= 48
    assert raster["bbox"]["width"] >= 60
    assert raster["bbox"]["height"] >= 60
    repair = raster["compileHints"]["rasterBoundaryRepair"]
    assert repair["policy"] == "source_connected_component.v1"
    assert repair["originalBBox"] == {"x": 70, "y": 78, "width": 60, "height": 36}
    assert repair["repairedBBox"] == raster["bbox"]
    crop = Image.open(evidence_dir / raster["cropRef"])
    assert crop.size == (raster["bbox"]["width"], raster["bbox"]["height"])


def test_hybrid_boundary_adds_low_coverage_m29_fallback_below_text(tmp_path: Path) -> None:
    psdlike_dir = write_fake_psdlike_text_only_output(tmp_path / "psdlike_text_only")
    m29_dir = write_fake_hybrid_m29_output(tmp_path / "m29", psdlike_dir / "source.png")
    hybrid_dir = tmp_path / "hybrid"

    build_hybrid_boundary_artifact(psdlike_dir=psdlike_dir, m29_dir=m29_dir, output_dir=hybrid_dir)

    layer_stack = read_json(hybrid_dir / "layer_stack.v1.json")
    fallback_layers = [item for item in layer_stack["layers"] if item.get("source") == "hybrid_boundary"]
    assert layer_stack["diagnostics"]["boundarySource"] == "hybrid"
    assert layer_stack["diagnostics"]["hybridFallbackLayerCount"] == 1
    assert len(fallback_layers) == 1
    assert fallback_layers[0]["reason"] == "m29_low_coverage_fallback_object"
    assert fallback_layers[0]["sourcePrimitiveIds"] == ["prim_pill"]
    assert fallback_layers[0]["z"] < min(item["z"] for item in layer_stack["layers"] if item.get("type") == "text")
    assert (hybrid_dir / fallback_layers[0]["asset"]).exists()
    assert (hybrid_dir / "hybrid_boundary_report.v1.json").exists()

    evidence_dir = tmp_path / "hybrid_evidence"
    adapt_psdlike_to_pencil_evidence(hybrid_dir, evidence_dir)
    evidence = read_json(evidence_dir / "m29_physical_evidence.v1.json")
    replay = read_json(evidence_dir / "m29-pencil-replay.v1.json")
    assert evidence["diagnostics"]["boundarySource"] == "hybrid"
    assert evidence["diagnostics"]["hybridFallbackLayerCount"] == 1
    assert replay["summary"]["boundarySource"] == "hybrid"
    assert any(item["source"]["sourceLayerId"] == "hybrid_m29_0001" for item in evidence["primitives"])


def write_image(path: Path, size: tuple[int, int], color: str) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def write_fake_m29extract(tmp_path: Path) -> Path:
    script = tmp_path / "fake_m29extract.py"
    script.write_text(
        """#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw

args = sys.argv[1:]
input_path = Path(args[args.index("-input") + 1])
out_dir = Path(args[args.index("-out") + 1])
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "crops").mkdir(exist_ok=True)
(out_dir / "masks").mkdir(exist_ok=True)
image = Image.open(input_path).convert("RGB")
w, h = image.size
image.save(out_dir / "source.png")
image.crop((0, 0, w, h)).save(out_dir / "crops" / "prim_0001.png")
Image.new("L", (w, h), 255).save(out_dir / "masks" / "prim_0001.png")
text_bbox = {"x": 8, "y": 8, "width": max(10, min(42, w - 8)), "height": max(10, min(18, h - 8))}
image.crop((text_bbox["x"], text_bbox["y"], text_bbox["x"] + text_bbox["width"], text_bbox["y"] + text_bbox["height"])).save(out_dir / "crops" / "prim_0002.png")
text_mask = Image.new("L", (w, h), 0)
ImageDraw.Draw(text_mask).rectangle(
    (
        text_bbox["x"],
        text_bbox["y"],
        text_bbox["x"] + text_bbox["width"] - 1,
        text_bbox["y"] + text_bbox["height"] - 1,
    ),
    fill=255,
)
text_mask.save(out_dir / "masks" / "prim_0002.png")
doc = {
  "schemaName": "M29PhysicalEvidence",
  "version": "1.0",
  "generator": {"name": "fake", "mode": "test"},
  "image": {"width": w, "height": h, "sourcePath": str(input_path)},
  "ocr": {"provided": True, "blockCount": 1},
  "primitives": [
    {"id": "prim_0001", "primitiveType": "image_region", "bbox": {"x": 0, "y": 0, "width": w, "height": h}, "maskRef": "masks/prim_0001.png", "cropRef": "crops/prim_0001.png", "source": {"kind": "pixel"}, "measurements": {}, "compileHints": {}},
    {"id": "prim_0002", "primitiveType": "text_region", "bbox": text_bbox, "maskRef": "masks/prim_0002.png", "cropRef": "crops/prim_0002.png", "source": {"kind": "ocr", "ocrBlockId": "ocr_1", "text": "测试"}, "measurements": {}, "compileHints": {}}
  ],
  "physicalRelations": [],
  "assets": [],
  "diagnostics": {"backgroundColor": "#FFFFFF"}
}
(out_dir / "m29_physical_evidence.v1.json").write_text(json.dumps(doc), encoding="utf-8")
print("fake m29extract wrote", out_dir)
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def write_fake_psdlike_output(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    assets = path / "assets"
    assets.mkdir()
    image = Image.new("RGB", (120, 80), "#f5f7fb")
    ImageDraw.Draw(image).rectangle((10, 12, 38, 40), fill="#2563eb")
    ImageDraw.Draw(image).text((50, 28), "测试", fill="#111111")
    image.save(path / "source.png")
    image.crop((10, 12, 38, 40)).save(assets / "raster_0001.png")
    layer_stack = {
        "version": "layer_stack.v1",
        "sourceImage": str(path / "source.png"),
        "canvas": {"width": 120, "height": 80},
        "pageBackground": "#f5f7fb",
        "layers": [
            {
                "id": "shape_0001",
                "type": "shape",
                "bbox": {"x": 0, "y": 0, "width": 120, "height": 80},
                "z": 100,
                "style": {"fill": "#f5f7fb", "stroke": {"color": "#e5e7eb", "width": 1}},
                "scores": {},
                "reason": "background_surface_band",
            },
            {
                "id": "raster_0001",
                "type": "raster",
                "bbox": {"x": 10, "y": 12, "width": 28, "height": 28},
                "z": 200,
                "asset": "assets/raster_0001.png",
                "scores": {},
                "ownership": {},
                "reason": "foreground_object_on_surface",
            },
            {
                "id": "text_0001",
                "type": "text",
                "bbox": {"x": 48, "y": 24, "width": 42, "height": 24},
                "z": 300,
                "text": "测试",
                "style": {"fontSize": 18, "fontFamily": "PingFang SC", "fontWeight": 500, "color": "#111111"},
                "confidence": 0.99,
                "reason": "ocr_authority",
            },
        ],
        "diagnostics": {"pageBackground": "#f5f7fb"},
    }
    (path / "layer_stack.v1.json").write_text(json.dumps(layer_stack), encoding="utf-8")
    return path


def write_empty_transparent_evidence(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (28, 28), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((7, 7, 20, 20), radius=3, fill=(36, 204, 148, 255))
    image.save(path / "source.png")
    evidence = {
        "schemaName": "M29PhysicalEvidence",
        "version": "1.0",
        "generator": {"name": "fake", "mode": "empty-transparent-test"},
        "image": {"width": 28, "height": 28, "sourceRef": "source.png"},
        "ocr": {"provided": False, "blockCount": 0},
        "primitives": [],
        "physicalRelations": [],
        "assets": [],
        "diagnostics": {"pageBackground": "#000000", "boundarySource": "psdlike"},
    }
    replay = {
        "schema": "m29.pencil.replay.v1",
        "layers": [],
        "summary": {"layerCount": 0, "boundarySource": "psdlike"},
    }
    (path / "m29_physical_evidence.v1.json").write_text(json.dumps(evidence), encoding="utf-8")
    (path / "m29-pencil-replay.v1.json").write_text(json.dumps(replay), encoding="utf-8")
    return path


def write_fake_visual_text_evidence(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "crops").mkdir()
    (path / "masks").mkdir()
    image = Image.new("RGB", (240, 160), "#f8fafc")
    draw = ImageDraw.Draw(image)
    for y in range(24, 124):
        for x in range(24, 204):
            value = 48 if (x // 7 + y // 5) % 2 else 208
            image.putpixel((x, y), (value, 60, 220 - value // 2))
    draw.rounded_rectangle((54, 62, 154, 92), radius=6, fill="#a7051a")
    draw.rounded_rectangle((54, 96, 174, 126), radius=6, fill="#a7051a")
    draw.text((64, 68), "¥518.5", fill="#ffffff")
    draw.text((64, 101), "9", fill="#ffffff")
    draw.text((84, 101), "折", fill="#ffffff")
    draw.text((112, 103), "满298使用", fill="#ffffff")
    image.save(path / "source.png")
    media_bbox = {"x": 24, "y": 24, "width": 180, "height": 70}
    price_bbox = {"x": 60, "y": 64, "width": 92, "height": 24}
    digit_bbox = {"x": 60, "y": 98, "width": 20, "height": 24}
    discount_bbox = {"x": 82, "y": 99, "width": 24, "height": 23}
    coupon_bbox = {"x": 110, "y": 101, "width": 58, "height": 20}
    for primitive_id, bbox in (
        ("prim_media", media_bbox),
        ("prim_price", price_bbox),
        ("prim_digit", digit_bbox),
        ("prim_discount", discount_bbox),
        ("prim_coupon", coupon_bbox),
    ):
        image.crop((bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"])).save(
            path / "crops" / f"{primitive_id}.png"
        )
        mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(mask).rectangle(
            (
                bbox["x"],
                bbox["y"],
                bbox["x"] + bbox["width"] - 1,
                bbox["y"] + bbox["height"] - 1,
            ),
            fill=255,
        )
        mask.save(path / "masks" / f"{primitive_id}.png")
    evidence = {
        "schemaName": "M29PhysicalEvidence",
        "version": "1.0",
        "generator": {"name": "fake", "mode": "visual-text-test"},
        "image": {"width": 240, "height": 160, "sourceRef": "source.png"},
        "ocr": {"provided": True, "blockCount": 1},
        "primitives": [
            {
                "id": "prim_media",
                "primitiveType": "image_region",
                "bbox": media_bbox,
                "maskRef": "masks/prim_media.png",
                "cropRef": "crops/prim_media.png",
                "source": {"kind": "pixel", "reason": "high_texture_with_internal_text"},
                "measurements": {"texture": 0.78, "edge": 0.64, "entropy": 0.72, "unique": 0.52},
                "compileHints": {},
            },
            {
                "id": "prim_price",
                "primitiveType": "text_region",
                "bbox": price_bbox,
                "maskRef": "masks/prim_price.png",
                "cropRef": "crops/prim_price.png",
                "source": {"kind": "ocr", "ocrBlockId": "ocr_price", "text": "¥518.5", "confidence": 0.99},
                "measurements": {},
                "compileHints": {},
            },
            {
                "id": "prim_digit",
                "primitiveType": "text_region",
                "bbox": digit_bbox,
                "maskRef": "masks/prim_digit.png",
                "cropRef": "crops/prim_digit.png",
                "source": {"kind": "ocr", "ocrBlockId": "ocr_digit", "text": "9", "confidence": 0.99},
                "measurements": {},
                "compileHints": {},
            },
            {
                "id": "prim_discount",
                "primitiveType": "text_region",
                "bbox": discount_bbox,
                "maskRef": "masks/prim_discount.png",
                "cropRef": "crops/prim_discount.png",
                "source": {"kind": "ocr", "ocrBlockId": "ocr_discount", "text": "折", "confidence": 0.99},
                "measurements": {},
                "compileHints": {},
            },
            {
                "id": "prim_coupon",
                "primitiveType": "text_region",
                "bbox": coupon_bbox,
                "maskRef": "masks/prim_coupon.png",
                "cropRef": "crops/prim_coupon.png",
                "source": {"kind": "ocr", "ocrBlockId": "ocr_coupon", "text": "满298使用", "confidence": 0.99},
                "measurements": {},
                "compileHints": {},
            },
        ],
        "physicalRelations": [],
        "assets": [],
        "diagnostics": {"pageBackground": "#f8fafc"},
    }
    replay = {
        "schema": "m29.pencil.replay.v1",
        "layers": [
            {
                "id": "prim_media",
                "sourcePrimitiveId": "prim_media",
                "role": "image_region",
                "nodeType": "rectangle",
                "bbox": media_bbox,
                "fillImage": "./assets/crops/prim_media.png",
                "maskImage": "./assets/masks/prim_media.png",
                "editableMode": "raster_crop",
                "z": 100,
            },
            {
                "id": "prim_price",
                "sourcePrimitiveId": "prim_price",
                "role": "text_region",
                "nodeType": "rectangle",
                "bbox": price_bbox,
                "fillImage": "./assets/crops/prim_price.png",
                "maskImage": "./assets/masks/prim_price.png",
                "editableMode": "raster_crop",
                "z": 200,
            },
            {
                "id": "prim_digit",
                "sourcePrimitiveId": "prim_digit",
                "role": "text_region",
                "nodeType": "rectangle",
                "bbox": digit_bbox,
                "fillImage": "./assets/crops/prim_digit.png",
                "maskImage": "./assets/masks/prim_digit.png",
                "editableMode": "raster_crop",
                "z": 210,
            },
            {
                "id": "prim_discount",
                "sourcePrimitiveId": "prim_discount",
                "role": "text_region",
                "nodeType": "rectangle",
                "bbox": discount_bbox,
                "fillImage": "./assets/crops/prim_discount.png",
                "maskImage": "./assets/masks/prim_discount.png",
                "editableMode": "raster_crop",
                "z": 220,
            },
            {
                "id": "prim_coupon",
                "sourcePrimitiveId": "prim_coupon",
                "role": "text_region",
                "nodeType": "rectangle",
                "bbox": coupon_bbox,
                "fillImage": "./assets/crops/prim_coupon.png",
                "maskImage": "./assets/masks/prim_coupon.png",
                "editableMode": "raster_crop",
                "z": 230,
            },
        ],
        "summary": {"layerCount": 5},
    }
    (path / "m29_physical_evidence.v1.json").write_text(json.dumps(evidence), encoding="utf-8")
    (path / "m29-pencil-replay.v1.json").write_text(json.dumps(replay), encoding="utf-8")
    return path


def write_fake_psdlike_text_only_output(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (400, 300), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((100, 100, 180, 128), radius=14, fill="#e0f2fe")
    draw.text((120, 107), "待审核", fill="#0369a1")
    image.save(path / "source.png")
    layer_stack = {
        "version": "layer_stack.v1",
        "sourceImage": str(path / "source.png"),
        "canvas": {"width": 400, "height": 300},
        "pageBackground": "#f8fafc",
        "layers": [
            {
                "id": "shape_background",
                "type": "shape",
                "bbox": {"x": 0, "y": 0, "width": 400, "height": 300},
                "z": 100,
                "style": {"fill": "#f8fafc"},
                "scores": {},
                "reason": "background_surface_band",
            },
            {
                "id": "text_status",
                "type": "text",
                "bbox": {"x": 118, "y": 106, "width": 52, "height": 18},
                "z": 300,
                "text": "待审核",
                "style": {"fontSize": 14, "fontFamily": "PingFang SC", "fontWeight": 500, "color": "#0369a1"},
                "confidence": 0.99,
                "reason": "ocr_authority",
            },
        ],
        "diagnostics": {"pageBackground": "#f8fafc"},
    }
    (path / "layer_stack.v1.json").write_text(json.dumps(layer_stack), encoding="utf-8")
    return path


def write_fake_small_shape_output(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (240, 240), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 240, 240), fill="#f8fafc")
    draw.ellipse((80, 60, 160, 140), fill="#24cc94")
    draw.line((102, 100, 118, 116), fill="#ffffff", width=6)
    draw.line((118, 116, 142, 84), fill="#ffffff", width=6)
    image.save(path / "source.png")
    layer_stack = {
        "version": "layer_stack.v1",
        "sourceImage": str(path / "source.png"),
        "canvas": {"width": 240, "height": 240},
        "pageBackground": "#f8fafc",
        "layers": [
            {
                "id": "shape_background",
                "type": "shape",
                "bbox": {"x": 0, "y": 0, "width": 240, "height": 240},
                "z": 100,
                "style": {"fill": "#f8fafc"},
                "scores": {},
                "reason": "background_surface_band",
            },
            {
                "id": "shape_icon",
                "type": "shape",
                "bbox": {"x": 80, "y": 60, "width": 80, "height": 80},
                "z": 200,
                "style": {"fill": "#24cc94"},
                "scores": {"shape": 0.7, "raster": 0.13, "texture": 0.2, "dominant": 0.91},
                "reason": "low_texture_solid_region",
            },
        ],
        "diagnostics": {"pageBackground": "#f8fafc"},
    }
    (path / "layer_stack.v1.json").write_text(json.dumps(layer_stack), encoding="utf-8")
    return path


def write_fake_truncated_raster_output(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    assets = path / "assets"
    assets.mkdir()
    image = Image.new("RGB", (220, 180), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 30, 180, 150), radius=16, fill="#eef6ff")
    draw.ellipse((68, 48, 132, 112), fill="#2563eb")
    draw.line((88, 82, 100, 70), fill="#ffffff", width=6)
    draw.line((100, 70, 116, 88), fill="#ffffff", width=6)
    draw.line((100, 70, 100, 98), fill="#ffffff", width=6)
    draw.text((142, 58), "文本", fill="#111111")
    image.save(path / "source.png")
    image.crop((70, 78, 130, 114)).save(assets / "raster_icon.png")
    layer_stack = {
        "version": "layer_stack.v1",
        "sourceImage": str(path / "source.png"),
        "canvas": {"width": 220, "height": 180},
        "pageBackground": "#f8fafc",
        "layers": [
            {
                "id": "shape_background",
                "type": "shape",
                "bbox": {"x": 0, "y": 0, "width": 220, "height": 180},
                "z": 100,
                "style": {"fill": "#f8fafc"},
                "scores": {},
                "reason": "background_surface_band",
            },
            {
                "id": "shape_card",
                "type": "shape",
                "bbox": {"x": 40, "y": 30, "width": 140, "height": 120},
                "z": 120,
                "style": {"fill": "#eef6ff"},
                "scores": {},
                "reason": "local_container_surface",
            },
            {
                "id": "raster_icon",
                "type": "raster",
                "bbox": {"x": 70, "y": 78, "width": 60, "height": 36},
                "z": 200,
                "asset": "assets/raster_icon.png",
                "scores": {},
                "ownership": {},
                "reason": "foreground_object_on_surface",
            },
            {
                "id": "text_label",
                "type": "text",
                "bbox": {"x": 142, "y": 58, "width": 38, "height": 24},
                "z": 300,
                "text": "文本",
                "style": {"fontSize": 18, "fontFamily": "PingFang SC", "fontWeight": 500, "color": "#111111"},
                "confidence": 0.99,
                "reason": "ocr_authority",
            },
        ],
        "diagnostics": {"pageBackground": "#f8fafc"},
    }
    (path / "layer_stack.v1.json").write_text(json.dumps(layer_stack), encoding="utf-8")
    return path


def write_fake_hybrid_m29_output(path: Path, source_png: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "crops").mkdir()
    (path / "masks").mkdir()
    source = Image.open(source_png).convert("RGB")
    source.save(path / "source.png")
    pill_bbox = {"x": 100, "y": 100, "width": 80, "height": 28}
    text_fragment_bbox = {"x": 118, "y": 106, "width": 52, "height": 18}
    covered_bbox = {"x": 0, "y": 0, "width": 400, "height": 300}
    for primitive_id, bbox in (
        ("prim_pill", pill_bbox),
        ("prim_text_fragment", text_fragment_bbox),
        ("prim_full_background", covered_bbox),
    ):
        source.crop((bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"])).save(path / "crops" / f"{primitive_id}.png")
        mask = Image.new("L", source.size, 0)
        ImageDraw.Draw(mask).rectangle(
            (
                bbox["x"],
                bbox["y"],
                bbox["x"] + bbox["width"] - 1,
                bbox["y"] + bbox["height"] - 1,
            ),
            fill=255,
        )
        mask.save(path / "masks" / f"{primitive_id}.png")
    evidence = {
        "schema": "m29.physical_evidence.v1",
        "image": {"width": source.width, "height": source.height, "sourceRef": "source.png"},
        "primitives": [
            {
                "id": "prim_pill",
                "primitiveType": "symbol_region",
                "bbox": pill_bbox,
                "cropRef": "crops/prim_pill.png",
                "maskRef": "masks/prim_pill.png",
                "source": {"kind": "pixel"},
                "measurements": {},
                "compileHints": {},
            },
            {
                "id": "prim_text_fragment",
                "primitiveType": "symbol_region",
                "bbox": text_fragment_bbox,
                "cropRef": "crops/prim_text_fragment.png",
                "maskRef": "masks/prim_text_fragment.png",
                "source": {"kind": "pixel"},
                "measurements": {},
                "compileHints": {},
            },
            {
                "id": "prim_full_background",
                "primitiveType": "image_region",
                "bbox": covered_bbox,
                "cropRef": "crops/prim_full_background.png",
                "maskRef": "masks/prim_full_background.png",
                "source": {"kind": "pixel"},
                "measurements": {},
                "compileHints": {},
            },
        ],
    }
    (path / "m29_physical_evidence.v1.json").write_text(json.dumps(evidence), encoding="utf-8")
    return path


def collect_ids(nodes: list[dict[str, object]]) -> list[str]:
    ids: list[str] = []
    for node in nodes:
        ids.append(str(node["id"]))
        children = node.get("children")
        if isinstance(children, list):
            ids.extend(collect_ids(children))
    return ids


def collect_nodes(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    collected: list[dict[str, object]] = []
    for node in nodes:
        collected.append(node)
        children = node.get("children")
        if isinstance(children, list):
            collected.extend(collect_nodes(children))
    return collected


def collect_image_fills(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    fills: list[dict[str, object]] = []
    for node in nodes:
        fill = node.get("fill")
        if isinstance(fill, dict) and fill.get("type") == "image" and isinstance(fill.get("url"), str):
            fills.append(fill)
        children = node.get("children")
        if isinstance(children, list):
            fills.extend(collect_image_fills(children))
    return fills


def collect_image_urls(nodes: list[dict[str, object]]) -> list[str]:
    urls: list[str] = []
    for node in nodes:
        fill = node.get("fill")
        if isinstance(fill, dict) and fill.get("type") == "image" and isinstance(fill.get("url"), str):
            urls.append(fill["url"])
        children = node.get("children")
        if isinstance(children, list):
            urls.extend(collect_image_urls(children))
    return urls
