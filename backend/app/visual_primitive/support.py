from __future__ import annotations

from ..png_tools import PngMetadata, PngPixels, sample_rect_edges_dominant_background
from .bbox import bbox_area, bbox_clamp, bbox_intersection_area, bbox_intersects, bbox_iou
from .geometry import fit_low_contrast_support_geometry, geometry_radius, is_line_like, support_region_metrics
from .metrics import rgb_to_hex
from .support_scoring import (
    find_low_contrast_support_bbox,
    find_text_support_background_bbox,
    low_contrast_support_evidence_bboxes,
)
from .types import M29ConnectedComponent, M29PrimitiveNode, M29TextBox, M29VisualPrimitiveOptions


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
