from __future__ import annotations

from typing import Literal

from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_area, measure_region
from .geometry import group_confidence, is_text_like_sequence, merge_bboxes
from .lineage import build_group_lineage
from .types import M291FragmentCandidate, M291FragmentEdge, M291GroupMember, M291GroupType, M291Options, M291SymbolGroup


def build_symbol_groups(
    candidates: list[M291FragmentCandidate],
    edges: list[M291FragmentEdge],
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
    options: M291Options,
) -> list[M291SymbolGroup]:
    by_id = {candidate.id: candidate for candidate in candidates}
    parent = {candidate.id: candidate.id for candidate in candidates}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for edge in edges:
        if edge.decision == "accepted":
            union(edge.left_id, edge.right_id)

    clusters: dict[str, list[M291FragmentCandidate]] = {}
    for candidate in candidates:
        clusters.setdefault(find(candidate.id), []).append(candidate)

    groups: list[M291SymbolGroup] = []
    accepted_edges = [edge for edge in edges if edge.decision == "accepted"]
    for members in clusters.values():
        if len(members) < 2:
            continue
        group = score_symbol_group(f"group_{len(groups) + 1:03d}", members, accepted_edges, pixels, options)
        groups.append(group)
    return groups

def score_symbol_group(
    id: str,
    candidates: list[M291FragmentCandidate],
    accepted_edges: list[M291FragmentEdge],
    pixels: PngPixels,
    options: M291Options,
) -> M291SymbolGroup:
    bboxes = [candidate.bbox for candidate in candidates]
    bbox = merge_bboxes(bboxes)
    reasons: list[str] = []
    if len(candidates) > options.max_group_members:
        reasons.append("too_many_members")
    if is_text_like_sequence(candidates, bbox, options):
        reasons.append("text_like_sequence")
    merged_metrics = measure_region(pixels, bbox)
    if merged_metrics.color_count >= 48 and merged_metrics.texture_score >= 0.24 and bbox_area(bbox) >= 1200:
        reasons.append("image_like_merged_result")
    edge_scores = [
        edge.score
        for edge in accepted_edges
        if edge.left_id in {candidate.id for candidate in candidates} and edge.right_id in {candidate.id for candidate in candidates}
    ]
    mean_edge = sum(edge_scores) / max(1, len(edge_scores))
    confidence = group_confidence(candidates, bbox, mean_edge, merged_metrics, options)
    decision: Literal["accepted", "uncertain", "rejected"]
    group_type: M291GroupType
    if "text_like_sequence" in reasons or "image_like_merged_result" in reasons:
        decision = "rejected"
        group_type = "rejected_group"
        confidence = min(confidence, 0.35)
    elif len(candidates) > options.max_group_members:
        decision = "uncertain"
        group_type = "uncertain_group"
        confidence = min(confidence, 0.6)
    elif confidence >= options.accepted_group_threshold:
        decision = "accepted"
        group_type = "grouped_symbol"
        reasons.append("group_confidence_accepted")
    elif confidence >= options.uncertain_group_threshold:
        decision = "uncertain"
        group_type = "uncertain_group"
        reasons.append("group_confidence_uncertain")
    else:
        decision = "rejected"
        group_type = "rejected_group"
        reasons.append("group_confidence_rejected")
    members = [
        M291GroupMember(candidate.id, candidate.source_node_id, "foreground_symbol" if candidate.source_kind == "symbol" else "symbol_fragment")
        for candidate in candidates
    ]
    lineage = build_group_lineage(id, decision, candidates, reasons)
    rejected_lineage_reason = None
    if lineage is None and ("text_like_sequence" in reasons or "image_like_merged_result" in reasons):
        rejected_lineage_reason = "text_like_glyph_sequence" if "text_like_sequence" in reasons else "image_like_merged_result"
    return M291SymbolGroup(
        id=id,
        group_type=group_type,
        decision=decision,
        member_ids=[candidate.id for candidate in candidates],
        members=members,
        bbox=bbox,
        confidence=round(confidence, 4),
        reasons=reasons,
        source_lineage=lineage,
        rejected_lineage_reason=rejected_lineage_reason,
    )
