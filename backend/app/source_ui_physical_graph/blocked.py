from __future__ import annotations

from typing import Any

from ..m29_materialization_utils import bbox_overlap_ratio
from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_in_bounds
from .artifacts import local_background_confidence, parse_bbox
from .shapes import is_small_foreground_bbox
from .types import M292SourceObject, M292SourcePhysicalOptions, make_object


def classify_blocked_objects(
    blocked_nodes: list[dict[str, Any]],
    media_objects: list[M292SourceObject],
    ocr_boxes: list[Any],
    pixels: PngPixels,
    width: int,
    height: int,
    options: M292SourcePhysicalOptions,
) -> list[M292SourceObject]:
    objects: list[M292SourceObject] = []
    for node in blocked_nodes:
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        reasons = [str(reason) for reason in node.get("reasons", []) if isinstance(reason, str)]
        text_overlap = max((bbox_overlap_ratio(bbox, box.bbox) for box in ocr_boxes), default=0.0)
        media_containment = max((bbox_overlap_ratio(bbox, media.bbox) for media in media_objects), default=0.0)
        if is_recoverable_blocked_foreground(bbox, reasons, text_overlap, media_containment, options):
            objects.append(
                make_object(
                    bbox=bbox,
                    visual_kind="raster_icon",
                    pixel_owner="raster_icon",
                    replay_decision="icon_replay",
                    m29_ids=[],
                    blocked_ids=[str(node.get("id") or "")],
                    ocr_ids=[],
                    local_bg_confidence=local_background_confidence(pixels, bbox),
                    text_overlap=text_overlap,
                    media_containment=media_containment,
                    confidence="medium",
                    reasons=["blocked_small_complex_foreground"],
                    risks=reasons,
                )
            )
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
                local_bg_confidence=local_background_confidence(pixels, bbox),
                text_overlap=text_overlap,
                media_containment=media_containment,
                confidence="low",
                reasons=["blocked_primitive"],
                risks=reasons,
            )
        )
    return objects


def is_recoverable_blocked_foreground(
    bbox: list[int],
    reasons: list[str],
    text_overlap: float,
    media_containment: float,
    options: M292SourcePhysicalOptions,
) -> bool:
    recoverable = {"symbol_color_too_high", "symbol_texture_too_high", "symbol_edge_too_high", "weak_symbol_metrics"}
    hard_blocks = {
        "text_overlap",
        "inside_image_primitive",
        "image_internal_texture",
        "protective_shape_overlap",
        "large_container_fragment",
        "line_like",
        "symbol_area_too_small",
        "symbol_area_too_large",
    }
    reason_set = set(reasons)
    return (
        bool(reason_set & recoverable)
        and not (reason_set & hard_blocks)
        and is_small_foreground_bbox(bbox, options)
        and text_overlap < 0.20
        and media_containment < 0.80
    )
