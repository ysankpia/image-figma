from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class InputCase:
    case_id: str
    source_path: Path
    sha256: str
    duplicate_paths: list[Path]


def collect_image_paths(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def build_cases(paths: list[Path], dedupe: bool = True) -> list[InputCase]:
    if not dedupe:
        return [
            InputCase(
                case_id=f"case_{index:04d}_{file_sha256(path)[:10]}",
                source_path=path,
                sha256=file_sha256(path),
                duplicate_paths=[path],
            )
            for index, path in enumerate(paths, start=1)
        ]

    by_hash: dict[str, list[Path]] = {}
    for path in paths:
        by_hash.setdefault(file_sha256(path), []).append(path)

    cases: list[InputCase] = []
    for index, sha in enumerate(sorted(by_hash), start=1):
        duplicates = sorted(by_hash[sha])
        cases.append(
            InputCase(
                case_id=f"case_{index:04d}_{sha[:10]}",
                source_path=duplicates[0],
                sha256=sha,
                duplicate_paths=duplicates,
            )
        )
    return cases


def cases_from_manifest(manifest_path: Path) -> list[InputCase]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases: list[InputCase] = []
    for index, item in enumerate(data.get("cases", []), start=1):
        source_path = Path(str(item["sourcePath"])).expanduser().resolve()
        sha = str(item.get("sha256") or file_sha256(source_path))
        case_id = str(item.get("caseId") or f"case_{index:04d}_{sha[:10]}")
        duplicate_paths = [Path(str(path)).expanduser().resolve() for path in item.get("duplicatePaths", [source_path])]
        cases.append(InputCase(case_id=case_id, source_path=source_path, sha256=sha, duplicate_paths=duplicate_paths))
    return cases


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_basic_dsl(path: Path, case_out: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not path.exists():
        return False, ["dsl_missing"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"dsl_parse_error:{type(exc).__name__}:{exc}"]

    if data.get("version") != "1.0":
        errors.append("version_not_1_0")
    if data.get("kind") != "draft_runtime":
        errors.append("kind_not_draft_runtime")

    asset_paths = {item.get("assetId"): item.get("path") or item.get("url") for item in data.get("assets", [])}
    asset_ids = set(asset_paths)
    for child in data.get("root", {}).get("children", []):
        if child.get("type") != "image":
            continue
        asset_id = child.get("image", {}).get("assetId")
        if not asset_id:
            errors.append(f"{child.get('id')}:image_asset_missing")
            continue
        if asset_id not in asset_ids:
            errors.append(f"{child.get('id')}:image_asset_unknown:{asset_id}")
            continue
        asset_ref = asset_paths.get(asset_id)
        if asset_ref and not (case_out / str(asset_ref)).exists():
            errors.append(f"{child.get('id')}:asset_file_missing:{asset_ref}")
    return len(errors) == 0, errors


def compute_visual_metrics(source_path: Path, draft_path: Path) -> dict[str, float]:
    if not source_path.exists() or not draft_path.exists():
        return {"visualMae": 0.0, "visualDiff30Ratio": 0.0, "visualDiff60Ratio": 0.0}
    with Image.open(source_path) as source, Image.open(draft_path) as draft:
        source_rgb = source.convert("RGB")
        draft_rgb = draft.convert("RGB")
        if draft_rgb.size != source_rgb.size:
            draft_rgb = draft_rgb.resize(source_rgb.size)
        source_arr = np.asarray(source_rgb).astype(np.int16)
        draft_arr = np.asarray(draft_rgb).astype(np.int16)
        diff = np.abs(source_arr - draft_arr).mean(axis=2)
    return {
        "visualMae": round(float(diff.mean()), 4),
        "visualDiff30Ratio": round(float((diff > 30).mean()), 4),
        "visualDiff60Ratio": round(float((diff > 60).mean()), 4),
    }


def count_assets(dsl_path: Path) -> int:
    if not dsl_path.exists():
        return 0
    data = json.loads(dsl_path.read_text(encoding="utf-8"))
    return len(data.get("assets", []))


def count_reason(layer_stack: dict[str, Any], reason: str) -> int:
    return sum(1 for layer in layer_stack.get("layers", []) if layer.get("reason") == reason)


def write_contact_sheet(path: Path, rows: list[dict[str, Any]], image_name: str) -> None:
    items: list[tuple[str, Image.Image, bool]] = []
    for row in rows:
        case_out = path.parent / str(row.get("case", ""))
        image_path = case_out / image_name
        if not image_path.exists():
            continue
        with Image.open(image_path) as image:
            thumb = image.convert("RGB")
            thumb.thumbnail((180, 320))
            items.append((str(row.get("case", "")), thumb.copy(), bool(row.get("failureTypes"))))
    if not items:
        return
    columns = min(6, max(1, math.ceil(math.sqrt(len(items)))))
    cell_w = 210
    cell_h = 360
    rows_count = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows_count * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image, failed) in enumerate(items):
        x = (index % columns) * cell_w + 12
        y = (index // columns) * cell_h + 28
        color = (180, 30, 30) if failed else (20, 120, 45)
        draw.text((x, y - 20), label, fill=color)
        sheet.paste(image, (x, y))
    sheet.save(path)


def write_source_vs_draft_contact_sheet(path: Path, rows: list[dict[str, Any]]) -> None:
    items: list[tuple[str, Image.Image, Image.Image, bool]] = []
    for row in rows:
        source_path = Path(str(row.get("sourcePath", "")))
        draft_path = path.parent / str(row.get("case", "")) / "draft_preview.png"
        if not source_path.exists() or not draft_path.exists():
            continue
        with Image.open(source_path) as source, Image.open(draft_path) as draft:
            source_thumb = source.convert("RGB")
            draft_thumb = draft.convert("RGB")
            source_thumb.thumbnail((130, 260))
            draft_thumb.thumbnail((130, 260))
            items.append((str(row.get("case", "")), source_thumb.copy(), draft_thumb.copy(), bool(row.get("failureTypes"))))
    if not items:
        return
    columns = 4
    cell_w = 300
    cell_h = 330
    rows_count = math.ceil(len(items) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows_count * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, source, draft, failed) in enumerate(items):
        x = (index % columns) * cell_w + 8
        y = (index // columns) * cell_h + 34
        color = (180, 30, 30) if failed else (20, 120, 45)
        draw.text((x, y - 30), label, fill=color)
        draw.text((x, y - 16), "src", fill=(0, 0, 0))
        draw.text((x + 142, y - 16), "draft", fill=(0, 0, 0))
        sheet.paste(source, (x, y))
        sheet.paste(draft, (x + 142, y))
    sheet.save(path)
