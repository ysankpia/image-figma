from __future__ import annotations

from typing import Any

from ..m29_materialization_utils import bbox_overlap_ratio
from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_clamp
from .artifacts import local_background_confidence, parse_bbox
from .types import M292SourceObject, M292SourcePhysicalOptions, make_object


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
        containing_media = best_containing_media(bbox, media_objects)
        media_overlap = bbox_overlap_ratio(bbox, containing_media.bbox) if containing_media is not None else 0.0
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
        if (
            containing_media is not None
            and media_overlap >= options.editable_text_max_media_overlap
            and is_media_display_text(bbox, containing_media.bbox, width, options)
        ):
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


def best_containing_media(bbox: list[int], media_objects: list[M292SourceObject]) -> M292SourceObject | None:
    matches = [
        (bbox_overlap_ratio(bbox, media.bbox), media)
        for media in media_objects
    ]
    matches = [match for match in matches if match[0] > 0]
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]


def is_media_display_text(
    bbox: list[int],
    media_bbox: list[int],
    image_width: int,
    options: M292SourcePhysicalOptions,
) -> bool:
    media_width = max(1, media_bbox[2])
    media_height = max(1, media_bbox[3])
    absolute_display_height = bbox[3] >= options.media_display_text_min_height
    relative_display_height = bbox[3] >= round(media_height * 0.08)
    relative_display_width = bbox[2] >= round(media_width * options.media_display_text_min_width_ratio)
    image_relative_width = bbox[2] >= round(image_width * options.media_display_text_min_width_ratio)
    return absolute_display_height and (
        relative_display_height
        or (relative_display_width and bbox[3] >= round(options.media_display_text_min_height * 0.75))
        or (image_relative_width and bbox[3] >= round(media_height * 0.06))
    )
