from __future__ import annotations

from typing import Any

from ..m29_materialization_utils import bbox_intersection_area, bbox_overlap_ratio
from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_gap_distance, bbox_in_bounds
from .artifacts import local_background_confidence, parse_bbox, union_bbox
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
    records: list[dict[str, Any]] = []
    for node in blocked_nodes:
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        reasons = [str(reason) for reason in node.get("reasons", []) if isinstance(reason, str)]
        text_overlap = max((bbox_overlap_ratio(bbox, box.bbox) for box in ocr_boxes), default=0.0)
        containing_media = best_containing_media(bbox, media_objects)
        media_containment = bbox_overlap_ratio(bbox, containing_media.bbox) if containing_media is not None else 0.0
        label_anchor = label_anchor_evidence(bbox, containing_media.bbox, ocr_boxes) if containing_media is not None else None
        records.append(
            {
                "index": len(records),
                "node": node,
                "bbox": bbox,
                "reasons": reasons,
                "text_overlap": text_overlap,
                "containing_media": containing_media,
                "media_containment": media_containment,
                "label_anchor": label_anchor,
            }
        )

    grouped_indexes: set[int] = set()
    for cluster in label_anchored_fragment_clusters(records, options):
        bbox = union_bbox([record["bbox"] for record in cluster])
        media = cluster[0]["containing_media"]
        label_anchor = str(cluster[0]["label_anchor"] or "")
        if bbox is None or media is None or not label_anchor:
            continue
        reasons = unique_strings([reason for record in cluster for reason in record["reasons"]])
        text_overlap = max((bbox_overlap_ratio(bbox, box.bbox) for box in ocr_boxes), default=0.0)
        media_containment = bbox_overlap_ratio(bbox, media.bbox)
        if not is_recoverable_blocked_foreground(bbox, reasons, text_overlap, media_containment, True, options):
            continue
        for record in cluster:
            grouped_indexes.add(int(record["index"]))
        objects.append(
            make_object(
                bbox=bbox,
                visual_kind="raster_icon",
                pixel_owner="raster_icon",
                replay_decision="icon_replay",
                m29_ids=[],
                blocked_ids=[str(record["node"].get("id") or "") for record in cluster],
                ocr_ids=[],
                local_bg_confidence=local_background_confidence(pixels, bbox),
                text_overlap=text_overlap,
                media_containment=media_containment,
                confidence="medium",
                reasons=["blocked_media_contained_label_anchored_foreground", "blocked_fragment_group"],
                risks=reasons,
                extra_evidence={"labelAnchorOcrBoxId": label_anchor},
            )
        )

    for index, record in enumerate(records):
        if index in grouped_indexes:
            continue
        node = record["node"]
        bbox = record["bbox"]
        reasons = record["reasons"]
        text_overlap = record["text_overlap"]
        media_containment = record["media_containment"]
        label_anchor = record["label_anchor"]
        if is_recoverable_blocked_foreground(bbox, reasons, text_overlap, media_containment, label_anchor is not None, options):
            recovery_reason = "blocked_media_contained_label_anchored_foreground" if media_containment >= 0.80 else "blocked_small_complex_foreground"
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
                    reasons=[recovery_reason],
                    risks=reasons,
                    extra_evidence={"labelAnchorOcrBoxId": label_anchor} if label_anchor is not None else None,
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
    has_label_anchor: bool,
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
    if not (reason_set & recoverable):
        return False
    if reason_set & hard_blocks:
        return False
    if not is_small_foreground_bbox(bbox, options):
        return False
    if text_overlap >= 0.20:
        return False
    if media_containment < 0.80:
        return True
    return has_label_anchor


def label_anchored_fragment_clusters(
    records: list[dict[str, Any]],
    options: M292SourcePhysicalOptions,
) -> list[list[dict[str, Any]]]:
    eligible = [
        record
        for record in records
        if record["media_containment"] >= 0.80
        and record["label_anchor"] is not None
        and is_recoverable_blocked_foreground(record["bbox"], record["reasons"], record["text_overlap"], record["media_containment"], True, options)
    ]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in eligible:
        media = record["containing_media"]
        if media is None:
            continue
        groups.setdefault((media.id, str(record["label_anchor"])), []).append(record)

    clusters: list[list[dict[str, Any]]] = []
    for grouped in groups.values():
        for record in sorted(grouped, key=lambda item: (item["bbox"][1], item["bbox"][0])):
            matched: list[dict[str, Any]] | None = None
            for cluster in clusters:
                cluster_bbox = union_bbox([item["bbox"] for item in cluster])
                if cluster_bbox is not None and bbox_gap_distance(cluster_bbox, record["bbox"]) <= options.icon_cluster_gap:
                    matched = cluster
                    break
            if matched is None:
                clusters.append([record])
            else:
                matched.append(record)
    return [cluster for cluster in clusters if len(cluster) > 1]


def best_containing_media(bbox: list[int], media_objects: list[M292SourceObject]) -> M292SourceObject | None:
    return max(media_objects, key=lambda media: bbox_overlap_ratio(bbox, media.bbox), default=None)


def label_anchor_evidence(bbox: list[int], media_bbox: list[int], ocr_boxes: list[Any]) -> str | None:
    if bbox_overlap_ratio(bbox, media_bbox) < 0.80:
        return None
    icon_cx = bbox[0] + bbox[2] / 2
    icon_cy = bbox[1] + bbox[3] / 2
    max_dx = max(bbox[2] * 0.85, 36)
    for box in ocr_boxes:
        text_bbox = parse_bbox(getattr(box, "bbox", None))
        if text_bbox is None:
            continue
        text = str(getattr(box, "text", "") or "").strip()
        if not text:
            continue
        if not text_is_in_media_context(text_bbox, media_bbox):
            continue
        if bbox_intersection_area(bbox, text_bbox) > 0:
            continue
        text_cx = text_bbox[0] + text_bbox[2] / 2
        text_cy = text_bbox[1] + text_bbox[3] / 2
        dx = abs(icon_cx - text_cx)
        vertical_gap = text_bbox[1] - (bbox[1] + bbox[3])
        same_cell_vertical = abs(icon_cy - text_cy) <= max(bbox[3], text_bbox[3]) * 1.8
        above_label = -max(4, text_bbox[3] * 0.35) <= vertical_gap <= max(36, bbox[3] * 1.25)
        if dx <= max_dx and (above_label or same_cell_vertical):
            return str(getattr(box, "id", "") or "")
    return None


def text_is_in_media_context(text_bbox: list[int], media_bbox: list[int]) -> bool:
    if bbox_overlap_ratio(text_bbox, media_bbox) >= 0.70:
        return True
    text_cx = text_bbox[0] + text_bbox[2] / 2
    text_cy = text_bbox[1] + text_bbox[3] / 2
    return media_bbox[0] <= text_cx <= media_bbox[0] + media_bbox[2] and media_bbox[1] <= text_cy <= media_bbox[1] + media_bbox[3]


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
