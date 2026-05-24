from __future__ import annotations

from ..png_tools import PngMetadata, PngPixels
from .bbox import bbox_area, bbox_clamp, bbox_contains, bbox_gap_distance, bbox_iou, pad_bbox
from .components import is_protective_shape
from .geometry import fit_connected_component_geometry, geometry_radius, is_line_like, is_rect_like, rect_subtype, shape_layer_hint
from .mask import M29BinaryMask, mask_bbox_near, mask_bbox_overlap_ratio, mask_intersects_bbox
from .metrics import clamp_float, rgb_to_hex
from .pixels import measure_region
from .types import M29BlockedPrimitive, M29ConnectedComponent, M29PrimitiveNode, M29TextBox, M29VisualPrimitiveOptions


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
