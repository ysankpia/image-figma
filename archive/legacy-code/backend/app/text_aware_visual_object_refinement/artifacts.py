from __future__ import annotations

from pathlib import Path

from ..png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png
from ..visual_primitive_graph import crop_pixels, draw_rect
from .types import (
    M2905DebugArtifacts,
    M2905Options,
    RefinedObjectDecision,
    RefinedTextMember,
    RefinedVisualAsset,
    RefinedVisualObject,
    ShapeCandidate,
    UnresolvedMember,
)


def export_crop(pixels: PngPixels, output_dir: Path, folder: str, id: str, bbox: list[int]) -> str:
    target = output_dir / "assets" / folder
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{id}.png"
    path.write_bytes(crop_pixels(pixels, bbox))
    return str(path.relative_to(output_dir))

def write_debug_artifacts(
    pixels: PngPixels,
    output_dir: Path,
    objects: list[RefinedVisualObject],
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
) -> M2905DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    visual_assets_path = overlay_dir / "20_visual_assets.png"
    text_members_path = overlay_dir / "21_text_members.png"
    separation_path = overlay_dir / "22_text_visual_separation.png"
    unresolved_path = overlay_dir / "23_unresolved_refinement.png"
    shape_path = overlay_dir / "24_shape_candidates.png"
    visual_assets_path.write_bytes(overlay_visual_assets(pixels, visual_assets))
    text_members_path.write_bytes(overlay_text_members(pixels, text_members))
    separation_path.write_bytes(overlay_separation(pixels, objects, visual_assets, shape_candidates, text_members, unresolved_members))
    unresolved_path.write_bytes(overlay_unresolved(pixels, objects, unresolved_members))
    shape_path.write_bytes(overlay_shapes(pixels, shape_candidates))
    return M2905DebugArtifacts(
        visual_assets=str(visual_assets_path.relative_to(output_dir)),
        text_members=str(text_members_path.relative_to(output_dir)),
        text_visual_separation=str(separation_path.relative_to(output_dir)),
        unresolved_refinement=str(unresolved_path.relative_to(output_dir)),
        shape_candidates=str(shape_path.relative_to(output_dir)),
    )

def overlay_visual_assets(pixels: PngPixels, visual_assets: list[RefinedVisualAsset]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in visual_assets:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (0, 200, 90), 3)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def overlay_text_members(pixels: PngPixels, text_members: list[RefinedTextMember]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in text_members:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (238, 190, 40), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def overlay_shapes(pixels: PngPixels, shape_candidates: list[ShapeCandidate]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in shape_candidates:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (0, 122, 255), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def overlay_unresolved(pixels: PngPixels, objects: list[RefinedVisualObject], unresolved_members: list[UnresolvedMember]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in objects:
        if item.decision in {"unresolved", "partially_separated", "split_needed", "rejected"}:
            draw_rect(rows, pixels.width, pixels.height, item.bbox, object_color(item), 2)
    for item in unresolved_members:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (235, 64, 52), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def overlay_separation(
    pixels: PngPixels,
    objects: list[RefinedVisualObject],
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in objects:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, object_color(item), 1)
    for item in visual_assets:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (0, 200, 90), 3)
    for item in shape_candidates:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (0, 122, 255), 2)
    for item in text_members:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (238, 190, 40), 2)
    for item in unresolved_members:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (235, 64, 52), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def build_preview_sheet(
    pixels: PngPixels,
    output_dir: Path,
    debug: M2905DebugArtifacts,
    objects: list[RefinedVisualObject],
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
    options: M2905Options,
) -> bytes:
    overlays = [decode_png_pixels((output_dir / path).read_bytes()) for path in debug.to_dict().values()]
    sheet_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.26, (sheet_width - margin * 2 - gap * 5) / max(1, pixels.width * 6))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    previews = crop_previews(output_dir, objects, visual_assets, shape_candidates, text_members, unresolved_members, options.output_preview_max_thumb)
    grid_h = grid_height(previews, sheet_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    x = margin
    for image in [pixels, *overlays]:
        paste_scaled(canvas, sheet_width, image, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, sheet_width, previews, margin, margin + top_h + margin, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])

def crop_previews(
    output_dir: Path,
    objects: list[RefinedVisualObject],
    visual_assets: list[RefinedVisualAsset],
    shape_candidates: list[ShapeCandidate],
    text_members: list[RefinedTextMember],
    unresolved_members: list[UnresolvedMember],
    max_edge: int,
) -> list[tuple[str, list[int], str, PngPixels, int, int]]:
    items: list[tuple[str, list[int], str | None, str]] = []
    items.extend((f"combined:{item.id}", item.bbox, item.combined_asset_path, color_key_for_decision(item.decision)) for item in objects[:80])
    items.extend((f"visual:{item.id}", item.bbox, item.asset_path, "visual") for item in visual_assets)
    items.extend((f"shape:{item.id}", item.bbox, item.preview_asset_path, "shape") for item in shape_candidates)
    items.extend((f"text:{item.id}", item.bbox, item.preview_asset_path, "text") for item in text_members[:120])
    unresolved_by_id = {item.id: item for item in unresolved_members}
    for item in unresolved_members[:120]:
        path = export_existing_preview(output_dir, "unresolved_objects", item.id, item.bbox)
        items.append((f"unresolved:{item.id}", item.bbox, path, "unresolved"))
        unresolved_by_id[item.id] = item
    previews: list[tuple[str, list[int], str, PngPixels, int, int]] = []
    for label, bbox, path, color_key in items:
        if not path:
            continue
        try:
            crop = decode_png_pixels((output_dir / path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, crop.width, crop.height))
        previews.append((label, bbox, color_key, crop, max(1, round(crop.width * scale)), max(1, round(crop.height * scale))))
    return previews

def export_existing_preview(output_dir: Path, folder: str, id: str, bbox: list[int]) -> str | None:
    # Unresolved member previews are optional in the schema; this helper only reuses
    # already-written object crops when present and otherwise leaves the preview out.
    candidates = sorted((output_dir / "assets" / folder).glob("*.png")) if (output_dir / "assets" / folder).exists() else []
    return str(candidates[0].relative_to(output_dir)) if candidates else None

def object_color(item: RefinedVisualObject) -> tuple[int, int, int]:
    return {
        "separated": (0, 200, 90),
        "visual_only": (0, 180, 210),
        "text_only": (238, 190, 40),
        "partially_separated": (238, 140, 40),
        "unresolved": (235, 64, 52),
        "split_needed": (180, 60, 220),
        "rejected": (170, 170, 170),
    }[item.decision]

def color_key_for_decision(decision: RefinedObjectDecision) -> str:
    return {
        "separated": "visual",
        "visual_only": "visual",
        "text_only": "text",
        "partially_separated": "partial",
        "unresolved": "unresolved",
        "split_needed": "split",
        "rejected": "rejected",
    }[decision]

def frame_color(key: str) -> tuple[int, int, int]:
    return {
        "visual": (0, 200, 90),
        "shape": (0, 122, 255),
        "text": (238, 190, 40),
        "partial": (238, 140, 40),
        "unresolved": (235, 64, 52),
        "split": (180, 60, 220),
        "rejected": (170, 170, 170),
    }.get(key, (170, 170, 170))

def grid_height(previews: list[tuple[str, list[int], str, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 48
    x = margin
    row_h = 0
    total = 0
    for _label, _bbox, _key, _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h

def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[str, list[int], str, PngPixels, int, int]], x: int, y: int, gap: int) -> int:
    row_h = 0
    margin = x
    if not previews:
        fill_rect(canvas, sheet_width, x, y, sheet_width - x * 2, 48, (232, 232, 232))
        return y + 48
    for _label, _bbox, key, preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, frame_color(key))
        fill_rect(canvas, sheet_width, x - 2, y - 2, width + 4, height + 4, (244, 244, 244))
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

def fill_rect(canvas: list[bytearray], sheet_width: int, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            row[column * 3 : column * 3 + 3] = color_bytes
