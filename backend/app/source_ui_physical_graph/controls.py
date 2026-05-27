from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..m29_materialization_utils import bbox_intersection_area, bbox_overlap_ratio
from ..png_tools import PngPixels, rgb_to_hex
from ..visual_primitive_graph import bbox_area, color_distance, measure_region
from .artifacts import parse_bbox
from .types import M292SourcePhysicalOptions

CONTROL_BACKGROUND_SUBTYPES = {
    "low_contrast_support",
    "text_support_background",
    "search_field_background",
    "small_rounded_rect",
    "badge_background",
    "icon_button_background",
    "small_ellipse",
}


@dataclass(frozen=True)
class ControlUnknownEvidence:
    text_ids: list[str]
    text_area_ratio: float
    fill: str
    radius: int | None
    confidence: str


def classify_control_like_unknown(
    node: dict[str, Any],
    bbox: list[int],
    ocr_boxes: list[Any],
    pixels: PngPixels,
    image_width: int,
    image_height: int,
    options: M292SourcePhysicalOptions,
) -> ControlUnknownEvidence | None:
    if str(node.get("type") or "") != "unknown":
        return None
    if str(node.get("subtype") or "") != "image_like_low_confidence":
        return None
    if not is_finite_control_bbox(bbox, image_width, image_height, options):
        return None
    metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
    if not has_control_unknown_metrics(metrics, options):
        return None
    text_ids, text_area = contained_text_evidence(bbox, ocr_boxes, options)
    if not text_ids:
        return None
    fill = source_fill_excluding_text(pixels, bbox, ocr_boxes)
    return ControlUnknownEvidence(
        text_ids=text_ids,
        text_area_ratio=round(text_area / max(1, bbox_area(bbox)), 4),
        fill=fill,
        radius=radius_from_control_pixels(pixels, bbox, ocr_boxes),
        confidence="high",
    )


def is_finite_control_bbox(
    bbox: list[int],
    image_width: int,
    image_height: int,
    options: M292SourcePhysicalOptions,
) -> bool:
    area = bbox_area(bbox)
    if area <= 0:
        return False
    if bbox[2] < options.control_unknown_min_width or bbox[3] < options.control_unknown_min_height:
        return False
    if bbox[3] > options.control_unknown_max_height:
        return False
    aspect = bbox[2] / max(1, bbox[3])
    if aspect < options.control_unknown_min_aspect_ratio or aspect > options.control_unknown_max_aspect_ratio:
        return False
    return area <= round(image_width * image_height * options.control_unknown_max_area_ratio)


def has_control_unknown_metrics(metrics: dict[str, Any], options: M292SourcePhysicalOptions) -> bool:
    return (
        metric_int(metrics, "colorCount") <= options.control_unknown_max_color_count
        and metric_float(metrics, "textureScore") <= options.control_unknown_max_texture_score
        and metric_float(metrics, "edgeScore") <= options.control_unknown_max_edge_score
        and metric_float(metrics, "fillRatio") >= options.control_unknown_min_fill_ratio
    )


def contained_text_evidence(
    bbox: list[int],
    ocr_boxes: list[Any],
    options: M292SourcePhysicalOptions,
) -> tuple[list[str], int]:
    text_ids: list[str] = []
    text_area = 0
    for box in ocr_boxes:
        text_bbox = parse_bbox(getattr(box, "bbox", None))
        if text_bbox is None:
            continue
        text = str(getattr(box, "text", "") or "").strip()
        if not text:
            continue
        confidence = getattr(box, "confidence", 1.0)
        try:
            if float(confidence) < options.min_text_confidence:
                continue
        except (TypeError, ValueError):
            continue
        if bbox_overlap_ratio(text_bbox, bbox) < options.control_unknown_min_text_containment:
            continue
        text_ids.append(str(getattr(box, "id", "") or ""))
        text_area += bbox_intersection_area(bbox, text_bbox)
    text_ratio = text_area / max(1, bbox_area(bbox))
    if text_ratio < options.control_unknown_min_text_area_ratio:
        return [], text_area
    if text_ratio > options.control_unknown_max_text_area_ratio:
        return [], text_area
    return [text_id for text_id in text_ids if text_id], text_area


def source_fill_excluding_text(pixels: PngPixels, bbox: list[int], ocr_boxes: list[Any]) -> str:
    x, y, width, height = bbox
    text_bboxes = [
        text_bbox
        for box in ocr_boxes
        if (text_bbox := parse_bbox(getattr(box, "bbox", None))) is not None and bbox_overlap_ratio(text_bbox, bbox) > 0
    ]
    samples: list[tuple[int, int, int]] = []
    for row_idx in range(max(0, y), min(pixels.height, y + height)):
        row = pixels.rows[row_idx]
        for col_idx in range(max(0, x), min(pixels.width, x + width)):
            if any(point_in_bbox(col_idx, row_idx, text_bbox) for text_bbox in text_bboxes):
                continue
            offset = col_idx * 3
            samples.append((row[offset], row[offset + 1], row[offset + 2]))
    if not samples:
        metrics = measure_region(pixels, bbox)
        return rgb_to_hex(list(metrics.mean_rgb))
    return rgb_to_hex(median_rgb(samples))


def radius_from_control_pixels(pixels: PngPixels, bbox: list[int], ocr_boxes: list[Any]) -> int | None:
    ignored = [
        text_bbox
        for box in ocr_boxes
        if (text_bbox := parse_bbox(getattr(box, "bbox", None))) is not None and bbox_overlap_ratio(text_bbox, bbox) > 0
    ]
    fill = median_control_rgb(pixels, bbox, ignored)
    limit = max(2, min(bbox[2], bbox[3]) // 2)
    corner_edge_offsets: list[int] = []
    for corner in ("top_left", "top_right", "bottom_left", "bottom_right"):
        offset = first_corner_fill_offset(pixels, bbox, fill, ignored, corner, limit)
        if offset is not None:
            corner_edge_offsets.append(offset)
    if len(corner_edge_offsets) < 3:
        return None
    corner_edge_offsets = sorted(corner_edge_offsets)
    radius = corner_edge_offsets[len(corner_edge_offsets) // 2]
    if radius < 2:
        return None
    return max(0, min(radius, limit))


def median_control_rgb(pixels: PngPixels, bbox: list[int], ignored: list[list[int]]) -> tuple[int, int, int]:
    x, y, width, height = bbox
    samples: list[tuple[int, int, int]] = []
    for row_idx in range(max(0, y), min(pixels.height, y + height)):
        row = pixels.rows[row_idx]
        for col_idx in range(max(0, x), min(pixels.width, x + width)):
            if any(point_in_bbox(col_idx, row_idx, text_bbox) for text_bbox in ignored):
                continue
            offset = col_idx * 3
            samples.append((row[offset], row[offset + 1], row[offset + 2]))
    if not samples:
        metrics = measure_region(pixels, bbox)
        return tuple(metrics.mean_rgb)
    rgb = median_rgb(samples)
    return (rgb[0], rgb[1], rgb[2])


def first_corner_fill_offset(
    pixels: PngPixels,
    bbox: list[int],
    fill: tuple[int, int, int],
    ignored: list[list[int]],
    corner: str,
    limit: int,
) -> int | None:
    x, y, width, height = bbox
    for offset in range(limit):
        if corner == "top_left":
            col_idx, row_idx = x + offset, y
        elif corner == "top_right":
            col_idx, row_idx = x + width - 1 - offset, y
        elif corner == "bottom_left":
            col_idx, row_idx = x + offset, y + height - 1
        else:
            col_idx, row_idx = x + width - 1 - offset, y + height - 1
        if any(point_in_bbox(col_idx, row_idx, text_bbox) for text_bbox in ignored):
            continue
        row = pixels.rows[max(0, min(pixels.height - 1, row_idx))]
        offset_idx = max(0, min(pixels.width - 1, col_idx)) * 3
        rgb = (row[offset_idx], row[offset_idx + 1], row[offset_idx + 2])
        if color_distance(rgb, fill) <= 24:
            return offset
    return None


def point_in_bbox(x: int, y: int, bbox: list[int]) -> bool:
    return bbox[0] <= x < bbox[0] + bbox[2] and bbox[1] <= y < bbox[1] + bbox[3]


def median_rgb(samples: list[tuple[int, int, int]]) -> list[int]:
    return [
        sorted(sample[channel] for sample in samples)[len(samples) // 2]
        for channel in range(3)
    ]


def metric_float(metrics: dict[str, Any], key: str) -> float:
    value = metrics.get(key)
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def metric_int(metrics: dict[str, Any], key: str) -> int:
    value = metrics.get(key)
    if isinstance(value, bool):
        return 0
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0
