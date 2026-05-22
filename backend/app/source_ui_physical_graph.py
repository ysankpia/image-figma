from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .evidence_grounded_dsl_materialization import bbox_overlap_ratio, sample_outer_bbox_ring_rgb
from .png_tools import (
    PngPixels,
    UnsupportedPngCropError,
    decode_png_pixels,
    encode_rgb_png,
    read_png_metadata,
)
from .text_masked_media_audit import text_boxes_from_ocr_document
from .visual_primitive_graph import (
    bbox_area,
    bbox_clamp,
    bbox_gap_distance,
    bbox_in_bounds,
    bbox_iou,
    draw_rect,
    measure_region,
)

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
    icon_max_area: int = 12000
    icon_cluster_gap: int = 8
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


def extract_source_ui_physical_graph(
    *,
    source_png: bytes,
    m29_document: dict[str, Any],
    ocr_document: dict[str, Any] | None,
    output_dir: Path,
    options: M292SourcePhysicalOptions | None = None,
) -> dict[str, Any]:
    options = options or M292SourcePhysicalOptions()
    image = read_png_metadata(source_png)
    if image is None:
        raise UnsupportedPngCropError("M29.2 source image is not a readable PNG.")
    pixels = decode_png_pixels(source_png)
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr_boxes, warnings = text_boxes_from_ocr_document(ocr_document or {"blocks": []})
    m29_nodes = [item for item in m29_document.get("nodes", []) if isinstance(item, dict)]
    blocked_nodes = [item for item in m29_document.get("blocked", []) if isinstance(item, dict)]
    media_nodes = detect_media_objects(m29_nodes, ocr_boxes, pixels, image.width, image.height, options)
    objects: list[M292SourceObject] = []
    objects.extend(media_nodes)
    objects.extend(classify_ocr_text_objects(ocr_boxes, m29_nodes, media_nodes, pixels, image.width, image.height, options))
    objects.extend(cluster_icon_objects(m29_nodes, media_nodes, ocr_boxes, pixels, image.width, image.height, options))
    objects.extend(classify_shape_objects(m29_nodes, media_nodes, ocr_boxes, pixels, image.width, image.height, options))
    objects.extend(classify_unknown_objects(m29_nodes, media_nodes, ocr_boxes, pixels, image.width, image.height, options))
    objects.extend(classify_blocked_objects(blocked_nodes, image.width, image.height))
    objects = dedupe_objects(objects, options.duplicate_iou_threshold)

    summary = build_summary(objects, m29_nodes, ocr_boxes)
    overlay_path = output_dir / "source_ui_physical_graph_overlay.png"
    overlay_path.write_bytes(render_overlay(pixels, objects))
    payload = {
        "schemaName": "M292SourceUiPhysicalGraph",
        "schemaVersion": "0.1",
        "sourceImage": str(m29_document.get("sourceImage") or ""),
        "imageSize": {"width": image.width, "height": image.height},
        "summary": summary,
        "options": options.to_dict(),
        "sourceObjects": [item.to_dict() for item in objects],
        "warnings": warnings,
        "debug": {"overlay": overlay_path.name},
        "meta": {
            "dslChanged": False,
            "assetChanged": False,
            "truthSource": "source_png_plus_ocr_plus_m29_primitives",
        },
    }
    (output_dir / "source_ui_physical_graph.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def detect_media_objects(
    m29_nodes: list[dict[str, Any]],
    ocr_boxes: list[Any],
    pixels: PngPixels,
    width: int,
    height: int,
    options: M292SourcePhysicalOptions,
) -> list[M292SourceObject]:
    objects: list[M292SourceObject] = []
    for node in m29_nodes:
        if str(node.get("type") or "") not in {"image", "unknown"}:
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        metrics = measure_region(pixels, bbox)
        text_overlap = max((bbox_overlap_ratio(box.bbox, bbox) for box in ocr_boxes), default=0.0)
        if str(node.get("type") or "") == "image" or (
            bbox_area(bbox) >= options.min_media_area
            and metrics.color_count >= options.media_color_threshold
            and metrics.texture_score >= options.media_texture_threshold
        ):
            objects.append(
                make_object(
                    bbox=bbox,
                    visual_kind="media_region",
                    pixel_owner="preserve_raster",
                    replay_decision="image_replay",
                    m29_ids=[str(node.get("id") or "")],
                    ocr_ids=[box.id for box in ocr_boxes if bbox_overlap_ratio(box.bbox, bbox) > 0],
                    local_bg_confidence=local_background_confidence(pixels, bbox),
                    text_overlap=text_overlap,
                    media_containment=1.0,
                    confidence="high" if str(node.get("type") or "") == "image" else "medium",
                    reasons=["m29_image_region"] if str(node.get("type") or "") == "image" else ["large_textured_region"],
                    risks=["contains_internal_text"] if text_overlap >= options.media_text_overlap_preserve_threshold else [],
                )
            )
    return objects


def classify_ocr_text_objects(
    ocr_boxes: list[Any],
    m29_nodes: list[dict[str, Any]],
    media_objects: list[M292SourceObject],
    pixels: PngPixels,
    width: int,
    height: int,
    options: M292SourcePhysicalOptions,
) -> list[M292SourceObject]:
    objects: list[M292SourceObject] = []
    for box in ocr_boxes:
        bbox = bbox_clamp(box.bbox, width, height)
        if bbox is None:
            continue
        text = str(box.text or "").strip()
        media_overlap = max((bbox_overlap_ratio(bbox, media.bbox) for media in media_objects), default=0.0)
        local_conf = local_background_confidence(pixels, bbox)
        overlapped_m29 = [
            str(node.get("id") or "")
            for node in m29_nodes
            if (node_bbox := parse_bbox(node.get("bbox"))) is not None and bbox_overlap_ratio(node_bbox, bbox) > 0.2
        ]
        if not text or box.confidence < options.min_text_confidence:
            objects.append(
                make_object(
                    bbox=bbox,
                    visual_kind="preserve_raster_text",
                    pixel_owner="preserve_raster",
                    replay_decision="preserve_in_parent_raster",
                    m29_ids=overlapped_m29,
                    ocr_ids=[box.id],
                    local_bg_confidence=local_conf,
                    text_overlap=1.0,
                    media_containment=media_overlap,
                    confidence="low",
                    reasons=["low_confidence_or_empty_ocr_text"],
                    risks=["not_safe_editable_text"],
                )
            )
            continue
        if media_overlap >= options.editable_text_max_media_overlap and is_media_display_text(bbox, width, options):
            objects.append(
                make_object(
                    bbox=bbox,
                    visual_kind="preserve_raster_text",
                    pixel_owner="preserve_raster",
                    replay_decision="preserve_in_parent_raster",
                    m29_ids=overlapped_m29,
                    ocr_ids=[box.id],
                    local_bg_confidence=local_conf,
                    text_overlap=1.0,
                    media_containment=media_overlap,
                    confidence="medium",
                    reasons=["large_display_text_inside_media"],
                    risks=["preserve_raster_text"],
                )
            )
            continue
        objects.append(
            make_object(
                bbox=bbox,
                visual_kind="editable_ui_text",
                pixel_owner="editable_text",
                replay_decision="text_replay",
                m29_ids=overlapped_m29,
                ocr_ids=[box.id],
                local_bg_confidence=local_conf,
                text_overlap=1.0,
                media_containment=media_overlap,
                confidence="high" if local_conf >= 0.45 else "medium",
                reasons=["ocr_text_on_stable_ui_background"],
                risks=[] if local_conf >= 0.35 else ["low_local_background_confidence"],
            )
        )
    return objects


def is_media_display_text(bbox: list[int], image_width: int, options: M292SourcePhysicalOptions) -> bool:
    return bbox[3] >= options.media_display_text_min_height or (
        bbox[2] >= round(image_width * options.media_display_text_min_width_ratio) and bbox[3] >= round(options.media_display_text_min_height * 0.75)
    )


def cluster_icon_objects(
    m29_nodes: list[dict[str, Any]],
    media_objects: list[M292SourceObject],
    ocr_boxes: list[Any],
    pixels: PngPixels,
    width: int,
    height: int,
    options: M292SourcePhysicalOptions,
) -> list[M292SourceObject]:
    candidates: list[dict[str, Any]] = []
    for node in m29_nodes:
        if str(node.get("type") or "") != "symbol":
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        if bbox_area(bbox) > options.icon_max_area:
            continue
        if any(bbox_overlap_ratio(bbox, media.bbox) >= 0.80 for media in media_objects):
            continue
        if any(bbox_overlap_ratio(bbox, box.bbox) >= 0.45 for box in ocr_boxes):
            continue
        candidates.append(node)

    clusters: list[list[dict[str, Any]]] = []
    for node in candidates:
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None:
            continue
        matched: list[dict[str, Any]] | None = None
        for cluster in clusters:
            cluster_bbox = union_bbox([parse_bbox(item.get("bbox")) for item in cluster])
            if cluster_bbox is not None and bbox_gap_distance(cluster_bbox, bbox) <= options.icon_cluster_gap:
                matched = cluster
                break
        if matched is None:
            clusters.append([node])
        else:
            matched.append(node)

    objects: list[M292SourceObject] = []
    for cluster in clusters:
        bbox = union_bbox([parse_bbox(node.get("bbox")) for node in cluster])
        if bbox is None:
            continue
        objects.append(
            make_object(
                bbox=bbox,
                visual_kind="raster_icon",
                pixel_owner="raster_icon",
                replay_decision="icon_replay",
                m29_ids=[str(node.get("id") or "") for node in cluster],
                ocr_ids=[],
                local_bg_confidence=local_background_confidence(pixels, bbox),
                text_overlap=0.0,
                media_containment=max((bbox_overlap_ratio(bbox, media.bbox) for media in media_objects), default=0.0),
                confidence="high" if len(cluster) > 1 else "medium",
                reasons=["symbol_fragment_cluster"] if len(cluster) > 1 else ["standalone_symbol_icon"],
                risks=[],
            )
        )
    return objects


def classify_shape_objects(
    m29_nodes: list[dict[str, Any]],
    media_objects: list[M292SourceObject],
    ocr_boxes: list[Any],
    pixels: PngPixels,
    width: int,
    height: int,
    options: M292SourcePhysicalOptions,
) -> list[M292SourceObject]:
    objects: list[M292SourceObject] = []
    for node in m29_nodes:
        if str(node.get("type") or "") != "shape":
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        if any(bbox_overlap_ratio(bbox, media.bbox) >= 0.80 for media in media_objects):
            continue
        subtype = str(node.get("subtype") or "")
        metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
        texture = float(metrics.get("textureScore") or 0.0)
        color_count = int(metrics.get("colorCount") or 0)
        text_overlap = max((bbox_overlap_ratio(bbox, box.bbox) for box in ocr_boxes), default=0.0)
        if subtype == "separator":
            visual_kind: M292VisualKind = "separator"
            reasons = ["separator_shape"]
        elif subtype in {"card_background", "container_background", "background", "large_container"}:
            visual_kind = "card_background"
            reasons = ["container_background_shape"]
        elif subtype in {"search_field_background", "small_rounded_rect", "badge_background", "icon_button_background", "small_ellipse"}:
            visual_kind = "control_background"
            reasons = ["control_background_shape"]
        elif color_count <= 12 and texture <= 0.14 and text_overlap < 0.45:
            visual_kind = "control_background"
            reasons = ["solid_ui_shape"]
        else:
            objects.append(
                make_object(
                    bbox=bbox,
                    visual_kind="shadow_or_blur",
                    pixel_owner="diagnostic_only",
                    replay_decision="skip",
                    m29_ids=[str(node.get("id") or "")],
                    ocr_ids=[],
                    local_bg_confidence=local_background_confidence(pixels, bbox),
                    text_overlap=text_overlap,
                    media_containment=max((bbox_overlap_ratio(bbox, media.bbox) for media in media_objects), default=0.0),
                    confidence="low",
                    reasons=["shape_not_safe_for_geometry_replay"],
                    risks=["complex_shape_or_blur"],
                )
            )
            continue
        objects.append(
            make_object(
                bbox=bbox,
                visual_kind=visual_kind,
                pixel_owner="shape_geometry",
                replay_decision="shape_replay",
                m29_ids=[str(node.get("id") or "")],
                ocr_ids=[],
                local_bg_confidence=local_background_confidence(pixels, bbox),
                text_overlap=text_overlap,
                media_containment=max((bbox_overlap_ratio(bbox, media.bbox) for media in media_objects), default=0.0),
                confidence="high",
                reasons=reasons,
                risks=[],
            )
        )
    return objects


def classify_unknown_objects(
    m29_nodes: list[dict[str, Any]],
    media_objects: list[M292SourceObject],
    ocr_boxes: list[Any],
    pixels: PngPixels,
    width: int,
    height: int,
    options: M292SourcePhysicalOptions,
) -> list[M292SourceObject]:
    objects: list[M292SourceObject] = []
    known_types = {"text", "shape", "image", "symbol", "unknown"}
    for node in m29_nodes:
        node_type = str(node.get("type") or "")
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        if node_type in {"text", "shape", "image", "symbol"}:
            continue
        if any(bbox_overlap_ratio(bbox, media.bbox) >= 0.80 for media in media_objects):
            continue
        if node_type in known_types:
            metrics = measure_region(pixels, bbox)
            if (
                bbox_area(bbox) >= options.min_media_area
                and metrics.color_count >= options.media_color_threshold
                and metrics.texture_score >= options.media_texture_threshold
            ):
                continue
        objects.append(
            make_object(
                bbox=bbox,
                visual_kind="unknown",
                pixel_owner="diagnostic_only",
                replay_decision="skip",
                m29_ids=[str(node.get("id") or "")],
                ocr_ids=[box.id for box in ocr_boxes if bbox_overlap_ratio(bbox, box.bbox) > 0],
                local_bg_confidence=local_background_confidence(pixels, bbox),
                text_overlap=max((bbox_overlap_ratio(bbox, box.bbox) for box in ocr_boxes), default=0.0),
                media_containment=max((bbox_overlap_ratio(bbox, media.bbox) for media in media_objects), default=0.0),
                confidence="low",
                reasons=["unsupported_visual_kind"],
                risks=["diagnostic_only"],
            )
        )
    return objects


def classify_blocked_objects(blocked_nodes: list[dict[str, Any]], width: int, height: int) -> list[M292SourceObject]:
    objects: list[M292SourceObject] = []
    for node in blocked_nodes:
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        objects.append(
            make_object(
                bbox=bbox,
                visual_kind="unknown",
                pixel_owner="diagnostic_only",
                replay_decision="skip",
                m29_ids=[],
                blocked_ids=[str(node.get("id") or "")],
                ocr_ids=[],
                local_bg_confidence=0.0,
                text_overlap=0.0,
                media_containment=0.0,
                confidence="low",
                reasons=["blocked_primitive"],
                risks=[str(reason) for reason in node.get("reasons", []) if isinstance(reason, str)],
            )
        )
    return objects


def dedupe_objects(objects: list[M292SourceObject], threshold: float) -> list[M292SourceObject]:
    priority = {
        "text_replay": 5,
        "image_replay": 4,
        "icon_replay": 3,
        "shape_replay": 2,
        "preserve_in_parent_raster": 1,
        "skip": 0,
    }
    kept: list[M292SourceObject] = []
    for item in sorted(objects, key=lambda obj: (-priority[obj.replay_decision], obj.bbox[1], obj.bbox[0], -bbox_area(obj.bbox))):
        duplicate_index = next((index for index, kept_item in enumerate(kept) if bbox_iou(item.bbox, kept_item.bbox) >= threshold), None)
        if duplicate_index is None:
            kept.append(item)
            continue
        existing = kept[duplicate_index]
        if priority[item.replay_decision] > priority[existing.replay_decision]:
            kept[duplicate_index] = item
    return sorted(rename_objects(kept), key=lambda obj: (obj.bbox[1], obj.bbox[0], bbox_area(obj.bbox)))


def rename_objects(objects: list[M292SourceObject]) -> list[M292SourceObject]:
    return [
        M292SourceObject(
            id=f"m292_object_{index + 1:04d}",
            bbox=item.bbox,
            visual_kind=item.visual_kind,
            pixel_owner=item.pixel_owner,
            replay_decision=item.replay_decision,
            source_evidence=item.source_evidence,
            confidence=item.confidence,
            reasons=item.reasons,
            risks=item.risks,
        )
        for index, item in enumerate(objects)
    ]


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


def local_background_confidence(pixels: PngPixels, bbox: list[int]) -> float:
    try:
        bg = sample_outer_bbox_ring_rgb(pixels, bbox)
    except Exception:
        return 0.0
    try:
        metrics = measure_region(pixels, bbox)
    except Exception:
        return 0.0
    distance = abs(metrics.mean_rgb[0] - bg[0]) + abs(metrics.mean_rgb[1] - bg[1]) + abs(metrics.mean_rgb[2] - bg[2])
    texture_penalty = min(1.0, metrics.texture_score)
    return max(0.0, min(1.0, 1.0 - (distance / 765.0) - (texture_penalty * 0.35)))


def build_summary(objects: list[M292SourceObject], m29_nodes: list[dict[str, Any]], ocr_boxes: list[Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in objects:
        counts[item.visual_kind] = counts.get(item.visual_kind, 0) + 1
    return {
        "sourceObjectCount": len(objects),
        "m29NodeCount": len(m29_nodes),
        "ocrTextCount": len(ocr_boxes),
        "editableTextCount": counts.get("editable_ui_text", 0),
        "preservedRasterTextCount": counts.get("preserve_raster_text", 0),
        "rasterIconCount": counts.get("raster_icon", 0),
        "mediaRegionCount": counts.get("media_region", 0),
        "shapeGeometryCount": counts.get("control_background", 0) + counts.get("card_background", 0) + counts.get("separator", 0),
        "diagnosticOnlyCount": sum(1 for item in objects if item.replay_decision == "skip"),
        "dslChanged": False,
        "assetChanged": False,
    }


def render_overlay(pixels: PngPixels, objects: list[M292SourceObject]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {
        "editable_ui_text": (20, 160, 80),
        "preserve_raster_text": (240, 160, 20),
        "media_region": (20, 100, 220),
        "raster_icon": (180, 80, 220),
        "control_background": (40, 190, 190),
        "card_background": (80, 180, 120),
        "separator": (120, 120, 120),
        "shadow_or_blur": (220, 80, 80),
        "unknown": (220, 80, 80),
    }
    for item in objects:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, colors.get(item.visual_kind, (220, 80, 80)), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def parse_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [int(round(float(item))) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def union_bbox(bboxes: list[list[int] | None]) -> list[int] | None:
    valid = [bbox for bbox in bboxes if bbox is not None]
    if not valid:
        return None
    x1 = min(bbox[0] for bbox in valid)
    y1 = min(bbox[1] for bbox in valid)
    x2 = max(bbox[0] + bbox[2] for bbox in valid)
    y2 = max(bbox[1] + bbox[3] for bbox in valid)
    return [x1, y1, x2 - x1, y2 - y1]


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
