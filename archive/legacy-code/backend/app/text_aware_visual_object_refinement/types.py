from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ..visual_primitive_graph import M29PrimitiveMetrics, metrics_to_dict


RefinedObjectDecision = Literal["separated", "partially_separated", "visual_only", "text_only", "unresolved", "split_needed", "rejected"]

VisualKind = Literal["image_like", "icon_like", "weak_visual", "unknown_visual"]

VisualAssetUse = Literal["image_asset", "icon_asset", "audit_only", "unresolved"]

VisualAssetDecision = Literal["accepted", "candidate", "uncertain", "rejected"]

ShapeDecision = Literal["candidate", "uncertain", "rejected"]

TextMemberSource = Literal["m2904_member", "m2902_text_box"]

UnresolvedReason = Literal[
    "text_touching_visual",
    "high_text_overlap",
    "weak_visual",
    "noise_member",
    "wide_source",
    "source_conflict",
    "missing_lookup",
    "unsafe_union",
    "invalid_bbox",
]

@dataclass(frozen=True)
class M2905Options:
    text_preview_max_chars: int = 24
    visual_asset_text_overlap_max: float = 0.12
    icon_asset_text_overlap_max: float = 0.18
    weak_visual_text_overlap_max: float = 0.28
    min_visual_asset_area: int = 16
    max_icon_asset_area: int = 12000
    max_icon_asset_edge: int = 128
    max_visual_union_members: int = 4
    max_visual_union_gap: int = 12
    min_separation_quality: float = 0.62
    output_preview_max_thumb: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class M2905SourceExpansionRefs:
    m29_nodes_json: str | None = None
    m291_group_nodes_json: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "m29NodesJson": self.m29_nodes_json,
            "m291GroupNodesJson": self.m291_group_nodes_json,
        }

@dataclass(frozen=True)
class RefinedVisualObject:
    id: str
    source_object_id: str
    source_object_kind: str
    source_decision: str
    bbox: list[int]
    decision: RefinedObjectDecision
    combined_asset_path: str
    combined_asset_use: Literal["audit_only"]
    visual_asset_ids: list[str]
    shape_candidate_ids: list[str]
    text_member_ids: list[str]
    unresolved_member_ids: list[str]
    risks: list[str]
    reasons: list[str]
    separation_quality: float
    suggested_next_action: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "sourceObjectKind": self.source_object_kind,
            "sourceDecision": self.source_decision,
            "bbox": self.bbox,
            "decision": self.decision,
            "combinedAssetPath": self.combined_asset_path,
            "combinedAssetUse": self.combined_asset_use,
            "visualAssetIds": self.visual_asset_ids,
            "shapeCandidateIds": self.shape_candidate_ids,
            "textMemberIds": self.text_member_ids,
            "unresolvedMemberIds": self.unresolved_member_ids,
            "risks": self.risks,
            "reasons": self.reasons,
            "separationQuality": round(self.separation_quality, 3),
            "suggestedNextAction": self.suggested_next_action,
        }

@dataclass(frozen=True)
class RefinedVisualAsset:
    id: str
    source_object_id: str
    source_evidence_node_ids: list[str]
    bbox: list[int]
    visual_kind: VisualKind
    asset_use: VisualAssetUse
    decision: VisualAssetDecision
    asset_path: str | None
    text_overlap_ratio: float
    metrics: M29PrimitiveMetrics | None
    risks: list[str]
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "sourceEvidenceNodeIds": self.source_evidence_node_ids,
            "bbox": self.bbox,
            "visualKind": self.visual_kind,
            "assetUse": self.asset_use,
            "decision": self.decision,
            "assetPath": self.asset_path,
            "textOverlapRatio": round(self.text_overlap_ratio, 4),
            "metrics": metrics_to_dict(self.metrics) if self.metrics is not None else None,
            "risks": self.risks,
            "reasons": self.reasons,
        }

@dataclass(frozen=True)
class ShapeCandidate:
    id: str
    source_object_id: str
    source_evidence_node_ids: list[str]
    source_subtype: str | None
    source_reasons: list[str]
    bbox: list[int]
    asset_use: Literal["shape_candidate"]
    decision: ShapeDecision
    metrics: M29PrimitiveMetrics | None
    color: str | None
    text_overlap_ratio: float
    reasons: list[str]
    risks: list[str]
    preview_asset_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "sourceEvidenceNodeIds": self.source_evidence_node_ids,
            "sourceSubtype": self.source_subtype,
            "sourceReasons": self.source_reasons,
            "bbox": self.bbox,
            "assetUse": self.asset_use,
            "decision": self.decision,
            "metrics": metrics_to_dict(self.metrics) if self.metrics is not None else None,
            "color": self.color,
            "textOverlapRatio": round(self.text_overlap_ratio, 4),
            "reasons": self.reasons,
            "risks": self.risks,
            "previewAssetPath": self.preview_asset_path,
        }

@dataclass(frozen=True)
class RefinedTextMember:
    id: str
    source_object_id: str
    source: TextMemberSource
    source_evidence_node_id: str | None
    source_text_box_id: str | None
    bbox: list[int]
    text_preview: str
    text: str | None
    confidence: float
    risks: list[str]
    reasons: list[str]
    preview_asset_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "source": self.source,
            "sourceEvidenceNodeId": self.source_evidence_node_id,
            "sourceTextBoxId": self.source_text_box_id,
            "bbox": self.bbox,
            "textPreview": self.text_preview,
            "text": self.text,
            "confidence": round(self.confidence, 3),
            "risks": self.risks,
            "reasons": self.reasons,
            "previewAssetPath": self.preview_asset_path,
        }

@dataclass(frozen=True)
class UnresolvedMember:
    id: str
    source_object_id: str
    source_evidence_node_id: str | None
    bbox: list[int]
    member_role: str
    reason: UnresolvedReason
    risks: list[str]
    suggested_next_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "sourceEvidenceNodeId": self.source_evidence_node_id,
            "bbox": self.bbox,
            "memberRole": self.member_role,
            "reason": self.reason,
            "risks": self.risks,
            "suggestedNextAction": self.suggested_next_action,
        }

@dataclass(frozen=True)
class TextVisualSeparationAuditItem:
    id: str
    source_object_id: str
    refined_object_id: str
    decision: RefinedObjectDecision
    visual_asset_ids: list[str]
    shape_candidate_ids: list[str]
    text_member_ids: list[str]
    unresolved_member_ids: list[str]
    combined_asset_path: str
    risks: list[str]
    reasons: list[str]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceObjectId": self.source_object_id,
            "refinedObjectId": self.refined_object_id,
            "decision": self.decision,
            "visualAssetIds": self.visual_asset_ids,
            "shapeCandidateIds": self.shape_candidate_ids,
            "textMemberIds": self.text_member_ids,
            "unresolvedMemberIds": self.unresolved_member_ids,
            "combinedAssetPath": self.combined_asset_path,
            "risks": self.risks,
            "reasons": self.reasons,
            "metrics": self.metrics,
        }

@dataclass(frozen=True)
class M2905DebugArtifacts:
    visual_assets: str | None = None
    text_members: str | None = None
    text_visual_separation: str | None = None
    unresolved_refinement: str | None = None
    shape_candidates: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "visualAssets": self.visual_assets,
                "textMembers": self.text_members,
                "textVisualSeparation": self.text_visual_separation,
                "unresolvedRefinement": self.unresolved_refinement,
                "shapeCandidates": self.shape_candidates,
            }.items()
            if value is not None
        }

@dataclass(frozen=True)
class M2905Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_m2904_visual_object_candidates_json: str
    source_m2903_visual_evidence_json: str
    source_m2902_audit_json: str
    source_expansion_refs: M2905SourceExpansionRefs
    options: M2905Options
    objects: list[RefinedVisualObject]
    visual_assets: list[RefinedVisualAsset]
    shape_candidates: list[ShapeCandidate]
    text_members: list[RefinedTextMember]
    unresolved_members: list[UnresolvedMember]
    audit: list[TextVisualSeparationAuditItem]
    debug: M2905DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM2904VisualObjectCandidatesJson": self.source_m2904_visual_object_candidates_json,
            "sourceM2903VisualEvidenceJson": self.source_m2903_visual_evidence_json,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "sourceExpansionRefs": self.source_expansion_refs.to_dict(),
            "options": self.options.to_dict(),
            "objects": [item.to_dict() for item in self.objects],
            "visualAssets": [item.to_dict() for item in self.visual_assets],
            "shapeCandidates": [item.to_dict() for item in self.shape_candidates],
            "textMembers": [item.to_dict() for item in self.text_members],
            "unresolvedMembers": [item.to_dict() for item in self.unresolved_members],
            "audit": [item.to_dict() for item in self.audit],
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }
