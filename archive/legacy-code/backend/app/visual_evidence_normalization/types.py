from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ..visual_primitive_graph import M29PrimitiveMetrics, metrics_to_dict


VisualEvidenceSource = Literal[
    "m29_image",
    "m29_unknown",
    "m29_symbol",
    "m29_shape",
    "m29_blocked",
    "m291_group",
    "after_text_mask_candidate",
]

VisualEvidenceKind = Literal[
    "accepted_image",
    "media_candidate",
    "icon_candidate",
    "mixed_symbol_text_candidate",
    "text_noise",
    "other_candidate",
]

VisualEvidenceDecision = Literal["accepted", "candidate", "uncertain", "noise", "rejected"]

TEXT_REJECTED_LINEAGE_FULL_OCR_COVERAGE_MIN = 0.72

TEXT_REJECTED_LINEAGE_ASPECT_MIN = 3.5

@dataclass(frozen=True)
class VisualEvidenceOptions:
    text_noise_overlap_threshold: float = 0.35
    media_candidate_text_overlap_max: float = 0.20
    icon_candidate_text_overlap_max: float = 0.20
    media_candidate_min_area: int = 1200
    media_candidate_min_color_count: int = 32
    media_candidate_min_texture_score: float = 0.18
    media_candidate_max_aspect_ratio: float = 4.0
    media_candidate_symbol_min_edge: int = 72
    icon_candidate_min_area: int = 16
    icon_candidate_max_area: int = 12000
    icon_candidate_max_edge: int = 128
    output_preview_max_thumb: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class VisualEvidenceItem:
    id: str
    source_evidence_id: str
    source: VisualEvidenceSource
    bbox: list[int]
    region_name: str
    visual_kind: VisualEvidenceKind
    decision: VisualEvidenceDecision
    confidence: float
    asset_path: str
    text_overlap_ratio: float
    image_overlap_ratio: float
    metrics: M29PrimitiveMetrics
    reasons: list[str]
    source_decision: str
    suggested_next_action: str
    source_lineage: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "sourceEvidenceId": self.source_evidence_id,
            "source": self.source,
            "bbox": self.bbox,
            "regionName": self.region_name,
            "visualKind": self.visual_kind,
            "decision": self.decision,
            "confidence": round(self.confidence, 3),
            "assetPath": self.asset_path,
            "textOverlapRatio": round(self.text_overlap_ratio, 4),
            "imageOverlapRatio": round(self.image_overlap_ratio, 4),
            "metrics": metrics_to_dict(self.metrics),
            "reasons": self.reasons,
            "sourceDecision": self.source_decision,
            "suggestedNextAction": self.suggested_next_action,
        }
        if self.source_lineage is not None:
            data["sourceLineage"] = self.source_lineage
        return data

@dataclass(frozen=True)
class VisualEvidenceDebugArtifacts:
    visual_evidence_buckets: str | None = None
    media_candidates: str | None = None
    text_noise: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "visualEvidenceBuckets": self.visual_evidence_buckets,
                "mediaCandidates": self.media_candidates,
                "textNoise": self.text_noise,
            }.items()
            if value is not None
        }

@dataclass(frozen=True)
class VisualEvidenceDocument:
    schema_name: str
    schema_version: str
    source_image: str
    source_m2902_audit_json: str
    options: VisualEvidenceOptions
    items: list[VisualEvidenceItem]
    groups: dict[str, Any]
    debug: VisualEvidenceDebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "options": self.options.to_dict(),
            "items": [item.to_dict() for item in self.items],
            "groups": self.groups,
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }
