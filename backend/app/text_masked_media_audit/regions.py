from __future__ import annotations

from typing import Any

from ..png_tools import PngPixels
from ..visual_primitive_graph import (
    M29PrimitiveMetrics,
    M29VisualPrimitiveGraphDocument,
    bbox_area,
    bbox_clamp,
    bbox_iou,
    bbox_x2,
    bbox_y2,
    estimate_global_background,
    pad_bbox,
)
from .types import MediaAuditRegion, TextMaskedMediaAuditOptions


def default_media_regions(width: int, height: int) -> list[MediaAuditRegion]:
    if height < 600:
        return [MediaAuditRegion("full", [0, 0, width, height])]
    header_h = min(max(round(height * 0.08), 96), 180)
    bottom_h = min(max(round(height * 0.08), 96), 180)
    body_top = header_h
    body_bottom = max(body_top, height - bottom_h)
    body_h = body_bottom - body_top
    band_h = max(1, body_h // 5)
    return [
        MediaAuditRegion("top/header", [0, 0, width, header_h]),
        MediaAuditRegion("hero/banner", [0, body_top, width, band_h]),
        MediaAuditRegion("category/grid", [0, body_top + band_h, width, band_h]),
        MediaAuditRegion("product/list", [0, body_top + band_h * 2, width, band_h]),
        MediaAuditRegion("supplier/card", [0, body_top + band_h * 3, width, band_h]),
        MediaAuditRegion("tools/icons", [0, body_top + band_h * 4, width, body_bottom - (body_top + band_h * 4)]),
        MediaAuditRegion("bottom/nav", [0, body_bottom, width, height - body_bottom]),
    ]

def build_text_suppressed_pixels(
    pixels: PngPixels,
    text_boxes: list[M29TextBox],
    options: TextMaskedMediaAuditOptions,
) -> PngPixels:
    rows = [bytearray(row) for row in pixels.rows]
    global_background = estimate_global_background(pixels)
    for text_box in text_boxes:
        padded = bbox_clamp(pad_bbox(text_box.bbox, options.text_padding), pixels.width, pixels.height)
        if padded is None:
            continue
        fill = local_background_rgb(pixels, padded, global_background)
        fill_bytes = bytes(fill)
        x, y, width, height = padded
        for row_index in range(y, y + height):
            row = rows[row_index]
            for column in range(x, x + width):
                row[column * 3 : column * 3 + 3] = fill_bytes
    return PngPixels(width=pixels.width, height=pixels.height, rows=[bytes(row) for row in rows])

def local_background_rgb(pixels: PngPixels, bbox: list[int], fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    x, y, width, height = bbox
    expanded = bbox_clamp([x - 4, y - 4, width + 8, height + 8], pixels.width, pixels.height)
    if expanded is None:
        return fallback
    ex, ey, ew, eh = expanded
    samples: list[tuple[int, int, int]] = []
    for row_index in range(ey, ey + eh):
        row = pixels.rows[row_index]
        for column in range(ex, ex + ew):
            if x <= column < x + width and y <= row_index < y + height:
                continue
            offset = column * 3
            samples.append((row[offset], row[offset + 1], row[offset + 2]))
    if not samples:
        return fallback
    buckets: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    for sample in samples:
        buckets.setdefault((sample[0] // 16, sample[1] // 16, sample[2] // 16), []).append(sample)
    dominant = max(buckets.values(), key=len)
    return tuple(round(sum(sample[channel] for sample in dominant) / len(dominant)) for channel in range(3))

def region_for_bbox(bbox: list[int], regions: list[MediaAuditRegion]) -> str:
    best = max(regions, key=lambda region: bbox_iou_or_overlap(bbox, region.bbox), default=None)
    if best is None or bbox_iou_or_overlap(bbox, best.bbox) <= 0:
        return "unknown"
    return best.name

def bbox_iou_or_overlap(bbox: list[int], region: list[int]) -> float:
    x1 = max(bbox[0], region[0])
    y1 = max(bbox[1], region[1])
    x2 = min(bbox_x2(bbox), bbox_x2(region))
    y2 = min(bbox_y2(bbox), bbox_y2(region))
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    return intersection / max(1, bbox_area(bbox))

def extract_counts(document: dict[str, Any]) -> dict[str, int]:
    counts = document.get("meta", {}).get("counts")
    if isinstance(counts, dict):
        return {str(key): int(value) for key, value in counts.items()}
    result = {"text": 0, "shape": 0, "image": 0, "symbol": 0, "unknown": 0, "blocked": len(document.get("blocked", []))}
    for node in document.get("nodes", []):
        if isinstance(node, dict) and node.get("type") in result:
            result[str(node.get("type"))] += 1
    return result

def parse_bbox(value: object) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [int(item) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox

def parse_metrics(value: object) -> M29PrimitiveMetrics | None:
    if not isinstance(value, dict):
        return None
    mean = value.get("meanRgb", value.get("mean_rgb", [0, 0, 0]))
    if not isinstance(mean, list) or len(mean) != 3:
        return None
    return M29PrimitiveMetrics(
        color_count=int(value.get("colorCount", value.get("color_count", 0))),
        texture_score=float(value.get("textureScore", value.get("texture_score", 0.0))),
        edge_score=float(value.get("edgeScore", value.get("edge_score", 0.0))),
        fill_ratio=float(value.get("fillRatio", value.get("fill_ratio", 0.0))),
        aspect_ratio=float(value.get("aspectRatio", value.get("aspect_ratio", 0.0))),
        brightness=float(value.get("brightness", 0.0)),
        mean_rgb=(int(mean[0]), int(mean[1]), int(mean[2])),
    )

def document_to_dict(document: M29VisualPrimitiveGraphDocument | dict[str, Any]) -> dict[str, Any]:
    return document.to_dict() if hasattr(document, "to_dict") else document
