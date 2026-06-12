from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


OwnershipSource = Literal["m2903_visual_evidence", "m2902_text_box"]

OwnershipKind = Literal["text_owned", "visual_owned", "shape_owned", "mixed_or_uncertain", "audit_only"]

OwnershipDecisionKind = Literal["accepted", "candidate", "uncertain", "rejected"]

@dataclass(frozen=True)
class M2907Options:
    text_owned_overlap_min: float = 0.55
    text_owned_text_covered_min: float = 0.45
    ocr_confidence_min: float = 0.55
    visual_candidate_high_text_overlap: float = 0.35
    text_preview_max_chars: int = 24
    output_preview_max_thumb: int = 160
    max_examples_per_kind: int = 40

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class OwnershipDecision:
    id: str
    source: OwnershipSource
    source_evidence_id: str | None
    source_visual_evidence_item_id: str | None
    source_text_box_id: str | None
    source_visual_kind: str | None
    bbox: list[int]
    ownership: OwnershipKind
    decision: OwnershipDecisionKind
    ownership_reason_kind: str
    matched_text_box_ids: list[str]
    text_overlap_ratio: float
    ocr_overlap_ratio: float
    text_preview: str | None
    ocr_confidence: float | None
    suppressed_as_visual: bool
    allowed_for_object_forming_visual_side: bool
    allowed_for_text_side: bool
    allowed_for_audit_only: bool
    risks: list[str]
    reasons: list[str]
    source_lineage: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "sourceEvidenceId": self.source_evidence_id,
            "sourceVisualEvidenceItemId": self.source_visual_evidence_item_id,
            "sourceTextBoxId": self.source_text_box_id,
            "sourceVisualKind": self.source_visual_kind,
            "bbox": self.bbox,
            "ownership": self.ownership,
            "decision": self.decision,
            "ownershipReasonKind": self.ownership_reason_kind,
            "matchedTextBoxIds": self.matched_text_box_ids,
            "textOverlapRatio": round(self.text_overlap_ratio, 4),
            "ocrOverlapRatio": round(self.ocr_overlap_ratio, 4),
            "textPreview": self.text_preview,
            "ocrConfidence": round(self.ocr_confidence, 3) if self.ocr_confidence is not None else None,
            "suppressedAsVisual": self.suppressed_as_visual,
            "allowedForObjectFormingVisualSide": self.allowed_for_object_forming_visual_side,
            "allowedForTextSide": self.allowed_for_text_side,
            "allowedForAuditOnly": self.allowed_for_audit_only,
            "risks": self.risks,
            "reasons": self.reasons,
        }
        if self.source_lineage is not None:
            data["sourceLineage"] = self.source_lineage
        return data

@dataclass(frozen=True)
class M2907DebugArtifacts:
    text_owned: str | None = None
    visual_owned: str | None = None
    mixed_or_uncertain: str | None = None
    object_forming_allowed: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "textOwned": self.text_owned,
                "visualOwned": self.visual_owned,
                "mixedOrUncertain": self.mixed_or_uncertain,
                "objectFormingAllowed": self.object_forming_allowed,
            }.items()
            if value is not None
        }

@dataclass(frozen=True)
class M2907Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_m2903_visual_evidence_json: str
    source_m2902_audit_json: str
    options: M2907Options
    ownership_decisions: list[OwnershipDecision]
    routing_views: dict[str, Any]
    audit: list[dict[str, Any]]
    debug: M2907DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM2903VisualEvidenceJson": self.source_m2903_visual_evidence_json,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "options": self.options.to_dict(),
            "ownershipDecisions": [item.to_dict() for item in self.ownership_decisions],
            "routingViews": self.routing_views,
            "audit": self.audit,
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }
