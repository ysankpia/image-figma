from __future__ import annotations

from typing import Any

from ..m29_materialization_utils import bbox_overlap_ratio
from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_area, bbox_in_bounds
from .artifacts import local_background_confidence, parse_bbox
from .controls import CONTROL_BACKGROUND_SUBTYPES, classify_control_like_unknown
from .media import media_blocks_child_foreground
from .types import M292SourceObject, M292SourcePhysicalOptions, M292VisualKind, make_object


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
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        evidence = classify_control_like_unknown(node, bbox, ocr_boxes, pixels, width, height, options)
        if evidence is None:
            continue
        objects.append(
            make_object(
                bbox=bbox,
                visual_kind="control_background",
                pixel_owner="shape_geometry",
                replay_decision="shape_replay",
                m29_ids=[str(node.get("id") or "")],
                ocr_ids=evidence.text_ids,
                local_bg_confidence=local_background_confidence(pixels, bbox),
                text_overlap=max((bbox_overlap_ratio(bbox, box.bbox) for box in ocr_boxes), default=0.0),
                media_containment=max((bbox_overlap_ratio(bbox, media.bbox) for media in media_objects), default=0.0),
                confidence=evidence.confidence,
                reasons=["low_confidence_unknown_control_background", "finite_control_bbox", "contains_ocr_text"],
                risks=["shape_from_low_confidence_unknown"],
                extra_evidence={
                    "sourceShapeInference": "finite_control_low_confidence_unknown",
                    "shapeFillOverride": evidence.fill,
                    **({"shapeRadiusOverride": evidence.radius} if evidence.radius is not None else {}),
                    "controlTextAreaRatio": evidence.text_area_ratio,
                },
            )
        )
    for node in m29_nodes:
        if str(node.get("type") or "") != "shape":
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        if any(media_blocks_child_foreground(media) and bbox_overlap_ratio(bbox, media.bbox) >= 0.80 for media in media_objects):
            continue
        subtype = str(node.get("subtype") or "")
        metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
        text_overlap = max((bbox_overlap_ratio(bbox, box.bbox) for box in ocr_boxes), default=0.0)
        media_containment = max((bbox_overlap_ratio(bbox, media.bbox) for media in media_objects), default=0.0)
        if is_small_textured_foreground_shape(subtype, bbox, metrics, text_overlap, options):
            objects.append(
                make_object(
                    bbox=bbox,
                    visual_kind="raster_icon",
                    pixel_owner="raster_icon",
                    replay_decision="icon_replay",
                    m29_ids=[str(node.get("id") or "")],
                    ocr_ids=[],
                    local_bg_confidence=local_background_confidence(pixels, bbox),
                    text_overlap=text_overlap,
                    media_containment=media_containment,
                    confidence="medium",
                    reasons=["small_textured_foreground_shape"],
                    risks=["raster_icon_from_shape_evidence"],
                )
            )
            continue
        if not is_shape_replay_safe(subtype, bbox, metrics, text_overlap, options):
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
                    media_containment=media_containment,
                    confidence="low",
                    reasons=["shape_not_safe_for_geometry_replay"],
                    risks=["complex_shape_or_blur"],
                )
            )
            continue
        if subtype == "separator":
            visual_kind: M292VisualKind = "separator"
            reasons = ["separator_shape"]
        elif subtype in {"card_background", "container_background", "background", "large_container"}:
            visual_kind = "card_background"
            reasons = ["container_background_shape"]
        elif subtype in CONTROL_BACKGROUND_SUBTYPES:
            visual_kind = "control_background"
            reasons = ["control_background_shape"]
        else:
            visual_kind = "control_background"
            reasons = ["solid_ui_shape"]
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
                media_containment=media_containment,
                confidence="high",
                reasons=reasons,
                risks=[],
            )
        )
    return objects


def is_shape_replay_safe(
    subtype: str,
    bbox: list[int],
    metrics: dict[str, Any],
    text_overlap: float,
    options: M292SourcePhysicalOptions,
) -> bool:
    if text_overlap >= 0.45:
        return False
    color_count = metric_int(metrics, "colorCount")
    texture = metric_float(metrics, "textureScore")
    edge = metric_float(metrics, "edgeScore")
    if color_count > options.shape_replay_color_threshold:
        return False
    if texture > options.shape_replay_texture_threshold:
        return False
    if edge >= options.shape_replay_edge_threshold:
        return False
    if subtype == "separator":
        return True
    if subtype in {
        "card_background",
        "container_background",
        "background",
        "large_container",
        *CONTROL_BACKGROUND_SUBTYPES,
    }:
        return True
    return True


def is_small_textured_foreground_shape(
    subtype: str,
    bbox: list[int],
    metrics: dict[str, Any],
    text_overlap: float,
    options: M292SourcePhysicalOptions,
) -> bool:
    if subtype not in {"badge_background", "small_ellipse", "icon_button_background", "small_rounded_rect"}:
        return False
    if not is_small_foreground_bbox(bbox, options):
        return False
    if text_overlap >= 0.20:
        return False
    return is_complex_foreground_metrics(metrics, options)


def is_small_foreground_bbox(bbox: list[int], options: M292SourcePhysicalOptions) -> bool:
    return bbox_area(bbox) <= options.icon_max_area and max(bbox[2], bbox[3]) <= options.raster_foreground_max_edge


def is_complex_foreground_metrics(metrics: dict[str, Any], options: M292SourcePhysicalOptions) -> bool:
    return (
        metric_int(metrics, "colorCount") > options.textured_foreground_color_threshold
        or metric_float(metrics, "textureScore") > options.textured_foreground_texture_threshold
        or metric_float(metrics, "edgeScore") >= options.textured_foreground_edge_threshold
    )


def metric_float(metrics: dict[str, Any], key: str) -> float:
    value = metrics.get(key)
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def metric_int(metrics: dict[str, Any], key: str) -> int:
    value = metrics.get(key)
    if isinstance(value, bool):
        return 0
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0
