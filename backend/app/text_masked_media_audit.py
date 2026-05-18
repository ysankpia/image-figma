from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_primitive_graph import (
    M29PrimitiveMetrics,
    M29TextBox,
    M29VisualPrimitiveGraphDocument,
    M29VisualPrimitiveOptions,
    bbox_area,
    bbox_clamp,
    bbox_in_bounds,
    bbox_iou,
    bbox_x2,
    bbox_y2,
    build_text_exclusion_mask,
    crop_pixels,
    draw_rect,
    estimate_global_background,
    extract_m29_visual_primitive_graph,
    mask_bbox_overlap_ratio,
    mask_from_bboxes,
    mask_to_png,
    measure_region,
    metrics_to_dict,
    pad_bbox,
)


M2902Source = Literal[
    "m29_image",
    "m29_unknown",
    "m29_symbol",
    "m29_blocked",
    "m291_group",
    "after_text_mask_candidate",
]
M2902Decision = Literal[
    "accepted_image",
    "image_like_unknown",
    "image_like_symbol",
    "image_like_blocked",
    "symbol_group",
    "text_suppressed_candidate",
]


@dataclass(frozen=True)
class TextMaskedMediaAuditOptions:
    text_padding: int = 2
    min_media_like_area: int = 400
    output_preview_max_thumb: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MediaAuditRegion:
    name: str
    bbox: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "bbox": self.bbox}


@dataclass(frozen=True)
class MediaEvidenceItem:
    id: str
    source: M2902Source
    bbox: list[int]
    region_name: str
    decision: M2902Decision
    asset_path: str | None
    text_overlap_ratio: float
    image_overlap_ratio: float
    metrics: M29PrimitiveMetrics
    reasons: list[str]
    suggested_next_action: str

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "bbox": self.bbox,
            "regionName": self.region_name,
            "decision": self.decision,
            "textOverlapRatio": round(self.text_overlap_ratio, 4),
            "imageOverlapRatio": round(self.image_overlap_ratio, 4),
            "metrics": metrics_to_dict(self.metrics),
            "reasons": self.reasons,
            "suggestedNextAction": self.suggested_next_action,
        }
        if self.asset_path is not None:
            data["assetPath"] = self.asset_path
        return data


@dataclass(frozen=True)
class TextMaskedDebugArtifacts:
    text_mask: str
    text_suppressed_analysis: str
    media_before_after: str
    media_evidence_map: str

    def to_dict(self) -> dict[str, str]:
        return {
            "textMask": self.text_mask,
            "textSuppressedAnalysis": self.text_suppressed_analysis,
            "mediaBeforeAfter": self.media_before_after,
            "mediaEvidenceMap": self.media_evidence_map,
        }


@dataclass(frozen=True)
class TextMaskedMediaAuditDocument:
    schema_name: str
    schema_version: str
    source_image: str
    source_m29_nodes_json: str | None
    source_m291_group_nodes_json: str | None
    text_source: str
    options: TextMaskedMediaAuditOptions
    text_boxes: list[M29TextBox]
    regions: list[MediaAuditRegion]
    before_counts: dict[str, int]
    after_counts: dict[str, int]
    media_evidence: list[MediaEvidenceItem]
    warnings: list[str]
    debug: TextMaskedDebugArtifacts
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM29NodesJson": self.source_m29_nodes_json,
            "sourceM291GroupNodesJson": self.source_m291_group_nodes_json,
            "textSource": self.text_source,
            "options": self.options.to_dict(),
            "textBoxes": [text_box_to_dict(item) for item in self.text_boxes],
            "regions": [region.to_dict() for region in self.regions],
            "beforeCounts": self.before_counts,
            "afterCounts": self.after_counts,
            "mediaEvidence": [item.to_dict() for item in self.media_evidence],
            "warnings": self.warnings,
            "debug": self.debug.to_dict(),
            "meta": self.meta,
        }


def extract_text_masked_media_audit(
    *,
    png_data: bytes,
    source_image: str,
    output_dir: Path,
    text_boxes: list[M29TextBox],
    text_source: str,
    m29_document: dict[str, Any] | None = None,
    m29_nodes_json_path: str | None = None,
    m291_document: dict[str, Any] | None = None,
    m291_group_nodes_json_path: str | None = None,
    regions: list[MediaAuditRegion] | None = None,
    options: TextMaskedMediaAuditOptions | None = None,
    warnings: list[str] | None = None,
) -> TextMaskedMediaAuditDocument:
    options = options or TextMaskedMediaAuditOptions()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    regions = regions or default_media_regions(pixels.width, pixels.height)

    text_mask = build_text_exclusion_mask(pixels.width, pixels.height, text_boxes, options.text_padding)
    suppressed_pixels = build_text_suppressed_pixels(pixels, text_boxes, options)
    suppressed_png = encode_rgb_png(suppressed_pixels.width, suppressed_pixels.height, suppressed_pixels.rows)

    before_document = m29_document or extract_m29_visual_primitive_graph(
        png_data=png_data,
        source_image=source_image,
        output_dir=output_dir / "m29_original",
        options=M29VisualPrimitiveOptions(),
        text_boxes=[],
    ).to_dict()
    after_document = extract_m29_visual_primitive_graph(
        png_data=suppressed_png,
        source_image=f"{source_image}#text_suppressed",
        output_dir=output_dir / "m29_text_suppressed",
        options=M29VisualPrimitiveOptions(),
        text_boxes=text_boxes,
    ).to_dict()

    image_mask = mask_from_bboxes(
        pixels.width,
        pixels.height,
        [parse_bbox(node.get("bbox")) or [0, 0, 0, 0] for node in before_document.get("nodes", []) if node.get("type") == "image"],
    )
    media_evidence = collect_media_evidence(
        pixels=pixels,
        output_dir=output_dir,
        text_mask=text_mask,
        image_mask=image_mask,
        regions=regions,
        before_document=before_document,
        after_document=after_document,
        m291_document=m291_document,
        options=options,
    )

    debug = write_debug_artifacts(
        pixels=pixels,
        output_dir=output_dir,
        text_mask=text_mask,
        suppressed_pixels=suppressed_pixels,
        before_document=before_document,
        after_document=after_document,
        evidence=media_evidence,
    )
    preview_path = output_dir / "preview_text_masked_media_audit.png"
    preview_path.write_bytes(build_preview_sheet(pixels, suppressed_pixels, output_dir, debug, media_evidence, options))

    document = TextMaskedMediaAuditDocument(
        schema_name="M2902TextMaskedMediaAuditDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m29_nodes_json=m29_nodes_json_path,
        source_m291_group_nodes_json=m291_group_nodes_json_path,
        text_source=text_source,
        options=options,
        text_boxes=text_boxes,
        regions=regions,
        before_counts=extract_counts(before_document),
        after_counts=extract_counts(after_document),
        media_evidence=media_evidence,
        warnings=warnings or [],
        debug=debug,
        meta=build_meta(text_boxes, media_evidence),
    )
    validate_text_masked_media_audit(document, output_dir, pixels.width, pixels.height)
    write_outputs(document, output_dir)
    return document


def text_boxes_from_ocr_document(payload: dict[str, Any]) -> tuple[list[M29TextBox], list[str]]:
    warnings: list[str] = []
    boxes: list[M29TextBox] = []
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return [], ["ocr_json_missing_blocks"]
    for index, item in enumerate(blocks):
        if not isinstance(item, dict):
            warnings.append(f"ocr_block_{index + 1}_invalid")
            continue
        bbox = parse_bbox(item.get("bbox"))
        if bbox is None:
            warnings.append(f"ocr_block_{item.get('id', index + 1)}_invalid_bbox")
            continue
        boxes.append(
            M29TextBox(
                id=str(item.get("id") or f"ocr_text_{index + 1:03d}"),
                bbox=bbox,
                text=str(item.get("text", "")).strip() or None,
                confidence=float(item.get("confidence", 1.0)),
                source="ocr",
                kind="line",
            )
        )
    return boxes, warnings


def text_box_to_dict(item: M29TextBox) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": item.id,
        "bbox": item.bbox,
        "confidence": round(item.confidence, 3),
        "source": item.source,
        "kind": item.kind,
    }
    if item.text is not None:
        data["text"] = item.text
    return data


def default_media_regions(width: int, height: int) -> list[MediaAuditRegion]:
    if height < 600:
        return [MediaAuditRegion("full", [0, 0, width, height])]
    header_h = min(max(round(height * 0.08), 96), 180)
    bottom_h = min(max(round(height * 0.08), 96), 180)
    body_top = header_h
    body_bottom = max(body_top, height - bottom_h)
    body_h = body_bottom - body_top
    band_h = max(1, body_h // 5)
    return [
        MediaAuditRegion("top/header", [0, 0, width, header_h]),
        MediaAuditRegion("hero/banner", [0, body_top, width, band_h]),
        MediaAuditRegion("category/grid", [0, body_top + band_h, width, band_h]),
        MediaAuditRegion("product/list", [0, body_top + band_h * 2, width, band_h]),
        MediaAuditRegion("supplier/card", [0, body_top + band_h * 3, width, band_h]),
        MediaAuditRegion("tools/icons", [0, body_top + band_h * 4, width, body_bottom - (body_top + band_h * 4)]),
        MediaAuditRegion("bottom/nav", [0, body_bottom, width, height - body_bottom]),
    ]


def build_text_suppressed_pixels(
    pixels: PngPixels,
    text_boxes: list[M29TextBox],
    options: TextMaskedMediaAuditOptions,
) -> PngPixels:
    rows = [bytearray(row) for row in pixels.rows]
    global_background = estimate_global_background(pixels)
    for text_box in text_boxes:
        padded = bbox_clamp(pad_bbox(text_box.bbox, options.text_padding), pixels.width, pixels.height)
        if padded is None:
            continue
        fill = local_background_rgb(pixels, padded, global_background)
        fill_bytes = bytes(fill)
        x, y, width, height = padded
        for row_index in range(y, y + height):
            row = rows[row_index]
            for column in range(x, x + width):
                row[column * 3 : column * 3 + 3] = fill_bytes
    return PngPixels(width=pixels.width, height=pixels.height, rows=[bytes(row) for row in rows])


def local_background_rgb(pixels: PngPixels, bbox: list[int], fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    x, y, width, height = bbox
    expanded = bbox_clamp([x - 4, y - 4, width + 8, height + 8], pixels.width, pixels.height)
    if expanded is None:
        return fallback
    ex, ey, ew, eh = expanded
    samples: list[tuple[int, int, int]] = []
    for row_index in range(ey, ey + eh):
        row = pixels.rows[row_index]
        for column in range(ex, ex + ew):
            if x <= column < x + width and y <= row_index < y + height:
                continue
            offset = column * 3
            samples.append((row[offset], row[offset + 1], row[offset + 2]))
    if not samples:
        return fallback
    buckets: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    for sample in samples:
        buckets.setdefault((sample[0] // 16, sample[1] // 16, sample[2] // 16), []).append(sample)
    dominant = max(buckets.values(), key=len)
    return tuple(round(sum(sample[channel] for sample in dominant) / len(dominant)) for channel in range(3))


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
                reasons=[str(reason) for reason in node.get("reasons", [])],
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


def region_for_bbox(bbox: list[int], regions: list[MediaAuditRegion]) -> str:
    best = max(regions, key=lambda region: bbox_iou_or_overlap(bbox, region.bbox), default=None)
    if best is None or bbox_iou_or_overlap(bbox, best.bbox) <= 0:
        return "unknown"
    return best.name


def bbox_iou_or_overlap(bbox: list[int], region: list[int]) -> float:
    x1 = max(bbox[0], region[0])
    y1 = max(bbox[1], region[1])
    x2 = min(bbox_x2(bbox), bbox_x2(region))
    y2 = min(bbox_y2(bbox), bbox_y2(region))
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    return intersection / max(1, bbox_area(bbox))


def write_debug_artifacts(
    *,
    pixels: PngPixels,
    output_dir: Path,
    text_mask: Any,
    suppressed_pixels: PngPixels,
    before_document: dict[str, Any],
    after_document: dict[str, Any],
    evidence: list[MediaEvidenceItem],
) -> TextMaskedDebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    text_mask_path = overlay_dir / "09_text_mask.png"
    suppressed_path = overlay_dir / "10_text_suppressed_analysis.png"
    before_after_path = overlay_dir / "11_media_before_after.png"
    evidence_path = overlay_dir / "12_media_evidence_map.png"
    text_mask_path.write_bytes(mask_to_png(text_mask))
    suppressed_path.write_bytes(encode_rgb_png(suppressed_pixels.width, suppressed_pixels.height, suppressed_pixels.rows))
    before_after_path.write_bytes(overlay_before_after(pixels, before_document, after_document))
    evidence_path.write_bytes(overlay_evidence(pixels, evidence))
    return TextMaskedDebugArtifacts(
        text_mask=str(text_mask_path.relative_to(output_dir)),
        text_suppressed_analysis=str(suppressed_path.relative_to(output_dir)),
        media_before_after=str(before_after_path.relative_to(output_dir)),
        media_evidence_map=str(evidence_path.relative_to(output_dir)),
    )


def overlay_before_after(pixels: PngPixels, before_document: dict[str, Any], after_document: dict[str, Any]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for node in before_document.get("nodes", []):
        if not isinstance(node, dict) or node.get("type") not in {"image", "unknown"}:
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is not None:
            draw_rect(rows, pixels.width, pixels.height, bbox, (0, 180, 210) if node.get("type") == "image" else (238, 190, 40), 2)
    for node in after_document.get("nodes", []):
        if not isinstance(node, dict) or node.get("type") not in {"image", "unknown", "symbol"}:
            continue
        bbox = parse_bbox(node.get("bbox"))
        if bbox is not None:
            draw_rect(rows, pixels.width, pixels.height, bbox, (220, 60, 220), 1)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_evidence(pixels: PngPixels, evidence: list[MediaEvidenceItem]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {
        "accepted_image": (0, 180, 210),
        "image_like_unknown": (238, 190, 40),
        "image_like_symbol": (0, 200, 90),
        "image_like_blocked": (235, 64, 52),
        "symbol_group": (60, 120, 255),
        "text_suppressed_candidate": (220, 60, 220),
    }
    for item in evidence:
        draw_rect(rows, pixels.width, pixels.height, item.bbox, colors[item.decision], 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def build_preview_sheet(
    pixels: PngPixels,
    suppressed_pixels: PngPixels,
    output_dir: Path,
    debug: TextMaskedDebugArtifacts,
    evidence: list[MediaEvidenceItem],
    options: TextMaskedMediaAuditOptions,
) -> bytes:
    evidence_overlay = decode_png_pixels((output_dir / debug.media_evidence_map).read_bytes())
    before_after = decode_png_pixels((output_dir / debug.media_before_after).read_bytes())
    max_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.38, (max_width - margin * 2 - gap * 3) / max(1, pixels.width * 4))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    crop_items = crop_previews_for_evidence(output_dir, evidence, options.output_preview_max_thumb)
    grid_h = grid_height(crop_items, max_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * max_width) for _ in range(sheet_height)]
    x = margin
    for item in [pixels, suppressed_pixels, before_after, evidence_overlay]:
        paste_scaled(canvas, max_width, item, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, max_width, crop_items, margin, margin + top_h + margin, gap)
    return encode_rgb_png(max_width, sheet_height, [bytes(row) for row in canvas])


def crop_previews_for_evidence(
    output_dir: Path,
    evidence: list[MediaEvidenceItem],
    max_edge: int,
) -> list[tuple[MediaEvidenceItem, PngPixels, int, int]]:
    previews: list[tuple[MediaEvidenceItem, PngPixels, int, int]] = []
    for item in sorted(evidence, key=preview_sort_key):
        if item.asset_path is None:
            continue
        try:
            pixels = decode_png_pixels((output_dir / item.asset_path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, pixels.width, pixels.height))
        previews.append((item, pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews


def preview_sort_key(item: MediaEvidenceItem) -> tuple[int, int, int, int, int, str]:
    source_rank = {
        "m29_image": 0,
        "m29_unknown": 1,
        "m29_blocked": 2,
        "m29_symbol": 3,
        "m291_group": 4,
        "after_text_mask_candidate": 5,
    }.get(item.source, 9)
    noise_rank = 1 if item.suggested_next_action == "likely_text_noise" else 0
    return (noise_rank, source_rank, -bbox_area(item.bbox), item.bbox[1], item.bbox[0], item.id)


def preview_border_color(item: MediaEvidenceItem) -> tuple[int, int, int]:
    if item.suggested_next_action == "likely_text_noise":
        return (190, 190, 190)
    return {
        "accepted_image": (0, 180, 210),
        "image_like_unknown": (238, 190, 40),
        "image_like_symbol": (0, 200, 90),
        "image_like_blocked": (235, 64, 52),
        "symbol_group": (60, 120, 255),
        "text_suppressed_candidate": (220, 60, 220),
    }.get(item.decision, (140, 140, 140))


def grid_height(previews: list[tuple[MediaEvidenceItem, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 48
    x = margin
    row_h = 0
    total = 0
    for _item, _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h


def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[MediaEvidenceItem, PngPixels, int, int]], x: int, y: int, gap: int) -> int:
    row_h = 0
    margin = x
    if not previews:
        fill_rect(canvas, sheet_width, x, y, sheet_width - x * 2, 48, (232, 232, 232))
        return y + 48
    for item, preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, preview_border_color(item))
        fill_rect(canvas, sheet_width, x - 2, y - 2, width + 4, height + 4, (244, 244, 244))
        paste_scaled(canvas, sheet_width, preview, x, y, width, height)
        x += width + gap
        row_h = max(row_h, height)
    return y + row_h


def paste_scaled(canvas: list[bytearray], sheet_width: int, source: PngPixels, x: int, y: int, target_width: int, target_height: int) -> None:
    for target_y in range(target_height):
        source_y = min(source.height - 1, round(target_y * source.height / target_height))
        if y + target_y < 0 or y + target_y >= len(canvas):
            continue
        source_row = source.rows[source_y]
        target_row = canvas[y + target_y]
        for target_x in range(target_width):
            source_x = min(source.width - 1, round(target_x * source.width / target_width))
            dst_x = x + target_x
            if 0 <= dst_x < sheet_width:
                target_row[dst_x * 3 : dst_x * 3 + 3] = source_row[source_x * 3 : source_x * 3 + 3]


def fill_rect(canvas: list[bytearray], sheet_width: int, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            row[column * 3 : column * 3 + 3] = color_bytes


def write_outputs(document: TextMaskedMediaAuditDocument, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "text_masked_media_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_masked_media_audit.md").write_text(build_markdown_report(document), encoding="utf-8")


def build_markdown_report(document: TextMaskedMediaAuditDocument) -> str:
    lines = [
        "# M29.0.2 Text-Masked Visual Media Audit",
        "",
        f"- Text source: `{document.text_source}`",
        f"- Text boxes: {len(document.text_boxes)}",
        f"- Media evidence: {len(document.media_evidence)}",
        f"- Before counts: `{document.before_counts}`",
        f"- After counts: `{document.after_counts}`",
        "",
        "## Evidence By Region",
        "",
    ]
    for region in document.regions:
        items = [item for item in document.media_evidence if item.region_name == region.name]
        if not items:
            continue
        lines.append(f"### {region.name}")
        for item in items[:80]:
            lines.append(
                f"- `{item.id}` `{item.source}` `{item.decision}` bbox={item.bbox} "
                f"textOverlap={item.text_overlap_ratio:.3f} action=`{item.suggested_next_action}`"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def validate_text_masked_media_audit(document: TextMaskedMediaAuditDocument, output_dir: Path, width: int, height: int) -> None:
    if document.schema_name != "M2902TextMaskedMediaAuditDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.2 document schema")
    seen: set[str] = set()
    for item in document.media_evidence:
        if item.id in seen:
            raise ValueError(f"duplicate M29.0.2 evidence id: {item.id}")
        seen.add(item.id)
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.2 evidence bbox out of bounds: {item.id}")
        if item.asset_path is not None:
            assert_readable_relative_png(output_dir, item.asset_path)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)


def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29.0.2 PNG output missing or unreadable: {path}")


def build_meta(text_boxes: list[M29TextBox], evidence: list[MediaEvidenceItem]) -> dict[str, Any]:
    by_source: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for item in evidence:
        by_source[item.source] = by_source.get(item.source, 0) + 1
        by_action[item.suggested_next_action] = by_action.get(item.suggested_next_action, 0) + 1
    return {
        "notes": "m29_0_2_text_masked_media_audit",
        "textBoxCount": len(text_boxes),
        "evidenceCount": len(evidence),
        "evidenceBySource": dict(sorted(by_source.items())),
        "suggestedActionSummary": dict(sorted(by_action.items())),
    }


def extract_counts(document: dict[str, Any]) -> dict[str, int]:
    counts = document.get("meta", {}).get("counts")
    if isinstance(counts, dict):
        return {str(key): int(value) for key, value in counts.items()}
    result = {"text": 0, "shape": 0, "image": 0, "symbol": 0, "unknown": 0, "blocked": len(document.get("blocked", []))}
    for node in document.get("nodes", []):
        if isinstance(node, dict) and node.get("type") in result:
            result[str(node.get("type"))] += 1
    return result


def parse_bbox(value: object) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [int(item) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def parse_metrics(value: object) -> M29PrimitiveMetrics | None:
    if not isinstance(value, dict):
        return None
    mean = value.get("meanRgb", value.get("mean_rgb", [0, 0, 0]))
    if not isinstance(mean, list) or len(mean) != 3:
        return None
    return M29PrimitiveMetrics(
        color_count=int(value.get("colorCount", value.get("color_count", 0))),
        texture_score=float(value.get("textureScore", value.get("texture_score", 0.0))),
        edge_score=float(value.get("edgeScore", value.get("edge_score", 0.0))),
        fill_ratio=float(value.get("fillRatio", value.get("fill_ratio", 0.0))),
        aspect_ratio=float(value.get("aspectRatio", value.get("aspect_ratio", 0.0))),
        brightness=float(value.get("brightness", 0.0)),
        mean_rgb=(int(mean[0]), int(mean[1]), int(mean[2])),
    )


def document_to_dict(document: M29VisualPrimitiveGraphDocument | dict[str, Any]) -> dict[str, Any]:
    return document.to_dict() if hasattr(document, "to_dict") else document
