from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ..visual_primitive_graph import M29PrimitiveMetrics, metrics_to_dict


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
