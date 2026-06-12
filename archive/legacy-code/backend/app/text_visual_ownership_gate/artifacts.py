from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png
from ..visual_primitive_graph import crop_pixels, draw_rect
from .types import M2907DebugArtifacts, M2907Options, OwnershipDecision


def export_examples(pixels: PngPixels, output_dir: Path, decisions: list[OwnershipDecision], options: M2907Options, examples: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    folder_by_ownership = {
        "text_owned": "text_owned_examples",
        "visual_owned": "visual_owned_examples",
        "mixed_or_uncertain": "mixed_or_uncertain_examples",
        "audit_only": "audit_only_examples",
        "shape_owned": "audit_only_examples",
    }
    for item in decisions:
        folder = folder_by_ownership[item.ownership]
        count = counts.get(item.ownership, 0)
        if count >= options.max_examples_per_kind:
            continue
        counts[item.ownership] = count + 1
        target = output_dir / "assets" / folder
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{item.ownership}_{count + 1:04d}_{item.id}.png"
        path.write_bytes(crop_pixels(pixels, item.bbox))
        examples.append({"ownershipDecisionId": item.id, "ownership": item.ownership, "bbox": item.bbox, "assetPath": str(path.relative_to(output_dir))})

def write_debug_artifacts(pixels: PngPixels, output_dir: Path, decisions: list[OwnershipDecision]) -> M2907DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "textOwned": overlay_dir / "29_text_owned.png",
        "visualOwned": overlay_dir / "30_visual_owned.png",
        "mixedOrUncertain": overlay_dir / "31_mixed_or_uncertain.png",
        "objectFormingAllowed": overlay_dir / "32_object_forming_allowed.png",
    }
    paths["textOwned"].write_bytes(overlay_decisions(pixels, decisions, lambda item: item.ownership == "text_owned", (235, 64, 52)))
    paths["visualOwned"].write_bytes(overlay_decisions(pixels, decisions, lambda item: item.ownership == "visual_owned", (0, 122, 255)))
    paths["mixedOrUncertain"].write_bytes(overlay_decisions(pixels, decisions, lambda item: item.ownership == "mixed_or_uncertain", (238, 140, 40)))
    paths["objectFormingAllowed"].write_bytes(overlay_decisions(pixels, decisions, lambda item: item.allowed_for_object_forming_visual_side, (0, 180, 90)))
    return M2907DebugArtifacts(
        text_owned=str(paths["textOwned"].relative_to(output_dir)),
        visual_owned=str(paths["visualOwned"].relative_to(output_dir)),
        mixed_or_uncertain=str(paths["mixedOrUncertain"].relative_to(output_dir)),
        object_forming_allowed=str(paths["objectFormingAllowed"].relative_to(output_dir)),
    )

def overlay_decisions(pixels: PngPixels, decisions: list[OwnershipDecision], include: Any, color: tuple[int, int, int]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in decisions:
        if include(item):
            draw_rect(rows, pixels.width, pixels.height, item.bbox, color, 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def build_preview_sheet(pixels: PngPixels, output_dir: Path, debug: M2907DebugArtifacts, examples: list[dict[str, Any]], options: M2907Options) -> bytes:
    overlays = [decode_png_pixels((output_dir / path).read_bytes()) for path in debug.to_dict().values()]
    sheet_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.32, (sheet_width - margin * 2 - gap * 4) / max(1, pixels.width * 5))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    previews = crop_previews(output_dir, examples, options.output_preview_max_thumb)
    grid_h = grid_height(previews, sheet_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    x = margin
    for image in [pixels, *overlays]:
        paste_scaled(canvas, sheet_width, image, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, sheet_width, previews, margin, margin + top_h + margin, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])

def crop_previews(output_dir: Path, examples: list[dict[str, Any]], max_edge: int) -> list[tuple[str, PngPixels, int, int]]:
    previews: list[tuple[str, PngPixels, int, int]] = []
    for example in examples[:160]:
        path = str(example.get("assetPath") or "")
        if not path:
            continue
        try:
            crop = decode_png_pixels((output_dir / path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, crop.width, crop.height))
        previews.append((str(example.get("ownership") or ""), crop, max(1, round(crop.width * scale)), max(1, round(crop.height * scale))))
    return previews

def grid_height(previews: list[tuple[str, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 48
    x = margin
    row_h = 0
    total = 0
    for _label, _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h

def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[str, PngPixels, int, int]], x: int, y: int, gap: int) -> int:
    row_h = 0
    margin = x
    if not previews:
        fill_rect(canvas, sheet_width, x, y, sheet_width - x * 2, 48, (232, 232, 232))
        return y + 48
    for label, preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, frame_color(label))
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

def frame_color(label: str) -> tuple[int, int, int]:
    if label == "text_owned":
        return (235, 64, 52)
    if label == "visual_owned":
        return (0, 122, 255)
    if label == "mixed_or_uncertain":
        return (238, 140, 40)
    return (170, 170, 170)
