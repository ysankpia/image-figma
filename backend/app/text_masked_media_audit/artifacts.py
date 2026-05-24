from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png
from ..visual_primitive_graph import bbox_area, draw_rect, mask_to_png
from .regions import parse_bbox
from .types import MediaEvidenceItem, TextMaskedDebugArtifacts, TextMaskedMediaAuditOptions


def write_debug_artifacts(
    *,
    pixels: PngPixels,
    output_dir: Path,
    text_mask: Any,
    suppressed_pixels: PngPixels,
    before_document: dict[str, Any],
    after_document: dict[str, Any],
    evidence: list[MediaEvidenceItem],
) -> TextMaskedDebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    text_mask_path = overlay_dir / "09_text_mask.png"
    suppressed_path = overlay_dir / "10_text_suppressed_analysis.png"
    before_after_path = overlay_dir / "11_media_before_after.png"
    evidence_path = overlay_dir / "12_media_evidence_map.png"
    text_mask_path.write_bytes(mask_to_png(text_mask))
    suppressed_path.write_bytes(encode_rgb_png(suppressed_pixels.width, suppressed_pixels.height, suppressed_pixels.rows))
    before_after_path.write_bytes(overlay_before_after(pixels, before_document, after_document))
    evidence_path.write_bytes(overlay_evidence(pixels, evidence))
    return TextMaskedDebugArtifacts(
        text_mask=str(text_mask_path.relative_to(output_dir)),
        text_suppressed_analysis=str(suppressed_path.relative_to(output_dir)),
        media_before_after=str(before_after_path.relative_to(output_dir)),
        media_evidence_map=str(evidence_path.relative_to(output_dir)),
    )

def overlay_before_after(pixels: PngPixels, before_document: dict[str, Any], after_document: dict[str, Any]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for node in before_document.get("nodes", []):
        if not isinstance(node, dict) or node.get("type") not in {"image", "unknown"}:
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is not None:
            draw_rect(rows, pixels.width, pixels.height, bbox, (0, 180, 210) if node.get("type") == "image" else (238, 190, 40), 2)
    for node in after_document.get("nodes", []):
        if not isinstance(node, dict) or node.get("type") not in {"image", "unknown", "symbol"}:
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is not None:
            draw_rect(rows, pixels.width, pixels.height, bbox, (220, 60, 220), 1)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def overlay_evidence(pixels: PngPixels, evidence: list[MediaEvidenceItem]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {
        "accepted_image": (0, 180, 210),
        "image_like_unknown": (238, 190, 40),
        "image_like_symbol": (0, 200, 90),
        "support_shape": (0, 122, 255),
        "image_like_blocked": (235, 64, 52),
        "symbol_group": (60, 120, 255),
        "text_suppressed_candidate": (220, 60, 220),
    }
    for item in evidence:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, colors[item.decision], 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def build_preview_sheet(
    pixels: PngPixels,
    suppressed_pixels: PngPixels,
    output_dir: Path,
    debug: TextMaskedDebugArtifacts,
    evidence: list[MediaEvidenceItem],
    options: TextMaskedMediaAuditOptions,
) -> bytes:
    evidence_overlay = decode_png_pixels((output_dir / debug.media_evidence_map).read_bytes())
    before_after = decode_png_pixels((output_dir / debug.media_before_after).read_bytes())
    max_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.38, (max_width - margin * 2 - gap * 3) / max(1, pixels.width * 4))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    crop_items = crop_previews_for_evidence(output_dir, evidence, options.output_preview_max_thumb)
    grid_h = grid_height(crop_items, max_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * max_width) for _ in range(sheet_height)]
    x = margin
    for item in [pixels, suppressed_pixels, before_after, evidence_overlay]:
        paste_scaled(canvas, max_width, item, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, max_width, crop_items, margin, margin + top_h + margin, gap)
    return encode_rgb_png(max_width, sheet_height, [bytes(row) for row in canvas])

def crop_previews_for_evidence(
    output_dir: Path,
    evidence: list[MediaEvidenceItem],
    max_edge: int,
) -> list[tuple[MediaEvidenceItem, PngPixels, int, int]]:
    previews: list[tuple[MediaEvidenceItem, PngPixels, int, int]] = []
    for item in sorted(evidence, key=preview_sort_key):
        if item.asset_path is None:
            continue
        try:
            pixels = decode_png_pixels((output_dir / item.asset_path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, pixels.width, pixels.height))
        previews.append((item, pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews

def preview_sort_key(item: MediaEvidenceItem) -> tuple[int, int, int, int, int, str]:
    source_rank = {
        "m29_image": 0,
        "m29_unknown": 1,
        "m29_shape": 2,
        "m29_blocked": 3,
        "m29_symbol": 4,
        "m291_group": 5,
        "after_text_mask_candidate": 6,
    }.get(item.source, 9)
    noise_rank = 1 if item.suggested_next_action == "likely_text_noise" else 0
    return (noise_rank, source_rank, -bbox_area(item.bbox), item.bbox[1], item.bbox[0], item.id)

def preview_border_color(item: MediaEvidenceItem) -> tuple[int, int, int]:
    if item.suggested_next_action == "likely_text_noise":
        return (190, 190, 190)
    return {
        "accepted_image": (0, 180, 210),
        "image_like_unknown": (238, 190, 40),
        "image_like_symbol": (0, 200, 90),
        "support_shape": (0, 122, 255),
        "image_like_blocked": (235, 64, 52),
        "symbol_group": (60, 120, 255),
        "text_suppressed_candidate": (220, 60, 220),
    }.get(item.decision, (140, 140, 140))

def grid_height(previews: list[tuple[MediaEvidenceItem, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
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

def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[MediaEvidenceItem, PngPixels, int, int]], x: int, y: int, gap: int) -> int:
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
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, preview_border_color(item))
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
