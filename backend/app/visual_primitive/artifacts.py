from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ..png_tools import PngPixels, PngRegion, UnsupportedPngCropError, crop_mask_pixels_to_rgba_png, decode_png_pixels, encode_rgb_png
from .bbox import bbox_area, bbox_clamp
from .mask import M29BinaryMask, mask_to_png
from .pixels import crop_pixels, draw_rect
from .types import M29BlockedPrimitive, M29ConnectedComponent, M29DebugArtifacts, M29PrimitiveNode, OVERLAY_COLORS


def export_node_assets(nodes: list[M29PrimitiveNode], pixels: PngPixels, output_dir: Path) -> list[M29PrimitiveNode]:
    image_dir = output_dir / "assets" / "images"
    symbol_dir = output_dir / "assets" / "symbols"
    image_dir.mkdir(parents=True, exist_ok=True)
    symbol_dir.mkdir(parents=True, exist_ok=True)
    image_count = 0
    symbol_count = 0
    exported: list[M29PrimitiveNode] = []
    for node in nodes:
        if node.type == "image":
            image_count += 1
            path = image_dir / f"image_{image_count:03d}.png"
            path.write_bytes(crop_pixels(pixels, node.bbox))
            exported.append(replace(node, asset_path=str(path.relative_to(output_dir))))
        elif node.type == "symbol":
            symbol_count += 1
            path = symbol_dir / f"symbol_{symbol_count:03d}.png"
            if node.mask_data is not None:
                x, y, w, h = node.bbox
                region = PngRegion("symbol", x, y, w, h)
                try:
                    path.write_bytes(crop_mask_pixels_to_rgba_png(pixels, node.mask_data, region))
                except Exception:
                    path.write_bytes(crop_pixels(pixels, node.bbox))
            else:
                path.write_bytes(crop_pixels(pixels, node.bbox))
            exported.append(replace(node, asset_path=str(path.relative_to(output_dir))))
        else:
            exported.append(node)
    return exported

def write_debug_overlays(
    *,
    pixels: PngPixels,
    output_dir: Path,
    text_mask: M29BinaryMask,
    initial_components: list[M29ConnectedComponent],
    shapes: list[M29PrimitiveNode],
    images: list[M29PrimitiveNode],
    image_mask: M29BinaryMask,
    foreground: M29BinaryMask,
    symbols: list[M29PrimitiveNode],
    nodes: list[M29PrimitiveNode],
    blocked: list[M29BlockedPrimitive],
) -> M29DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "text_exclusion": overlay_dir / "01_text_exclusion.png",
        "initial_components": overlay_dir / "02_initial_components.png",
        "shapes": overlay_dir / "03_shapes.png",
        "images": overlay_dir / "04_images.png",
        "image_protection": overlay_dir / "05_image_protection.png",
        "foreground_mask": overlay_dir / "06_foreground_mask.png",
        "symbols": overlay_dir / "07_symbols.png",
        "final_nodes": overlay_dir / "08_final_nodes.png",
    }
    paths["text_exclusion"].write_bytes(mask_to_png(text_mask))
    paths["initial_components"].write_bytes(overlay_components(pixels, initial_components))
    paths["shapes"].write_bytes(overlay_nodes(pixels, shapes, []))
    paths["images"].write_bytes(overlay_nodes(pixels, images, []))
    paths["image_protection"].write_bytes(mask_to_png(image_mask))
    paths["foreground_mask"].write_bytes(mask_to_png(foreground))
    paths["symbols"].write_bytes(overlay_nodes(pixels, symbols, blocked))
    paths["final_nodes"].write_bytes(overlay_nodes(pixels, nodes, blocked))
    return M29DebugArtifacts(**{key: str(path.relative_to(output_dir)) for key, path in paths.items()})

def overlay_components(pixels: PngPixels, components: list[M29ConnectedComponent]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for component in components:
        draw_rect(rows, pixels.width, pixels.height, component.bbox, (238, 190, 40), 1)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def overlay_nodes(pixels: PngPixels, nodes: list[M29PrimitiveNode], blocked: list[M29BlockedPrimitive]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in blocked:
        color = OVERLAY_COLORS["protected"] if "inside_image_primitive" in item.reasons else OVERLAY_COLORS["blocked"]
        draw_rect(rows, pixels.width, pixels.height, item.bbox, color, 1)
    for node in nodes:
        draw_rect(rows, pixels.width, pixels.height, node.bbox, OVERLAY_COLORS[node.type], 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def build_preview_sheet(
    pixels: PngPixels,
    output_dir: Path,
    debug: M29DebugArtifacts,
    nodes: list[M29PrimitiveNode] | None = None,
    blocked: list[M29BlockedPrimitive] | None = None,
) -> bytes:
    final_overlay = decode_png_pixels((output_dir / (debug.final_nodes or "overlays/08_final_nodes.png")).read_bytes())
    image_previews = crop_previews(output_dir / "assets" / "images", 160)
    symbol_previews = crop_previews(output_dir / "assets" / "symbols", 96)
    unknown_previews = bbox_previews(pixels, [node.bbox for node in nodes or [] if node.type == "unknown"], 96)
    blocked_previews = bbox_previews(pixels, [item.bbox for item in blocked or []], 72)
    preview_sections = [section for section in [image_previews, symbol_previews, unknown_previews, blocked_previews] if section]
    sheet_width = 1400
    margin = 24
    gap = 18
    source_scale = min(0.55, (sheet_width - margin * 2 - gap) / max(1, pixels.width * 2))
    source_w = max(1, round(pixels.width * source_scale))
    source_h = max(1, round(pixels.height * source_scale))
    sheet_height = source_h + sum(grid_height(section, sheet_width, margin, gap) for section in preview_sections) + margin * (3 + len(preview_sections))
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    y = margin
    paste_scaled(canvas, sheet_width, pixels, margin, y, source_w, source_h)
    paste_scaled(canvas, sheet_width, final_overlay, margin + source_w + gap, y, source_w, source_h)
    y += source_h + margin
    for section in preview_sections:
        y = paste_grid(canvas, sheet_width, section, margin, y, gap) + margin
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])

def crop_previews(path: Path, max_edge: int) -> list[tuple[PngPixels, int, int]]:
    previews: list[tuple[PngPixels, int, int]] = []
    if not path.exists():
        return previews
    for item in sorted(path.glob("*.png")):
        try:
            pixels = decode_png_pixels(item.read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, pixels.width, pixels.height))
        previews.append((pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews

def bbox_previews(pixels: PngPixels, bboxes: list[list[int]], max_edge: int) -> list[tuple[PngPixels, int, int]]:
    previews: list[tuple[PngPixels, int, int]] = []
    for bbox in sorted(bboxes, key=lambda item: (item[1], item[0], bbox_area(item))):
        clamped = bbox_clamp(bbox, pixels.width, pixels.height)
        if clamped is None:
            continue
        x, y, width, height = clamped
        rows = [pixels.rows[row_index][x * 3 : (x + width) * 3] for row_index in range(y, y + height)]
        preview = PngPixels(width=width, height=height, rows=rows)
        scale = min(1.0, max_edge / max(1, width, height))
        previews.append((preview, max(1, round(width * scale)), max(1, round(height * scale))))
    return previews

def grid_height(previews: list[tuple[PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 70
    x = margin
    row_h = 0
    total = 0
    for _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h

def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[PngPixels, int, int]], margin: int, y: int, gap: int) -> int:
    if not previews:
        fill_rect(canvas, sheet_width, y, margin, sheet_width - margin * 2, 48, (232, 232, 232))
        return y + 48
    x = margin
    row_h = 0
    for preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, y - 3, x - 3, width + 6, height + 6, (232, 232, 232))
        paste_scaled(canvas, sheet_width, preview, x, y, width, height)
        x += width + gap
        row_h = max(row_h, height)
    return y + row_h

def paste_scaled(canvas: list[bytearray], sheet_width: int, source: PngPixels, x: int, y: int, target_width: int, target_height: int) -> None:
    for target_y in range(target_height):
        source_y = min(source.height - 1, round(target_y * source.height / target_height))
        if y + target_y < 0 or y + target_y >= len(canvas):
            continue
        source_row = source.rows[source_y]
        target_row = canvas[y + target_y]
        for target_x in range(target_width):
            source_x = min(source.width - 1, round(target_x * source.width / target_width))
            dst_x = x + target_x
            if 0 <= dst_x < sheet_width:
                target_row[dst_x * 3 : dst_x * 3 + 3] = source_row[source_x * 3 : source_x * 3 + 3]

def fill_rect(canvas: list[bytearray], sheet_width: int, y: int, x: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            row[column * 3 : column * 3 + 3] = color_bytes
