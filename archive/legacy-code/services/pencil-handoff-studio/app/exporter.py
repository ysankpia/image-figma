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
from .projects import ProjectPaths, reset_output


@dataclass(frozen=True)
class PenRefCheck:
    refs: int
    bad_refs: int
    missing_refs: int
    bad_ref_values: list[str]
    missing_ref_values: list[str]


def export_handoff_project(*, paths: ProjectPaths, manual_slices: dict[str, Any], review_state: dict[str, Any]) -> dict[str, Any]:
    reset_output(paths)
    assets_manifest = write_assets(paths=paths, manual_slices=manual_slices)
    pen_result = write_design_pen(paths=paths, manual_slices=manual_slices, assets_manifest=assets_manifest)
    preview = write_export_preview(paths=paths, manual_slices=manual_slices)
    write_debug(paths=paths, manual_slices=manual_slices)
    write_json(paths.output / "manual_slices.v1.json", manual_slices)
    write_json(paths.output / "review_state.v1.json", review_state)
    create_assets_zip(paths.output)
    manifest = {
        "schema": "pencil_handoff.export_manifest.v1",
        "projectName": manual_slices.get("projectName") or "Pencil Handoff Project",
        "createdAt": now_iso(),
        "designPen": "design.pen",
        "assetsZip": "assets.zip",
        "projectZip": "project.zip",
        "assetCount": assets_manifest["sliceCount"],
        "originalCount": assets_manifest["originalCount"],
        "assetsManifest": "assets/manifest.json",
        "manualSlices": "manual_slices.v1.json",
        "reviewState": "review_state.v1.json",
        "contactSheet": "export-preview/contact-sheet.png",
        "exportPreviewUrl": preview["previewHtmlUrl"],
        "refCheck": pen_result["refCheck"],
        "projectZipUrl": f"/api/handoff-projects/{paths.project_id}/project.zip",
        "assetsZipUrl": f"/api/handoff-projects/{paths.project_id}/assets.zip",
    }
    write_json(paths.output / "manifest.json", manifest)
    create_project_zip(paths.output)
    write_json(paths.output / "manifest.json", manifest)
    return manifest


def write_assets(*, paths: ProjectPaths, manual_slices: dict[str, Any]) -> dict[str, Any]:
    assets_root = paths.output / "assets"
    originals_root = assets_root / "originals"
    slices_root = assets_root / "slices"
    originals: list[dict[str, Any]] = []
    slices: list[dict[str, Any]] = []
    for page in manual_slices.get("pages") or []:
        page_id = str(page["pageId"])
        source_path = paths.root / str(page["sourceImage"])
        original_file = f"{page_id}.png"
        originals_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, originals_root / original_file)
        originals.append(
            {
                "pageId": page_id,
                "file": f"originals/{original_file}",
                "width": int(page["width"]),
                "height": int(page["height"]),
            }
        )
        selected = [item for item in page.get("slices") or [] if item.get("selected") is not False]
        with Image.open(source_path) as image:
            source = image.convert("RGBA")
            page_dir = slices_root / page_id
            page_dir.mkdir(parents=True, exist_ok=True)
            for index, item in enumerate(selected, start=1):
                bbox = item["bbox"]
                filename = f"slice_{index:04d}.png"
                relative = f"slices/{page_id}/{filename}"
                crop = source.crop((bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]))
                crop.save(page_dir / filename)
                slices.append(
                    {
                        "id": item["id"],
                        "pageId": page_id,
                        "name": item["name"],
                        "displayName": item.get("displayName") or item["name"],
                        "kind": item["kind"],
                        "bbox": bbox,
                        "file": relative,
                        "source": item.get("source") or "manual",
                        "candidateIds": item.get("candidateIds") or [],
                        "tags": item.get("tags") or [],
                    }
                )
    manifest = {
        "schema": "pencil_handoff.assets_manifest.v1",
        "createdAt": now_iso(),
        "originalCount": len(originals),
        "sliceCount": len(slices),
        "originals": originals,
        "slices": slices,
    }
    write_json(assets_root / "manifest.json", manifest)
    return manifest


def write_design_pen(*, paths: ProjectPaths, manual_slices: dict[str, Any], assets_manifest: dict[str, Any]) -> dict[str, Any]:
    slices_by_id = {item["id"]: item for item in assets_manifest["slices"]}
    frames: list[dict[str, Any]] = []
    for page_index, page in enumerate(manual_slices.get("pages") or [], start=1):
        page_id = str(page["pageId"])
        width = int(page["width"])
        height = int(page["height"])
        children: list[dict[str, Any]] = [
            {
                "id": f"{page_id}__source_reference",
                "type": "rectangle",
                "name": "source reference",
                "x": 0,
                "y": 0,
                "width": width,
                "height": height,
                "opacity": 0.45,
                "locked": True,
                "fill": {"type": "image", "enabled": True, "url": f"./assets/originals/{page_id}.png", "mode": "stretch"},
                "metadata": {"type": "pencil_handoff_source_reference", "pageId": page_id, "role": "reference_only"},
            }
        ]
        for item in page.get("slices") or []:
            if item.get("selected") is False:
                continue
            bbox = item["bbox"]
            if item["kind"] in {"image", "icon"}:
                asset = slices_by_id[item["id"]]
                children.append(
                    {
                        "id": item["id"],
                        "type": "rectangle",
                        "name": item.get("displayName") or item.get("name") or item["id"],
                        "x": bbox["x"],
                        "y": bbox["y"],
                        "width": bbox["width"],
                        "height": bbox["height"],
                        "opacity": 1,
                        "fill": {"type": "image", "enabled": True, "url": f"./assets/{asset['file']}", "mode": "stretch"},
                        "metadata": {"type": "pencil_handoff_slice", "kind": item["kind"], "pageId": page_id, "bbox": bbox},
                    }
                )
            elif item["kind"] == "basic":
                children.append(
                    {
                        "id": item["id"],
                        "type": "rectangle",
                        "name": item.get("displayName") or item.get("name") or item["id"],
                        "x": bbox["x"],
                        "y": bbox["y"],
                        "width": bbox["width"],
                        "height": bbox["height"],
                        "fill": "#FFFFFF00",
                        "stroke": {"align": "inside", "thickness": 1, "fill": "#2563EB"},
                        "metadata": {"type": "pencil_handoff_basic", "pageId": page_id, "bbox": bbox},
                    }
                )
        frames.append(
            {
                "id": f"{page_id}__frame",
                "type": "frame",
                "name": f"{manual_slices.get('projectName') or 'Pencil Handoff Project'} {page_id}",
                "x": (page_index - 1) * (width + 120),
                "y": 0,
                "width": width,
                "height": height,
                "layout": "none",
                "fill": "#FFFFFF",
                "metadata": {"type": "pencil_handoff_page", "pageId": page_id},
                "children": children,
            }
        )
    document = {
        "schema": "pencil.design.v1",
        "name": manual_slices.get("projectName") or "Pencil Handoff Project",
        "metadata": {"type": "pencil_handoff_project", "projectId": paths.project_id},
        "children": frames,
    }
    write_json(paths.output / "design.pen", document)
    ref_check = check_pen_refs(paths.output, document)
    return {
        "designPen": "design.pen",
        "frameCount": len(frames),
        "refCheck": {
            "refs": ref_check.refs,
            "badRefs": ref_check.bad_refs,
            "missingRefs": ref_check.missing_refs,
            "badRefValues": ref_check.bad_ref_values,
            "missingRefValues": ref_check.missing_ref_values,
        },
    }


def write_export_preview(*, paths: ProjectPaths, manual_slices: dict[str, Any]) -> dict[str, Any]:
    preview_dir = paths.output / "export-preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    contact_sheet = write_contact_sheet(paths=paths, manual_slices=manual_slices, output_dir=preview_dir)
    html_path = preview_dir / "index.html"
    assets = contact_sheet["assets"]
    html_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Pencil Handoff Export Preview</title>"
        "<style>body{margin:0;background:#101418;color:#e5e7eb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:24px}"
        "img{max-width:100%;border:1px solid #324152;background:#05080c}table{border-collapse:collapse;width:100%;margin-top:18px}"
        "td,th{border-bottom:1px solid #293442;padding:8px;text-align:left;font-size:13px}</style></head><body>"
        f"<h1>Pencil Handoff Export Preview</h1><p>{len(assets)} selected slices</p>"
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
        "schema": "pencil_handoff.export_preview.v1",
        "createdAt": now_iso(),
        "assetCount": len(assets),
        "contactSheet": "contact-sheet.png",
        "contactSheetUrl": f"/api/handoff-projects/{paths.project_id}/export-preview/contact-sheet.png",
        "previewHtml": "index.html",
        "previewHtmlUrl": f"/api/handoff-projects/{paths.project_id}/export-preview/index.html",
        "assets": assets,
    }
    write_json(preview_dir / "manifest.json", manifest)
    return manifest


def write_contact_sheet(*, paths: ProjectPaths, manual_slices: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    thumbs: list[tuple[dict[str, Any], Image.Image]] = []
    for page in manual_slices.get("pages") or []:
        page_id = str(page["pageId"])
        source_path = paths.root / str(page["sourceImage"])
        with Image.open(source_path) as image:
            source = image.convert("RGBA")
            selected = [item for item in page.get("slices") or [] if item.get("selected") is not False]
            for index, item in enumerate(selected, start=1):
                bbox = item["bbox"]
                crop = source.crop((bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]))
                crop.thumbnail((140, 100))
                asset = {
                    "id": item["id"],
                    "pageId": page_id,
                    "displayName": item.get("displayName") or item.get("name") or item["id"],
                    "kind": item["kind"],
                    "bbox": bbox,
                    "file": f"slices/{page_id}/slice_{index:04d}.png",
                }
                thumbs.append((asset, crop.copy()))
    cell_w, cell_h = 220, 150
    cols = 4
    rows = max(1, (len(thumbs) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "#111827")
    draw = ImageDraw.Draw(sheet)
    for index, (asset, thumb) in enumerate(thumbs):
        col, row = index % cols, index // cols
        x, y = col * cell_w, row * cell_h
        sheet.paste(thumb.convert("RGB"), (x + 10, y + 10))
        draw.text((x + 10, y + 116), f"{asset['pageId']} {asset['displayName']}"[:28], fill="#e5e7eb")
        draw.text((x + 10, y + 132), f"{asset['kind']} {asset['bbox']['width']}x{asset['bbox']['height']}", fill="#94a3b8")
    sheet.save(output_dir / "contact-sheet.png")
    return {"assets": [asset for asset, _ in thumbs], "contactSheet": "contact-sheet.png"}


def write_debug(*, paths: ProjectPaths, manual_slices: dict[str, Any]) -> None:
    debug_root = paths.output / "debug"
    for page in manual_slices.get("pages") or []:
        page_id = str(page["pageId"])
        page_debug = debug_root / "pages" / page_id
        page_debug.mkdir(parents=True, exist_ok=True)
        write_json(page_debug / "manual_slices.v1.json", {"schema": manual_slices["schema"], "pages": [page]})
        source_path = paths.root / str(page["sourceImage"])
        with Image.open(source_path) as image:
            canvas = image.convert("RGB")
        draw = ImageDraw.Draw(canvas)
        for item in page.get("slices") or []:
            bbox = item["bbox"]
            x, y = bbox["x"], bbox["y"]
            draw.rectangle((x, y, x + bbox["width"], y + bbox["height"]), outline="#d946ef", width=3)
        canvas.save(page_debug / "manual_overlay.png")


def check_pen_refs(root: Path, document: dict[str, Any]) -> PenRefCheck:
    refs: list[str] = []
    collect_refs(document, refs)
    bad: list[str] = []
    missing: list[str] = []
    for ref in refs:
        if ref.startswith("/") or ".." in Path(ref).parts or not ref.startswith("./assets/"):
            bad.append(ref)
            continue
        if any(part in {"debug", "raw", "raw-crops", "masks"} for part in Path(ref).parts):
            bad.append(ref)
            continue
        target = root / ref.removeprefix("./")
        if not target.exists():
            missing.append(ref)
    return PenRefCheck(refs=len(refs), bad_refs=len(bad), missing_refs=len(missing), bad_ref_values=bad, missing_ref_values=missing)


def collect_refs(value: Any, refs: list[str]) -> None:
    if isinstance(value, dict):
        fill = value.get("fill")
        if isinstance(fill, dict) and fill.get("type") == "image" and isinstance(fill.get("url"), str):
            refs.append(fill["url"])
        for child in value.values():
            collect_refs(child, refs)
    elif isinstance(value, list):
        for item in value:
            collect_refs(item, refs)


def create_assets_zip(out_dir: Path) -> Path:
    zip_path = out_dir / "assets.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        assets_root = out_dir / "assets"
        for path in sorted(assets_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(assets_root).as_posix())
    return zip_path


def create_project_zip(out_dir: Path) -> Path:
    zip_path = out_dir / "project.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(out_dir.rglob("*")):
            if not path.is_file() or path == zip_path:
                continue
            relative = path.relative_to(out_dir)
            if relative.as_posix() == "assets.zip":
                continue
            archive.write(path, relative.as_posix())
    return zip_path


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
