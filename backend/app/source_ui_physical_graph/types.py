from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


M292VisualKind = Literal[
    "editable_ui_text",
    "preserve_raster_text",
    "media_region",
    "raster_icon",
    "control_background",
    "card_background",
    "separator",
    "shadow_or_blur",
    "unknown",
]
M292PixelOwner = Literal[
    "editable_text",
    "preserve_raster",
    "raster_icon",
    "shape_geometry",
    "fallback_only",
    "diagnostic_only",
]
M292ReplayDecision = Literal[
    "text_replay",
    "image_replay",
    "icon_replay",
    "shape_replay",
    "preserve_in_parent_raster",
    "skip",
]


@dataclass(frozen=True)
class M292SourcePhysicalOptions:
    min_text_confidence: float = 0.60
    editable_text_max_media_overlap: float = 0.82
    media_display_text_min_height: int = 40
    media_display_text_min_width_ratio: float = 0.22
    min_media_area: int = 1200
    media_color_threshold: int = 24
    media_texture_threshold: float = 0.16
    media_text_overlap_preserve_threshold: float = 0.55
    media_min_color_or_texture_area: int = 20000
    icon_max_area: int = 12000
    icon_cluster_gap: int = 8
    raster_foreground_max_edge: int = 128
    shape_replay_color_threshold: int = 12
    shape_replay_texture_threshold: float = 0.14
    shape_replay_edge_threshold: float = 0.28
    textured_foreground_color_threshold: int = 24
    textured_foreground_texture_threshold: float = 0.18
    textured_foreground_edge_threshold: float = 0.30
    duplicate_iou_threshold: float = 0.88

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M292SourceObject:
    id: str
    bbox: list[int]
    visual_kind: M292VisualKind
    pixel_owner: M292PixelOwner
    replay_decision: M292ReplayDecision
    source_evidence: dict[str, Any]
    confidence: Literal["high", "medium", "low"]
    reasons: list[str]
    risks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "bbox": self.bbox,
            "visualKind": self.visual_kind,
            "pixelOwner": self.pixel_owner,
            "replayDecision": self.replay_decision,
            "sourceEvidence": self.source_evidence,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "risks": self.risks,
        }


def make_object(
    *,
    bbox: list[int],
    visual_kind: M292VisualKind,
    pixel_owner: M292PixelOwner,
    replay_decision: M292ReplayDecision,
    m29_ids: list[str] | None = None,
    blocked_ids: list[str] | None = None,
    ocr_ids: list[str] | None = None,
    local_bg_confidence: float,
    text_overlap: float,
    media_containment: float,
    confidence: Literal["high", "medium", "low"],
    reasons: list[str],
    risks: list[str],
) -> M292SourceObject:
    return M292SourceObject(
        id="pending",
        bbox=bbox,
        visual_kind=visual_kind,
        pixel_owner=pixel_owner,
        replay_decision=replay_decision,
        source_evidence={
            "ocrBoxIds": clean_ids(ocr_ids or []),
            "m29NodeIds": clean_ids(m29_ids or []),
            "blockedIds": clean_ids(blocked_ids or []),
            "localBackgroundConfidence": round(local_bg_confidence, 4),
            "textOverlapRatio": round(text_overlap, 4),
            "mediaContainmentRatio": round(media_containment, 4),
        },
        confidence=confidence,
        reasons=unique_strings(reasons),
        risks=unique_strings(risks),
    )


def clean_ids(values: list[str]) -> list[str]:
    return unique_strings([value for value in values if value])


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
