from __future__ import annotations

import json
from pathlib import Path

from .png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, read_png_metadata
from .visual_primitive import (
    M29BinaryMask,
    M29BlockedPrimitive,
    M29ConnectedComponent,
    M29DebugArtifacts,
    M29PrimitiveMetrics,
    M29PrimitiveNode,
    M29PrimitiveRelation,
    M29TextBox,
    M29VisualPrimitiveGraphDocument,
    M29VisualPrimitiveOptions,
    add_internal_contrast_pixels,
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
from .visual_primitive.artifacts import (
    bbox_previews,
    build_preview_sheet,
    crop_previews,
    export_node_assets,
    fill_rect,
    grid_height,
    overlay_components,
    overlay_nodes,
    paste_grid,
    paste_scaled,
    write_debug_overlays,
)
from .visual_primitive.detectors import (
    blocked_inside_images,
    build_blocked_context,
    build_text_nodes,
    detect_images,
    detect_shapes,
    detect_symbols,
    hard_block_reasons,
    is_overlay_sized,
    metric_block_reasons,
    score_image_candidate,
    score_symbol_candidate,
)
from .visual_primitive.relations import attach_relation_children, build_containment_relations, stable_sort_nodes
from .visual_primitive.support import (
    detect_low_contrast_support_regions,
    detect_text_support_background_regions,
)
from .visual_primitive.support_scoring import (
    find_low_contrast_support_bbox,
    find_text_support_background_bbox,
    low_contrast_support_evidence_bboxes,
    low_contrast_support_line_evidence_bboxes,
    score_low_contrast_support_candidate,
    score_text_support_background_candidate,
    support_boundary_deltas,
    support_edge_delta,
)
from .visual_primitive.validation import assert_readable_relative_png, build_meta, validate_blocked_context, validate_m29_document


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
