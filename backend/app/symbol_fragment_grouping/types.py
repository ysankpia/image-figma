from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ..visual_primitive_graph import M29PrimitiveMetrics, metrics_to_dict


M291Decision = Literal["accepted", "weak", "rejected", "uncertain"]

M291SourceKind = Literal["symbol", "blocked"]

M291GroupType = Literal["grouped_symbol", "icon_button_group", "badge_group", "uncertain_group", "rejected_group"]

M291GroupRole = Literal["foreground_symbol", "symbol_fragment", "button_background", "badge", "unknown"]

ELIGIBLE_BLOCKED_REASONS = {
    "weak_symbol_metrics",
    "symbol_color_too_high",
    "symbol_texture_too_high",
    "symbol_edge_too_high",
    "symbol_area_too_small",
}

HARD_BLOCKED_REASONS = {
    "inside_image_primitive",
    "image_internal_texture",
    "text_overlap",
    "protective_shape_overlap",
    "large_container_fragment",
    "line_like",
    "symbol_area_too_large",
}

INTERACTIVE_SHAPE_SUBTYPES = {"button_background", "badge_background", "small_ellipse", "small_rounded_rect", "icon_button_background"}

PROTECTIVE_CONTAINER_SUBTYPES = {"background", "card_background", "search_field_background", "large_container", "separator"}

@dataclass(frozen=True)
class M291Options:
    neighbor_search_radius: int = 24
    icon_cluster_max_edge: int = 96
    max_group_members: int = 5
    accepted_edge_threshold: float = 0.68
    weak_edge_threshold: float = 0.52
    accepted_group_threshold: float = 0.72
    uncertain_group_threshold: float = 0.55
    max_merged_symbol_area: int = 12000
    max_text_like_aspect_ratio: float = 3.5
    output_preview_max_thumb: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class M291FragmentCandidate:
    id: str
    source_node_id: str
    source_kind: M291SourceKind
    bbox: list[int]
    metrics: M29PrimitiveMetrics
    mean_rgb: tuple[int, int, int]
    container_id: str | None
    interactive_shape_id: str | None
    layer_hint: str
    risk_reasons: list[str]
    source_lineage: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "sourceNodeId": self.source_node_id,
            "sourceKind": self.source_kind,
            "bbox": self.bbox,
            "metrics": metrics_to_dict(self.metrics),
            "meanRgb": list(self.mean_rgb),
            "containerId": self.container_id,
            "interactiveShapeId": self.interactive_shape_id,
            "layerHint": self.layer_hint,
            "riskReasons": self.risk_reasons,
        }
        if self.source_lineage is not None:
            data["sourceLineage"] = self.source_lineage
        return data

@dataclass(frozen=True)
class M291FragmentEdge:
    id: str
    left_id: str
    right_id: str
    score: float
    decision: Literal["accepted", "weak", "rejected"]
    reasons: list[str]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "leftId": self.left_id,
            "rightId": self.right_id,
            "score": round(self.score, 3),
            "decision": self.decision,
            "reasons": self.reasons,
            "metrics": {key: round(value, 4) for key, value in self.metrics.items()},
        }

@dataclass(frozen=True)
class M291GroupMember:
    candidate_id: str
    source_node_id: str
    role: M291GroupRole

    def to_dict(self) -> dict[str, Any]:
        return {"candidateId": self.candidate_id, "sourceNodeId": self.source_node_id, "role": self.role}

@dataclass(frozen=True)
class M291SymbolGroup:
    id: str
    group_type: M291GroupType
    decision: Literal["accepted", "uncertain", "rejected"]
    member_ids: list[str]
    members: list[M291GroupMember]
    bbox: list[int]
    confidence: float
    reasons: list[str]
    asset_path: str | None = None
    source_lineage: dict[str, Any] | None = None
    rejected_lineage_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "groupType": self.group_type,
            "decision": self.decision,
            "memberIds": self.member_ids,
            "members": [member.to_dict() for member in self.members],
            "bbox": self.bbox,
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
        }
        if self.asset_path is not None:
            data["assetPath"] = self.asset_path
        if self.source_lineage is not None:
            data["sourceLineage"] = self.source_lineage
        if self.rejected_lineage_reason is not None:
            data["rejectedLineageReason"] = self.rejected_lineage_reason
        return data

@dataclass(frozen=True)
class M291AssetAuditItem:
    node_id: str
    bbox: list[int]
    risk: Literal["ok", "fragmented", "text_like", "overcropped", "isolated", "unknown"]
    score: float
    reasons: list[str]
    neighbor_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodeId": self.node_id,
            "bbox": self.bbox,
            "risk": self.risk,
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "neighborIds": self.neighbor_ids,
        }

@dataclass(frozen=True)
class M291EdgeAuditItem:
    edge_id: str
    left_id: str
    right_id: str
    decision: Literal["accepted", "weak", "rejected"]
    score: float
    reasons: list[str]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "edgeId": self.edge_id,
            "leftId": self.left_id,
            "rightId": self.right_id,
            "decision": self.decision,
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "metrics": {key: round(value, 4) for key, value in self.metrics.items()},
        }

@dataclass(frozen=True)
class M291DebugArtifacts:
    symbol_fragment_risks: str | None = None
    symbol_groups: str | None = None
    grouped_vs_original: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "symbolFragmentRisks": self.symbol_fragment_risks,
                "symbolGroups": self.symbol_groups,
                "groupedVsOriginal": self.grouped_vs_original,
            }.items()
            if value is not None
        }

@dataclass(frozen=True)
class M291Document:
    schema_name: str
    schema_version: str
    source_m29_nodes_json: str
    source_image: str
    options: M291Options
    candidates: list[M291FragmentCandidate]
    edges: list[M291FragmentEdge]
    groups: list[M291SymbolGroup]
    asset_audit: list[M291AssetAuditItem]
    edge_audit: list[M291EdgeAuditItem]
    debug: M291DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceM29NodesJson": self.source_m29_nodes_json,
            "sourceImage": self.source_image,
            "options": self.options.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "edges": [edge.to_dict() for edge in self.edges],
            "groups": [group.to_dict() for group in self.groups],
            "assetAudit": [item.to_dict() for item in self.asset_audit],
            "edgeAudit": [item.to_dict() for item in self.edge_audit],
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }
