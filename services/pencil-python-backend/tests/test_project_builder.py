from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from app.config import Settings
from app.jsonio import read_json
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


def collect_ids(nodes: list[dict[str, object]]) -> list[str]:
    ids: list[str] = []
    for node in nodes:
        ids.append(str(node["id"]))
        children = node.get("children")
        if isinstance(children, list):
            ids.extend(collect_ids(children))
    return ids
