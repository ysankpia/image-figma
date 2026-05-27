from __future__ import annotations

import zlib
from pathlib import Path
from typing import Any

from ..m29_materialization_utils import list_dicts, map_page_bbox_to_asset_pixels, sample_outer_bbox_ring_rgb
from ..png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, parse_chunks, read_png_metadata, unfilter_rows
from ..visual_primitive_graph import bbox_clamp
from .background import sample_canvas_background
from .types import ReplayNode


def clean_text_from_copied_image_assets(
    dsl: dict[str, Any],
    output_dir: Path,
    replayed: list[ReplayNode],
    *,
    plan_items: list[dict[str, Any]] | None = None,
) -> int:
    text_nodes = [item for item in replayed if item.role == "m29_text" and item.replay_decision in {"ocr_text_replay", "text_replay"}]
    image_nodes = [item for item in replayed if item.role == "m29_image" and item.asset_url]
    if not text_nodes or not image_nodes:
        return 0

    assets = {
        str(asset.get("assetId")): asset
        for asset in list_dicts(dsl.get("assets"))
        if asset.get("assetId") and asset.get("role") == "m29_image"
    }
    erased_count = 0
    for image_node in image_nodes:
        if image_node.asset_id and image_node.asset_id not in assets:
            continue
        image_path = (output_dir / str(image_node.asset_url)).resolve()
        if not image_path.exists():
            continue
        try:
            pixels = decode_png_pixels(image_path.read_bytes())
        except Exception:
            continue

        scale_x = pixels.width / max(1, image_node.bbox[2])
        scale_y = pixels.height / max(1, image_node.bbox[3])
        rows = [bytearray(row) for row in pixels.rows]
        modified = False
        for text_node in text_nodes:
            if not plan_allows_copied_image_cleanup(plan_items or [], text_node.source_id, image_node.source_id):
                continue
            local_bbox = map_page_bbox_to_asset_pixels(text_node.bbox, image_node.bbox, pixels.width, pixels.height, scale_x, scale_y)
            if local_bbox is None:
                continue
            try:
                fill = sample_outer_bbox_ring_rgb(pixels, local_bbox)
            except Exception:
                fill = sample_canvas_background(pixels)
            x, y, width, height = local_bbox
            for row_idx in range(y, y + height):
                row = rows[row_idx]
                for col_idx in range(x, x + width):
                    offset = col_idx * 3
                    row[offset] = fill[0]
                    row[offset + 1] = fill[1]
                    row[offset + 2] = fill[2]
            modified = True
            erased_count += 1
        if modified:
            image_path.write_bytes(encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows]))
    return erased_count


def clean_internal_assets_from_copied_image_assets(
    dsl: dict[str, Any],
    output_dir: Path,
    replayed: list[ReplayNode],
    *,
    plan_items: list[dict[str, Any]] | None = None,
) -> int:
    symbol_nodes = [item for item in replayed if item.role == "m29_symbol" and item.replay_decision == "icon_replay" and item.asset_url]
    image_nodes = [item for item in replayed if item.role == "m29_image" and item.asset_url]
    if not symbol_nodes or not image_nodes:
        return 0

    assets = {
        str(asset.get("assetId")): asset
        for asset in list_dicts(dsl.get("assets"))
        if asset.get("assetId") and asset.get("role") in {"m29_image", "m29_symbol"}
    }
    erased_count = 0
    for image_node in image_nodes:
        if image_node.asset_id and image_node.asset_id not in assets:
            continue
        image_path = (output_dir / str(image_node.asset_url)).resolve()
        if not image_path.exists():
            continue
        try:
            pixels = decode_png_pixels(image_path.read_bytes())
        except Exception:
            continue

        scale_x = pixels.width / max(1, image_node.bbox[2])
        scale_y = pixels.height / max(1, image_node.bbox[3])
        rows = [bytearray(row) for row in pixels.rows]
        modified = False
        for symbol_node in symbol_nodes:
            if not plan_allows_internal_asset_copied_image_cleanup(plan_items or [], symbol_node.source_id, image_node.source_id):
                continue
            local_bbox = map_page_bbox_to_asset_pixels(symbol_node.bbox, image_node.bbox, pixels.width, pixels.height, scale_x, scale_y)
            if local_bbox is None:
                continue
            try:
                fill = sample_outer_bbox_ring_rgb(pixels, local_bbox)
            except Exception:
                fill = sample_canvas_background(pixels)
            try:
                alpha = read_png_alpha_mask((output_dir / str(symbol_node.asset_url)).resolve())
            except Exception:
                alpha = None
            erase_with_alpha_mask(rows, local_bbox, fill, alpha)
            modified = True
            erased_count += 1
        if modified:
            image_path.write_bytes(encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows]))
    return erased_count


def clean_shape_backgrounds_from_copied_image_assets(
    dsl: dict[str, Any],
    output_dir: Path,
    replayed: list[ReplayNode],
    *,
    plan_items: list[dict[str, Any]] | None = None,
) -> int:
    shape_nodes = [item for item in replayed if item.role == "m29_shape" and item.replay_decision == "simple_shape_replay"]
    image_nodes = [item for item in replayed if item.role == "m29_image" and item.asset_url]
    if not shape_nodes or not image_nodes:
        return 0

    assets = {
        str(asset.get("assetId")): asset
        for asset in list_dicts(dsl.get("assets"))
        if asset.get("assetId") and asset.get("role") == "m29_image"
    }
    erased_count = 0
    for image_node in image_nodes:
        if image_node.asset_id and image_node.asset_id not in assets:
            continue
        image_path = (output_dir / str(image_node.asset_url)).resolve()
        if not image_path.exists():
            continue
        try:
            pixels = decode_png_pixels(image_path.read_bytes())
        except Exception:
            continue

        scale_x = pixels.width / max(1, image_node.bbox[2])
        scale_y = pixels.height / max(1, image_node.bbox[3])
        rows = [bytearray(row) for row in pixels.rows]
        modified = False
        for shape_node in shape_nodes:
            cleanup_target = shape_copied_image_cleanup_target(plan_items or [], shape_node.source_id, image_node.source_id)
            if cleanup_target is None:
                continue
            local_bbox = map_page_bbox_to_asset_pixels(shape_node.bbox, image_node.bbox, pixels.width, pixels.height, scale_x, scale_y)
            if local_bbox is None:
                continue
            try:
                fill = sample_outer_bbox_ring_rgb(pixels, local_bbox)
            except Exception:
                fill = sample_canvas_background(pixels)
            erase_with_geometry_mask(rows, local_bbox, fill, str(cleanup_target.get("maskKind") or "bbox"), numeric_mask_radius(cleanup_target.get("maskRadius")))
            modified = True
            erased_count += 1
        if modified:
            image_path.write_bytes(encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows]))
    return erased_count


def plan_allows_copied_image_cleanup(plan_items: list[dict[str, Any]], text_source_id: str, image_source_id: str) -> bool:
    for item in plan_items:
        if str(item.get("sourceObjectId") or "") != text_source_id:
            continue
        if item.get("finalReplayAction") != "text_replay":
            return False
        for target in item.get("cleanupTargets", []) if isinstance(item.get("cleanupTargets"), list) else []:
            if (
                isinstance(target, dict)
                and target.get("target") == "copied_image_asset"
                and str(target.get("targetSourceObjectId") or "") == image_source_id
            ):
                return True
    return False


def plan_allows_internal_asset_copied_image_cleanup(plan_items: list[dict[str, Any]], symbol_source_id: str, image_source_id: str) -> bool:
    for item in plan_items:
        if str(item.get("sourceObjectId") or "") != symbol_source_id:
            continue
        if item.get("finalReplayAction") != "icon_replay":
            return False
        for target in item.get("cleanupTargets", []) if isinstance(item.get("cleanupTargets"), list) else []:
            if (
                isinstance(target, dict)
                and target.get("target") == "copied_image_asset"
                and target.get("reason") in {
                    "promoted_internal_asset_contained_by_media",
                    "label_anchored_blocked_asset_contained_by_media",
                    "foreground_claim_removed_from_residual_media",
                }
                and str(target.get("targetSourceObjectId") or "") == image_source_id
            ):
                return True
    return False


def plan_allows_shape_copied_image_cleanup(plan_items: list[dict[str, Any]], shape_source_id: str, image_source_id: str) -> bool:
    return shape_copied_image_cleanup_target(plan_items, shape_source_id, image_source_id) is not None


def shape_copied_image_cleanup_target(plan_items: list[dict[str, Any]], shape_source_id: str, image_source_id: str) -> dict[str, Any] | None:
    for item in plan_items:
        if str(item.get("sourceObjectId") or "") != shape_source_id:
            continue
        if item.get("finalReplayAction") != "shape_replay":
            return None
        for target in item.get("cleanupTargets", []) if isinstance(item.get("cleanupTargets"), list) else []:
            if (
                isinstance(target, dict)
                and target.get("target") == "copied_image_asset"
                and target.get("reason") in {"shape_background_contained_by_media", "foreground_claim_removed_from_residual_media"}
                and str(target.get("targetSourceObjectId") or "") == image_source_id
            ):
                return target
    return None


def erase_with_alpha_mask(
    rows: list[bytearray],
    local_bbox: list[int],
    fill: tuple[int, int, int],
    alpha: tuple[int, int, bytes] | None,
) -> None:
    x, y, width, height = local_bbox
    alpha_width = alpha[0] if alpha is not None else width
    alpha_height = alpha[1] if alpha is not None else height
    alpha_data = alpha[2] if alpha is not None else None
    for row_offset in range(height):
        row_idx = y + row_offset
        row = rows[row_idx]
        for col_offset in range(width):
            should_erase = True
            if alpha_data is not None:
                alpha_x = min(alpha_width - 1, round(col_offset * alpha_width / max(1, width)))
                alpha_y = min(alpha_height - 1, round(row_offset * alpha_height / max(1, height)))
                should_erase = alpha_data[alpha_y * alpha_width + alpha_x] > 32
            if not should_erase:
                continue
            col_idx = x + col_offset
            offset = col_idx * 3
            row[offset] = fill[0]
            row[offset + 1] = fill[1]
            row[offset + 2] = fill[2]


def erase_with_geometry_mask(rows: list[bytearray], local_bbox: list[int], fill: tuple[int, int, int], mask_kind: str, mask_radius: int | None = None) -> None:
    x, y, width, height = local_bbox
    for row_offset in range(height):
        row = rows[y + row_offset]
        for col_offset in range(width):
            if not geometry_mask_contains(col_offset, row_offset, width, height, mask_kind, mask_radius):
                continue
            col_idx = x + col_offset
            offset = col_idx * 3
            row[offset] = fill[0]
            row[offset + 1] = fill[1]
            row[offset + 2] = fill[2]


def geometry_mask_contains(col_offset: int, row_offset: int, width: int, height: int, mask_kind: str, mask_radius: int | None = None) -> bool:
    if mask_kind == "circle":
        radius = min(width, height) / 2.0
        cx = (width - 1) / 2.0
        cy = (height - 1) / 2.0
        return (col_offset - cx) ** 2 + (row_offset - cy) ** 2 <= radius**2
    if mask_kind == "rounded_rect":
        radius = min(width, height) / 2.0 if mask_radius is None else max(0.0, min(float(mask_radius), min(width, height) / 2.0))
        left = radius
        right = width - 1 - radius
        top = radius
        bottom = height - 1 - radius
        if left <= col_offset <= right or top <= row_offset <= bottom:
            return True
        cx = left if col_offset < left else right
        cy = top if row_offset < top else bottom
        return (col_offset - cx) ** 2 + (row_offset - cy) ** 2 <= radius**2
    return True


def numeric_mask_radius(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return max(0, round(float(value)))
    except (TypeError, ValueError):
        return None


def read_png_alpha_mask(path: Path) -> tuple[int, int, bytes] | None:
    if not path.exists():
        return None
    data = path.read_bytes()
    metadata = read_png_metadata(data)
    if metadata is None or metadata.bit_depth != 8 or metadata.color_type != 6 or metadata.interlace != 0:
        return None
    chunks = parse_chunks(data)
    idat = b"".join(chunk_data for chunk_type, chunk_data in chunks if chunk_type == b"IDAT")
    try:
        raw = zlib.decompress(idat)
    except zlib.error as error:
        raise UnsupportedPngCropError("PNG IDAT data could not be decompressed.") from error
    rows = unfilter_rows(raw, metadata.width, metadata.height, 4)
    alpha = bytearray(metadata.width * metadata.height)
    for row_idx, row in enumerate(rows):
        for col_idx in range(metadata.width):
            alpha[row_idx * metadata.width + col_idx] = row[col_idx * 4 + 3]
    return metadata.width, metadata.height, bytes(alpha)


def erase_replayed_bboxes_from_fallback(
    dsl: dict[str, Any],
    output_dir: Path,
    source_pixels: PngPixels,
    replayed: list[ReplayNode],
    *,
    plan_items: list[dict[str, Any]],
) -> int:
    fallback_assets = [asset for asset in list_dicts(dsl.get("assets")) if asset.get("role") == "fallback_region" and asset.get("type") == "image"]
    if not fallback_assets or not replayed:
        return 0
    erased = 0
    for asset in fallback_assets:
        path = output_dir / str(asset.get("url") or "")
        if not path.exists():
            continue
        try:
            pixels = decode_png_pixels(path.read_bytes())
        except Exception:
            continue
        rows = [bytearray(row) for row in pixels.rows]
        modified = False
        for item in replayed:
            if not plan_allows_fallback_cleanup(plan_items, item.source_id):
                continue
            bbox = bbox_clamp(item.bbox, pixels.width, pixels.height)
            if bbox is None:
                continue
            fill = sample_outer_bbox_ring_rgb(source_pixels, bbox)
            x, y, width, height = bbox
            for row_idx in range(y, y + height):
                row = rows[row_idx]
                for col_idx in range(x, x + width):
                    offset = col_idx * 3
                    row[offset] = fill[0]
                    row[offset + 1] = fill[1]
                    row[offset + 2] = fill[2]
            modified = True
            erased += 1
        if modified:
            path.write_bytes(encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows]))
    return erased


def plan_allows_fallback_cleanup(plan_items: list[dict[str, Any]], source_id: str) -> bool:
    for item in plan_items:
        if str(item.get("sourceObjectId") or "") != source_id:
            continue
        if item.get("finalReplayAction") not in {"text_replay", "image_replay", "icon_replay", "shape_replay"}:
            return False
        for target in item.get("cleanupTargets", []) if isinstance(item.get("cleanupTargets"), list) else []:
            if isinstance(target, dict) and target.get("target") == "fallback":
                return True
    return False
