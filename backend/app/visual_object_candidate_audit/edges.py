from __future__ import annotations

from .geometry import (
    bbox_union,
    center_alignment_score,
    compact_union_score,
    dedupe_strings,
    expand_bbox,
    baseline_alignment_score,
    out_of_reasonable_bounds,
    same_column_like,
    same_row_like,
    size_compatibility,
)
from ..visual_primitive_graph import bbox_gap_distance, bbox_intersects
from .types import EdgeDecision, EvidenceEdgeKind, M2904Options, VisualObjectEvidenceEdge, VisualObjectEvidenceNode


def build_evidence_edges(nodes: list[VisualObjectEvidenceNode], width: int, height: int, options: M2904Options) -> list[VisualObjectEvidenceEdge]:
    edges: list[VisualObjectEvidenceEdge] = []
    pairs = candidate_pairs(nodes, options)
    for left, right in pairs:
        edge = score_edge(left, right, width, height, options, len(edges) + 1)
        edges.append(edge)
    return edges

def candidate_pairs(nodes: list[VisualObjectEvidenceNode], options: M2904Options) -> list[tuple[VisualObjectEvidenceNode, VisualObjectEvidenceNode]]:
    if len(nodes) <= options.max_full_pair_nodes:
        return [(left, right) for index, left in enumerate(nodes) for right in nodes[index + 1 :]]
    pairs: list[tuple[VisualObjectEvidenceNode, VisualObjectEvidenceNode]] = []
    for index, left in enumerate(nodes):
        candidates: list[tuple[int, VisualObjectEvidenceNode]] = []
        expanded = expand_bbox(left.bbox, options.near_distance * 2)
        for right in nodes[index + 1 :]:
            if bbox_intersects(expanded, right.bbox) or same_row_like(left.bbox, right.bbox, options) or same_column_like(left.bbox, right.bbox, options):
                candidates.append((bbox_gap_distance(left.bbox, right.bbox), right))
        for _distance, right in sorted(candidates, key=lambda item: item[0])[: options.max_neighbors_per_node]:
            pairs.append((left, right))
    return pairs

def score_edge(
    left: VisualObjectEvidenceNode,
    right: VisualObjectEvidenceNode,
    width: int,
    height: int,
    options: M2904Options,
    index: int,
) -> VisualObjectEvidenceEdge:
    distance = bbox_gap_distance(left.bbox, right.bbox)
    distance_score = max(0.0, 1.0 - distance / max(1, options.near_distance * 2))
    alignment_score = max(center_alignment_score(left.bbox, right.bbox), baseline_alignment_score(left.bbox, right.bbox, options))
    compactness_score = compact_union_score([left.bbox, right.bbox], options)
    source_compatibility_score = source_compatibility(left, right)
    shape_size_score = size_compatibility(left.bbox, right.bbox)
    repeated_context_score = 0.0
    text_overlap_penalty = 1.0 if "text_overlap" in {*left.risks, *right.risks} else 0.0
    boundary_penalty = 1.0 if out_of_reasonable_bounds(bbox_union([left.bbox, right.bbox]), width, height) else 0.0
    wide_source_penalty = 1.0 if "wide_source_bbox" in {*left.risks, *right.risks} else 0.0
    score = (
        0.25 * distance_score
        + 0.20 * alignment_score
        + 0.15 * compactness_score
        + 0.15 * source_compatibility_score
        + 0.15 * shape_size_score
        + 0.10 * repeated_context_score
        - 0.25 * text_overlap_penalty
        - 0.35 * boundary_penalty
        - 0.30 * wide_source_penalty
    )
    reasons = edge_reasons(left, right, distance, alignment_score, compactness_score)
    risks: list[str] = []
    if text_overlap_penalty:
        risks.append("text_overlap")
    if wide_source_penalty:
        risks.extend(["wide_source_bbox", "split_needed"])
    if boundary_penalty:
        risks.append("cross_boundary")
    if duplicate_source(left, right):
        risks.append("duplicate_source")
        reasons.append("duplicate_source")
    decision: EdgeDecision = "accepted" if score >= options.edge_threshold else "weak" if score >= options.weak_edge_threshold else "rejected"
    if boundary_penalty:
        decision = "rejected"
        reasons.append("boundary_violation")
    return VisualObjectEvidenceEdge(
        id=f"edge_{index:04d}",
        left_id=left.id,
        right_id=right.id,
        edge_kind=edge_kind_for(left, right, reasons, risks),
        decision=decision,
        score=max(0.0, min(1.0, score)),
        reasons=dedupe_strings(reasons),
        risks=dedupe_strings(risks),
        metrics={
            "distance": distance,
            "distanceScore": round(distance_score, 4),
            "alignmentScore": round(alignment_score, 4),
            "compactnessScore": round(compactness_score, 4),
            "sourceCompatibilityScore": round(source_compatibility_score, 4),
            "shapeSizeScore": round(shape_size_score, 4),
        },
    )

def source_compatibility(left: VisualObjectEvidenceNode, right: VisualObjectEvidenceNode) -> float:
    if duplicate_source(left, right):
        return 0.0
    if object_forming_visual_side(left) and object_forming_visual_side(right):
        return 0.9
    if (object_forming_visual_side(left) and text_side_allowed(right)) or (object_forming_visual_side(right) and text_side_allowed(left)):
        return 0.9
    if left.node_kind == right.node_kind == "text":
        return 0.75
    return 0.35

def edge_reasons(left: VisualObjectEvidenceNode, right: VisualObjectEvidenceNode, distance: int, alignment_score: float, compactness_score: float) -> list[str]:
    reasons: list[str] = []
    if distance <= 0:
        reasons.append("overlaps")
    elif distance <= 42:
        reasons.append("nearby_bbox")
    if alignment_score >= 0.65:
        reasons.append("aligned_centers")
    if compactness_score >= 0.55:
        reasons.append("compact_union_bbox")
    if is_visual_text_pair_nodes(left, right):
        reasons.append("short_text_near_visual")
    if left.node_kind == right.node_kind == "text":
        reasons.append("text_text_cluster")
    return reasons or ["weak_evidence_relation"]

def edge_kind_for(left: VisualObjectEvidenceNode, right: VisualObjectEvidenceNode, reasons: list[str], risks: list[str]) -> EvidenceEdgeKind:
    if "cross_boundary" in risks:
        return "cross_boundary"
    if duplicate_source(left, right):
        return "duplicate_overlap"
    if "overlaps" in reasons:
        return "overlaps"
    if "aligned_centers" in reasons:
        return "aligned_center"
    if "compact_union_bbox" in reasons:
        return "compact_union"
    if left.node_kind == right.node_kind == "text":
        return "same_row"
    return "near"

def duplicate_source(left: VisualObjectEvidenceNode, right: VisualObjectEvidenceNode) -> bool:
    return left.source == right.source and left.source_id == right.source_id

def object_forming_visual_side(node: VisualObjectEvidenceNode) -> bool:
    if node.ownership_routing is not None:
        return bool(node.ownership_routing.get("allowedForObjectFormingVisualSide"))
    return node.node_kind in {"visual", "weak_visual_text_noise", "wide_visual_source"}

def text_side_allowed(node: VisualObjectEvidenceNode) -> bool:
    if node.ownership_routing is not None:
        return bool(node.ownership_routing.get("allowedForTextSide"))
    return node.node_kind == "text"

def is_visual_text_pair_nodes(left: VisualObjectEvidenceNode, right: VisualObjectEvidenceNode) -> bool:
    return (object_forming_visual_side(left) and text_side_allowed(right)) or (object_forming_visual_side(right) and text_side_allowed(left))
