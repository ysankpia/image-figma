from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageDraw

from app.config import Settings
from app.exporter.single_page import SinglePageExportOptions, export_single_page
from app.jsonio import read_json
from app.psdlike_adapter import adapt_psdlike_to_pencil_evidence
from app.project_builder import export_project
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

    visual_ocr_manifest = read_json(out_dir / "work" / "page_0001" / "single_page_export" / "visual-ocr" / "manifest.json")
    assert visual_ocr_manifest["visibleOcrText"] is True
    assert visual_ocr_manifest["cropTextRegions"] is False
    assert visual_ocr_manifest["textNodes"] == 1
    assert visual_ocr_manifest["cropTextNodes"] == 0
    assert visual_ocr_manifest["textKnockoutCropNodes"] >= 1
    assert {item["decision"] for item in visual_ocr_manifest["textDecisions"]} == {"editable_text"}

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
                "style": {"fill": "#f5f7fb"},
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


def collect_ids(nodes: list[dict[str, object]]) -> list[str]:
    ids: list[str] = []
    for node in nodes:
        ids.append(str(node["id"]))
        children = node.get("children")
        if isinstance(children, list):
            ids.extend(collect_ids(children))
    return ids
