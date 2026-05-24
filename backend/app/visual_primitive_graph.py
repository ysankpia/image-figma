from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from .png_tools import PngMetadata, PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata, sample_rect_edges_dominant_background
from .visual_primitive import (
    LAYER_ORDER,
    M29_BLOCKED_EVIDENCE_VERSION,
    OVERLAY_COLORS,
    M29BinaryMask,
    M29BlockedPrimitive,
    M29ConnectedComponent,
    M29DebugArtifacts,
    M29LayerHint,
    M29PrimitiveMetrics,
    M29PrimitiveNode,
    M29PrimitiveRelation,
    M29PrimitiveType,
    M29RelationType,
    M29TextBox,
    M29TextKind,
    M29TextSource,
    M29VisualPrimitiveGraphDocument,
    M29VisualPrimitiveOptions,
    bbox_area,
    bbox_clamp,
    bbox_contains,
    bbox_gap_distance,
    bbox_in_bounds,
    bbox_intersection_area,
    bbox_intersects,
    bbox_iou,
    bbox_vertical_overlap_ratio,
    bbox_x2,
    bbox_y2,
    add_internal_contrast_pixels,
    build_global_foreground_mask,
    build_image_protection_mask,
    build_remaining_foreground_mask,
    build_text_exclusion_mask,
    clamp_float,
    color_distance,
    connected_components,
    crop_pixels,
    draw_rect,
    estimate_global_background,
    fit_connected_component_geometry,
    fit_low_contrast_support_geometry,
    geometry_radius,
    is_line_like,
    is_protective_shape,
    is_rect_like,
    mask_bbox_near,
    mask_bbox_overlap_ratio,
    mask_empty,
    mask_from_bboxes,
    mask_get,
    mask_intersects_bbox,
    mask_subtract,
    mask_to_png,
    mask_union,
    measure_region,
    metrics_to_dict,
    near_white,
    pad_bbox,
    require_same_mask_size,
    rgb_to_hex,
    sample_outer_ring_mean_rgb,
    sample_region_mean_rgb,
    rect_subtype,
    shape_layer_hint,
    support_region_metrics,
    union_bbox,
    validate_mask,
)


def extract_m29_visual_primitive_graph(
    *,
    png_data: bytes,
    source_image: str,
    output_dir: Path,
    options: M29VisualPrimitiveOptions | None = None,
    text_boxes: list[M29TextBox] | None = None,
    emit_debug_artifacts: bool = True,
    emit_preview_artifacts: bool = True,
) -> M29VisualPrimitiveGraphDocument:
    options = options or M29VisualPrimitiveOptions()
    image = read_png_metadata(png_data)
    if image is None:
        raise UnsupportedPngCropError("M29 source image is not a readable PNG.")
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    texts = build_text_nodes(text_boxes or [], pixels, options)
    text_mask = build_text_exclusion_mask(pixels.width, pixels.height, text_boxes or [], options.text_padding)
    base_foreground = build_global_foreground_mask(pixels, text_mask)
    initial_components = connected_components(
        base_foreground,
        pixels,
        min_area=options.min_component_area,
        max_area_ratio=max(options.max_component_area_ratio, 0.80),
    )
    shapes = detect_shapes(initial_components, pixels, image, options)
    support_shapes = detect_low_contrast_support_regions(pixels, image, text_boxes or [], initial_components, shapes, options)
    shapes = stable_sort_nodes([*shapes, *support_shapes])
    images, unknown_images = detect_images(initial_components, pixels, text_mask, shapes, options)
    text_support_shapes = detect_text_support_background_regions(pixels, image, text_boxes or [], shapes, images, options)
    shapes = stable_sort_nodes([*shapes, *text_support_shapes])
    images = [node for node in images if not any(bbox_iou(node.bbox, shape.bbox) > 0.72 for shape in text_support_shapes)]
    image_mask = build_image_protection_mask(pixels.width, pixels.height, images, options.image_protection_padding)
    foreground = build_remaining_foreground_mask(pixels, text_mask, image_mask, shapes)
    remaining_components = connected_components(
        foreground,
        pixels,
        min_area=options.min_component_area,
        max_area_ratio=options.max_component_area_ratio,
    )
    symbols, blocked = detect_symbols(remaining_components, pixels, text_mask, image_mask, shapes, options)
    blocked.extend(blocked_inside_images([*initial_components, *remaining_components], images))

    nodes = stable_sort_nodes([*texts, *shapes, *images, *symbols, *unknown_images])
    nodes = export_node_assets(nodes, pixels, output_dir)
    relations = build_containment_relations(nodes)
    nodes = attach_relation_children(nodes, relations)
    debug = M29DebugArtifacts()
    if emit_debug_artifacts:
        debug = write_debug_overlays(
            pixels=pixels,
            output_dir=output_dir,
            text_mask=text_mask,
            initial_components=initial_components,
            shapes=shapes,
            images=images,
            image_mask=image_mask,
            foreground=foreground,
            symbols=symbols,
            nodes=nodes,
            blocked=blocked,
        )
    if emit_preview_artifacts and debug.to_dict():
        preview_path = output_dir / "preview_sheet.png"
        preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, nodes, blocked))

    document = M29VisualPrimitiveGraphDocument(
        version="0.1",
        source_image=source_image,
        image_size={"width": image.width, "height": image.height},
        nodes=nodes,
        relations=relations,
        blocked=blocked,
        debug=debug,
        warnings=[],
        meta=build_meta(nodes, blocked, options),
    )
    validate_m29_document(document, output_dir)
    (output_dir / "nodes.json").write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return document


def build_text_nodes(text_boxes: list[M29TextBox], pixels: PngPixels, options: M29VisualPrimitiveOptions) -> list[M29PrimitiveNode]:
    nodes: list[M29PrimitiveNode] = []
    for index, item in enumerate(text_boxes):
        bbox = bbox_clamp(pad_bbox(item.bbox, options.text_padding), pixels.width, pixels.height)
        if bbox is None:
            continue
        nodes.append(
            M29PrimitiveNode(
                id=f"text_{index + 1:03d}",
                type="text",
                subtype=item.kind,
                bbox=bbox,
                confidence=clamp_float(item.confidence, 0, 1),
                source=item.source,
                source_order=index,
                layer_hint="content",
                reasons=["text_box"],
                metrics=measure_region(pixels, bbox),
                text=item.text,
            )
        )
    return nodes


def detect_shapes(
    components: list[M29ConnectedComponent],
    pixels: PngPixels,
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> list[M29PrimitiveNode]:
    nodes: list[M29PrimitiveNode] = []
    for component in components:
        bbox = component.bbox
        metrics = component.metrics
        area = bbox_area(bbox)
        subtype: str | None = None
        confidence = 0.0
        reasons: list[str] = []
        geometry = fit_connected_component_geometry(component, options)
        if is_line_like(bbox, metrics, options):
            subtype = "separator"
            confidence = 0.86
            reasons = ["line_like", "low_texture"]
        elif geometry["kind"] in {"circle", "ellipse"} and geometry["confidence"] in {"high", "medium"}:
            subtype = "badge_background" if area < 3200 else "small_ellipse"
            confidence = 0.78
            reasons = ["ellipse_like", "corner_background_like", "shape_geometry_fit"]
        elif geometry["kind"] == "rect" and geometry["confidence"] in {"high", "medium"} and is_rect_like(component, options):
            subtype = rect_subtype(bbox, image)
            confidence = 0.82
            reasons = ["solid_fill", "low_texture", "rect_like", "shape_geometry_fit"]
        if subtype is None:
            continue
        style: dict[str, object] = {"fill": rgb_to_hex(metrics.mean_rgb)}
        radius = geometry_radius(geometry, bbox)
        if radius is not None and subtype not in {"separator"}:
            style["radius"] = radius
        nodes.append(
            M29PrimitiveNode(
                id=f"shape_{len(nodes) + 1:03d}",
                type="shape",
                subtype=subtype,
                bbox=bbox,
                confidence=confidence,
                source="shape_detector",
                source_order=len(nodes),
                layer_hint=shape_layer_hint(subtype),
                reasons=reasons,
                metrics=metrics,
                style=style,
                geometry=geometry,
            )
        )
    return nodes


def detect_low_contrast_support_regions(
    pixels: PngPixels,
    image: PngMetadata,
    text_boxes: list[M29TextBox],
    components: list[M29ConnectedComponent],
    shapes: list[M29PrimitiveNode],
    options: M29VisualPrimitiveOptions,
) -> list[M29PrimitiveNode]:
    if not options.low_contrast_support_enabled or not text_boxes:
        return []
    foreground_bboxes = [
        component.bbox
        for component in components
        if bbox_area(component.bbox) <= options.symbol_max_area and not is_line_like(component.bbox, component.metrics, options)
    ]
    existing_shape_bboxes = [node.bbox for node in shapes]
    candidates: list[M29PrimitiveNode] = []
    for text_box in text_boxes:
        bbox = bbox_clamp(text_box.bbox, image.width, image.height)
        if bbox is None:
            continue
        candidate = find_low_contrast_support_bbox(pixels, bbox, foreground_bboxes, image, options)
        if candidate is None:
            continue
        if any(bbox_iou(candidate, existing) > 0.82 for existing in existing_shape_bboxes):
            continue
        if any(bbox_iou(candidate, existing.bbox) > 0.82 for existing in candidates):
            continue
        metrics = support_region_metrics(pixels, candidate)
        try:
            fill = sample_rect_edges_dominant_background(
                pixels,
                candidate,
                sides={"top", "bottom", "left", "right"},
                inset=2,
                thickness=2,
                tolerance=18,
                min_fraction=0.50,
            ).mean_rgb
        except Exception:
            fill = list(metrics.mean_rgb)
        containing_evidence = low_contrast_support_evidence_bboxes(candidate, bbox, foreground_bboxes)
        reasons = ["low_contrast_support_region", "stable_local_fill", "contains_text_evidence"]
        if any(not bbox_intersects(bbox, item) for item in containing_evidence):
            reasons.append("contains_visual_evidence")
        geometry = fit_low_contrast_support_geometry(pixels, candidate, [bbox, *containing_evidence])
        radius = geometry_radius(geometry, candidate)
        style: dict[str, object] = {"fill": rgb_to_hex(tuple(fill))}
        if radius is not None:
            style["radius"] = radius
        candidates.append(
            M29PrimitiveNode(
                id=f"shape_support_{len(candidates) + 1:03d}",
                type="shape",
                subtype="low_contrast_support",
                bbox=candidate,
                confidence=0.78,
                source="low_contrast_support_detector",
                source_order=len(candidates),
                layer_hint="container",
                reasons=reasons,
                metrics=metrics,
                style=style,
                geometry=geometry,
            )
        )
    return candidates


def find_low_contrast_support_bbox(
    pixels: PngPixels,
    text_bbox: list[int],
    foreground_bboxes: list[list[int]],
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> list[int] | None:
    _, _, width, height = text_bbox
    line_evidence = low_contrast_support_line_evidence_bboxes(text_bbox, foreground_bboxes)
    evidence_union = union_bbox([text_bbox, *line_evidence])
    if not line_evidence or evidence_union is None:
        return None
    min_w = max(options.low_contrast_support_min_width, width + 24)
    min_h = max(options.low_contrast_support_min_height, height + 12)
    max_w = round(image.width * options.low_contrast_support_max_width_ratio)
    max_h = min(max(min_h, height + 44), 96)
    best: tuple[float, list[int]] | None = None
    pad_x = max(14, round(height * 0.8))
    vertical_paddings = sorted(
        {
            max(8, round(height * 0.45)),
            max(8, round((height + max(26, round(height * 1.2)) - evidence_union[3]) / 2)),
        }
    )
    union_candidates = []
    for pad_y in vertical_paddings:
        union_candidates.extend(
            [
                [evidence_union[0] - pad_x, evidence_union[1] - pad_y, evidence_union[2] + pad_x * 2, evidence_union[3] + pad_y * 2],
                [
                    evidence_union[0] - round(pad_x * 1.5),
                    evidence_union[1] - pad_y,
                    evidence_union[2] + round(pad_x * 3.0),
                    evidence_union[3] + pad_y * 2,
                ],
            ]
        )
    for raw in union_candidates:
        candidate = bbox_clamp(raw, image.width, image.height)
        if candidate is None or not bbox_contains(candidate, text_bbox):
            continue
        if candidate[2] < min_w or candidate[2] > max_w or candidate[3] < min_h or candidate[3] > max_h:
            continue
        score = score_low_contrast_support_candidate(pixels, candidate, text_bbox, foreground_bboxes, image, options)
        if score is None:
            continue
        if best is None or score > best[0] or (score == best[0] and bbox_area(candidate) < bbox_area(best[1])):
            best = (score, candidate)
    return best[1] if best is not None else None


def low_contrast_support_line_evidence_bboxes(text_bbox: list[int], foreground_bboxes: list[list[int]]) -> list[list[int]]:
    _, _, width, height = text_bbox
    max_gap = max(96, height * 16)
    max_evidence_width = max(48, round(width * 0.45), height * 2)
    max_evidence_height = max(24, round(height * 1.2))
    evidence = [
        item
        for item in foreground_bboxes
        if not bbox_intersects(item, text_bbox)
        and bbox_vertical_overlap_ratio(item, text_bbox) >= 0.25
        and bbox_gap_distance(item, text_bbox) <= max_gap
        and item[2] <= max_evidence_width
        and item[3] <= max_evidence_height
    ]
    return sorted(evidence, key=lambda item: (bbox_gap_distance(item, text_bbox), item[0], item[1], item[2], item[3]))


def score_low_contrast_support_candidate(
    pixels: PngPixels,
    candidate: list[int],
    text_bbox: list[int],
    foreground_bboxes: list[list[int]],
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> float | None:
    area_ratio = bbox_area(candidate) / max(1, image.width * image.height)
    if area_ratio <= 0 or area_ratio > options.low_contrast_support_max_area_ratio:
        return None
    if candidate[2] < options.low_contrast_support_min_width or candidate[3] < options.low_contrast_support_min_height:
        return None
    if candidate[2] > image.width * options.low_contrast_support_max_width_ratio:
        return None
    if candidate[3] > max(110, image.height * 0.08):
        return None
    fill_metrics = support_region_metrics(pixels, candidate)
    if fill_metrics.texture_score > options.low_contrast_support_max_texture:
        return None
    if fill_metrics.color_count > options.low_contrast_support_max_color_count:
        return None
    boundary_deltas = support_boundary_deltas(pixels, candidate, padding=3, thickness=3)
    if boundary_deltas is None:
        return None
    min_boundary_delta = min(boundary_deltas.values())
    edge_delta = round(sum(boundary_deltas.values()) / len(boundary_deltas))
    if min_boundary_delta < options.low_contrast_support_min_edge_delta:
        return None
    if edge_delta > options.low_contrast_support_max_edge_delta:
        return None
    evidence_count = len(low_contrast_support_evidence_bboxes(candidate, text_bbox, foreground_bboxes))
    if evidence_count == 0:
        return None
    horizontal_support = candidate[2] / max(1, candidate[3])
    if horizontal_support < 2.0:
        return None
    area_penalty = area_ratio * 20
    return round(edge_delta + evidence_count * 4 + min(horizontal_support, 10) * 0.2 - fill_metrics.texture_score * 30 - fill_metrics.color_count * 0.1 - area_penalty, 4)


def low_contrast_support_evidence_bboxes(candidate: list[int], text_bbox: list[int], foreground_bboxes: list[list[int]]) -> list[list[int]]:
    return [
        item
        for item in foreground_bboxes
        if bbox_contains(candidate, item)
        and bbox_area(item) < bbox_area(candidate) * 0.65
        and not bbox_intersects(item, text_bbox)
        and bbox_vertical_overlap_ratio(item, text_bbox) >= 0.25
    ]


def detect_text_support_background_regions(
    pixels: PngPixels,
    image: PngMetadata,
    text_boxes: list[M29TextBox],
    existing_shapes: list[M29PrimitiveNode],
    images: list[M29PrimitiveNode],
    options: M29VisualPrimitiveOptions,
) -> list[M29PrimitiveNode]:
    if not options.text_support_background_enabled or not text_boxes:
        return []
    existing_bboxes = [node.bbox for node in existing_shapes]
    candidates: list[M29PrimitiveNode] = []
    for text_box in text_boxes:
        bbox = bbox_clamp(text_box.bbox, image.width, image.height)
        if bbox is None:
            continue
        candidate = find_text_support_background_bbox(pixels, bbox, image, options)
        if candidate is None:
            continue
        if any(bbox_intersection_area(candidate, image_node.bbox) > 0 for image_node in images):
            continue
        if any(bbox_iou(candidate, existing) > 0.82 for existing in existing_bboxes):
            continue
        if any(bbox_iou(candidate, existing.bbox) > 0.82 for existing in candidates):
            continue
        metrics = support_region_metrics(pixels, candidate)
        try:
            fill = sample_rect_edges_dominant_background(
                pixels,
                candidate,
                sides={"top", "bottom", "left", "right"},
                inset=2,
                thickness=2,
                tolerance=18,
                min_fraction=0.50,
            ).mean_rgb
        except Exception:
            fill = list(metrics.mean_rgb)
        geometry = fit_low_contrast_support_geometry(pixels, candidate, [bbox])
        radius = geometry_radius(geometry, candidate)
        style: dict[str, object] = {"fill": rgb_to_hex(tuple(fill))}
        if radius is not None:
            style["radius"] = radius
        candidates.append(
            M29PrimitiveNode(
                id=f"shape_text_support_{len(candidates) + 1:03d}",
                type="shape",
                subtype="text_support_background",
                bbox=candidate,
                confidence=0.78,
                source="text_support_background_detector",
                source_order=len(candidates),
                layer_hint="container",
                reasons=["text_support_background_region", "stable_local_fill", "contains_text_evidence", "finite_outer_ring"],
                metrics=metrics,
                style=style,
                geometry=geometry,
            )
        )
    return candidates


def find_text_support_background_bbox(
    pixels: PngPixels,
    text_bbox: list[int],
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> list[int] | None:
    text_area = bbox_area(text_bbox)
    if text_area <= 0:
        return None
    _, _, width, height = text_bbox
    max_w = round(image.width * options.low_contrast_support_max_width_ratio)
    max_h = min(max(options.low_contrast_support_min_height, height + 44), 96)
    pad_x_values = sorted(
        {
            max(4, round(height * options.text_support_background_padding_x_ratio)),
            max(6, round(height * 0.85)),
            max(8, round(width * 0.20)),
            max(10, round(width * 0.30)),
            max(10, round(height * 1.20)),
        }
    )
    pad_y_values = sorted(
        {
            max(3, round(height * options.text_support_background_padding_y_ratio)),
            max(4, round(height * 0.55)),
            max(5, round(height * 0.85)),
        }
    )
    best: tuple[float, list[int]] | None = None
    for pad_x in pad_x_values:
        for pad_y in pad_y_values:
            raw = [text_bbox[0] - pad_x, text_bbox[1] - pad_y, text_bbox[2] + pad_x * 2, text_bbox[3] + pad_y * 2]
            candidate = bbox_clamp(raw, image.width, image.height)
            if candidate is None:
                continue
            score = score_text_support_background_candidate(pixels, candidate, text_bbox, image, options)
            if score is None:
                continue
            if candidate[2] > max_w or candidate[3] > max_h:
                continue
            if best is None or score > best[0] or (score == best[0] and bbox_area(candidate) < bbox_area(best[1])):
                best = (score, candidate)
    return best[1] if best is not None else None


def score_text_support_background_candidate(
    pixels: PngPixels,
    candidate: list[int],
    text_bbox: list[int],
    image: PngMetadata,
    options: M29VisualPrimitiveOptions,
) -> float | None:
    text_area = bbox_area(text_bbox)
    candidate_area = bbox_area(candidate)
    if text_area <= 0 or candidate_area <= 0:
        return None
    text_contained = bbox_intersection_area(candidate, text_bbox) / text_area
    if text_contained < 0.90:
        return None
    support_area_ratio = candidate_area / text_area
    if support_area_ratio < options.text_support_background_min_area_ratio or support_area_ratio > options.text_support_background_max_area_ratio:
        return None
    support_aspect = candidate[2] / max(1, candidate[3])
    if support_aspect < options.text_support_background_min_aspect:
        return None
    fill_metrics = support_region_metrics(pixels, candidate)
    if fill_metrics.texture_score > options.low_contrast_support_max_texture:
        return None
    if fill_metrics.color_count > options.low_contrast_support_max_color_count:
        return None
    boundary_deltas = support_boundary_deltas(pixels, candidate, padding=3, thickness=3)
    if boundary_deltas is None:
        return None
    min_boundary_delta = min(boundary_deltas.values())
    edge_delta = round(sum(boundary_deltas.values()) / len(boundary_deltas))
    if min_boundary_delta < options.low_contrast_support_min_edge_delta:
        return None
    if edge_delta > options.low_contrast_support_max_edge_delta:
        return None
    return round(
        edge_delta
        + min(support_aspect, 8) * 0.25
        + fill_metrics.fill_ratio
        - fill_metrics.texture_score * 30
        - fill_metrics.color_count * 0.1
        - support_area_ratio * 0.05,
        4,
    )


def support_edge_delta(pixels: PngPixels, bbox: list[int]) -> int:
    inner = support_region_metrics(pixels, bbox).mean_rgb
    outer = sample_outer_ring_mean_rgb(pixels, bbox, padding=3, thickness=3)
    return color_distance(inner, outer)


def support_boundary_deltas(pixels: PngPixels, bbox: list[int], *, padding: int, thickness: int) -> dict[str, int] | None:
    if bbox[0] - padding < 0 or bbox[1] - padding < 0:
        return None
    if bbox_x2(bbox) + padding > pixels.width or bbox_y2(bbox) + padding > pixels.height:
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    inner = support_region_metrics(pixels, bbox).mean_rgb
    x, y, width, height = bbox
    top = sample_region_mean_rgb(pixels, [x, y - padding, width, thickness])
    bottom = sample_region_mean_rgb(pixels, [x, y + height + padding - thickness, width, thickness])
    left = sample_region_mean_rgb(pixels, [x - padding, y, thickness, height])
    right = sample_region_mean_rgb(pixels, [x + width + padding - thickness, y, thickness, height])
    return {
        "top": color_distance(inner, top),
        "bottom": color_distance(inner, bottom),
        "left": color_distance(inner, left),
        "right": color_distance(inner, right),
    }


def detect_images(
    components: list[M29ConnectedComponent],
    pixels: PngPixels,
    text_mask: M29BinaryMask,
    shapes: list[M29PrimitiveNode],
    options: M29VisualPrimitiveOptions,
) -> tuple[list[M29PrimitiveNode], list[M29PrimitiveNode]]:
    images: list[M29PrimitiveNode] = []
    unknowns: list[M29PrimitiveNode] = []
    protective = [node for node in shapes if is_protective_shape(node)]
    for component in components:
        if any(bbox_iou(component.bbox, shape.bbox) > 0.72 for shape in shapes):
            continue
        text_overlap = mask_bbox_overlap_ratio(text_mask, component.bbox)
        shape_overlap = max((bbox_iou(component.bbox, shape.bbox) for shape in protective), default=0.0)
        candidate_confidence = score_image_candidate(component, text_overlap, shape_overlap, options)
        if candidate_confidence >= options.image_accept_threshold:
            images.append(
                M29PrimitiveNode(
                    id=f"image_{len(images) + 1:03d}",
                    type="image",
                    subtype="bitmap_candidate",
                    bbox=component.bbox,
                    confidence=candidate_confidence,
                    source="image_detector",
                    source_order=len(images),
                    layer_hint="content",
                    reasons=["high_color_count", "texture_rich", "conservative_image_accept"],
                    metrics=component.metrics,
                )
            )
        elif component.area >= options.min_image_area and component.metrics.color_count >= options.image_color_threshold:
            unknowns.append(
                M29PrimitiveNode(
                    id=f"unknown_{len(unknowns) + 1:03d}",
                    type="unknown",
                    subtype="image_like_low_confidence",
                    bbox=component.bbox,
                    confidence=round(candidate_confidence, 3),
                    source="image_detector",
                    source_order=len(unknowns),
                    layer_hint="unknown",
                    reasons=["image_confidence_below_threshold"],
                    metrics=component.metrics,
                )
            )
    return images, unknowns


def detect_symbols(
    components: list[M29ConnectedComponent],
    pixels: PngPixels,
    text_mask: M29BinaryMask,
    image_mask: M29BinaryMask,
    shapes: list[M29PrimitiveNode],
    options: M29VisualPrimitiveOptions,
) -> tuple[list[M29PrimitiveNode], list[M29BlockedPrimitive]]:
    symbols: list[M29PrimitiveNode] = []
    blocked: list[M29BlockedPrimitive] = []
    for component in components:
        context = build_blocked_context(component, text_mask=text_mask, image_mask=image_mask, shapes=shapes)
        reasons = hard_block_reasons(component, context, options)
        if reasons:
            blocked.append(M29BlockedPrimitive(f"blocked_{len(blocked) + 1:03d}", component.bbox, "symbol_detector", reasons, component.metrics, context))
            continue
        if component.metrics.color_count <= options.symbol_color_threshold or component.metrics.texture_score <= options.symbol_texture_threshold:
            symbols.append(
                M29PrimitiveNode(
                    id=f"symbol_{len(symbols) + 1:03d}",
                    type="symbol",
                    subtype="icon_candidate",
                    bbox=component.bbox,
                    confidence=score_symbol_candidate(component, options),
                    source="symbol_detector",
                    source_order=len(symbols),
                    layer_hint="overlay" if is_overlay_sized(component.bbox) else "content",
                    reasons=["small_visual", "non_text", "non_image"],
                    metrics=component.metrics,
                    mask_data=component.mask_data,
                )
            )
        else:
            blocked.append(M29BlockedPrimitive(f"blocked_{len(blocked) + 1:03d}", component.bbox, "symbol_detector", metric_block_reasons(component, options), component.metrics, context))
    return symbols, blocked


def build_blocked_context(
    component: M29ConnectedComponent,
    *,
    text_mask: M29BinaryMask,
    image_mask: M29BinaryMask,
    shapes: list[M29PrimitiveNode],
) -> dict[str, object]:
    protective_shapes = [shape for shape in shapes if is_protective_shape(shape)]
    overlaps = [(shape, bbox_iou(component.bbox, shape.bbox)) for shape in protective_shapes]
    nearest_shape = min(protective_shapes, key=lambda shape: bbox_gap_distance(component.bbox, shape.bbox), default=None)
    max_overlap_shape, max_overlap = max(overlaps, key=lambda item: item[1], default=(None, 0.0))
    return {
        "area": component.area,
        "maxEdge": max(component.bbox[2], component.bbox[3]),
        "textOverlapRatio": round(mask_bbox_overlap_ratio(text_mask, component.bbox), 4),
        "imageOverlapRatio": round(mask_bbox_overlap_ratio(image_mask, component.bbox), 4),
        "protectiveShapeOverlapRatio": round(max_overlap, 4),
        "insideImage": mask_intersects_bbox(image_mask, component.bbox),
        "nearImage": mask_bbox_near(image_mask, component.bbox, 4),
        "nearProtectiveShape": nearest_shape is not None and bbox_gap_distance(component.bbox, nearest_shape.bbox) <= 8,
        "nearestShapeId": (max_overlap_shape or nearest_shape).id if (max_overlap_shape or nearest_shape) is not None else None,
    }


def hard_block_reasons(component: M29ConnectedComponent, context: dict[str, object], options: M29VisualPrimitiveOptions) -> list[str]:
    reasons: list[str] = []
    if float(context["textOverlapRatio"]) > 0:
        reasons.append("text_overlap")
    if float(context["imageOverlapRatio"]) > 0:
        reasons.append("inside_image_primitive")
    if float(context["protectiveShapeOverlapRatio"]) > 0.70:
        reasons.append("protective_shape_overlap")
        if not is_overlay_sized(component.bbox):
            reasons.append("large_container_fragment")
    if component.area < options.symbol_min_area:
        reasons.append("symbol_area_too_small")
    if bbox_area(component.bbox) > options.symbol_max_area:
        reasons.append("symbol_area_too_large")
    if is_line_like(component.bbox, component.metrics, options):
        reasons.append("line_like")
    return reasons


def metric_block_reasons(component: M29ConnectedComponent, options: M29VisualPrimitiveOptions) -> list[str]:
    metrics = component.metrics
    reasons: list[str] = []
    if metrics.color_count > options.symbol_color_threshold:
        reasons.append("symbol_color_too_high")
    if metrics.texture_score > options.symbol_texture_threshold:
        reasons.append("symbol_texture_too_high")
    if metrics.edge_score >= 0.30:
        reasons.append("symbol_edge_too_high")
    if (
        metrics.color_count <= options.symbol_color_threshold * 3
        or metrics.texture_score <= options.symbol_texture_threshold + 0.35
        or metrics.edge_score < 0.50
    ):
        reasons.append("weak_symbol_metrics")
    return reasons or ["weak_symbol_metrics"]


def blocked_inside_images(components: list[M29ConnectedComponent], images: list[M29PrimitiveNode]) -> list[M29BlockedPrimitive]:
    blocked: list[M29BlockedPrimitive] = []
    for component in components:
        containing = next((image for image in images if bbox_contains(image.bbox, component.bbox) and bbox_iou(image.bbox, component.bbox) < 0.95), None)
        if containing is not None:
            if any(existing.bbox == component.bbox for existing in blocked):
                continue
            context = {
                "area": component.area,
                "maxEdge": max(component.bbox[2], component.bbox[3]),
                "textOverlapRatio": 0.0,
                "imageOverlapRatio": 1.0,
                "protectiveShapeOverlapRatio": 0.0,
                "insideImage": True,
                "nearImage": True,
                "nearProtectiveShape": False,
                "nearestShapeId": None,
            }
            blocked.append(M29BlockedPrimitive(f"blocked_image_internal_{len(blocked) + 1:03d}", component.bbox, "image_protection", ["inside_image_primitive", "image_internal_texture"], component.metrics, context))
    return blocked


def build_containment_relations(nodes: list[M29PrimitiveNode]) -> list[M29PrimitiveRelation]:
    relations: list[M29PrimitiveRelation] = []
    containers = [node for node in nodes if node.type == "shape" and node.layer_hint in {"background", "container"}]
    children = [node for node in nodes if node.type in {"text", "image", "symbol"}]
    for child in children:
        parents = [container for container in containers if bbox_contains(container.bbox, child.bbox) and container.id != child.id]
        if not parents:
            continue
        parent = min(parents, key=lambda item: bbox_area(item.bbox))
        relations.append(M29PrimitiveRelation(parent.id, child.id, "contains", 0.72, ["bbox_contains"]))
    return relations


def attach_relation_children(nodes: list[M29PrimitiveNode], relations: list[M29PrimitiveRelation]) -> list[M29PrimitiveNode]:
    by_id = {node.id: node for node in nodes}
    children: dict[str, list[str]] = {}
    parent: dict[str, str] = {}
    for relation in relations:
        if relation.type == "contains":
            children.setdefault(relation.parent_id, []).append(relation.child_id)
            parent[relation.child_id] = relation.parent_id
    return [replace(node, parent_id=parent.get(node.id), child_ids=sorted(children.get(node.id, []))) for node in nodes]


def stable_sort_nodes(nodes: list[M29PrimitiveNode]) -> list[M29PrimitiveNode]:
    sorted_nodes = sorted(nodes, key=lambda item: (LAYER_ORDER[item.layer_hint], item.bbox[1], item.bbox[0], bbox_area(item.bbox)))
    return [replace(node, source_order=index) for index, node in enumerate(sorted_nodes)]


def export_node_assets(nodes: list[M29PrimitiveNode], pixels: PngPixels, output_dir: Path) -> list[M29PrimitiveNode]:
    image_dir = output_dir / "assets" / "images"
    symbol_dir = output_dir / "assets" / "symbols"
    image_dir.mkdir(parents=True, exist_ok=True)
    symbol_dir.mkdir(parents=True, exist_ok=True)
    image_count = 0
    symbol_count = 0
    exported: list[M29PrimitiveNode] = []
    for node in nodes:
        if node.type == "image":
            image_count += 1
            path = image_dir / f"image_{image_count:03d}.png"
            path.write_bytes(crop_pixels(pixels, node.bbox))
            exported.append(replace(node, asset_path=str(path.relative_to(output_dir))))
        elif node.type == "symbol":
            symbol_count += 1
            path = symbol_dir / f"symbol_{symbol_count:03d}.png"
            if node.mask_data is not None:
                from .png_tools import crop_mask_pixels_to_rgba_png, PngRegion
                x, y, w, h = node.bbox
                region = PngRegion("symbol", x, y, w, h)
                try:
                    path.write_bytes(crop_mask_pixels_to_rgba_png(pixels, node.mask_data, region))
                except Exception:
                    path.write_bytes(crop_pixels(pixels, node.bbox))
            else:
                path.write_bytes(crop_pixels(pixels, node.bbox))
            exported.append(replace(node, asset_path=str(path.relative_to(output_dir))))
        else:
            exported.append(node)
    return exported


def write_debug_overlays(
    *,
    pixels: PngPixels,
    output_dir: Path,
    text_mask: M29BinaryMask,
    initial_components: list[M29ConnectedComponent],
    shapes: list[M29PrimitiveNode],
    images: list[M29PrimitiveNode],
    image_mask: M29BinaryMask,
    foreground: M29BinaryMask,
    symbols: list[M29PrimitiveNode],
    nodes: list[M29PrimitiveNode],
    blocked: list[M29BlockedPrimitive],
) -> M29DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "text_exclusion": overlay_dir / "01_text_exclusion.png",
        "initial_components": overlay_dir / "02_initial_components.png",
        "shapes": overlay_dir / "03_shapes.png",
        "images": overlay_dir / "04_images.png",
        "image_protection": overlay_dir / "05_image_protection.png",
        "foreground_mask": overlay_dir / "06_foreground_mask.png",
        "symbols": overlay_dir / "07_symbols.png",
        "final_nodes": overlay_dir / "08_final_nodes.png",
    }
    paths["text_exclusion"].write_bytes(mask_to_png(text_mask))
    paths["initial_components"].write_bytes(overlay_components(pixels, initial_components))
    paths["shapes"].write_bytes(overlay_nodes(pixels, shapes, []))
    paths["images"].write_bytes(overlay_nodes(pixels, images, []))
    paths["image_protection"].write_bytes(mask_to_png(image_mask))
    paths["foreground_mask"].write_bytes(mask_to_png(foreground))
    paths["symbols"].write_bytes(overlay_nodes(pixels, symbols, blocked))
    paths["final_nodes"].write_bytes(overlay_nodes(pixels, nodes, blocked))
    return M29DebugArtifacts(**{key: str(path.relative_to(output_dir)) for key, path in paths.items()})


def overlay_components(pixels: PngPixels, components: list[M29ConnectedComponent]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for component in components:
        draw_rect(rows, pixels.width, pixels.height, component.bbox, (238, 190, 40), 1)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_nodes(pixels: PngPixels, nodes: list[M29PrimitiveNode], blocked: list[M29BlockedPrimitive]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in blocked:
        color = OVERLAY_COLORS["protected"] if "inside_image_primitive" in item.reasons else OVERLAY_COLORS["blocked"]
        draw_rect(rows, pixels.width, pixels.height, item.bbox, color, 1)
    for node in nodes:
        draw_rect(rows, pixels.width, pixels.height, node.bbox, OVERLAY_COLORS[node.type], 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def build_preview_sheet(
    pixels: PngPixels,
    output_dir: Path,
    debug: M29DebugArtifacts,
    nodes: list[M29PrimitiveNode] | None = None,
    blocked: list[M29BlockedPrimitive] | None = None,
) -> bytes:
    final_overlay = decode_png_pixels((output_dir / (debug.final_nodes or "overlays/08_final_nodes.png")).read_bytes())
    image_previews = crop_previews(output_dir / "assets" / "images", 160)
    symbol_previews = crop_previews(output_dir / "assets" / "symbols", 96)
    unknown_previews = bbox_previews(pixels, [node.bbox for node in nodes or [] if node.type == "unknown"], 96)
    blocked_previews = bbox_previews(pixels, [item.bbox for item in blocked or []], 72)
    preview_sections = [section for section in [image_previews, symbol_previews, unknown_previews, blocked_previews] if section]
    sheet_width = 1400
    margin = 24
    gap = 18
    source_scale = min(0.55, (sheet_width - margin * 2 - gap) / max(1, pixels.width * 2))
    source_w = max(1, round(pixels.width * source_scale))
    source_h = max(1, round(pixels.height * source_scale))
    sheet_height = source_h + sum(grid_height(section, sheet_width, margin, gap) for section in preview_sections) + margin * (3 + len(preview_sections))
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    y = margin
    paste_scaled(canvas, sheet_width, pixels, margin, y, source_w, source_h)
    paste_scaled(canvas, sheet_width, final_overlay, margin + source_w + gap, y, source_w, source_h)
    y += source_h + margin
    for section in preview_sections:
        y = paste_grid(canvas, sheet_width, section, margin, y, gap) + margin
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])


def crop_previews(path: Path, max_edge: int) -> list[tuple[PngPixels, int, int]]:
    previews: list[tuple[PngPixels, int, int]] = []
    if not path.exists():
        return previews
    for item in sorted(path.glob("*.png")):
        try:
            pixels = decode_png_pixels(item.read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, pixels.width, pixels.height))
        previews.append((pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews


def bbox_previews(pixels: PngPixels, bboxes: list[list[int]], max_edge: int) -> list[tuple[PngPixels, int, int]]:
    previews: list[tuple[PngPixels, int, int]] = []
    for bbox in sorted(bboxes, key=lambda item: (item[1], item[0], bbox_area(item))):
        clamped = bbox_clamp(bbox, pixels.width, pixels.height)
        if clamped is None:
            continue
        x, y, width, height = clamped
        rows = [pixels.rows[row_index][x * 3 : (x + width) * 3] for row_index in range(y, y + height)]
        preview = PngPixels(width=width, height=height, rows=rows)
        scale = min(1.0, max_edge / max(1, width, height))
        previews.append((preview, max(1, round(width * scale)), max(1, round(height * scale))))
    return previews


def grid_height(previews: list[tuple[PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 70
    x = margin
    row_h = 0
    total = 0
    for _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h


def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[PngPixels, int, int]], margin: int, y: int, gap: int) -> int:
    if not previews:
        fill_rect(canvas, sheet_width, y, margin, sheet_width - margin * 2, 48, (232, 232, 232))
        return y + 48
    x = margin
    row_h = 0
    for preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, y - 3, x - 3, width + 6, height + 6, (232, 232, 232))
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


def fill_rect(canvas: list[bytearray], sheet_width: int, y: int, x: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            row[column * 3 : column * 3 + 3] = color_bytes


def validate_m29_document(document: M29VisualPrimitiveGraphDocument, output_dir: Path) -> None:
    if document.version != "0.1":
        raise ValueError("M29 document version must be 0.1")
    width = int(document.image_size.get("width", 0))
    height = int(document.image_size.get("height", 0))
    seen: set[str] = set()
    orders: set[int] = set()
    for node in document.nodes:
        if node.id in seen:
            raise ValueError(f"duplicate M29 node id: {node.id}")
        seen.add(node.id)
        if node.source_order in orders:
            raise ValueError(f"duplicate M29 source_order: {node.source_order}")
        orders.add(node.source_order)
        if not bbox_in_bounds(node.bbox, width, height):
            raise ValueError(f"M29 node bbox out of bounds: {node.id}")
        if node.asset_path is not None:
            assert_readable_relative_png(output_dir, node.asset_path)
        if node.mask_path is not None:
            assert_readable_relative_png(output_dir, node.mask_path)
    for relation in document.relations:
        if relation.parent_id not in seen or relation.child_id not in seen:
            raise ValueError("M29 relation references a missing node")
    for item in document.blocked:
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29 blocked bbox out of bounds: {item.id}")
        if item.metrics is None:
            raise ValueError(f"M29 blocked metrics missing: {item.id}")
        if not item.reasons:
            raise ValueError(f"M29 blocked reasons missing: {item.id}")
        if item.context is None:
            raise ValueError(f"M29 blocked context missing: {item.id}")
        validate_blocked_context(item)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)


def validate_blocked_context(item: M29BlockedPrimitive) -> None:
    context = item.context or {}
    required = {
        "area": int,
        "maxEdge": int,
        "textOverlapRatio": (int, float),
        "imageOverlapRatio": (int, float),
        "protectiveShapeOverlapRatio": (int, float),
        "insideImage": bool,
        "nearImage": bool,
        "nearProtectiveShape": bool,
    }
    for key, expected_type in required.items():
        if key not in context or not isinstance(context[key], expected_type):
            raise ValueError(f"M29 blocked context missing or invalid {key}: {item.id}")
    nearest_shape = context.get("nearestShapeId")
    if nearest_shape is not None and not isinstance(nearest_shape, str):
        raise ValueError(f"M29 blocked context nearestShapeId invalid: {item.id}")


def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29 PNG output missing or unreadable: {path}")


def build_meta(nodes: list[M29PrimitiveNode], blocked: list[M29BlockedPrimitive], options: M29VisualPrimitiveOptions) -> dict[str, Any]:
    counts = {"text": 0, "shape": 0, "image": 0, "symbol": 0, "unknown": 0, "blocked": len(blocked)}
    for node in nodes:
        counts[node.type] += 1
    reason_summary: dict[str, int] = {}
    for item in blocked:
        for reason in item.reasons:
            reason_summary[reason] = reason_summary.get(reason, 0) + 1
    return {
        "notes": "m29_visual_primitive_graph_harness",
        "blockedEvidenceVersion": M29_BLOCKED_EVIDENCE_VERSION,
        "counts": counts,
        "blockedReasonSummary": dict(sorted(reason_summary.items())),
        "options": options.to_dict(),
    }


def score_image_candidate(component: M29ConnectedComponent, text_overlap: float, shape_overlap: float, options: M29VisualPrimitiveOptions) -> float:
    if component.area < options.min_image_area or text_overlap > 0.08 or shape_overlap > 0.35:
        return 0.0
    score = 0.45
    if component.metrics.color_count >= options.image_color_threshold:
        score += 0.18
    if component.metrics.texture_score >= options.image_texture_threshold:
        score += 0.20
    if component.fill_ratio >= 0.70:
        score += 0.08
    if component.metrics.edge_score >= 0.08:
        score += 0.07
    return round(min(score, 0.98), 3)


def score_symbol_candidate(component: M29ConnectedComponent, options: M29VisualPrimitiveOptions) -> float:
    score = 0.58
    if component.area >= options.symbol_min_area:
        score += 0.08
    if component.metrics.color_count <= options.symbol_color_threshold:
        score += 0.14
    if component.metrics.texture_score <= options.symbol_texture_threshold:
        score += 0.12
    if 0.18 <= component.fill_ratio <= 1.0:
        score += 0.05
    return round(min(score, 0.96), 3)


def is_overlay_sized(bbox: list[int]) -> bool:
    return bbox_area(bbox) <= 3200 and max(bbox[2], bbox[3]) <= 80
