#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2].parent
BACKEND = ROOT / "services" / "backend-python"
TOOL = BACKEND / "tools" / "psd_like_layer_decomposition_experiment.py"


CASES = [
    {
        "id": "t018",
        "image": ROOT / "docs/reference/codia-samples/images/腾讯动漫_018_1440.png",
        "ocr": Path("/tmp/backend_python_omni_vlm_smoke/t018/evidence/ocr_blocks.v1.json"),
    },
    {
        "id": "t022",
        "image": ROOT / "docs/reference/codia-samples/images/腾讯动漫_022_1440.png",
        "ocr": Path("/tmp/backend_python_omni_vlm_smoke/t022/evidence/ocr_blocks.v1.json"),
    },
    {
        "id": "lizhi",
        "image": ROOT / "docs/reference/codia-samples/images/荔枝_011_1440.png",
        "ocr": Path("/tmp/backend_python_omni_vlm_smoke/lizhi/evidence/ocr_blocks.v1.json"),
    },
    {
        "id": "xianyu",
        "image": ROOT / "docs/reference/codia-samples/images/闲鱼.png",
        "ocr": Path("/tmp/backend_python_omni_vlm_smoke/xianyu/evidence/ocr_blocks.v1.json"),
    },
]


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for case in CASES:
        case_id = str(case["id"])
        case_out = out_dir / case_id
        command = [
            sys.executable,
            str(TOOL),
            "--image",
            str(case["image"]),
            "--ocr",
            str(case["ocr"]),
            "--out",
            str(case_out),
        ]
        subprocess.run(command, cwd=BACKEND, check=True)
        dsl_valid = validate_basic_dsl(case_out / "draft_runtime.dsl.v1_0.json")
        diagnostics = json.loads((case_out / "layer_stack.v1.json").read_text(encoding="utf-8"))["diagnostics"]
        rows.append({"case": case_id, "dslValid": dsl_valid, **diagnostics})

    write_summary(out_dir / "summary.md", rows)
    write_contact_sheet(out_dir / "contact_sheet.png", out_dir)
    write_draft_preview_contact_sheet(out_dir / "draft_preview_contact_sheet.png", out_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PSD-like layer decomposition on the four reference images.")
    parser.add_argument("--out", default="/tmp/psd_like_layer_exp_smoke", help="Output directory.")
    return parser.parse_args()


def validate_basic_dsl(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    asset_ids = {item["assetId"] for item in data.get("assets", [])}
    children = data.get("root", {}).get("children", [])
    if data.get("version") != "1.0" or data.get("kind") != "draft_runtime":
        return False
    for child in children:
        if child.get("type") == "image":
            asset_id = child.get("image", {}).get("assetId")
            if not asset_id or asset_id not in asset_ids:
                return False
    return True


def write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "# PSD-like Four Image Smoke",
        "",
        "| case | text | raster | shape | surfaceShape | visibleTextOverlap | rawTextOverlap | knockoutRasters | tinyRaster | missingAsset | dslValid |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "|{case}|{textLayerCount}|{rasterLayerCount}|{shapeLayerCount}|{surfaceShapeLayerCount}|{textOverlapRaster}|"
            "{rawTextOverlapRaster}|{rasterTextKnockoutCount}|{tinyRasterFragments}|{missingAssetCount}|{dslValid}|".format(
                **row
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_contact_sheet(path: Path, out_dir: Path) -> None:
    items: list[tuple[str, Image.Image]] = []
    for case in CASES:
        case_id = str(case["id"])
        for kind in ["overlay", "reconstructed_preview"]:
            image_path = out_dir / case_id / f"{kind}.png"
            image = Image.open(image_path).convert("RGB")
            image.thumbnail((240, 520))
            items.append((f"{case_id} {kind}", image.copy()))

    sheet = Image.new("RGB", (520, 1100), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(items):
        x = (index % 2) * 260 + 10
        y = (index // 2) * 270 + 25
        draw.text((x, y - 18), label, fill=(0, 0, 0))
        sheet.paste(image, (x, y))
    sheet.save(path)


def write_draft_preview_contact_sheet(path: Path, out_dir: Path) -> None:
    items: list[tuple[str, Image.Image]] = []
    for case in CASES:
        case_id = str(case["id"])
        image_path = out_dir / case_id / "draft_preview.png"
        image = Image.open(image_path).convert("RGB")
        image.thumbnail((240, 520))
        items.append((case_id, image.copy()))

    sheet = Image.new("RGB", (520, 560), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(items):
        x = (index % 2) * 260 + 10
        y = (index // 2) * 270 + 25
        draw.text((x, y - 18), label, fill=(0, 0, 0))
        sheet.paste(image, (x, y))
    sheet.save(path)


if __name__ == "__main__":
    main()
