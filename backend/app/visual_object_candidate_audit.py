from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_evidence_normalization import parse_bbox, parse_metrics
from .visual_primitive_graph import (
    M29PrimitiveMetrics,
    bbox_area,
    bbox_clamp,
    bbox_contains,
    bbox_gap_distance,
    bbox_in_bounds,
    bbox_intersects,
    bbox_iou,
    bbox_x2,
    bbox_y2,
    crop_pixels,
    draw_rect,
    metrics_to_dict,
)


EvidenceSource = Literal["m2903_visual_evidence", "m2902_text_box"]
EvidenceNodeKind = Literal["visual", "text", "weak_visual_text_noise", "wide_visual_source", "noise"]
EvidenceEdgeKind = Literal[
    "near",
    "aligned_center",
    "above_below",
    "contains",
    "overlaps",
    "same_row",
    "same_column",
    "regular_spacing",
    "compact_union",
    "duplicate_overlap",
    "cross_boundary",
]
EdgeDecision = Literal["accepted", "weak", "rejected"]
ObjectKind = Literal["single_visual", "compound_visual", "visual_text_pair", "text_cluster", "split_candidate", "uncertain_compound"]
ObjectDecision = Literal["accepted", "candidate", "uncertain", "rejected"]
MemberRole = Literal["visual", "text", "weak_visual", "nearby_text", "wide_source", "noise", "unknown"]
SetKind = Literal["repeated_visual_set", "aligned_row_set", "aligned_grid_set"]
SetDecision = Literal["candidate", "uncertain", "rejected"]


@dataclass(frozen=True)
class M2904Options:
    edge_threshold: float = 0.68
    weak_edge_threshold: float = 0.52
    max_object_members: int = 5
    output_preview_max_thumb: int = 160
    text_preview_max_chars: int = 24
    max_full_pair_nodes: int = 300
    max_neighbors_per_node: int = 32
    near_distance: int = 42
    alignment_tolerance: int = 32
    row_tolerance: int = 20
    max_visual_text_gap: int = 58
    compact_area_multiplier: float = 3.0
    wide_aspect_ratio: float = 4.0
    wide_anchor_min_count: int = 2
    min_set_members: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M2904SourceExpansionRefs:
    m29_nodes_json: str | None = None
    m291_group_nodes_json: str | None = None
    m2902_media_evidence_json: str | None = None
    m2907_ownership_json: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        data = {
            "m29NodesJson": self.m29_nodes_json,
            "m291GroupNodesJson": self.m291_group_nodes_json,
            "m2902MediaEvidenceJson": self.m2902_media_evidence_json,
        }
        if self.m2907_ownership_json is not None:
            data["m2907OwnershipJson"] = self.m2907_ownership_json
        return data


@dataclass(frozen=True)
class VisualObjectEvidenceNode:
    id: str
    source: EvidenceSource
    source_id: str
    bbox: list[int]
    node_kind: EvidenceNodeKind
    source_visual_kind: str | None
    source_decision: str | None
    text: str | None
    text_preview: str | None
    confidence: float
    metrics: M29PrimitiveMetrics | None
    risks: list[str]
    reasons: list[str]
    ownership_routing: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "source": self.source,
            "sourceId": self.source_id,
            "bbox": self.bbox,
            "nodeKind": self.node_kind,
            "sourceVisualKind": self.source_visual_kind,
            "sourceDecision": self.source_decision,
            "text": self.text,
            "textPreview": self.text_preview,
            "confidence": round(self.confidence, 3),
            "metrics": metrics_to_dict(self.metrics) if self.metrics is not None else None,
            "risks": self.risks,
            "reasons": self.reasons,
        }
        if self.ownership_routing is not None:
            data["ownershipRouting"] = self.ownership_routing
        return data


@dataclass(frozen=True)
class VisualObjectEvidenceEdge:
    id: str
    left_id: str
    right_id: str
    edge_kind: EvidenceEdgeKind
    decision: EdgeDecision
    score: float
    reasons: list[str]
    risks: list[str]
    metrics: dict[str, object]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "leftId": self.left_id,
            "rightId": self.right_id,
            "edgeKind": self.edge_kind,
            "decision": self.decision,
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "risks": self.risks,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class VisualObjectMember:
    evidence_node_id: str
    source: EvidenceSource
    source_id: str
    bbox: list[int]
    member_role: MemberRole
    confidence: float
    risks: list[str]
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidenceNodeId": self.evidence_node_id,
            "source": self.source,
            "sourceId": self.source_id,
            "bbox": self.bbox,
            "memberRole": self.member_role,
            "confidence": round(self.confidence, 3),
            "risks": self.risks,
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class VisualObjectCandidate:
    id: str
    object_kind: ObjectKind
    decision: ObjectDecision
    bbox: list[int]
    confidence: float
    members: list[VisualObjectMember]
    edge_ids: list[str]
    risks: list[str]
    reasons: list[str]
    suggested_next_action: str | None
    asset_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "objectKind": self.object_kind,
            "decision": self.decision,
            "bbox": self.bbox,
            "confidence": round(self.confidence, 3),
            "members": [member.to_dict() for member in self.members],
            "edgeIds": self.edge_ids,
            "risks": self.risks,
            "reasons": self.reasons,
            "suggestedNextAction": self.suggested_next_action,
            "assetPath": self.asset_path,
        }


@dataclass(frozen=True)
class VisualObjectSetCandidate:
    id: str
    set_kind: SetKind
    decision: SetDecision
    member_object_ids: list[str]
    bbox: list[int]
    confidence: float
    edge_ids: list[str]
    risks: list[str]
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "setKind": self.set_kind,
            "decision": self.decision,
            "memberObjectIds": self.member_object_ids,
            "bbox": self.bbox,
            "confidence": round(self.confidence, 3),
            "edgeIds": self.edge_ids,
            "risks": self.risks,
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class EdgeAuditItem:
    edge_id: str
    left_id: str
    right_id: str
    decision: EdgeDecision
    score: float
    reasons: list[str]
    risks: list[str]
    metrics: dict[str, object]

    def to_dict(self) -> dict[str, Any]:
        return {
            "edgeId": self.edge_id,
            "leftId": self.left_id,
            "rightId": self.right_id,
            "decision": self.decision,
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "risks": self.risks,
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class M2904DebugArtifacts:
    visual_object_candidates: str | None = None
    visual_object_edges: str | None = None
    split_candidates: str | None = None
    visual_object_sets: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "visualObjectCandidates": self.visual_object_candidates,
                "visualObjectEdges": self.visual_object_edges,
                "splitCandidates": self.split_candidates,
                "visualObjectSets": self.visual_object_sets,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class M2904Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_m2903_visual_evidence_json: str
    source_m2902_audit_json: str
    source_expansion_refs: M2904SourceExpansionRefs
    options: M2904Options
    evidence_nodes: list[VisualObjectEvidenceNode]
    evidence_edges: list[VisualObjectEvidenceEdge]
    objects: list[VisualObjectCandidate]
    sets: list[VisualObjectSetCandidate]
    edge_audit: list[EdgeAuditItem]
    debug: M2904DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM2903VisualEvidenceJson": self.source_m2903_visual_evidence_json,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "sourceExpansionRefs": self.source_expansion_refs.to_dict(),
            "options": self.options.to_dict(),
            "evidenceNodes": [node.to_dict() for node in self.evidence_nodes],
            "evidenceEdges": [edge.to_dict() for edge in self.evidence_edges],
            "objects": [item.to_dict() for item in self.objects],
            "sets": [item.to_dict() for item in self.sets],
            "edgeAudit": [item.to_dict() for item in self.edge_audit],
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }


def extract_visual_object_candidate_audit(
    *,
    png_data: bytes,
    source_image: str,
    m2903_document: dict[str, Any],
    m2903_visual_evidence_json_path: str,
    m2902_document: dict[str, Any],
    m2902_audit_json_path: str,
    output_dir: Path,
    source_expansion_refs: M2904SourceExpansionRefs | None = None,
    options: M2904Options | None = None,
    m2907_ownership_document: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    emit_debug_artifacts: bool = True,
    emit_preview_artifacts: bool = True,
) -> M2904Document:
    options = options or M2904Options()
    source_expansion_refs = source_expansion_refs or M2904SourceExpansionRefs(m2902_media_evidence_json=m2902_audit_json_path)
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    ownership_routing, ownership_warnings = build_ownership_routing(m2907_ownership_document)
    evidence_nodes, node_warnings = build_evidence_nodes(m2903_document, m2902_document, pixels.width, pixels.height, options, ownership_routing)
    evidence_edges = build_evidence_edges(evidence_nodes, pixels.width, pixels.height, options)
    edge_audit = [EdgeAuditItem(edge.id, edge.left_id, edge.right_id, edge.decision, edge.score, edge.reasons, edge.risks, edge.metrics) for edge in evidence_edges]
    objects = build_object_candidates(pixels, output_dir, evidence_nodes, evidence_edges, options)
    sets = build_set_candidates(objects, evidence_edges, options)
    debug = M2904DebugArtifacts()
    if emit_debug_artifacts:
        debug = write_debug_artifacts(pixels, output_dir, evidence_nodes, objects, sets, evidence_edges)
    if emit_preview_artifacts and debug.to_dict():
        preview_path = output_dir / "preview_visual_objects.png"
        preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, objects, sets, options))
    document = M2904Document(
        schema_name="M2904GenericVisualObjectCandidateAuditDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m2903_visual_evidence_json=m2903_visual_evidence_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        source_expansion_refs=source_expansion_refs,
        options=options,
        evidence_nodes=evidence_nodes,
        evidence_edges=evidence_edges,
        objects=objects,
        sets=sets,
        edge_audit=edge_audit,
        debug=debug,
        warnings=[*(warnings or []), *ownership_warnings, *node_warnings],
        meta=build_meta(evidence_nodes, evidence_edges, objects, sets),
    )
    validate_visual_object_candidate_audit_document(
        document,
        output_dir,
        pixels.width,
        pixels.height,
        require_preview_artifacts=emit_preview_artifacts,
    )
    write_outputs(document, output_dir)
    return document


def build_evidence_nodes(
    m2903_document: dict[str, Any],
    m2902_document: dict[str, Any],
    width: int,
    height: int,
    options: M2904Options,
    ownership_routing: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[VisualObjectEvidenceNode], list[str]]:
    warnings: list[str] = []
    nodes: list[VisualObjectEvidenceNode] = []
    for raw in m2903_document.get("items", []):
        if not isinstance(raw, dict):
            continue
        bbox = parse_bbox(raw.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        source_id = str(raw.get("id") or "")
        if not source_id:
            continue
        visual_kind = str(raw.get("visualKind") or "")
        metrics = parse_metrics(raw.get("metrics"))
        node_kind, risks, reasons = classify_m2903_node(raw, bbox, metrics, options, warnings)
        ownership = (ownership_routing or {}).get(f"m2903_visual_evidence:{source_id}")
        nodes.append(
            VisualObjectEvidenceNode(
                id=f"evidence_{len(nodes) + 1:04d}",
                source="m2903_visual_evidence",
                source_id=source_id,
                bbox=bbox,
                node_kind=node_kind,
                source_visual_kind=visual_kind,
                source_decision=str(raw.get("decision") or ""),
                text=None,
                text_preview=None,
                confidence=float(raw.get("confidence", 0.5)),
                metrics=metrics,
                risks=ownership_augmented_risks(risks, ownership),
                reasons=ownership_augmented_reasons([*reasons, *[str(reason) for reason in raw.get("reasons", [])]], ownership),
                ownership_routing=ownership,
            )
        )
    for raw in m2902_document.get("textBoxes", []):
        if not isinstance(raw, dict):
            continue
        bbox = parse_bbox(raw.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        source_id = str(raw.get("id") or "")
        if not source_id:
            continue
        text = str(raw.get("text") or "").strip() or None
        ownership = (ownership_routing or {}).get(f"m2902_text_box:{source_id}")
        nodes.append(
            VisualObjectEvidenceNode(
                id=f"evidence_{len(nodes) + 1:04d}",
                source="m2902_text_box",
                source_id=source_id,
                bbox=bbox,
                node_kind="text",
                source_visual_kind=None,
                source_decision=None,
                text=text,
                text_preview=truncate_text(text, options.text_preview_max_chars),
                confidence=float(raw.get("confidence", 1.0)),
                metrics=None,
                risks=ownership_augmented_risks([], ownership),
                reasons=ownership_augmented_reasons(["m2902_text_box"], ownership),
                ownership_routing=ownership,
            )
        )
    return nodes, warnings


def build_ownership_routing(document: dict[str, Any] | None) -> tuple[dict[str, dict[str, Any]] | None, list[str]]:
    if document is None:
        return None, []
    if document.get("schemaName") != "M2907TextVisualOwnershipGateDocument" or document.get("schemaVersion") != "0.1":
        raise ValueError("M29.0.4 ownership input must be M2907TextVisualOwnershipGateDocument v0.1")
    routing: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for raw in document.get("ownershipDecisions", []):
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source") or "")
        if source == "m2903_visual_evidence":
            source_id = str(raw.get("sourceVisualEvidenceItemId") or "")
        elif source == "m2902_text_box":
            source_id = str(raw.get("sourceTextBoxId") or "")
        else:
            warnings.append(f"unknown_m2907_ownership_source:{source or '<empty>'}")
            continue
        if not source_id:
            warnings.append(f"missing_m2907_ownership_source_id:{raw.get('id', '<missing>')}")
            continue
        routing[f"{source}:{source_id}"] = {
            "ownershipDecisionId": str(raw.get("id") or ""),
            "ownership": str(raw.get("ownership") or ""),
            "decision": str(raw.get("decision") or ""),
            "ownershipReasonKind": str(raw.get("ownershipReasonKind") or ""),
            "matchedTextBoxIds": [str(item) for item in raw.get("matchedTextBoxIds", [])],
            "textPreview": raw.get("textPreview"),
            "suppressedAsVisual": bool(raw.get("suppressedAsVisual")),
            "allowedForObjectFormingVisualSide": bool(raw.get("allowedForObjectFormingVisualSide")),
            "allowedForTextSide": bool(raw.get("allowedForTextSide")),
            "allowedForAuditOnly": bool(raw.get("allowedForAuditOnly", True)),
        }
    return routing, warnings


def ownership_augmented_risks(risks: list[str], ownership: dict[str, Any] | None) -> list[str]:
    if ownership is None:
        return risks
    additions: list[str] = []
    if bool(ownership.get("suppressedAsVisual")):
        additions.append("ownership_suppressed_as_visual")
    if str(ownership.get("ownership") or "") == "mixed_or_uncertain":
        additions.append("ownership_mixed_or_uncertain")
    return dedupe_strings([*risks, *additions])


def ownership_augmented_reasons(reasons: list[str], ownership: dict[str, Any] | None) -> list[str]:
    if ownership is None:
        return reasons
    additions = [
        "m2907_ownership_routing",
        str(ownership.get("ownershipReasonKind") or ""),
    ]
    return dedupe_strings([*reasons, *additions])


def classify_m2903_node(
    raw: dict[str, Any],
    bbox: list[int],
    metrics: M29PrimitiveMetrics,
    options: M2904Options,
    warnings: list[str],
) -> tuple[EvidenceNodeKind, list[str], list[str]]:
    visual_kind = str(raw.get("visualKind") or "")
    text_overlap = float(raw.get("textOverlapRatio", 0.0))
    risks: list[str] = []
    reasons: list[str] = [f"from_{visual_kind or 'unknown_visual_kind'}"]
    if is_wide_bbox(bbox, options):
        risks.append("wide_source_bbox")
        return "wide_visual_source", risks, [*reasons, "wide_visual_source"]
    if visual_kind in {"accepted_image", "media_candidate", "icon_candidate", "other_candidate"}:
        return "visual", risks, reasons
    if visual_kind == "mixed_symbol_text_candidate":
        return "noise", ["symbol_text_ownership_conflict"], [*reasons, "mixed_symbol_text_candidate_audit_only"]
    if visual_kind == "text_noise":
        if is_icon_like_text_noise(bbox, metrics):
            return "weak_visual_text_noise", ["text_overlap", "icon_like_text_noise"], [*reasons, "icon_like_text_noise"]
        return "noise", ["text_overlap"] if text_overlap > 0 else [], reasons
    warnings.append(f"unknown_visual_kind:{visual_kind or '<empty>'}")
    return "noise", ["unknown_visual_kind"], [*reasons, "unknown_visual_kind"]


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


def build_set_candidates(
    objects: list[VisualObjectCandidate],
    edges: list[VisualObjectEvidenceEdge],
    options: M2904Options,
) -> list[VisualObjectSetCandidate]:
    usable = [item for item in objects if item.decision in {"accepted", "candidate", "uncertain"} and item.object_kind in {"visual_text_pair", "single_visual", "compound_visual"}]
    rows = group_objects_by_row(usable, options)
    sets: list[VisualObjectSetCandidate] = []
    for row in rows:
        if len(row) < options.min_set_members:
            continue
        row = sorted(row, key=lambda item: center_x(item.bbox))
        if not regular_spacing(row):
            set_kind: SetKind = "aligned_row_set"
            confidence = 0.58
            reasons = ["aligned_row"]
        else:
            set_kind = "repeated_visual_set"
            confidence = 0.72
            reasons = ["same_row", "regular_spacing"]
        sets.append(
            VisualObjectSetCandidate(
                id=f"set_{len(sets) + 1:04d}",
                set_kind=set_kind,
                decision="candidate",
                member_object_ids=[item.id for item in row],
                bbox=bbox_union([item.bbox for item in row]),
                confidence=confidence,
                edge_ids=[],
                risks=[],
                reasons=reasons,
            )
        )
    return sets


def export_object_asset(pixels: PngPixels, output_dir: Path, object_kind: ObjectKind, decision: ObjectDecision, id: str, bbox: list[int]) -> str:
    if object_kind == "split_candidate":
        folder = "split_candidates"
    elif decision == "uncertain":
        folder = "uncertain_objects"
    elif decision == "rejected":
        folder = "rejected_objects"
    else:
        folder = "visual_objects"
    target = output_dir / "assets" / folder
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{id}.png"
    path.write_bytes(crop_pixels(pixels, bbox))
    return str(path.relative_to(output_dir))


def write_debug_artifacts(
    pixels: PngPixels,
    output_dir: Path,
    nodes: list[VisualObjectEvidenceNode],
    objects: list[VisualObjectCandidate],
    sets: list[VisualObjectSetCandidate],
    edges: list[VisualObjectEvidenceEdge],
) -> M2904DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = overlay_dir / "16_visual_object_candidates.png"
    edges_path = overlay_dir / "17_visual_object_edges.png"
    split_path = overlay_dir / "18_split_candidates.png"
    sets_path = overlay_dir / "19_visual_object_sets.png"
    candidates_path.write_bytes(overlay_objects(pixels, objects, include=lambda item: True))
    edges_path.write_bytes(overlay_edges(pixels, nodes, objects, edges))
    split_path.write_bytes(overlay_objects(pixels, objects, include=lambda item: item.object_kind == "split_candidate" or item.decision in {"uncertain", "rejected"}))
    sets_path.write_bytes(overlay_sets(pixels, objects, sets))
    return M2904DebugArtifacts(
        visual_object_candidates=str(candidates_path.relative_to(output_dir)),
        visual_object_edges=str(edges_path.relative_to(output_dir)),
        split_candidates=str(split_path.relative_to(output_dir)),
        visual_object_sets=str(sets_path.relative_to(output_dir)),
    )


def overlay_objects(pixels: PngPixels, objects: list[VisualObjectCandidate], *, include: Any) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in objects:
        if include(item):
            draw_rect(rows, pixels.width, pixels.height, item.bbox, object_color(item), 3 if item.decision in {"accepted", "candidate"} else 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_edges(
    pixels: PngPixels,
    nodes: list[VisualObjectEvidenceNode],
    objects: list[VisualObjectCandidate],
    edges: list[VisualObjectEvidenceEdge],
) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    node_by_id = {node.id: node for node in nodes}
    for edge in edges:
        left = node_by_id.get(edge.left_id)
        right = node_by_id.get(edge.right_id)
        if left is None or right is None:
            continue
        draw_line(rows, pixels.width, pixels.height, bbox_center(left.bbox), bbox_center(right.bbox), edge_color(edge))
    for item in objects:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, object_color(item), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_sets(pixels: PngPixels, objects: list[VisualObjectCandidate], sets: list[VisualObjectSetCandidate]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    object_by_id = {item.id: item for item in objects}
    for item in sets:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, (0, 122, 255), 3)
        for object_id in item.member_object_ids:
            member = object_by_id.get(object_id)
            if member is not None:
                draw_rect(rows, pixels.width, pixels.height, member.bbox, (0, 200, 90), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def build_preview_sheet(
    pixels: PngPixels,
    output_dir: Path,
    debug: M2904DebugArtifacts,
    objects: list[VisualObjectCandidate],
    sets: list[VisualObjectSetCandidate],
    options: M2904Options,
) -> bytes:
    overlays = [decode_png_pixels((output_dir / path).read_bytes()) for path in debug.to_dict().values()]
    sheet_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.32, (sheet_width - margin * 2 - gap * 4) / max(1, pixels.width * 5))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    previews = crop_previews_for_objects(output_dir, objects, options.output_preview_max_thumb)
    grid_h = grid_height(previews, sheet_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    x = margin
    for image in [pixels, *overlays]:
        paste_scaled(canvas, sheet_width, image, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, sheet_width, previews, margin, margin + top_h + margin, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])


def crop_previews_for_objects(output_dir: Path, objects: list[VisualObjectCandidate], max_edge: int) -> list[tuple[VisualObjectCandidate, PngPixels, int, int]]:
    previews: list[tuple[VisualObjectCandidate, PngPixels, int, int]] = []
    for item in sorted(objects, key=object_sort_key):
        if item.asset_path is None:
            continue
        try:
            pixels = decode_png_pixels((output_dir / item.asset_path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, pixels.width, pixels.height))
        previews.append((item, pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews


def write_outputs(document: M2904Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "visual_object_candidates.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "edge_audit.json").write_text(json.dumps([item.to_dict() for item in document.edge_audit], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "visual_object_candidates.md").write_text(build_markdown_report(document), encoding="utf-8")


def build_markdown_report(document: M2904Document) -> str:
    lines = [
        "# M29.0.4 Generic Visual Object Candidate Audit",
        "",
        f"- Source M29.0.3: `{document.source_m2903_visual_evidence_json}`",
        f"- Source M29.0.2: `{document.source_m2902_audit_json}`",
        f"- Evidence nodes: {len(document.evidence_nodes)}",
        f"- Evidence edges: {len(document.evidence_edges)}",
        f"- Objects: {len(document.objects)}",
        f"- Sets: {len(document.sets)}",
        f"- Object decisions: `{document.meta.get('objectDecisionCounts', {})}`",
        f"- Object kinds: `{document.meta.get('objectKindCounts', {})}`",
        "",
        "## Objects",
        "",
    ]
    for item in document.objects[:180]:
        member_summary = ", ".join(f"{member.member_role}:{member.source_id}" for member in item.members)
        lines.append(f"- `{item.id}` `{item.object_kind}` `{item.decision}` bbox={item.bbox} risks={item.risks} members=[{member_summary}]")
    if document.sets:
        lines.extend(["", "## Sets", ""])
        for item in document.sets:
            lines.append(f"- `{item.id}` `{item.set_kind}` `{item.decision}` members={item.member_object_ids} bbox={item.bbox}")
    return "\n".join(lines).rstrip() + "\n"


def validate_visual_object_candidate_audit_document(
    document: M2904Document,
    output_dir: Path,
    width: int,
    height: int,
    *,
    require_preview_artifacts: bool = True,
) -> None:
    if document.schema_name != "M2904GenericVisualObjectCandidateAuditDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.4 document schema")
    node_ids = assert_unique([node.id for node in document.evidence_nodes], "evidence node")
    edge_ids = assert_unique([edge.id for edge in document.evidence_edges], "evidence edge")
    object_ids = assert_unique([item.id for item in document.objects], "object")
    assert_unique([item.id for item in document.sets], "set")
    for node in document.evidence_nodes:
        if not bbox_in_bounds(node.bbox, width, height):
            raise ValueError(f"M29.0.4 evidence node bbox out of bounds: {node.id}")
        if node.source not in {"m2903_visual_evidence", "m2902_text_box"}:
            raise ValueError(f"M29.0.4 illegal candidate source: {node.source}")
    for edge in document.evidence_edges:
        if edge.left_id not in node_ids or edge.right_id not in node_ids:
            raise ValueError(f"M29.0.4 edge references missing node: {edge.id}")
    for item in document.objects:
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.4 object bbox out of bounds: {item.id}")
        for member in item.members:
            if member.evidence_node_id not in node_ids:
                raise ValueError(f"M29.0.4 object member references missing node: {item.id}")
        for edge_id in item.edge_ids:
            if edge_id not in edge_ids:
                raise ValueError(f"M29.0.4 object references missing edge: {item.id}")
        if item.asset_path is not None:
            metadata = assert_readable_relative_png(output_dir, item.asset_path)
            if metadata.width != item.bbox[2] or metadata.height != item.bbox[3]:
                raise ValueError(f"M29.0.4 object asset dimensions do not match bbox: {item.id}")
    for item in document.sets:
        for object_id in item.member_object_ids:
            if object_id not in object_ids:
                raise ValueError(f"M29.0.4 set references missing object: {item.id}")
            if next(obj for obj in document.objects if obj.id == object_id).decision == "rejected" and item.decision != "rejected":
                raise ValueError(f"M29.0.4 set references rejected object: {item.id}")
        for edge_id in item.edge_ids:
            if edge_id not in edge_ids:
                raise ValueError(f"M29.0.4 set references missing edge: {item.id}")
    audited = {item.edge_id for item in document.edge_audit}
    if audited != edge_ids:
        raise ValueError("M29.0.4 edgeAudit must cover all evidenceEdges")
    for path in document.debug.to_dict().values():
        metadata = assert_readable_relative_png(output_dir, path)
        if metadata.width != width or metadata.height != height:
            raise ValueError(f"M29.0.4 overlay dimensions do not match source image: {path}")
    if require_preview_artifacts:
        assert_readable_relative_png(output_dir, "preview_visual_objects.png")


def assert_readable_relative_png(output_dir: Path, path: str):
    resolved = output_dir / path
    if not resolved.exists():
        raise ValueError(f"M29.0.4 PNG output missing or unreadable: {path}")
    metadata = read_png_metadata(resolved.read_bytes())
    if metadata is None:
        raise ValueError(f"M29.0.4 PNG output missing or unreadable: {path}")
    return metadata


def assert_unique(values: list[str], label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate M29.0.4 {label} id: {value}")
        seen.add(value)
    return seen


def build_meta(
    nodes: list[VisualObjectEvidenceNode],
    edges: list[VisualObjectEvidenceEdge],
    objects: list[VisualObjectCandidate],
    sets: list[VisualObjectSetCandidate],
) -> dict[str, Any]:
    return {
        "notes": "m29_0_4_generic_visual_object_candidate_audit",
        "evidenceNodeCount": len(nodes),
        "evidenceEdgeCount": len(edges),
        "objectCount": len(objects),
        "setCount": len(sets),
        "objectKindCounts": count_by(objects, lambda item: item.object_kind),
        "objectDecisionCounts": count_by(objects, lambda item: item.decision),
        "edgeDecisionCounts": count_by(edges, lambda item: item.decision),
        "setKindCounts": count_by(sets, lambda item: item.set_kind),
    }


def count_by(items: list[Any], key_fn: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(key_fn(item))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def is_icon_like_text_noise(bbox: list[int], metrics: M29PrimitiveMetrics) -> bool:
    area = bbox_area(bbox)
    max_edge = max(bbox[2], bbox[3])
    aspect = bbox[2] / max(1, bbox[3])
    return 16 <= area <= 12000 and max_edge <= 128 and aspect <= 3.0 and (metrics.color_count >= 6 or metrics.texture_score >= 0.04)


def is_wide_bbox(bbox: list[int], options: M2904Options) -> bool:
    aspect = bbox[2] / max(1, bbox[3])
    return aspect >= options.wide_aspect_ratio and bbox[2] >= options.near_distance * 3


def truncate_text(text: str | None, max_chars: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= max_chars else text[:max_chars] + "..."


def expand_bbox(bbox: list[int], padding: int) -> list[int]:
    return [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding * 2, bbox[3] + padding * 2]


def center_x(bbox: list[int]) -> float:
    return bbox[0] + bbox[2] / 2


def center_y(bbox: list[int]) -> float:
    return bbox[1] + bbox[3] / 2


def same_row_like(left: list[int], right: list[int], options: M2904Options) -> bool:
    return abs(center_y(left) - center_y(right)) <= options.row_tolerance


def same_column_like(left: list[int], right: list[int], options: M2904Options) -> bool:
    return abs(center_x(left) - center_x(right)) <= options.alignment_tolerance


def center_alignment_score(left: list[int], right: list[int]) -> float:
    delta = min(abs(center_x(left) - center_x(right)), abs(center_y(left) - center_y(right)))
    return max(0.0, 1.0 - delta / 64)


def baseline_alignment_score(left: list[int], right: list[int], options: M2904Options) -> float:
    return max(0.0, 1.0 - abs(bbox_y2(left) - bbox_y2(right)) / max(1, options.row_tolerance * 2))


def compact_union_score(bboxes: list[list[int]], options: M2904Options) -> float:
    union = bbox_union(bboxes)
    area_sum = sum(bbox_area(bbox) for bbox in bboxes)
    if bbox_area(union) <= 0:
        return 0.0
    ratio = bbox_area(union) / max(1, area_sum)
    return max(0.0, 1.0 - (ratio - 1.0) / max(1.0, options.compact_area_multiplier))


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


def size_compatibility(left: list[int], right: list[int]) -> float:
    left_area = bbox_area(left)
    right_area = bbox_area(right)
    if left_area <= 0 or right_area <= 0:
        return 0.0
    ratio = max(left_area, right_area) / max(1, min(left_area, right_area))
    return max(0.0, 1.0 - (ratio - 1.0) / 8.0)


def out_of_reasonable_bounds(bbox: list[int], width: int, height: int) -> bool:
    return not bbox_in_bounds(bbox, width, height) or bbox_area(bbox) > width * height * 0.35


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


def group_objects_by_row(objects: list[VisualObjectCandidate], options: M2904Options) -> list[list[VisualObjectCandidate]]:
    rows: list[list[VisualObjectCandidate]] = []
    for item in sorted(objects, key=lambda obj: (center_y(obj.bbox), center_x(obj.bbox))):
        for row in rows:
            if abs(sum(center_y(obj.bbox) for obj in row) / len(row) - center_y(item.bbox)) <= options.row_tolerance:
                row.append(item)
                break
        else:
            rows.append([item])
    return rows


def regular_spacing(objects: list[VisualObjectCandidate]) -> bool:
    if len(objects) < 3:
        return False
    centers = [center_x(item.bbox) for item in objects]
    gaps = [centers[index + 1] - centers[index] for index in range(len(centers) - 1)]
    avg = sum(gaps) / len(gaps)
    return avg > 0 and all(abs(gap - avg) <= max(18, avg * 0.35) for gap in gaps)


def object_color(item: VisualObjectCandidate) -> tuple[int, int, int]:
    if item.object_kind == "split_candidate":
        return (235, 64, 52)
    return {
        "accepted": (0, 180, 210),
        "candidate": (0, 200, 90),
        "uncertain": (238, 190, 40),
        "rejected": (170, 170, 170),
    }[item.decision]


def edge_color(edge: VisualObjectEvidenceEdge) -> tuple[int, int, int]:
    if edge.decision == "accepted":
        return (0, 180, 90)
    if edge.decision == "weak":
        return (238, 190, 40)
    return (170, 170, 170)


def bbox_center(bbox: list[int]) -> tuple[int, int]:
    return (round(bbox[0] + bbox[2] / 2), round(bbox[1] + bbox[3] / 2))


def draw_line(
    rows: list[bytearray],
    image_width: int,
    image_height: int,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    color_bytes = bytes(color)
    while True:
        if 0 <= x0 < image_width and 0 <= y0 < image_height:
            rows[y0][x0 * 3 : x0 * 3 + 3] = color_bytes
        if x0 == x1 and y0 == y1:
            break
        twice_error = 2 * error
        if twice_error >= dy:
            error += dy
            x0 += sx
        if twice_error <= dx:
            error += dx
            y0 += sy


def object_sort_key(item: VisualObjectCandidate) -> tuple[int, int, int, int, str]:
    decision_rank = {"accepted": 0, "candidate": 1, "uncertain": 2, "rejected": 3}.get(item.decision, 9)
    kind_rank = {"visual_text_pair": 0, "compound_visual": 1, "single_visual": 2, "split_candidate": 3, "uncertain_compound": 4, "text_cluster": 5}.get(item.object_kind, 9)
    return (decision_rank, kind_rank, item.bbox[1], item.bbox[0], item.id)


def grid_height(previews: list[tuple[VisualObjectCandidate, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 48
    x = margin
    row_h = 0
    total = 0
    for _item, _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h


def paste_grid(
    canvas: list[bytearray],
    sheet_width: int,
    previews: list[tuple[VisualObjectCandidate, PngPixels, int, int]],
    x: int,
    y: int,
    gap: int,
) -> int:
    row_h = 0
    margin = x
    if not previews:
        fill_rect(canvas, sheet_width, x, y, sheet_width - x * 2, 48, (232, 232, 232))
        return y + 48
    for item, preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, object_color(item))
        fill_rect(canvas, sheet_width, x - 2, y - 2, width + 4, height + 4, (244, 244, 244))
        paste_scaled(canvas, sheet_width, preview, x, y, width, height)
        x += width + gap
        row_h = max(row_h, height)
    return y + row_h


def paste_scaled(canvas: list[bytearray], sheet_width: int, source: PngPixels, x: int, y: int, target_width: int, target_height: int) -> None:
    for target_y in range(target_height):
        source_y = min(source.height - 1, round(target_y * source.height / target_height))
        if y + target_y < 0 or y + target_y >= len(canvas):
            continue
        source_row = source.rows[source_y]
        target_row = canvas[y + target_y]
        for target_x in range(target_width):
            source_x = min(source.width - 1, round(target_x * source.width / target_width))
            dst_x = x + target_x
            if 0 <= dst_x < sheet_width:
                target_row[dst_x * 3 : dst_x * 3 + 3] = source_row[source_x * 3 : source_x * 3 + 3]


def fill_rect(canvas: list[bytearray], sheet_width: int, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            row[column * 3 : column * 3 + 3] = color_bytes


def bbox_union(bboxes: list[list[int]]) -> list[int]:
    if not bboxes:
        return [0, 0, 1, 1]
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox_x2(bbox) for bbox in bboxes)
    y2 = max(bbox_y2(bbox) for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]


def dedupe_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
