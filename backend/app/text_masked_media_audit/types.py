from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ..visual_primitive_graph import M29PrimitiveMetrics, M29TextBox, metrics_to_dict


M2902Source = Literal[
    "m29_image",
    "m29_unknown",
    "m29_symbol",
    "m29_shape",
    "m29_blocked",
    "m291_group",
    "after_text_mask_candidate",
]

M2902Decision = Literal[
    "accepted_image",
    "image_like_unknown",
    "image_like_symbol",
    "support_shape",
    "image_like_blocked",
    "symbol_group",
    "text_suppressed_candidate",
]


def text_box_to_dict(item: M29TextBox) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": item.id,
        "bbox": item.bbox,
        "confidence": round(item.confidence, 3),
        "source": item.source,
        "kind": item.kind,
    }
    if item.text is not None:
        data["text"] = item.text
    if item.meta:
        data["meta"] = item.meta
    return data

@dataclass(frozen=True)
class TextMaskedMediaAuditOptions:
    text_padding: int = 2
    min_media_like_area: int = 400
    output_preview_max_thumb: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class MediaAuditRegion:
    name: str
    bbox: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "bbox": self.bbox}

@dataclass(frozen=True)
class MediaEvidenceItem:
    id: str
    source: M2902Source
    bbox: list[int]
    region_name: str
    decision: M2902Decision
    asset_path: str | None
    text_overlap_ratio: float
    image_overlap_ratio: float
    metrics: M29PrimitiveMetrics
    reasons: list[str]
    suggested_next_action: str

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "bbox": self.bbox,
            "regionName": self.region_name,
            "decision": self.decision,
            "textOverlapRatio": round(self.text_overlap_ratio, 4),
            "imageOverlapRatio": round(self.image_overlap_ratio, 4),
            "metrics": metrics_to_dict(self.metrics),
            "reasons": self.reasons,
            "suggestedNextAction": self.suggested_next_action,
        }
        if self.asset_path is not None:
            data["assetPath"] = self.asset_path
        return data

@dataclass(frozen=True)
class TextMaskedDebugArtifacts:
    text_mask: str | None = None
    text_suppressed_analysis: str | None = None
    media_before_after: str | None = None
    media_evidence_map: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "textMask": self.text_mask,
                "textSuppressedAnalysis": self.text_suppressed_analysis,
                "mediaBeforeAfter": self.media_before_after,
                "mediaEvidenceMap": self.media_evidence_map,
            }.items()
            if value is not None
        }

@dataclass(frozen=True)
class TextMaskedMediaAuditDocument:
    schema_name: str
    schema_version: str
    source_image: str
    source_m29_nodes_json: str | None
    source_m291_group_nodes_json: str | None
    text_source: str
    options: TextMaskedMediaAuditOptions
    text_boxes: list[M29TextBox]
    regions: list[MediaAuditRegion]
    before_counts: dict[str, int]
    after_counts: dict[str, int]
    media_evidence: list[MediaEvidenceItem]
    warnings: list[str]
    debug: TextMaskedDebugArtifacts
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM29NodesJson": self.source_m29_nodes_json,
            "sourceM291GroupNodesJson": self.source_m291_group_nodes_json,
            "textSource": self.text_source,
            "options": self.options.to_dict(),
            "textBoxes": [text_box_to_dict(item) for item in self.text_boxes],
            "regions": [region.to_dict() for region in self.regions],
            "beforeCounts": self.before_counts,
            "afterCounts": self.after_counts,
            "mediaEvidence": [item.to_dict() for item in self.media_evidence],
            "warnings": self.warnings,
            "debug": self.debug.to_dict(),
            "meta": self.meta,
        }
