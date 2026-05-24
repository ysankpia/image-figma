from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


M29PrimitiveType = Literal["text", "shape", "image", "symbol", "unknown"]
M29LayerHint = Literal["background", "container", "content", "overlay", "unknown"]
M29TextSource = Literal["ocr", "manual", "detector", "test"]
M29TextKind = Literal["line", "word", "block", "unknown"]
M29RelationType = Literal["contains", "overlaps", "protects", "near", "aligned"]
M29_BLOCKED_EVIDENCE_VERSION = "0.2"

LAYER_ORDER: dict[str, int] = {"background": 0, "container": 1, "content": 2, "overlay": 3, "unknown": 4}
OVERLAY_COLORS: dict[str, tuple[int, int, int]] = {
    "text": (160, 80, 220),
    "shape": (0, 122, 255),
    "image": (0, 180, 210),
    "symbol": (0, 200, 90),
    "unknown": (238, 190, 40),
    "blocked": (235, 64, 52),
    "protected": (140, 140, 140),
}


@dataclass(frozen=True)
class M29TextBox:
    id: str
    bbox: list[int]
    text: str | None = None
    confidence: float = 1.0
    source: M29TextSource = "ocr"
    kind: M29TextKind = "unknown"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class M29BinaryMask:
    width: int
    height: int
    data: bytes


@dataclass(frozen=True)
class M29PrimitiveMetrics:
    color_count: int
    texture_score: float
    edge_score: float
    fill_ratio: float
    aspect_ratio: float
    brightness: float
    mean_rgb: tuple[int, int, int]


@dataclass(frozen=True)
class M29PrimitiveNode:
    id: str
    type: M29PrimitiveType
    subtype: str
    bbox: list[int]
    confidence: float
    source: str
    source_order: int
    layer_hint: M29LayerHint
    reasons: list[str]
    metrics: M29PrimitiveMetrics
    style: dict[str, object] | None = None
    text: str | None = None
    asset_path: str | None = None
    mask_path: str | None = None
    parent_id: str | None = None
    child_ids: list[str] = field(default_factory=list)
    mask_data: bytes | None = None
    geometry: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        from .metrics import metrics_to_dict

        data = {
            "id": self.id,
            "type": self.type,
            "subtype": self.subtype,
            "bbox": self.bbox,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "sourceOrder": self.source_order,
            "layerHint": self.layer_hint,
            "reasons": self.reasons,
            "metrics": metrics_to_dict(self.metrics),
        }
        optional = {
            "style": self.style,
            "text": self.text,
            "assetPath": self.asset_path,
            "maskPath": self.mask_path,
            "parentId": self.parent_id,
            "childIds": self.child_ids or None,
            "geometry": self.geometry,
        }
        data.update({key: value for key, value in optional.items() if value is not None})
        return data


@dataclass(frozen=True)
class M29BlockedPrimitive:
    id: str
    bbox: list[int]
    source: str
    reasons: list[str]
    metrics: M29PrimitiveMetrics | None = None
    context: dict[str, object] | None = None

    def to_dict(self) -> dict[str, Any]:
        from .metrics import metrics_to_dict

        data: dict[str, Any] = {
            "id": self.id,
            "bbox": self.bbox,
            "source": self.source,
            "reasons": self.reasons,
        }
        if self.metrics is not None:
            data["metrics"] = metrics_to_dict(self.metrics)
        if self.context is not None:
            data["context"] = self.context
        return data


@dataclass(frozen=True)
class M29PrimitiveRelation:
    parent_id: str
    child_id: str
    type: M29RelationType
    confidence: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "parentId": self.parent_id,
            "childId": self.child_id,
            "type": self.type,
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class M29VisualPrimitiveOptions:
    min_component_area: int = 16
    max_component_area_ratio: float = 0.25
    min_shape_area: int = 64
    shape_texture_threshold: float = 0.12
    shape_color_threshold: int = 10
    line_max_thickness: int = 4
    line_min_length: int = 20
    min_image_area: int = 1200
    image_color_threshold: int = 32
    image_texture_threshold: float = 0.18
    image_accept_threshold: float = 0.78
    image_protection_padding: int = 2
    symbol_min_area: int = 16
    symbol_max_area: int = 12000
    symbol_texture_threshold: float = 0.20
    symbol_color_threshold: int = 24
    text_padding: int = 2
    output_preview_max_thumb: int = 160
    low_contrast_support_enabled: bool = True
    low_contrast_support_min_width: int = 48
    low_contrast_support_min_height: int = 18
    low_contrast_support_max_area_ratio: float = 0.08
    low_contrast_support_max_width_ratio: float = 0.90
    low_contrast_support_max_texture: float = 0.075
    low_contrast_support_max_color_count: int = 10
    low_contrast_support_min_edge_delta: int = 6
    low_contrast_support_max_edge_delta: int = 80
    text_support_background_enabled: bool = True
    text_support_background_min_area_ratio: float = 1.15
    text_support_background_max_area_ratio: float = 4.00
    text_support_background_min_aspect: float = 1.8
    text_support_background_padding_x_ratio: float = 0.55
    text_support_background_padding_y_ratio: float = 0.45

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M29ConnectedComponent:
    id: str
    bbox: list[int]
    area: int
    centroid: tuple[float, float]
    fill_ratio: float
    metrics: M29PrimitiveMetrics
    source: str
    mask_data: bytes | None = None


@dataclass(frozen=True)
class M29DebugArtifacts:
    text_exclusion: str | None = None
    initial_components: str | None = None
    shapes: str | None = None
    images: str | None = None
    image_protection: str | None = None
    foreground_mask: str | None = None
    symbols: str | None = None
    final_nodes: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "textExclusion": self.text_exclusion,
                "initialComponents": self.initial_components,
                "shapes": self.shapes,
                "images": self.images,
                "imageProtection": self.image_protection,
                "foregroundMask": self.foreground_mask,
                "symbols": self.symbols,
                "finalNodes": self.final_nodes,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class M29VisualPrimitiveGraphDocument:
    version: str
    source_image: str
    image_size: dict[str, int]
    nodes: list[M29PrimitiveNode]
    relations: list[M29PrimitiveRelation]
    blocked: list[M29BlockedPrimitive]
    debug: M29DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sourceImage": self.source_image,
            "imageSize": self.image_size,
            "nodes": [node.to_dict() for node in self.nodes],
            "relations": [relation.to_dict() for relation in self.relations],
            "blocked": [item.to_dict() for item in self.blocked],
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }

