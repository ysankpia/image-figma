from __future__ import annotations

from typing import Any

from ..m29_materialization_utils import bbox_overlap_ratio
from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_area, bbox_in_bounds, measure_region
from .artifacts import local_background_confidence, parse_bbox
from .types import M292SourceObject, M292SourcePhysicalOptions, make_object


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
