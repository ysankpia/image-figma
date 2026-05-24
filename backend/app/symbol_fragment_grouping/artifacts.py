from __future__ import annotations

import json
from pathlib import Path

from ..png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png
from ..visual_primitive_graph import bbox_area, bbox_clamp, draw_rect
from .types import M291AssetAuditItem, M291DebugArtifacts, M291Document, M291FragmentCandidate, M291SymbolGroup


def write_m291_outputs(document: M291Document, output_dir: Path) -> None:
    (output_dir / "group_nodes.json").write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "symbol_asset_audit.json").write_text(
        json.dumps([item.to_dict() for item in document.asset_audit], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "edge_audit.json").write_text(
        json.dumps([item.to_dict() for item in document.edge_audit], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "symbol_asset_audit.md").write_text(render_asset_audit_markdown(document.asset_audit), encoding="utf-8")

def render_asset_audit_markdown(items: list[M291AssetAuditItem]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.risk] = counts.get(item.risk, 0) + 1
    lines = ["# M29.1 Symbol Asset Audit", "", "## Summary", ""]
    for risk, count in sorted(counts.items()):
        lines.append(f"- {risk}: {count}")
    lines.extend(["", "## Highest Risk", ""])
    for item in sorted(items, key=lambda entry: entry.score, reverse=True)[:20]:
        lines.append(f"- {item.node_id} `{item.risk}` score={item.score:.3f} bbox={item.bbox} reasons={','.join(item.reasons)}")
    lines.append("")
    return "\n".join(lines)

def write_m291_overlays(
    pixels: PngPixels,
    output_dir: Path,
    candidates: list[M291FragmentCandidate],
    groups: list[M291SymbolGroup],
    asset_audit: list[M291AssetAuditItem],
) -> M291DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    risk_path = overlay_dir / "09_symbol_fragment_risks.png"
    groups_path = overlay_dir / "10_symbol_groups.png"
    compare_path = overlay_dir / "11_grouped_vs_original.png"
    risk_path.write_bytes(overlay_asset_risks(pixels, candidates, asset_audit))
    groups_path.write_bytes(overlay_groups(pixels, groups))
    compare_path.write_bytes(overlay_grouped_vs_original(pixels, candidates, groups))
    return M291DebugArtifacts(
        symbol_fragment_risks=str(risk_path.relative_to(output_dir)),
        symbol_groups=str(groups_path.relative_to(output_dir)),
        grouped_vs_original=str(compare_path.relative_to(output_dir)),
    )

def overlay_asset_risks(pixels: PngPixels, candidates: list[M291FragmentCandidate], audit: list[M291AssetAuditItem]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    risk_by_id = {item.node_id: item.risk for item in audit}
    colors = {
        "ok": (0, 180, 90),
        "fragmented": (235, 64, 52),
        "text_like": (160, 80, 220),
        "overcropped": (238, 190, 40),
        "isolated": (120, 120, 120),
        "unknown": (60, 60, 60),
    }
    for candidate in candidates:
        draw_rect(rows, pixels.width, pixels.height, candidate.bbox, colors.get(risk_by_id.get(candidate.id, "unknown"), (60, 60, 60)), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def overlay_groups(pixels: PngPixels, groups: list[M291SymbolGroup]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {"accepted": (0, 200, 90), "uncertain": (238, 190, 40), "rejected": (235, 64, 52)}
    for group in groups:
        draw_rect(rows, pixels.width, pixels.height, group.bbox, colors[group.decision], 3 if group.decision == "accepted" else 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def overlay_grouped_vs_original(pixels: PngPixels, candidates: list[M291FragmentCandidate], groups: list[M291SymbolGroup]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for candidate in candidates:
        draw_rect(rows, pixels.width, pixels.height, candidate.bbox, (150, 150, 150), 1)
    for group in groups:
        if group.decision == "accepted":
            draw_rect(rows, pixels.width, pixels.height, group.bbox, (0, 200, 90), 3)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def build_preview_sheet(
    pixels: PngPixels,
    output_dir: Path,
    debug: M291DebugArtifacts,
    candidates: list[M291FragmentCandidate] | None = None,
    groups: list[M291SymbolGroup] | None = None,
) -> bytes:
    group_overlay = decode_png_pixels((output_dir / (debug.symbol_groups or "overlays/10_symbol_groups.png")).read_bytes())
    m29_output_dir = output_dir.parent
    retained_image_previews = crop_previews(m29_output_dir / "assets" / "images", 160)
    retained_symbol_previews = crop_previews(m29_output_dir / "assets" / "symbols", 96)
    candidate_previews = bbox_previews(pixels, [candidate.bbox for candidate in candidates or []], 72)
    accepted_group_previews = crop_previews(output_dir / "assets" / "symbol_groups", 120)
    uncertain_group_previews = bbox_previews(pixels, [group.bbox for group in groups or [] if group.decision == "uncertain"], 96)
    rejected_group_previews = bbox_previews(pixels, [group.bbox for group in groups or [] if group.decision == "rejected"], 72)
    preview_sections = [
        section
        for section in [
            retained_image_previews,
            retained_symbol_previews,
            candidate_previews,
            accepted_group_previews,
            uncertain_group_previews,
            rejected_group_previews,
        ]
        if section
    ]
    sheet_width = 1400
    margin = 24
    gap = 18
    scale = min(0.55, (sheet_width - margin * 2 - gap) / max(1, pixels.width * 2))
    source_w = max(1, round(pixels.width * scale))
    source_h = max(1, round(pixels.height * scale))
    sheet_height = source_h + sum(grid_height(section, sheet_width, margin, gap) for section in preview_sections) + margin * (3 + len(preview_sections))
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    paste_scaled(canvas, sheet_width, pixels, margin, margin, source_w, source_h)
    paste_scaled(canvas, sheet_width, group_overlay, margin + source_w + gap, margin, source_w, source_h)
    y = margin + source_h + margin
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
        return 60
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
