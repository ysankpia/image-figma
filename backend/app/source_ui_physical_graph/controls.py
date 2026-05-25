from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..m29_materialization_utils import bbox_intersection_area, bbox_overlap_ratio
from ..png_tools import PngPixels, rgb_to_hex
from ..visual_primitive_graph import bbox_area, measure_region
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
        radius=radius_from_unknown_control_metrics(bbox, metrics),
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


def radius_from_unknown_control_metrics(bbox: list[int], metrics: dict[str, Any]) -> int | None:
    fill_ratio = metric_float(metrics, "fillRatio")
    aspect = bbox[2] / max(1, bbox[3])
    if fill_ratio <= 0.82 and aspect >= 1.40:
        return max(2, min(bbox[2], bbox[3]) // 2)
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
