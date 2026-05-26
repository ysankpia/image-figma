from __future__ import annotations

from typing import Any

from ..m29_materialization_utils import bbox_overlap_ratio
from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_area, bbox_gap_distance, bbox_in_bounds
from .artifacts import local_background_confidence, parse_bbox, union_bbox
from .types import M292SourceObject, M292SourcePhysicalOptions, make_object


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
        if is_selected_tab_indicator_symbol(bbox, ocr_boxes):
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


def is_selected_tab_indicator_symbol(bbox: list[int], ocr_boxes: list[Any]) -> bool:
    width = bbox[2]
    height = bbox[3]
    if height <= 0 or width / max(1, height) < 3.2:
        return False
    text_height = median_ocr_height(ocr_boxes)
    scale = max(0.5, min(6.0, text_height / 14.0)) if text_height > 0 else 1.0
    if height > max(round(18 * scale), round(text_height * 0.75)):
        return False
    for box in ocr_boxes:
        text_bbox = getattr(box, "bbox", None)
        if not isinstance(text_bbox, list) or len(text_bbox) != 4:
            continue
        text_cx = text_bbox[0] + text_bbox[2] / 2
        indicator_cx = bbox[0] + bbox[2] / 2
        dx = abs(indicator_cx - text_cx)
        vertical_gap = bbox[1] - (text_bbox[1] + text_bbox[3])
        width_ratio = width / max(1, text_bbox[2])
        if (
            dx <= max(round(12 * scale), text_bbox[2] * 0.45)
            and 0 <= vertical_gap <= max(round(28 * scale), text_bbox[3] * 1.15)
            and 0.70 <= width_ratio <= 1.80
        ):
            return True
    return False


def median_ocr_height(ocr_boxes: list[Any]) -> float:
    heights: list[float] = []
    for box in ocr_boxes:
        text_bbox = getattr(box, "bbox", None)
        if not isinstance(text_bbox, list) or len(text_bbox) != 4:
            continue
        try:
            height = float(text_bbox[3])
        except (TypeError, ValueError):
            continue
        if 4 <= height <= 160:
            heights.append(height)
    if not heights:
        return 0.0
    ordered = sorted(heights)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0
