from __future__ import annotations

from ..png_tools import PngMetadata, PngPixels
from .bbox import (
    bbox_area,
    bbox_clamp,
    bbox_contains,
    bbox_gap_distance,
    bbox_intersection_area,
    bbox_intersects,
    bbox_vertical_overlap_ratio,
    bbox_x2,
    bbox_y2,
    union_bbox,
)
from .geometry import support_region_metrics
from .metrics import color_distance
from .pixels import sample_outer_ring_mean_rgb, sample_region_mean_rgb
from .types import M29VisualPrimitiveOptions


def find_low_contrast_support_bbox(
    pixels: PngPixels,
    text_bbox: list[int],
    foreground_bboxes: list[list[int]],
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> list[int] | None:
    _, _, width, height = text_bbox
    line_evidence = low_contrast_support_line_evidence_bboxes(text_bbox, foreground_bboxes)
    evidence_union = union_bbox([text_bbox, *line_evidence])
    if not line_evidence or evidence_union is None:
        return None
    min_w = max(options.low_contrast_support_min_width, width + 24)
    min_h = max(options.low_contrast_support_min_height, height + 12)
    max_w = round(image.width * options.low_contrast_support_max_width_ratio)
    max_h = min(max(min_h, height + 44), 96)
    best: tuple[float, list[int]] | None = None
    pad_x = max(14, round(height * 0.8))
    vertical_paddings = sorted(
        {
            max(8, round(height * 0.45)),
            max(8, round((height + max(26, round(height * 1.2)) - evidence_union[3]) / 2)),
        }
    )
    union_candidates = []
    for pad_y in vertical_paddings:
        union_candidates.extend(
            [
                [evidence_union[0] - pad_x, evidence_union[1] - pad_y, evidence_union[2] + pad_x * 2, evidence_union[3] + pad_y * 2],
                [
                    evidence_union[0] - round(pad_x * 1.5),
                    evidence_union[1] - pad_y,
                    evidence_union[2] + round(pad_x * 3.0),
                    evidence_union[3] + pad_y * 2,
                ],
            ]
        )
    for raw in union_candidates:
        candidate = bbox_clamp(raw, image.width, image.height)
        if candidate is None or not bbox_contains(candidate, text_bbox):
            continue
        if candidate[2] < min_w or candidate[2] > max_w or candidate[3] < min_h or candidate[3] > max_h:
            continue
        score = score_low_contrast_support_candidate(pixels, candidate, text_bbox, foreground_bboxes, image, options)
        if score is None:
            continue
        if best is None or score > best[0] or (score == best[0] and bbox_area(candidate) < bbox_area(best[1])):
            best = (score, candidate)
    return best[1] if best is not None else None

def low_contrast_support_line_evidence_bboxes(text_bbox: list[int], foreground_bboxes: list[list[int]]) -> list[list[int]]:
    _, _, width, height = text_bbox
    max_gap = max(96, height * 16)
    max_evidence_width = max(48, round(width * 0.45), height * 2)
    max_evidence_height = max(24, round(height * 1.2))
    evidence = [
        item
        for item in foreground_bboxes
        if not bbox_intersects(item, text_bbox)
        and bbox_vertical_overlap_ratio(item, text_bbox) >= 0.25
        and bbox_gap_distance(item, text_bbox) <= max_gap
        and item[2] <= max_evidence_width
        and item[3] <= max_evidence_height
    ]
    return sorted(evidence, key=lambda item: (bbox_gap_distance(item, text_bbox), item[0], item[1], item[2], item[3]))

def score_low_contrast_support_candidate(
    pixels: PngPixels,
    candidate: list[int],
    text_bbox: list[int],
    foreground_bboxes: list[list[int]],
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> float | None:
    area_ratio = bbox_area(candidate) / max(1, image.width * image.height)
    if area_ratio <= 0 or area_ratio > options.low_contrast_support_max_area_ratio:
        return None
    if candidate[2] < options.low_contrast_support_min_width or candidate[3] < options.low_contrast_support_min_height:
        return None
    if candidate[2] > image.width * options.low_contrast_support_max_width_ratio:
        return None
    if candidate[3] > max(110, image.height * 0.08):
        return None
    fill_metrics = support_region_metrics(pixels, candidate)
    if fill_metrics.texture_score > options.low_contrast_support_max_texture:
        return None
    if fill_metrics.color_count > options.low_contrast_support_max_color_count:
        return None
    boundary_deltas = support_boundary_deltas(pixels, candidate, padding=3, thickness=3)
    if boundary_deltas is None:
        return None
    min_boundary_delta = min(boundary_deltas.values())
    edge_delta = round(sum(boundary_deltas.values()) / len(boundary_deltas))
    if min_boundary_delta < options.low_contrast_support_min_edge_delta:
        return None
    if edge_delta > options.low_contrast_support_max_edge_delta:
        return None
    evidence_count = len(low_contrast_support_evidence_bboxes(candidate, text_bbox, foreground_bboxes))
    if evidence_count == 0:
        return None
    horizontal_support = candidate[2] / max(1, candidate[3])
    if horizontal_support < 2.0:
        return None
    area_penalty = area_ratio * 20
    return round(edge_delta + evidence_count * 4 + min(horizontal_support, 10) * 0.2 - fill_metrics.texture_score * 30 - fill_metrics.color_count * 0.1 - area_penalty, 4)

def low_contrast_support_evidence_bboxes(candidate: list[int], text_bbox: list[int], foreground_bboxes: list[list[int]]) -> list[list[int]]:
    return [
        item
        for item in foreground_bboxes
        if bbox_contains(candidate, item)
        and bbox_area(item) < bbox_area(candidate) * 0.65
        and not bbox_intersects(item, text_bbox)
        and bbox_vertical_overlap_ratio(item, text_bbox) >= 0.25
    ]

def find_text_support_background_bbox(
    pixels: PngPixels,
    text_bbox: list[int],
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> list[int] | None:
    text_area = bbox_area(text_bbox)
    if text_area <= 0:
        return None
    _, _, width, height = text_bbox
    max_w = round(image.width * options.low_contrast_support_max_width_ratio)
    max_h = min(max(options.low_contrast_support_min_height, height + 44), 96)
    pad_x_values = sorted(
        {
            max(4, round(height * options.text_support_background_padding_x_ratio)),
            max(6, round(height * 0.85)),
            max(8, round(width * 0.20)),
            max(10, round(width * 0.30)),
            max(10, round(height * 1.20)),
        }
    )
    pad_y_values = sorted(
        {
            max(3, round(height * options.text_support_background_padding_y_ratio)),
            max(4, round(height * 0.55)),
            max(5, round(height * 0.85)),
        }
    )
    best: tuple[float, list[int]] | None = None
    for pad_x in pad_x_values:
        for pad_y in pad_y_values:
            raw = [text_bbox[0] - pad_x, text_bbox[1] - pad_y, text_bbox[2] + pad_x * 2, text_bbox[3] + pad_y * 2]
            candidate = bbox_clamp(raw, image.width, image.height)
            if candidate is None:
                continue
            score = score_text_support_background_candidate(pixels, candidate, text_bbox, image, options)
            if score is None:
                continue
            if candidate[2] > max_w or candidate[3] > max_h:
                continue
            if best is None or score > best[0] or (score == best[0] and bbox_area(candidate) < bbox_area(best[1])):
                best = (score, candidate)
    return best[1] if best is not None else None

def score_text_support_background_candidate(
    pixels: PngPixels,
    candidate: list[int],
    text_bbox: list[int],
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> float | None:
    text_area = bbox_area(text_bbox)
    candidate_area = bbox_area(candidate)
    if text_area <= 0 or candidate_area <= 0:
        return None
    text_contained = bbox_intersection_area(candidate, text_bbox) / text_area
    if text_contained < 0.90:
        return None
    support_area_ratio = candidate_area / text_area
    if support_area_ratio < options.text_support_background_min_area_ratio or support_area_ratio > options.text_support_background_max_area_ratio:
        return None
    support_aspect = candidate[2] / max(1, candidate[3])
    if support_aspect < options.text_support_background_min_aspect:
        return None
    fill_metrics = support_region_metrics(pixels, candidate)
    if fill_metrics.texture_score > options.low_contrast_support_max_texture:
        return None
    if fill_metrics.color_count > options.low_contrast_support_max_color_count:
        return None
    boundary_deltas = support_boundary_deltas(pixels, candidate, padding=3, thickness=3)
    if boundary_deltas is None:
        return None
    min_boundary_delta = min(boundary_deltas.values())
    edge_delta = round(sum(boundary_deltas.values()) / len(boundary_deltas))
    if min_boundary_delta < options.low_contrast_support_min_edge_delta:
        return None
    if edge_delta > options.low_contrast_support_max_edge_delta:
        return None
    return round(
        edge_delta
        + min(support_aspect, 8) * 0.25
        + fill_metrics.fill_ratio
        - fill_metrics.texture_score * 30
        - fill_metrics.color_count * 0.1
        - support_area_ratio * 0.05,
        4,
    )

def support_edge_delta(pixels: PngPixels, bbox: list[int]) -> int:
    inner = support_region_metrics(pixels, bbox).mean_rgb
    outer = sample_outer_ring_mean_rgb(pixels, bbox, padding=3, thickness=3)
    return color_distance(inner, outer)

def support_boundary_deltas(pixels: PngPixels, bbox: list[int], *, padding: int, thickness: int) -> dict[str, int] | None:
    if bbox[0] - padding < 0 or bbox[1] - padding < 0:
        return None
    if bbox_x2(bbox) + padding > pixels.width or bbox_y2(bbox) + padding > pixels.height:
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    inner = support_region_metrics(pixels, bbox).mean_rgb
    x, y, width, height = bbox
    top = sample_region_mean_rgb(pixels, [x, y - padding, width, thickness])
    bottom = sample_region_mean_rgb(pixels, [x, y + height + padding - thickness, width, thickness])
    left = sample_region_mean_rgb(pixels, [x - padding, y, thickness, height])
    right = sample_region_mean_rgb(pixels, [x + width + padding - thickness, y, thickness, height])
    return {
        "top": color_distance(inner, top),
        "bottom": color_distance(inner, bottom),
        "left": color_distance(inner, left),
        "right": color_distance(inner, right),
    }
