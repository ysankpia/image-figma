from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import PngPixels
from ..visual_primitive_graph import (
    M29PrimitiveMetrics,
    bbox_area,
    bbox_in_bounds,
    bbox_iou,
    crop_pixels,
    mask_bbox_overlap_ratio,
    measure_region,
)
from .regions import parse_bbox, parse_metrics, region_for_bbox
from .types import MediaAuditRegion, MediaEvidenceItem, TextMaskedMediaAuditOptions


def collect_media_evidence(
    *,
    pixels: PngPixels,
    output_dir: Path,
    text_mask: Any,
    image_mask: Any,
    regions: list[MediaAuditRegion],
    before_document: dict[str, Any],
    after_document: dict[str, Any],
    m291_document: dict[str, Any] | None,
    options: TextMaskedMediaAuditOptions,
) -> list[MediaEvidenceItem]:
    evidence: list[MediaEvidenceItem] = []
    nodes = [node for node in before_document.get("nodes", []) if isinstance(node, dict)]
    blocked = [item for item in before_document.get("blocked", []) if isinstance(item, dict)]
    after_nodes = [node for node in after_document.get("nodes", []) if isinstance(node, dict)]
    source_by_type = {
        "image": ("m29_image", "accepted_image"),
        "unknown": ("m29_unknown", "image_like_unknown"),
        "symbol": ("m29_symbol", "image_like_symbol"),
        "shape": ("m29_shape", "support_shape"),
    }
    counters: dict[str, int] = {}

    for node in nodes:
        node_type = str(node.get("type"))
        if node_type not in source_by_type:
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
            continue
        if node_type == "symbol" and not is_media_like_symbol(node, options):
            continue
        if node_type == "shape" and not is_source_support_shape(node):
            continue
        source, decision = source_by_type[node_type]
        evidence.append(
            build_evidence_item(
                id=next_evidence_id(source, counters),
                source=source,
                decision=decision,
                bbox=bbox,
                region_name=region_for_bbox(bbox, regions),
                asset_path=export_evidence_asset(pixels, output_dir, source, bbox, counters),
                text_mask=text_mask,
                image_mask=image_mask,
                metrics=parse_metrics(node.get("metrics")) or measure_region(pixels, bbox),
                reasons=support_shape_reasons(node),
            )
        )

    for item in blocked:
        bbox = parse_bbox(item.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height) or not is_media_like_blocked(item, options):
            continue
        evidence.append(
            build_evidence_item(
                id=next_evidence_id("m29_blocked", counters),
                source="m29_blocked",
                decision="image_like_blocked",
                bbox=bbox,
                region_name=region_for_bbox(bbox, regions),
                asset_path=export_evidence_asset(pixels, output_dir, "m29_blocked", bbox, counters),
                text_mask=text_mask,
                image_mask=image_mask,
                metrics=parse_metrics(item.get("metrics")) or measure_region(pixels, bbox),
                reasons=[str(reason) for reason in item.get("reasons", [])],
            )
        )

    if m291_document is not None:
        for group in [item for item in m291_document.get("groups", []) if isinstance(item, dict)]:
            if group.get("decision") not in {"accepted", "uncertain"}:
                continue
            bbox = parse_bbox(group.get("bbox"))
            if bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
                continue
            evidence.append(
                build_evidence_item(
                    id=next_evidence_id("m291_group", counters),
                    source="m291_group",
                    decision="symbol_group",
                    bbox=bbox,
                    region_name=region_for_bbox(bbox, regions),
                    asset_path=export_evidence_asset(pixels, output_dir, "m291_group", bbox, counters),
                    text_mask=text_mask,
                    image_mask=image_mask,
                    metrics=measure_region(pixels, bbox),
                    reasons=[str(reason) for reason in group.get("reasons", [])],
                )
            )

    before_bboxes = [parse_bbox(node.get("bbox")) for node in nodes if node.get("type") in {"image", "unknown", "symbol"}]
    before_bboxes = [bbox for bbox in before_bboxes if bbox is not None]
    for node in after_nodes:
        if node.get("type") not in {"image", "unknown", "symbol"}:
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
            continue
        if bbox_area(bbox) < options.min_media_like_area:
            continue
        if any(bbox_iou(bbox, before_bbox) >= 0.60 for before_bbox in before_bboxes):
            continue
        evidence.append(
            build_evidence_item(
                id=next_evidence_id("after_text_mask_candidate", counters),
                source="after_text_mask_candidate",
                decision="text_suppressed_candidate",
                bbox=bbox,
                region_name=region_for_bbox(bbox, regions),
                asset_path=export_evidence_asset(pixels, output_dir, "after_text_mask_candidate", bbox, counters),
                text_mask=text_mask,
                image_mask=image_mask,
                metrics=parse_metrics(node.get("metrics")) or measure_region(pixels, bbox),
                reasons=[str(reason) for reason in node.get("reasons", [])],
            )
        )
    return sorted(evidence, key=lambda item: (item.bbox[1], item.bbox[0], item.source, item.id))

def build_evidence_item(
    *,
    id: str,
    source: str,
    decision: str,
    bbox: list[int],
    region_name: str,
    asset_path: str | None,
    text_mask: Any,
    image_mask: Any,
    metrics: M29PrimitiveMetrics,
    reasons: list[str],
) -> MediaEvidenceItem:
    text_overlap = mask_bbox_overlap_ratio(text_mask, bbox)
    image_overlap = mask_bbox_overlap_ratio(image_mask, bbox)
    return MediaEvidenceItem(
        id=id,
        source=source,  # type: ignore[arg-type]
        bbox=bbox,
        region_name=region_name,
        decision=decision,  # type: ignore[arg-type]
        asset_path=asset_path,
        text_overlap_ratio=text_overlap,
        image_overlap_ratio=image_overlap,
        metrics=metrics,
        reasons=reasons,
        suggested_next_action=suggested_next_action(source, decision, text_overlap, reasons),
    )

def next_evidence_id(source: str, counters: dict[str, int]) -> str:
    counters[source] = counters.get(source, 0) + 1
    return f"{source}_{counters[source]:03d}"

def export_evidence_asset(
    pixels: PngPixels,
    output_dir: Path,
    source: str,
    bbox: list[int],
    counters: dict[str, int],
) -> str:
    folder = {
        "m29_image": "accepted_images",
        "m29_unknown": "media_like_unknowns",
        "m29_symbol": "media_like_symbols",
        "m29_shape": "support_shapes",
        "m29_blocked": "media_like_blocked",
        "m291_group": "symbol_groups",
        "after_text_mask_candidate": "media_like_unknowns",
    }.get(source, "media_like_symbols")
    target_dir = output_dir / "assets" / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    index = counters.get(f"{source}_asset", 0) + 1
    counters[f"{source}_asset"] = index
    path = target_dir / f"{source}_{index:03d}.png"
    path.write_bytes(crop_pixels(pixels, bbox))
    return str(path.relative_to(output_dir))

def is_media_like_symbol(node: dict[str, Any], options: TextMaskedMediaAuditOptions) -> bool:
    bbox = parse_bbox(node.get("bbox"))
    metrics = parse_metrics(node.get("metrics"))
    if bbox is None:
        return False
    area = bbox_area(bbox)
    if area >= options.min_media_like_area:
        return True
    if metrics is None:
        return False
    return area >= options.min_media_like_area * 0.5 and (metrics.color_count >= 32 or metrics.texture_score >= 0.18)

def is_source_support_shape(node: dict[str, Any]) -> bool:
    if str(node.get("type") or "") != "shape":
        return False
    subtype = str(node.get("subtype") or "")
    reasons = {str(reason) for reason in node.get("reasons", []) if isinstance(reason, str)}
    return subtype in {"low_contrast_support", "text_support_background"} or bool(
        reasons & {"low_contrast_support_region", "text_support_background_region"}
    )

def support_shape_reasons(node: dict[str, Any]) -> list[str]:
    reasons = [str(reason) for reason in node.get("reasons", []) if isinstance(reason, str)]
    if is_source_support_shape(node):
        subtype = str(node.get("subtype") or "")
        if subtype:
            reasons.append(f"sourceSubtype:{subtype}")
    return dedupe_strings(reasons)

def dedupe_strings(items: list[str]) -> list[str]:
    output: list[str] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output

def is_media_like_blocked(item: dict[str, Any], options: TextMaskedMediaAuditOptions) -> bool:
    bbox = parse_bbox(item.get("bbox"))
    metrics = parse_metrics(item.get("metrics"))
    if bbox is None:
        return False
    reasons = {str(reason) for reason in item.get("reasons", [])}
    area = bbox_area(bbox)
    if "image_internal_texture" in reasons:
        return area >= options.min_media_like_area
    if "text_overlap" in reasons and area < options.min_media_like_area * 2:
        return False
    if area >= options.min_media_like_area and reasons & {"weak_symbol_metrics", "symbol_color_too_high", "symbol_texture_too_high"}:
        return True
    return metrics is not None and area >= options.min_media_like_area * 0.5 and metrics.color_count >= 32

def suggested_next_action(source: str, decision: str, text_overlap: float, reasons: list[str]) -> str:
    if source == "m29_shape":
        return "support_shape_candidate"
    if text_overlap >= 0.35:
        return "likely_text_noise"
    if source == "m29_image":
        return "keep_accepted_image"
    if source == "m29_unknown":
        return "review_image_threshold"
    if source == "m29_symbol":
        return "review_symbol_vs_image"
    if source == "m29_blocked":
        if "image_internal_texture" in reasons:
            return "review_inside_image_boundary"
        return "review_blocked_media_candidate"
    if source == "m291_group":
        return "review_symbol_group"
    if decision == "text_suppressed_candidate":
        return "compare_after_text_mask"
    return "review"
