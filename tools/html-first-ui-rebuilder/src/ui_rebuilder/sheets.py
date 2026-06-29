from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from .geometry import BBox
from .io import now_iso, read_json, rel, write_json
from .paths import RunPaths
from .planner import source_image_path


def make_sheets(
    paths: RunPaths,
    max_sheet_side: int = 1400,
    padding: int = 16,
    gutter: int = 32,
    one_roi_per_sheet: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if paths.sheet_manifest_json.exists() and not force:
        return read_json(paths.sheet_manifest_json)

    paths.ensure()
    plan = read_json(paths.asset_plan_json)
    source_path = source_image_path(paths)
    source = Image.open(source_path).convert("RGB")
    width, height = source.size

    cells: list[dict[str, Any]] = []
    for roi in plan["rois"]:
        bbox = BBox.from_dict(roi["bbox"]).clamp(width, height)
        crop = source.crop((bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height))
        crop_path = paths.rois_dir / f"{roi['id']}.png"
        crop.save(crop_path)
        cells.append(
            {
                "roiId": roi["id"],
                "label": roi.get("label", roi["id"]),
                "kind": roi.get("kind", "asset"),
                "pageBBox": bbox.to_dict(),
                "cropPath": rel(crop_path, paths.root),
                "sourceSize": {"width": crop.width, "height": crop.height},
                "image": crop,
            }
        )

    sheets: list[dict[str, Any]] = []
    sheet_cells: list[dict[str, Any]] = []
    sheet = Image.new("RGB", (max_sheet_side, max_sheet_side), "white")
    x = padding
    y = padding
    row_height = 0
    sheet_index = 1

    def flush() -> None:
        nonlocal sheet, sheet_cells, sheet_index, x, y, row_height
        if not sheet_cells:
            return
        used_width = max(cell["cellBBox"]["x"] + cell["cellBBox"]["width"] + padding for cell in sheet_cells)
        used_height = max(cell["cellBBox"]["y"] + cell["cellBBox"]["height"] + padding for cell in sheet_cells)
        cropped_sheet = sheet.crop((0, 0, min(max_sheet_side, used_width), min(max_sheet_side, used_height)))
        sheet_path = paths.sheets_dir / f"sheet_{sheet_index:04d}.png"
        cropped_sheet.save(sheet_path)
        sheets.append(
            {
                "id": f"sheet_{sheet_index:04d}",
                "path": rel(sheet_path, paths.root),
                "width": cropped_sheet.width,
                "height": cropped_sheet.height,
                "cells": sheet_cells,
            }
        )
        sheet_index += 1
        sheet_cells = []
        sheet = Image.new("RGB", (max_sheet_side, max_sheet_side), "white")
        x = padding
        y = padding
        row_height = 0

    for cell in cells:
        crop = cell.pop("image")
        if one_roi_per_sheet and sheet_cells:
            flush()
        scale = min(1.0, (max_sheet_side - padding * 2) / max(crop.width, crop.height, 1))
        if scale < 1.0:
            crop = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.Resampling.LANCZOS)

        cell_width = crop.width + padding * 2
        cell_height = crop.height + padding * 2
        if x + cell_width > max_sheet_side and x > padding:
            x = padding
            y += row_height + gutter
            row_height = 0
        if y + cell_height > max_sheet_side and sheet_cells:
            flush()

        content_bbox = BBox(x + padding, y + padding, crop.width, crop.height)
        cell_bbox = BBox(x, y, cell_width, cell_height)
        sheet.paste(crop, (content_bbox.x, content_bbox.y))
        sheet_cells.append(
            {
                **cell,
                "cellBBox": cell_bbox.to_dict(),
                "contentBBox": content_bbox.to_dict(),
                "sheetContentSize": {"width": crop.width, "height": crop.height},
                "sheetScale": scale,
            }
        )
        x += cell_width + gutter
        row_height = max(row_height, cell_height)
        if one_roi_per_sheet:
            flush()

    flush()
    manifest = {
        "schema": "html_first_asset_sheet_manifest.v1",
        "createdAt": now_iso(),
        "settings": {
            "maxSheetSide": max_sheet_side,
            "padding": padding,
            "gutter": gutter,
            "oneRoiPerSheet": one_roi_per_sheet,
            "background": "white",
            "labelsDrawnOnImage": False,
        },
        "sheets": sheets,
    }
    write_json(paths.sheet_manifest_json, manifest)
    return manifest
