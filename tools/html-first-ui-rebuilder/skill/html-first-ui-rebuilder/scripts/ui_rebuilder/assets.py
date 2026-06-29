from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageFilter

from .geometry import BBox
from .io import now_iso, read_json, rel, write_json
from .paths import RunPaths
from .planner import source_image_path


def extract_assets(
    paths: RunPaths,
    alpha_threshold: int = 20,
    min_mask_ratio: float = 0.01,
    max_mask_ratio: float = 0.98,
    include_full_page_components: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    if paths.asset_manifest_json.exists() and not force:
        return read_json(paths.asset_manifest_json)

    sheet_manifest = read_json(paths.sheet_manifest_json)
    qwen_manifest = read_json(paths.qwen_manifest_json) if paths.qwen_manifest_json.exists() else {"results": []}
    qwen_by_sheet = {result["sheetId"]: result for result in qwen_manifest.get("results", []) if result.get("ok")}
    assets: list[dict[str, Any]] = []

    for sheet in sheet_manifest["sheets"]:
        sheet_id = sheet["id"]
        layers = [paths.root / path for path in qwen_by_sheet.get(sheet_id, {}).get("layers", [])]
        for cell in sheet["cells"]:
            roi_id = cell["roiId"]
            crop_path = paths.root / cell["cropPath"]
            original_crop = Image.open(crop_path).convert("RGBA")
            original_path = paths.assets_dir / f"{roi_id}__original.png"
            original_crop.save(original_path)
            assets.append(
                {
                    "id": f"{roi_id}__original",
                    "roiId": roi_id,
                    "kind": cell.get("kind", "asset"),
                    "source": "original_crop",
                    "primary": True,
                    "path": rel(original_path, paths.root),
                    "bboxOnPage": cell["pageBBox"],
                    "width": original_crop.width,
                    "height": original_crop.height,
                }
            )
            for layer_index, layer_path in enumerate(layers):
                extracted = _extract_layer_asset(
                    paths,
                    cell,
                    int(sheet["width"]),
                    int(sheet["height"]),
                    original_crop,
                    layer_path,
                    layer_index,
                    alpha_threshold,
                    min_mask_ratio,
                    max_mask_ratio,
                )
                if extracted:
                    assets.append(extracted)

    if include_full_page_components:
        assets.extend(_extract_full_page_components(paths, alpha_threshold))

    manifest = {
        "schema": "html_first_asset_manifest.v1",
        "createdAt": now_iso(),
        "assets": assets,
        "summary": {
            "assetCount": len(assets),
            "originalCropCount": len([asset for asset in assets if asset["source"] == "original_crop"]),
            "qwenMaskCount": len([asset for asset in assets if asset["source"] == "qwen_masked_original"]),
            "qwenFullComponentCount": len(
                [asset for asset in assets if asset["source"] == "qwen_full_component_masked_original"]
            ),
        },
    }
    write_json(paths.asset_manifest_json, manifest)
    return manifest


def _extract_layer_asset(
    paths: RunPaths,
    cell: dict[str, Any],
    sheet_width: int,
    sheet_height: int,
    original_crop: Image.Image,
    layer_path: Path,
    layer_index: int,
    alpha_threshold: int,
    min_mask_ratio: float,
    max_mask_ratio: float,
) -> dict[str, Any] | None:
    layer = Image.open(layer_path).convert("RGBA")
    content = BBox.from_dict(cell["contentBBox"])
    sx = layer.width / max(sheet_width, 1)
    sy = layer.height / max(sheet_height, 1)
    layer_box = (
        round(content.x * sx),
        round(content.y * sy),
        round((content.x + content.width) * sx),
        round((content.y + content.height) * sy),
    )
    layer_crop = layer.crop(layer_box)
    mask = _mask_from_layer(layer_crop, alpha_threshold)
    if mask.size != original_crop.size:
        mask = mask.resize(original_crop.size, Image.Resampling.LANCZOS)
    mask = mask.filter(ImageFilter.MedianFilter(size=3))
    mask = mask.point(lambda value: 255 if value > alpha_threshold else 0)
    bbox = mask.getbbox()
    if not bbox:
        return None
    mask_ratio = _mask_area(mask) / max(mask.width * mask.height, 1)
    if mask_ratio < min_mask_ratio or mask_ratio > max_mask_ratio:
        return None

    rgba = original_crop.copy()
    rgba.putalpha(mask)
    cropped = rgba.crop(bbox)
    out_path = paths.assets_dir / f"{cell['roiId']}__layer_{layer_index:02d}.png"
    cropped.save(out_path)
    page_bbox = BBox.from_dict(cell["pageBBox"])
    asset_bbox = BBox(
        page_bbox.x + bbox[0],
        page_bbox.y + bbox[1],
        bbox[2] - bbox[0],
        bbox[3] - bbox[1],
    )
    return {
        "id": f"{cell['roiId']}__layer_{layer_index:02d}",
        "roiId": cell["roiId"],
        "kind": cell.get("kind", "asset"),
        "source": "qwen_masked_original",
        "primary": False,
        "path": rel(out_path, paths.root),
        "bboxOnPage": asset_bbox.to_dict(),
        "width": cropped.width,
        "height": cropped.height,
        "sourceLayer": rel(layer_path, paths.root),
        "maskRatio": round(mask_ratio, 4),
    }


def _extract_full_page_components(
    paths: RunPaths,
    alpha_threshold: int,
    min_component_area_ratio: float = 0.00018,
    max_component_area_ratio: float = 0.18,
    merge_filter_size: int = 5,
    bbox_padding: int = 2,
    min_page_side: int = 12,
) -> list[dict[str, Any]]:
    if not paths.qwen_full_manifest_json.exists():
        return []

    manifest = read_json(paths.qwen_full_manifest_json)
    result = manifest.get("result", {})
    if not result.get("ok"):
        return []

    source = Image.open(source_image_path(paths)).convert("RGBA")
    page_width, page_height = source.size
    assets: list[dict[str, Any]] = []

    for layer_index, layer_rel in enumerate(result.get("layers", [])):
        if layer_index == 0:
            continue
        layer_path = paths.root / layer_rel
        if not layer_path.exists():
            continue

        layer = Image.open(layer_path).convert("RGBA")
        mask = _mask_from_layer(layer, alpha_threshold)
        mask = mask.filter(ImageFilter.MedianFilter(size=3))
        mask = mask.point(lambda value: 255 if value > alpha_threshold else 0)
        mask_ratio = _mask_area(mask) / max(mask.width * mask.height, 1)
        if mask_ratio <= 0:
            continue

        component_mask = mask.filter(ImageFilter.MaxFilter(size=merge_filter_size))
        component_mask = component_mask.point(lambda value: 255 if value > alpha_threshold else 0)
        min_area = max(8, round(mask.width * mask.height * min_component_area_ratio))
        component_boxes = _connected_component_boxes(component_mask, min_area)

        sx = page_width / max(mask.width, 1)
        sy = page_height / max(mask.height, 1)
        for component_index, component in enumerate(component_boxes):
            layer_area_ratio = component["area"] / max(mask.width * mask.height, 1)
            if layer_area_ratio > max_component_area_ratio:
                continue

            lx1, ly1, lx2, ly2 = component["bbox"]
            lx1 = max(0, lx1 - bbox_padding)
            ly1 = max(0, ly1 - bbox_padding)
            lx2 = min(mask.width, lx2 + bbox_padding)
            ly2 = min(mask.height, ly2 + bbox_padding)
            page_box = BBox(
                math.floor(lx1 * sx),
                math.floor(ly1 * sy),
                max(1, math.ceil(lx2 * sx) - math.floor(lx1 * sx)),
                max(1, math.ceil(ly2 * sy) - math.floor(ly1 * sy)),
            ).clamp(page_width, page_height)
            if page_box.area() <= 0:
                continue

            alpha = mask.crop((lx1, ly1, lx2, ly2)).resize((page_box.width, page_box.height), Image.Resampling.LANCZOS)
            alpha = alpha.point(lambda value: 255 if value > alpha_threshold else 0)
            tight = alpha.getbbox()
            if not tight:
                continue

            page_box = BBox(
                page_box.x + tight[0],
                page_box.y + tight[1],
                tight[2] - tight[0],
                tight[3] - tight[1],
            ).clamp(page_width, page_height)
            if page_box.area() <= 0 or min(page_box.width, page_box.height) < min_page_side:
                continue

            alpha = alpha.crop(tight)
            rgba = source.crop((page_box.x, page_box.y, page_box.x + page_box.width, page_box.y + page_box.height))
            if alpha.size != rgba.size:
                alpha = alpha.resize(rgba.size, Image.Resampling.LANCZOS)
                alpha = alpha.point(lambda value: 255 if value > alpha_threshold else 0)
            rgba.putalpha(alpha)

            out_id = f"full_page__layer_{layer_index:02d}__component_{component_index:03d}"
            out_path = paths.assets_dir / f"{out_id}.png"
            rgba.save(out_path)
            assets.append(
                {
                    "id": out_id,
                    "roiId": "full_page",
                    "kind": "qwen_full_component",
                    "source": "qwen_full_component_masked_original",
                    "primary": False,
                    "path": rel(out_path, paths.root),
                    "bboxOnPage": page_box.to_dict(),
                    "width": rgba.width,
                    "height": rgba.height,
                    "sourceLayer": rel(layer_path, paths.root),
                    "sourceLayerIndex": layer_index,
                    "layerMaskRatio": round(mask_ratio, 4),
                    "componentAreaLayerPx": component["area"],
                    "componentAreaRatio": round(layer_area_ratio, 5),
                }
            )

    return sorted(assets, key=lambda asset: (asset["sourceLayerIndex"], asset["bboxOnPage"]["y"], asset["bboxOnPage"]["x"]))


def _connected_component_boxes(mask: Image.Image, min_area: int) -> list[dict[str, Any]]:
    binary = mask.convert("L")
    width, height = binary.size
    data = binary.tobytes()
    visited = bytearray(width * height)
    components: list[dict[str, Any]] = []

    for start, value in enumerate(data):
        if value == 0 or visited[start]:
            continue

        stack = [start]
        visited[start] = 1
        area = 0
        min_x = width
        min_y = height
        max_x = -1
        max_y = -1

        while stack:
            index = stack.pop()
            y, x = divmod(index, width)
            area += 1
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

            if x > 0:
                neighbor = index - 1
                if data[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    stack.append(neighbor)
            if x + 1 < width:
                neighbor = index + 1
                if data[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    stack.append(neighbor)
            if y > 0:
                neighbor = index - width
                if data[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    stack.append(neighbor)
            if y + 1 < height:
                neighbor = index + width
                if data[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    stack.append(neighbor)

        if area >= min_area:
            components.append({"bbox": (min_x, min_y, max_x + 1, max_y + 1), "area": area})

    return sorted(components, key=lambda component: (component["bbox"][1], component["bbox"][0]))


def _mask_from_layer(layer_crop: Image.Image, alpha_threshold: int) -> Image.Image:
    alpha = layer_crop.getchannel("A")
    alpha_min, alpha_max = alpha.getextrema()
    if alpha_max <= alpha_threshold:
        return Image.new("L", layer_crop.size, 0)
    if alpha_min < alpha_max and alpha_max > alpha_threshold:
        return alpha
    if alpha_min < 250 or alpha_max < 250:
        return Image.new("L", layer_crop.size, 0)
    rgb = layer_crop.convert("RGB")
    white = Image.new("RGB", rgb.size, "white")
    diff = ImageChops.difference(rgb, white).convert("L")
    return diff.point(lambda value: 255 if value > alpha_threshold else 0)


def _mask_area(mask: Image.Image) -> int:
    histogram = mask.histogram()
    return sum(count for value, count in enumerate(histogram) if value > 0)
