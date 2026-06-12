from __future__ import annotations

from typing import Any

from ..m29_materialization_utils import sample_outer_bbox_ring_rgb
from ..png_tools import PngPixels, encode_rgb_png
from ..visual_primitive_graph import draw_rect, measure_region
from .types import M292SourceObject


def local_background_confidence(pixels: PngPixels, bbox: list[int]) -> float:
    try:
        bg = sample_outer_bbox_ring_rgb(pixels, bbox)
    except Exception:
        return 0.0
    try:
        metrics = measure_region(pixels, bbox)
    except Exception:
        return 0.0
    distance = abs(metrics.mean_rgb[0] - bg[0]) + abs(metrics.mean_rgb[1] - bg[1]) + abs(metrics.mean_rgb[2] - bg[2])
    texture_penalty = min(1.0, metrics.texture_score)
    return max(0.0, min(1.0, 1.0 - (distance / 765.0) - (texture_penalty * 0.35)))


def build_summary(objects: list[M292SourceObject], m29_nodes: list[dict[str, Any]], ocr_boxes: list[Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in objects:
        counts[item.visual_kind] = counts.get(item.visual_kind, 0) + 1
    return {
        "sourceObjectCount": len(objects),
        "m29NodeCount": len(m29_nodes),
        "ocrTextCount": len(ocr_boxes),
        "editableTextCount": counts.get("editable_ui_text", 0),
        "preservedRasterTextCount": counts.get("preserve_raster_text", 0),
        "rasterIconCount": counts.get("raster_icon", 0),
        "mediaRegionCount": counts.get("media_region", 0),
        "shapeGeometryCount": counts.get("control_background", 0) + counts.get("card_background", 0) + counts.get("separator", 0),
        "diagnosticOnlyCount": sum(1 for item in objects if item.replay_decision == "skip"),
        "dslChanged": False,
        "assetChanged": False,
    }


def render_overlay(pixels: PngPixels, objects: list[M292SourceObject]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {
        "editable_ui_text": (20, 160, 80),
        "preserve_raster_text": (240, 160, 20),
        "media_region": (20, 100, 220),
        "raster_icon": (180, 80, 220),
        "control_background": (40, 190, 190),
        "card_background": (80, 180, 120),
        "separator": (120, 120, 120),
        "shadow_or_blur": (220, 80, 80),
        "unknown": (220, 80, 80),
    }
    for item in objects:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, colors.get(item.visual_kind, (220, 80, 80)), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def parse_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [int(round(float(item))) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def union_bbox(bboxes: list[list[int] | None]) -> list[int] | None:
    valid = [bbox for bbox in bboxes if bbox is not None]
    if not valid:
        return None
    x1 = min(bbox[0] for bbox in valid)
    y1 = min(bbox[1] for bbox in valid)
    x2 = max(bbox[0] + bbox[2] for bbox in valid)
    y2 = max(bbox[1] + bbox[3] for bbox in valid)
    return [x1, y1, x2 - x1, y2 - y1]
