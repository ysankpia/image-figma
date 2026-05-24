from __future__ import annotations

from pathlib import Path

from ..png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png
from ..visual_primitive_graph import bbox_area, crop_pixels, draw_rect
from .types import VisualEvidenceDebugArtifacts, VisualEvidenceItem, VisualEvidenceKind, VisualEvidenceOptions


def export_visual_evidence_asset(
    pixels: PngPixels,
    output_dir: Path,
    visual_kind: VisualEvidenceKind,
    id: str,
    bbox: list[int],
) -> str:
    folder = {
        "accepted_image": "accepted_images",
        "media_candidate": "media_candidates",
        "icon_candidate": "icon_candidates",
        "mixed_symbol_text_candidate": "mixed_symbol_text_candidates",
        "text_noise": "text_noise",
        "other_candidate": "other_candidates",
    }[visual_kind]
    target_dir = output_dir / "assets" / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{id}.png"
    path.write_bytes(crop_pixels(pixels, bbox))
    return str(path.relative_to(output_dir))

def write_debug_artifacts(pixels: PngPixels, output_dir: Path, items: list[VisualEvidenceItem]) -> VisualEvidenceDebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    buckets_path = overlay_dir / "13_visual_evidence_buckets.png"
    media_path = overlay_dir / "14_media_candidates.png"
    noise_path = overlay_dir / "15_text_noise.png"
    buckets_path.write_bytes(overlay_items(pixels, items, {"accepted_image", "media_candidate", "icon_candidate", "mixed_symbol_text_candidate", "other_candidate", "text_noise"}))
    media_path.write_bytes(overlay_items(pixels, items, {"accepted_image", "media_candidate"}))
    noise_path.write_bytes(overlay_items(pixels, items, {"text_noise"}))
    return VisualEvidenceDebugArtifacts(
        visual_evidence_buckets=str(buckets_path.relative_to(output_dir)),
        media_candidates=str(media_path.relative_to(output_dir)),
        text_noise=str(noise_path.relative_to(output_dir)),
    )

def overlay_items(pixels: PngPixels, items: list[VisualEvidenceItem], kinds: set[str]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in items:
        if item.visual_kind not in kinds:
            continue
        draw_rect(rows, pixels.width, pixels.height, item.bbox, item_color(item), 3 if item.decision == "accepted" else 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def build_preview_sheet(
    pixels: PngPixels,
    output_dir: Path,
    debug: VisualEvidenceDebugArtifacts,
    items: list[VisualEvidenceItem],
    options: VisualEvidenceOptions,
) -> bytes:
    bucket_overlay = decode_png_pixels((output_dir / debug.visual_evidence_buckets).read_bytes())
    media_overlay = decode_png_pixels((output_dir / debug.media_candidates).read_bytes())
    noise_overlay = decode_png_pixels((output_dir / debug.text_noise).read_bytes())
    sheet_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.38, (sheet_width - margin * 2 - gap * 3) / max(1, pixels.width * 4))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    crop_items = crop_previews_for_items(output_dir, items, options.output_preview_max_thumb)
    grid_h = grid_height(crop_items, sheet_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    x = margin
    for image in [pixels, bucket_overlay, media_overlay, noise_overlay]:
        paste_scaled(canvas, sheet_width, image, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, sheet_width, crop_items, margin, margin + top_h + margin, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])

def crop_previews_for_items(
    output_dir: Path,
    items: list[VisualEvidenceItem],
    max_edge: int,
) -> list[tuple[VisualEvidenceItem, PngPixels, int, int]]:
    previews: list[tuple[VisualEvidenceItem, PngPixels, int, int]] = []
    for item in sorted(items, key=item_sort_key):
        try:
            pixels = decode_png_pixels((output_dir / item.asset_path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, pixels.width, pixels.height))
        previews.append((item, pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews

def grid_height(previews: list[tuple[VisualEvidenceItem, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 48
    x = margin
    row_h = 0
    total = 0
    for _item, _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h

def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[VisualEvidenceItem, PngPixels, int, int]], x: int, y: int, gap: int) -> int:
    row_h = 0
    margin = x
    if not previews:
        fill_rect(canvas, sheet_width, x, y, sheet_width - x * 2, 48, (232, 232, 232))
        return y + 48
    for item, preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, item_color(item))
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

def item_sort_key(item: VisualEvidenceItem) -> tuple[int, int, int, int, str]:
    kind_rank = {
        "accepted_image": 0,
        "media_candidate": 1,
        "icon_candidate": 2,
        "other_candidate": 3,
        "mixed_symbol_text_candidate": 4,
        "text_noise": 5,
    }.get(item.visual_kind, 9)
    return (kind_rank, -bbox_area(item.bbox), item.bbox[1], item.bbox[0], item.id)

def item_color(item: VisualEvidenceItem) -> tuple[int, int, int]:
    return {
        "accepted_image": (0, 180, 210),
        "media_candidate": (235, 64, 52),
        "icon_candidate": (0, 200, 90),
        "mixed_symbol_text_candidate": (238, 140, 40),
        "other_candidate": (238, 190, 40),
        "text_noise": (170, 170, 170),
    }[item.visual_kind]
