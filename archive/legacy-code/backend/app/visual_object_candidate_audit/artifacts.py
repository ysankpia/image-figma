from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png
from ..visual_primitive_graph import crop_pixels, draw_rect
from .types import (
    M2904DebugArtifacts,
    M2904Options,
    ObjectDecision,
    ObjectKind,
    VisualObjectCandidate,
    VisualObjectEvidenceEdge,
    VisualObjectEvidenceNode,
    VisualObjectSetCandidate,
)


def export_object_asset(pixels: PngPixels, output_dir: Path, object_kind: ObjectKind, decision: ObjectDecision, id: str, bbox: list[int]) -> str:
    if object_kind == "split_candidate":
        folder = "split_candidates"
    elif decision == "uncertain":
        folder = "uncertain_objects"
    elif decision == "rejected":
        folder = "rejected_objects"
    else:
        folder = "visual_objects"
    target = output_dir / "assets" / folder
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{id}.png"
    path.write_bytes(crop_pixels(pixels, bbox))
    return str(path.relative_to(output_dir))

def write_debug_artifacts(
    pixels: PngPixels,
    output_dir: Path,
    nodes: list[VisualObjectEvidenceNode],
    objects: list[VisualObjectCandidate],
    sets: list[VisualObjectSetCandidate],
    edges: list[VisualObjectEvidenceEdge],
) -> M2904DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = overlay_dir / "16_visual_object_candidates.png"
    edges_path = overlay_dir / "17_visual_object_edges.png"
    split_path = overlay_dir / "18_split_candidates.png"
    sets_path = overlay_dir / "19_visual_object_sets.png"
    candidates_path.write_bytes(overlay_objects(pixels, objects, include=lambda item: True))
    edges_path.write_bytes(overlay_edges(pixels, nodes, objects, edges))
    split_path.write_bytes(overlay_objects(pixels, objects, include=lambda item: item.object_kind == "split_candidate" or item.decision in {"uncertain", "rejected"}))
    sets_path.write_bytes(overlay_sets(pixels, objects, sets))
    return M2904DebugArtifacts(
        visual_object_candidates=str(candidates_path.relative_to(output_dir)),
        visual_object_edges=str(edges_path.relative_to(output_dir)),
        split_candidates=str(split_path.relative_to(output_dir)),
        visual_object_sets=str(sets_path.relative_to(output_dir)),
    )

def overlay_objects(pixels: PngPixels, objects: list[VisualObjectCandidate], *, include: Any) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in objects:
        if include(item):
            draw_rect(rows, pixels.width, pixels.height, item.bbox, object_color(item), 3 if item.decision in {"accepted", "candidate"} else 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def overlay_edges(
    pixels: PngPixels,
    nodes: list[VisualObjectEvidenceNode],
    objects: list[VisualObjectCandidate],
    edges: list[VisualObjectEvidenceEdge],
) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    node_by_id = {node.id: node for node in nodes}
    for edge in edges:
        left = node_by_id.get(edge.left_id)
        right = node_by_id.get(edge.right_id)
        if left is None or right is None:
            continue
        draw_line(rows, pixels.width, pixels.height, bbox_center(left.bbox), bbox_center(right.bbox), edge_color(edge))
    for item in objects:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, object_color(item), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def overlay_sets(pixels: PngPixels, objects: list[VisualObjectCandidate], sets: list[VisualObjectSetCandidate]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    object_by_id = {item.id: item for item in objects}
    for item in sets:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (0, 122, 255), 3)
        for object_id in item.member_object_ids:
            member = object_by_id.get(object_id)
            if member is not None:
                draw_rect(rows, pixels.width, pixels.height, member.bbox, (0, 200, 90), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])

def build_preview_sheet(
    pixels: PngPixels,
    output_dir: Path,
    debug: M2904DebugArtifacts,
    objects: list[VisualObjectCandidate],
    sets: list[VisualObjectSetCandidate],
    options: M2904Options,
) -> bytes:
    overlays = [decode_png_pixels((output_dir / path).read_bytes()) for path in debug.to_dict().values()]
    sheet_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.32, (sheet_width - margin * 2 - gap * 4) / max(1, pixels.width * 5))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    previews = crop_previews_for_objects(output_dir, objects, options.output_preview_max_thumb)
    grid_h = grid_height(previews, sheet_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    x = margin
    for image in [pixels, *overlays]:
        paste_scaled(canvas, sheet_width, image, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, sheet_width, previews, margin, margin + top_h + margin, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])

def crop_previews_for_objects(output_dir: Path, objects: list[VisualObjectCandidate], max_edge: int) -> list[tuple[VisualObjectCandidate, PngPixels, int, int]]:
    previews: list[tuple[VisualObjectCandidate, PngPixels, int, int]] = []
    for item in sorted(objects, key=object_sort_key):
        if item.asset_path is None:
            continue
        try:
            pixels = decode_png_pixels((output_dir / item.asset_path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, pixels.width, pixels.height))
        previews.append((item, pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews

def object_color(item: VisualObjectCandidate) -> tuple[int, int, int]:
    if item.object_kind == "split_candidate":
        return (235, 64, 52)
    return {
        "accepted": (0, 180, 210),
        "candidate": (0, 200, 90),
        "uncertain": (238, 190, 40),
        "rejected": (170, 170, 170),
    }[item.decision]

def edge_color(edge: VisualObjectEvidenceEdge) -> tuple[int, int, int]:
    if edge.decision == "accepted":
        return (0, 180, 90)
    if edge.decision == "weak":
        return (238, 190, 40)
    return (170, 170, 170)

def bbox_center(bbox: list[int]) -> tuple[int, int]:
    return (round(bbox[0] + bbox[2] / 2), round(bbox[1] + bbox[3] / 2))

def draw_line(
    rows: list[bytearray],
    image_width: int,
    image_height: int,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    color_bytes = bytes(color)
    while True:
        if 0 <= x0 < image_width and 0 <= y0 < image_height:
            rows[y0][x0 * 3 : x0 * 3 + 3] = color_bytes
        if x0 == x1 and y0 == y1:
            break
        twice_error = 2 * error
        if twice_error >= dy:
            error += dy
            x0 += sx
        if twice_error <= dx:
            error += dx
            y0 += sy

def object_sort_key(item: VisualObjectCandidate) -> tuple[int, int, int, int, str]:
    decision_rank = {"accepted": 0, "candidate": 1, "uncertain": 2, "rejected": 3}.get(item.decision, 9)
    kind_rank = {"visual_text_pair": 0, "compound_visual": 1, "single_visual": 2, "split_candidate": 3, "uncertain_compound": 4, "text_cluster": 5}.get(item.object_kind, 9)
    return (decision_rank, kind_rank, item.bbox[1], item.bbox[0], item.id)

def grid_height(previews: list[tuple[VisualObjectCandidate, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
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

def paste_grid(
    canvas: list[bytearray],
    sheet_width: int,
    previews: list[tuple[VisualObjectCandidate, PngPixels, int, int]],
    x: int,
    y: int,
    gap: int,
) -> int:
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
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, object_color(item))
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
