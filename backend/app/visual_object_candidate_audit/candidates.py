from __future__ import annotations

from pathlib import Path

from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_area
from .artifacts import export_object_asset
from .edges import is_visual_text_pair_nodes, object_forming_visual_side, text_side_allowed
from .geometry import bbox_union, dedupe_strings
from .types import (
    M2904Options,
    MemberRole,
    ObjectDecision,
    ObjectKind,
    VisualObjectCandidate,
    VisualObjectEvidenceEdge,
    VisualObjectEvidenceNode,
    VisualObjectMember,
)


def build_object_candidates(
    pixels: PngPixels,
    output_dir: Path,
    nodes: list[VisualObjectEvidenceNode],
    edges: list[VisualObjectEvidenceEdge],
    options: M2904Options,
) -> list[VisualObjectCandidate]:
    objects: list[VisualObjectCandidate] = []
    node_by_id = {node.id: node for node in nodes}
    accepted_or_weak = [edge for edge in edges if edge.decision in {"accepted", "weak"}]
    visual_text_edges = [
        edge
        for edge in accepted_or_weak
        if is_visual_text_pair_nodes(node_by_id[edge.left_id], node_by_id[edge.right_id])
        and "wide_source_bbox" not in edge.risks
    ]
    used_nodes: set[str] = set()
    for edge in sorted(visual_text_edges, key=lambda item: (-item.score, item.id)):
        left = node_by_id[edge.left_id]
        right = node_by_id[edge.right_id]
        if left.id in used_nodes or right.id in used_nodes:
            continue
        decision: ObjectDecision = "candidate" if edge.decision == "accepted" else "uncertain"
        objects.append(make_object(pixels, output_dir, f"voc_{len(objects) + 1:04d}", "visual_text_pair", decision, [left, right], [edge], options))
        used_nodes.update({left.id, right.id})

    for edge in sorted(accepted_or_weak, key=lambda item: (-item.score, item.id)):
        left = node_by_id[edge.left_id]
        right = node_by_id[edge.right_id]
        if "wide_source_bbox" in edge.risks:
            continue
        if left.id in used_nodes or right.id in used_nodes:
            continue
        if object_forming_visual_side(left) and object_forming_visual_side(right):
            decision = "candidate" if edge.decision == "accepted" else "uncertain"
            objects.append(make_object(pixels, output_dir, f"voc_{len(objects) + 1:04d}", "compound_visual", decision, [left, right], [edge], options))
            used_nodes.update({left.id, right.id})

    for edge in sorted(accepted_or_weak, key=lambda item: (-item.score, item.id)):
        left = node_by_id[edge.left_id]
        right = node_by_id[edge.right_id]
        if "wide_source_bbox" in edge.risks and any(node.node_kind == "wide_visual_source" for node in [left, right]):
            wide = left if left.node_kind == "wide_visual_source" else right
            other = right if wide is left else left
            if wide.id in used_nodes:
                continue
            objects.append(make_object(pixels, output_dir, f"voc_{len(objects) + 1:04d}", "split_candidate", "uncertain", [wide, other], [edge], options))
            used_nodes.add(wide.id)

    text_edges = [
        edge
        for edge in accepted_or_weak
        if node_by_id[edge.left_id].node_kind == "text" and node_by_id[edge.right_id].node_kind == "text"
    ]
    text_clusters = build_text_clusters(text_edges, node_by_id)
    for cluster_nodes, cluster_edges in text_clusters:
        if any(node.id in used_nodes for node in cluster_nodes):
            continue
        objects.append(make_object(pixels, output_dir, f"voc_{len(objects) + 1:04d}", "text_cluster", "rejected", cluster_nodes, cluster_edges, options))
        used_nodes.update(node.id for node in cluster_nodes)

    for node in nodes:
        if node.id in used_nodes:
            continue
        if node.node_kind == "visual" and object_forming_visual_side(node):
            objects.append(make_object(pixels, output_dir, f"voc_{len(objects) + 1:04d}", "single_visual", "candidate", [node], [], options))
            used_nodes.add(node.id)
        elif node.node_kind == "wide_visual_source":
            objects.append(make_object(pixels, output_dir, f"voc_{len(objects) + 1:04d}", "split_candidate", "uncertain", [node], [], options))
            used_nodes.add(node.id)
        elif node.node_kind in {"noise", "weak_visual_text_noise"} and object_forming_visual_side(node):
            objects.append(make_object(pixels, output_dir, f"voc_{len(objects) + 1:04d}", "uncertain_compound", "uncertain", [node], [], options))
            used_nodes.add(node.id)
        elif node.node_kind == "text":
            objects.append(make_object(pixels, output_dir, f"voc_{len(objects) + 1:04d}", "text_cluster", "rejected", [node], [], options))
            used_nodes.add(node.id)
    return dedupe_objects(objects)

def make_object(
    pixels: PngPixels,
    output_dir: Path,
    id: str,
    object_kind: ObjectKind,
    decision: ObjectDecision,
    nodes: list[VisualObjectEvidenceNode],
    edges: list[VisualObjectEvidenceEdge],
    options: M2904Options,
) -> VisualObjectCandidate:
    bbox = bbox_union([node.bbox for node in nodes])
    risks = dedupe_strings([risk for node in nodes for risk in node.risks] + [risk for edge in edges for risk in edge.risks])
    reasons = object_reasons(object_kind, nodes, edges)
    if object_kind == "split_candidate":
        risks = dedupe_strings([*risks, "wide_source_bbox", "split_needed"])
    if object_kind == "text_cluster":
        risks = dedupe_strings([*risks, "text_only"])
    confidence = object_confidence(object_kind, decision, nodes, edges)
    asset_path = export_object_asset(pixels, output_dir, object_kind, decision, id, bbox)
    return VisualObjectCandidate(
        id=id,
        object_kind=object_kind,
        decision=decision,
        bbox=bbox,
        confidence=confidence,
        members=[member_from_node(node) for node in nodes],
        edge_ids=[edge.id for edge in edges],
        risks=risks,
        reasons=reasons,
        suggested_next_action=suggested_action(object_kind, risks),
        asset_path=asset_path,
    )

def member_from_node(node: VisualObjectEvidenceNode) -> VisualObjectMember:
    role: MemberRole
    if node.ownership_routing is not None and text_side_allowed(node) and not object_forming_visual_side(node):
        role = "text"
    elif node.node_kind == "visual":
        role = "visual"
    elif node.node_kind == "text":
        role = "text"
    elif node.node_kind == "weak_visual_text_noise":
        role = "weak_visual"
    elif node.node_kind == "wide_visual_source":
        role = "wide_source"
    elif node.node_kind == "noise":
        role = "noise"
    else:
        role = "unknown"
    return VisualObjectMember(node.id, node.source, node.source_id, node.bbox, role, node.confidence, node.risks, node.reasons)

def object_reasons(object_kind: ObjectKind, nodes: list[VisualObjectEvidenceNode], edges: list[VisualObjectEvidenceEdge]) -> list[str]:
    reasons = [object_kind]
    reasons.extend(reason for edge in edges for reason in edge.reasons[:2])
    if any(node.node_kind == "weak_visual_text_noise" for node in nodes):
        reasons.append("weak_visual_text_noise_member")
    return dedupe_strings(reasons)

def object_confidence(object_kind: ObjectKind, decision: ObjectDecision, nodes: list[VisualObjectEvidenceNode], edges: list[VisualObjectEvidenceEdge]) -> float:
    if object_kind == "split_candidate":
        return 0.52
    if object_kind == "text_cluster":
        return 0.35
    edge_score = sum(edge.score for edge in edges) / len(edges) if edges else 0.58
    node_score = sum(node.confidence for node in nodes) / max(1, len(nodes))
    base = (edge_score + node_score) / 2
    if decision == "uncertain":
        return min(base, 0.62)
    if decision == "rejected":
        return min(base, 0.40)
    return min(0.88, max(0.45, base))

def suggested_action(object_kind: ObjectKind, risks: list[str]) -> str | None:
    if object_kind == "split_candidate" or "split_needed" in risks:
        return "needs_upstream_fragment_split_or_manual_review"
    if "text_overlap" in risks:
        return "review_text_overlap_weak_visual"
    if "duplicate_source" in risks:
        return "review_duplicate_source_conflict"
    return None

def build_text_clusters(edges: list[VisualObjectEvidenceEdge], node_by_id: dict[str, VisualObjectEvidenceNode]) -> list[tuple[list[VisualObjectEvidenceNode], list[VisualObjectEvidenceEdge]]]:
    clusters: list[tuple[list[VisualObjectEvidenceNode], list[VisualObjectEvidenceEdge]]] = []
    used: set[str] = set()
    for edge in edges:
        if edge.left_id in used or edge.right_id in used:
            continue
        nodes = [node_by_id[edge.left_id], node_by_id[edge.right_id]]
        used.update({edge.left_id, edge.right_id})
        clusters.append((nodes, [edge]))
    return clusters

def dedupe_objects(objects: list[VisualObjectCandidate]) -> list[VisualObjectCandidate]:
    result: list[VisualObjectCandidate] = []
    used_source_sets: list[set[str]] = []
    for item in sorted(objects, key=object_priority):
        source_set = {f"{member.source}:{member.source_id}" for member in item.members}
        if any(source_set and len(source_set & used) / max(1, min(len(source_set), len(used))) >= 0.80 for used in used_source_sets):
            result.append(
                VisualObjectCandidate(
                    id=item.id,
                    object_kind=item.object_kind,
                    decision="uncertain" if item.decision != "rejected" else "rejected",
                    bbox=item.bbox,
                    confidence=min(item.confidence, 0.45),
                    members=item.members,
                    edge_ids=item.edge_ids,
                    risks=dedupe_strings([*item.risks, "duplicate_source"]),
                    reasons=dedupe_strings([*item.reasons, "duplicate_source_conflict"]),
                    suggested_next_action=item.suggested_next_action or "review_duplicate_source_conflict",
                    asset_path=item.asset_path,
                )
            )
        else:
            result.append(item)
            used_source_sets.append(source_set)
    return sorted(result, key=lambda item: item.id)

def object_priority(item: VisualObjectCandidate) -> tuple[int, float, int]:
    kind_rank = {"visual_text_pair": 0, "compound_visual": 1, "single_visual": 2, "split_candidate": 3, "uncertain_compound": 4, "text_cluster": 5}
    return (kind_rank.get(item.object_kind, 9), -item.confidence, -bbox_area(item.bbox))
