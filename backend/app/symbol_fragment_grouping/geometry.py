from __future__ import annotations

from typing import Any

from ..png_tools import PngPixels
from ..visual_primitive_graph import (
    M29PrimitiveMetrics,
    bbox_area,
    bbox_contains,
    bbox_gap_distance,
    bbox_in_bounds,
    bbox_intersects,
    bbox_x2,
    bbox_y2,
    measure_region,
)
from .types import INTERACTIVE_SHAPE_SUBTYPES, PROTECTIVE_CONTAINER_SUBTYPES, M291FragmentCandidate, M291Options


def parse_bbox(value: object) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    return [int(item) for item in value]

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

def find_container_id(bbox: list[int], nodes: list[dict[str, Any]]) -> str | None:
    containers = [node for node in nodes if node.get("type") == "shape" and node.get("subtype") in PROTECTIVE_CONTAINER_SUBTYPES]
    containing = [node for node in containers if (shape_bbox := parse_bbox(node.get("bbox"))) is not None and bbox_contains(shape_bbox, bbox)]
    if not containing:
        return None
    return str(min(containing, key=lambda node: bbox_area(parse_bbox(node.get("bbox")) or bbox)).get("id"))

def find_interactive_shape_id(bbox: list[int], nodes: list[dict[str, Any]]) -> str | None:
    shapes = [node for node in nodes if is_interactive_shape(node)]
    containing = [node for node in shapes if (shape_bbox := parse_bbox(node.get("bbox"))) is not None and bbox_contains(shape_bbox, bbox)]
    if not containing:
        return None
    return str(min(containing, key=lambda node: bbox_area(parse_bbox(node.get("bbox")) or bbox)).get("id"))

def is_interactive_shape(node: dict[str, Any]) -> bool:
    return node.get("type") == "shape" and node.get("subtype") in INTERACTIVE_SHAPE_SUBTYPES

def has_near_symbol_or_interactive_shape(
    bbox: list[int],
    symbol_nodes: list[dict[str, Any]],
    interactive_shapes: list[dict[str, Any]],
    radius: int,
) -> bool:
    for node in [*symbol_nodes, *interactive_shapes]:
        other = parse_bbox(node.get("bbox"))
        if other is not None and bbox_gap_distance(bbox, other) <= radius:
            return True
    return False

def merge_bboxes(bboxes: list[list[int]]) -> list[int]:
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox_x2(bbox) for bbox in bboxes)
    y2 = max(bbox_y2(bbox) for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]

def intersects_node_type(bbox: list[int], nodes: list[dict[str, Any]], node_type: str) -> bool:
    for node in nodes:
        if node.get("type") != node_type:
            continue
        other = parse_bbox(node.get("bbox"))
        if other is not None and bbox_intersects(bbox, other):
            return True
    return False

def container_compatibility(left: M291FragmentCandidate, right: M291FragmentCandidate) -> float:
    if left.interactive_shape_id and left.interactive_shape_id == right.interactive_shape_id:
        return 1.0
    if left.container_id and left.container_id == right.container_id:
        return 0.8
    if left.container_id is None and right.container_id is None:
        return 0.55
    return 0.45

def merged_bbox_score(bbox: list[int], options: M291Options) -> float:
    area_score = max(0.0, 1.0 - bbox_area(bbox) / max(1, options.max_merged_symbol_area))
    edge_score = max(0.0, 1.0 - max(bbox[2], bbox[3]) / max(1, options.icon_cluster_max_edge))
    aspect = bbox[2] / max(1, bbox[3])
    aspect_score = 1.0 if 0.25 <= aspect <= 4.0 else 0.25
    return (area_score + edge_score + aspect_score) / 3

def are_horizontally_aligned(candidates: list[M291FragmentCandidate]) -> bool:
    centers = [(candidate.bbox[1] + candidate.bbox[3] / 2, candidate.bbox[3]) for candidate in candidates]
    heights = [height for _center, height in centers]
    return max(center for center, _height in centers) - min(center for center, _height in centers) <= max(3, max(heights) * 0.4)

def is_text_like_sequence(candidates: list[M291FragmentCandidate], bbox: list[int], options: M291Options) -> bool:
    if len(candidates) < 3:
        return False
    aspect = bbox[2] / max(1, bbox[3])
    if aspect <= options.max_text_like_aspect_ratio or not are_horizontally_aligned(candidates):
        return False
    ordered = sorted(candidates, key=lambda item: item.bbox[0])
    gaps = [max(0, ordered[index + 1].bbox[0] - bbox_x2(ordered[index].bbox)) for index in range(len(ordered) - 1)]
    return max(gaps) - min(gaps) <= max(4, bbox[3] * 0.5)

def group_confidence(
    candidates: list[M291FragmentCandidate],
    bbox: list[int],
    mean_edge_score: float,
    merged_metrics: M29PrimitiveMetrics,
    options: M291Options,
) -> float:
    style_values = [candidate.metrics.texture_score for candidate in candidates]
    style_consistency = 1.0 - (max(style_values) - min(style_values) if style_values else 0.0)
    container_ids = {candidate.container_id for candidate in candidates if candidate.container_id is not None}
    container_consistency = 1.0 if len(container_ids) <= 1 else 0.3
    asset_gain = 1.0 if any(candidate.source_kind == "blocked" for candidate in candidates) else 0.7
    text_penalty = 0.30 if is_text_like_sequence(candidates, bbox, options) else 0.0
    boundary_penalty = 0.20 if merged_metrics.color_count >= 48 and merged_metrics.texture_score >= 0.24 else 0.0
    confidence = (
        0.45 * mean_edge_score
        + 0.20 * merged_bbox_score(bbox, options)
        + 0.15 * max(0.0, style_consistency)
        + 0.10 * container_consistency
        + 0.10 * asset_gain
        - text_penalty
        - boundary_penalty
    )
    return max(0.0, min(1.0, confidence))
