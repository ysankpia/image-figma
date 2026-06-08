from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw

from .jsonio import read_json, write_json
from .projects import AssetProjectPaths, reset_output
from .utils import safe_slug


@dataclass(frozen=True)
class PenRefCheck:
    refs: int
    bad_refs: int
    missing_refs: int
    bad_ref_values: list[str]
    missing_ref_values: list[str]


def export_asset_project(*, paths: AssetProjectPaths, manual_slices: dict[str, Any]) -> dict[str, Any]:
    reset_output(paths)
    selected_manifest = write_selected_assets(paths=paths, manual_slices=manual_slices)
    mode_result = write_pencil_handoff(paths=paths, manual_slices=manual_slices, selected_assets_manifest=selected_manifest)
    preview = write_export_preview(paths=paths, manual_slices=manual_slices)
    write_debug(paths=paths, manual_slices=manual_slices)
    selected_zip = create_selected_assets_zip(paths.output, selected_manifest)
    manifest = {
        "schema": "pencil_asset.export_manifest.v1",
        "projectName": manual_slices.get("projectName") or "Pencil Asset Project",
        "createdAt": now_iso(),
        "mode": "pencil-handoff",
        "manualSlices": "manual_slices.v1.json",
        "designPen": "design.pen",
        "assetRoot": "assets/visible",
        "selectedAssetsZip": "selected-assets.zip",
        "exportPreview": "export-preview/manifest.json",
        "contactSheet": "export-preview/contact-sheet.png",
        "selectedAssetCount": len(selected_manifest["assets"]),
        "modeResult": mode_result,
        "refCheck": mode_result["refCheck"],
        "zip": "project.zip",
        "projectZipUrl": f"/api/asset-projects/{paths.project_id}/download.zip",
        "selectedAssetsZipUrl": f"/api/asset-projects/{paths.project_id}/selected-assets.zip",
        "exportPreviewUrl": preview["previewHtmlUrl"],
    }
    write_json(paths.output / "manual_slices.v1.json", manual_slices)
    write_json(paths.output / "manifest.json", manifest)
    create_project_zip(paths.output)
    write_json(paths.output / "manifest.json", manifest)
    return manifest


def write_export_preview(*, paths: AssetProjectPaths, manual_slices: dict[str, Any]) -> dict[str, Any]:
    preview_dir = paths.output / "export-preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    contact_sheet = write_contact_sheet(paths=paths, manual_slices=manual_slices, output_dir=preview_dir, filename="contact-sheet.png")
    html_path = preview_dir / "index.html"
    assets = contact_sheet["assets"]
    html_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Pencil Asset Export Preview</title>"
        "<style>body{margin:0;background:#101418;color:#e5e7eb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:24px}"
        "img{max-width:100%;border:1px solid #324152;background:#05080c}table{border-collapse:collapse;width:100%;margin-top:18px}"
        "td,th{border-bottom:1px solid #293442;padding:8px;text-align:left;font-size:13px}</style></head><body>"
        f"<h1>Pencil Asset Export Preview</h1><p>{len(assets)} selected PNG assets</p>"
        "<img src='contact-sheet.png' alt='contact sheet'>"
        "<table><thead><tr><th>Page</th><th>Name</th><th>Kind</th><th>Size</th><th>File</th></tr></thead><tbody>"
        + "".join(
            "<tr>"
            f"<td>{escape(str(asset['pageId']))}</td>"
            f"<td>{escape(str(asset['displayName']))}</td>"
            f"<td>{escape(str(asset['kind']))}</td>"
            f"<td>{asset['bbox']['width']}x{asset['bbox']['height']}</td>"
            f"<td>{escape(str(asset['file']))}</td>"
            "</tr>"
            for asset in assets
        )
        + "</tbody></table></body></html>",
        encoding="utf-8",
    )
    manifest = {
        "schema": "pencil_asset.export_preview.v1",
        "createdAt": now_iso(),
        "assetCount": len(assets),
        "contactSheet": "contact-sheet.png",
        "contactSheetUrl": f"/api/asset-projects/{paths.project_id}/export-preview/contact-sheet.png",
        "previewHtml": "index.html",
        "previewHtmlUrl": f"/api/asset-projects/{paths.project_id}/export-preview/index.html",
        "assets": assets,
    }
    write_json(preview_dir / "manifest.json", manifest)
    return manifest


def write_selected_assets(*, paths: AssetProjectPaths, manual_slices: dict[str, Any]) -> dict[str, Any]:
    assets_root = paths.output / "selected-assets"
    assets: list[dict[str, Any]] = []
    for page in manual_slices.get("pages") or []:
        page_id = str(page["pageId"])
        source_path = paths.root / str(page["sourceImage"])
        page_dir = assets_root / page_id
        page_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(source_path) as image:
            source = image.convert("RGBA")
            selected = [
                item
                for item in page.get("slices") or []
                if item.get("selected") is not False and item.get("kind") in {"image", "icon"}
            ]
            for index, item in enumerate(selected, start=1):
                bbox = item["bbox"]
                filename = f"slice_{index:04d}.png"
                relative = f"{page_id}/{filename}"
                crop = source.crop((bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]))
                crop.save(page_dir / filename)
                assets.append(
                    {
                        "id": item["id"],
                        "pageId": page_id,
                        "name": item["name"],
                        "displayName": item.get("displayName") or item["name"],
                        "kind": item["kind"],
                        "bbox": bbox,
                        "file": relative,
                        "exportMode": item.get("exportMode") or "rect",
                        "source": item.get("source") or "manual",
                        "candidateIds": item.get("candidateIds") or [],
                        "tags": item.get("tags") or [],
                    }
                )
    manifest = {
        "schema": "pencil_asset.selected_assets.v1",
        "createdAt": now_iso(),
        "assetCount": len(assets),
        "assets": assets,
    }
    write_json(assets_root / "manifest.json", manifest)
    return manifest


def write_pencil_handoff(
    *, paths: AssetProjectPaths, manual_slices: dict[str, Any], selected_assets_manifest: dict[str, Any]
) -> dict[str, Any]:
    visible_root = paths.output / "assets" / "visible"
    assets_by_id = {asset["id"]: asset for asset in selected_assets_manifest["assets"]}
    frames: list[dict[str, Any]] = []
    emitted_assets: list[dict[str, Any]] = []
    for page_index, page in enumerate(manual_slices.get("pages") or [], start=1):
        page_id = str(page["pageId"])
        frame = {
            "id": f"{page_id}__frame",
            "type": "frame",
            "name": f"{manual_slices.get('projectName') or 'Pencil Asset Project'} {page_id}",
            "x": (page_index - 1) * (int(page["width"]) + 120),
            "y": 0,
            "width": int(page["width"]),
            "height": int(page["height"]),
            "layout": "none",
            "fill": "#FFFFFF",
            "metadata": {
                "type": "pencil_asset_handoff_page",
                "pageId": page_id,
                "sourceImage": page["sourceImage"],
            },
            "children": [],
        }
        for item in page.get("slices") or []:
            if item.get("selected") is False or item.get("kind") not in {"image", "icon"}:
                continue
            asset = assets_by_id[item["id"]]
            source_asset = paths.output / "selected-assets" / asset["file"]
            target_dir = visible_root / page_id
            target_dir.mkdir(parents=True, exist_ok=True)
            target_name = Path(asset["file"]).name
            target_path = target_dir / target_name
            shutil.copy2(source_asset, target_path)
            bbox = item["bbox"]
            url = f"./assets/visible/{page_id}/{target_name}"
            frame["children"].append(
                {
                    "id": f"{page_id}__node_{safe_slug(item['id'], 'slice')}",
                    "type": "rectangle",
                    "name": item.get("displayName") or item["name"],
                    "x": bbox["x"],
                    "y": bbox["y"],
                    "width": bbox["width"],
                    "height": bbox["height"],
                    "fill": {"type": "image", "enabled": True, "url": url, "mode": "stretch"},
                    "metadata": {
                        "type": "pencil_asset_slice",
                        "pageId": page_id,
                        "sliceId": item["id"],
                        "kind": item["kind"],
                        "bbox": bbox,
                        "candidateIds": item.get("candidateIds") or [],
                    },
                }
            )
            emitted_assets.append({**asset, "url": url})
        frames.append(frame)
    document = {"version": "2.11", "children": frames}
    check = validate_pen_refs(document, paths.output)
    if check.bad_refs or check.missing_refs:
        raise RuntimeError(f"invalid .pen image refs: badRefs={check.bad_refs} missingRefs={check.missing_refs}")
    write_json(paths.output / "design.pen", document)
    write_json(paths.output / "pencil-handoff.manifest.json", {"mode": "pencil-handoff", "assets": emitted_assets})
    return {
        "mode": "pencil-handoff",
        "designPen": "design.pen",
        "assetCount": len(emitted_assets),
        "frameCount": len(frames),
        "refCheck": {
            "refs": check.refs,
            "badRefs": check.bad_refs,
            "missingRefs": check.missing_refs,
        },
    }


def validate_pen_refs(document: dict[str, Any], root: Path) -> PenRefCheck:
    refs: list[str] = []
    for child in document.get("children") or []:
        collect_image_refs(child, refs)
    bad = [
        ref
        for ref in refs
        if not ref.startswith("./assets/visible/")
        or "../" in ref
        or "source.png" in ref
        or "debug/" in ref
        or "raw-crops" in ref
        or "masks/" in ref
        or Path(ref).is_absolute()
    ]
    missing = [ref for ref in refs if not (root / ref.removeprefix("./")).exists()]
    return PenRefCheck(refs=len(refs), bad_refs=len(bad), missing_refs=len(missing), bad_ref_values=bad, missing_ref_values=missing)


def collect_image_refs(node: Any, refs: list[str]) -> None:
    if not isinstance(node, dict):
        return
    fill = node.get("fill")
    if isinstance(fill, dict):
        append_image_ref(fill, refs)
    elif isinstance(fill, list):
        for item in fill:
            if isinstance(item, dict):
                append_image_ref(item, refs)
    for child in node.get("children") or []:
        collect_image_refs(child, refs)


def append_image_ref(fill: dict[str, Any], refs: list[str]) -> None:
    if fill.get("type") == "image" and isinstance(fill.get("url"), str):
        refs.append(fill["url"])


def write_contact_sheet(
    *, paths: AssetProjectPaths, manual_slices: dict[str, Any], output_dir: Path, filename: str
) -> dict[str, Any]:
    selected = selected_asset_rows(manual_slices)
    thumb_w = 160
    thumb_h = 120
    label_h = 54
    gap = 16
    columns = 4 if len(selected) > 1 else 1
    rows = max(1, (len(selected) + columns - 1) // columns)
    sheet_w = columns * thumb_w + (columns + 1) * gap
    sheet_h = rows * (thumb_h + label_h) + (rows + 1) * gap
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#101418")
    draw = ImageDraw.Draw(sheet)
    for index, asset in enumerate(selected):
        row = index // columns
        col = index % columns
        left = gap + col * (thumb_w + gap)
        top = gap + row * (thumb_h + label_h + gap)
        source_path = paths.root / asset["sourceImage"]
        bbox = asset["bbox"]
        with Image.open(source_path) as image:
            crop = image.convert("RGBA").crop((bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]))
        crop.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        draw.rectangle((left, top, left + thumb_w, top + thumb_h), fill="#05080c", outline="#324152")
        sheet.paste(crop.convert("RGB"), (left + (thumb_w - crop.width) // 2, top + (thumb_h - crop.height) // 2))
        label_top = top + thumb_h + 6
        draw.text((left, label_top), f"{index + 1}. {asset['pageId']} {asset['kind']}", fill="#e5e7eb")
        draw.text((left, label_top + 16), str(asset["displayName"])[:22], fill="#cbd5e1")
        draw.text((left, label_top + 32), f"{bbox['width']}x{bbox['height']} {asset['file']}", fill="#94a3b8")
    if not selected:
        draw.text((gap, gap), "No selected assets", fill="#e5e7eb")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    sheet.save(path)
    return {"path": str(path), "assets": selected}


def selected_asset_rows(manual_slices: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in manual_slices.get("pages") or []:
        page_id = str(page["pageId"])
        selected = [
            item
            for item in page.get("slices") or []
            if item.get("selected") is not False and item.get("kind") in {"image", "icon"}
        ]
        for index, item in enumerate(selected, start=1):
            rows.append(
                {
                    "id": item["id"],
                    "pageId": page_id,
                    "name": item["name"],
                    "displayName": item.get("displayName") or item["name"],
                    "kind": item["kind"],
                    "bbox": item["bbox"],
                    "file": f"{page_id}/slice_{index:04d}.png",
                    "sourceImage": str(page["sourceImage"]),
                }
            )
    return rows


def write_debug(*, paths: AssetProjectPaths, manual_slices: dict[str, Any]) -> None:
    debug_root = paths.output / "debug" / "pages"
    candidates = read_json(paths.candidates_json) if paths.candidates_json.exists() else {"pages": []}
    candidates_by_page = {str(page["pageId"]): page for page in candidates.get("pages") or []}
    for page in manual_slices.get("pages") or []:
        page_id = str(page["pageId"])
        page_dir = debug_root / page_id
        page_dir.mkdir(parents=True, exist_ok=True)
        source_path = paths.root / str(page["sourceImage"])
        write_json(page_dir / "manual_slices.v1.json", {"schema": manual_slices.get("schema"), "pages": [page]})
        if page_id in candidates_by_page:
            write_json(page_dir / "candidates.v1.json", {"schema": candidates.get("schema"), "pages": [candidates_by_page[page_id]]})
        draw_overlay(source_path, page.get("slices") or [], page_dir / "manual_overlay.png", outline="#22c55e")


def draw_overlay(source_path: Path, slices: list[dict[str, Any]], output_path: Path, *, outline: str) -> None:
    with Image.open(source_path) as image:
        overlay = image.convert("RGB")
    draw = ImageDraw.Draw(overlay)
    for index, item in enumerate(slices, start=1):
        if item.get("selected") is False:
            continue
        bbox = item["bbox"]
        x = bbox["x"]
        y = bbox["y"]
        right = x + bbox["width"]
        bottom = y + bbox["height"]
        draw.rectangle((x, y, right, bottom), outline=outline, width=4)
        draw.rectangle((x, max(0, y - 18), x + 100, max(18, y)), fill="#111827")
        draw.text((x + 4, max(0, y - 17)), f"{index}. {item.get('kind', '')}", fill="#ffffff")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(output_path)


def create_selected_assets_zip(out_dir: Path, manifest: dict[str, Any]) -> Path:
    zip_path = out_dir / "selected-assets.zip"
    if zip_path.exists():
        zip_path.unlink()
    assets_root = out_dir / "selected-assets"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for asset in manifest["assets"]:
            asset_path = assets_root / asset["file"]
            archive.write(asset_path, asset["file"])
        archive.write(assets_root / "manifest.json", "manifest.json")
    return zip_path


def create_project_zip(out_dir: Path) -> Path:
    zip_path = out_dir / "project.zip"
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(out_dir.rglob("*")):
            if path.is_dir() or path == zip_path:
                continue
            relative = path.relative_to(out_dir)
            if relative.parts and relative.parts[0] == "selected-assets":
                continue
            if relative.name == "selected-assets.zip":
                continue
            archive.write(path, relative)
    return zip_path


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
