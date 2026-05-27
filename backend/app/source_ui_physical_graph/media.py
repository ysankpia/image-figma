from __future__ import annotations

from typing import Any

from ..m29_materialization_utils import bbox_overlap_ratio
from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_area, bbox_in_bounds, measure_region
from .artifacts import local_background_confidence, parse_bbox
from .controls import CONTROL_BACKGROUND_SUBTYPES, classify_control_like_unknown
from .types import M292SourceObject, M292SourcePhysicalOptions, make_object, unique_strings


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
        node_type = str(node.get("type") or "")
        subtype = str(node.get("subtype") or "")
        if classify_control_like_unknown(node, bbox, ocr_boxes, pixels, width, height, options) is not None:
            continue
        if is_control_shape_supported_low_confidence_unknown(node, bbox, m29_nodes):
            continue
        low_confidence_media = (
            node_type == "unknown"
            and subtype == "image_like_low_confidence"
            and bbox_area(bbox) >= options.media_min_color_or_texture_area
            and (
                metrics.color_count >= options.media_color_threshold
                or metrics.texture_score >= options.media_texture_threshold
                or float(getattr(metrics, "edge_score", 0.0)) >= options.textured_foreground_edge_threshold
            )
        )
        if node_type == "image" or low_confidence_media or (
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
                    confidence="high" if node_type == "image" else "medium",
                    reasons=["m29_image_region"] if node_type == "image" else ["large_image_like_region"],
                    risks=unique_strings([
                        *(["contains_internal_text"] if text_overlap >= options.media_text_overlap_preserve_threshold else []),
                        *(["low_confidence_media_region"] if low_confidence_media else []),
                    ]),
                )
            )
    return objects


def is_control_shape_supported_low_confidence_unknown(node: dict[str, Any], bbox: list[int], m29_nodes: list[dict[str, Any]]) -> bool:
    if str(node.get("type") or "") != "unknown":
        return False
    if str(node.get("subtype") or "") != "image_like_low_confidence":
        return False
    for candidate in m29_nodes:
        if candidate is node:
            continue
        if str(candidate.get("type") or "") != "shape":
            continue
        if str(candidate.get("subtype") or "") not in CONTROL_BACKGROUND_SUBTYPES:
            continue
        candidate_bbox = parse_bbox(candidate.get("bbox"))
        if candidate_bbox is None:
            continue
        if bbox_overlap_ratio(bbox, candidate_bbox) >= 0.65:
            return True
    return False


def media_blocks_child_foreground(media: M292SourceObject) -> bool:
    if media.visual_kind != "media_region" or media.pixel_owner != "preserve_raster":
        return False
    if "low_confidence_media_region" in media.risks:
        return False
    if "contains_internal_text" in media.risks:
        return False
    return "m29_image_region" in media.reasons
