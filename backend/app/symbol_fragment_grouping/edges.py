from __future__ import annotations

from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_area, bbox_gap_distance, color_distance, measure_region
from .geometry import (
    are_horizontally_aligned,
    container_compatibility,
    intersects_node_type,
    merge_bboxes,
    merged_bbox_score,
)
from .types import M291FragmentCandidate, M291FragmentEdge, M291Options


def build_fragment_edges(
    candidates: list[M291FragmentCandidate],
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
    options: M291Options,
) -> list[M291FragmentEdge]:
    edges: list[M291FragmentEdge] = []
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1 :]:
            gap = bbox_gap_distance(left.bbox, right.bbox)
            same_interactive = left.interactive_shape_id is not None and left.interactive_shape_id == right.interactive_shape_id
            same_container = left.container_id is not None and left.container_id == right.container_id
            if gap > options.neighbor_search_radius and not same_interactive:
                if not same_container or gap > options.neighbor_search_radius * 2:
                    continue
            if gap > options.icon_cluster_max_edge:
                continue
            edge = score_fragment_edge(f"edge_{len(edges) + 1:04d}", left, right, nodes, pixels, options)
            edges.append(edge)
    return edges

def score_fragment_edge(
    id: str,
    left: M291FragmentCandidate,
    right: M291FragmentCandidate,
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
    options: M291Options,
) -> M291FragmentEdge:
    hard_reasons = hard_boundary_reasons(left, right, nodes, pixels, options)
    metrics = edge_metric_values(left, right, pixels, options, boundary_violation=1.0 if hard_reasons else 0.0)
    score = (
        0.30 * metrics["distanceScore"]
        + 0.20 * metrics["colorSimilarityScore"]
        + 0.15 * metrics["sizeCompatibilityScore"]
        + 0.15 * metrics["containerCompatibilityScore"]
        + 0.10 * metrics["mergedBboxScore"]
        + 0.10 * metrics["styleSimilarityScore"]
        - 0.25 * metrics["textLikePenalty"]
        - 0.40 * metrics["boundaryViolationPenalty"]
    )
    score = max(0.0, min(1.0, round(score, 4)))
    if hard_reasons:
        return M291FragmentEdge(id, left.id, right.id, score, "rejected", hard_reasons, metrics)
    if score >= options.accepted_edge_threshold:
        return M291FragmentEdge(id, left.id, right.id, score, "accepted", ["edge_score_accepted"], metrics)
    if score >= options.weak_edge_threshold:
        return M291FragmentEdge(id, left.id, right.id, score, "weak", ["edge_score_weak"], metrics)
    return M291FragmentEdge(id, left.id, right.id, score, "rejected", ["edge_score_below_threshold"], metrics)

def hard_boundary_reasons(
    left: M291FragmentCandidate,
    right: M291FragmentCandidate,
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
    options: M291Options,
) -> list[str]:
    reasons: list[str] = []
    merged = merge_bboxes([left.bbox, right.bbox])
    if left.interactive_shape_id and right.interactive_shape_id and left.interactive_shape_id != right.interactive_shape_id:
        reasons.append("different_interactive_shape")
    if left.container_id and right.container_id and left.container_id != right.container_id:
        reasons.append("different_protective_container")
    if bbox_area(merged) > options.max_merged_symbol_area:
        reasons.append("merged_bbox_too_large")
    if max(merged[2], merged[3]) > options.icon_cluster_max_edge:
        reasons.append("merged_edge_too_large")
    if intersects_node_type(merged, nodes, "text"):
        reasons.append("cross_text_node")
    if intersects_node_type(merged, nodes, "image"):
        reasons.append("cross_image_node")
    if reasons:
        return reasons
    merged_metrics = measure_region(pixels, merged)
    if merged_metrics.color_count >= 48 and merged_metrics.texture_score >= 0.24 and bbox_area(merged) >= 1200:
        reasons.append("image_like_merged_result")
    return reasons

def edge_metric_values(
    left: M291FragmentCandidate,
    right: M291FragmentCandidate,
    pixels: PngPixels,
    options: M291Options,
    *,
    boundary_violation: float,
) -> dict[str, float]:
    gap = bbox_gap_distance(left.bbox, right.bbox)
    merged = merge_bboxes([left.bbox, right.bbox])
    merged_metrics = measure_region(pixels, merged)
    area_ratio = min(bbox_area(left.bbox), bbox_area(right.bbox)) / max(1, max(bbox_area(left.bbox), bbox_area(right.bbox)))
    texture_gap = abs(left.metrics.texture_score - right.metrics.texture_score)
    edge_gap = abs(left.metrics.edge_score - right.metrics.edge_score)
    brightness_gap = abs(left.metrics.brightness - right.metrics.brightness) / 255
    aspect = merged[2] / max(1, merged[3])
    return {
        "distanceScore": max(0.0, 1.0 - gap / max(1, options.neighbor_search_radius)),
        "colorSimilarityScore": max(0.0, 1.0 - color_distance(left.mean_rgb, right.mean_rgb) / 765),
        "sizeCompatibilityScore": max(0.0, min(1.0, area_ratio)),
        "containerCompatibilityScore": container_compatibility(left, right),
        "mergedBboxScore": merged_bbox_score(merged, options),
        "styleSimilarityScore": max(0.0, 1.0 - (texture_gap + edge_gap + brightness_gap) / 3),
        "textLikePenalty": 1.0 if aspect > options.max_text_like_aspect_ratio and are_horizontally_aligned([left, right]) else 0.0,
        "boundaryViolationPenalty": boundary_violation,
        "mergedTextureScore": merged_metrics.texture_score,
    }
