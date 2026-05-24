from __future__ import annotations


from .artifacts import (
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
from .detectors import (
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
from .relations import attach_relation_children, build_containment_relations, stable_sort_nodes
from .support import detect_low_contrast_support_regions, detect_text_support_background_regions
from .support_scoring import (
    find_low_contrast_support_bbox,
    find_text_support_background_bbox,
    low_contrast_support_evidence_bboxes,
    low_contrast_support_line_evidence_bboxes,
    score_low_contrast_support_candidate,
    score_text_support_background_candidate,
    support_boundary_deltas,
    support_edge_delta,
)
from .validation import assert_readable_relative_png, build_meta, validate_blocked_context, validate_m29_document

from .bbox import (
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
    pad_bbox,
    union_bbox,
)
from .components import (
    add_internal_contrast_pixels,
    build_global_foreground_mask,
    build_image_protection_mask,
    build_remaining_foreground_mask,
    build_text_exclusion_mask,
    connected_components,
    estimate_global_background,
    is_protective_shape,
)
from .geometry import (
    clamp_local_bbox,
    estimate_support_radius_from_occupancy,
    fit_connected_component_geometry,
    fit_low_contrast_support_geometry,
    geometry_radius,
    is_line_like,
    is_rect_like,
    local_bbox_contains,
    local_intersection_bbox,
    local_mask_edge_occupancy,
    local_mask_occupancy,
    rect_subtype,
    shape_geometry,
    shape_layer_hint,
    support_fill_occupancy,
    support_region_metrics,
)
from .mask import (
    mask_bbox_near,
    mask_bbox_overlap_ratio,
    mask_empty,
    mask_from_bboxes,
    mask_get,
    mask_intersects_bbox,
    mask_subtract,
    mask_to_png,
    mask_union,
    require_same_mask_size,
    validate_mask,
)
from .metrics import clamp_float, color_distance, measure_region, metrics_to_dict, near_white, rgb_to_hex
from .pixels import crop_pixels, draw_rect, sample_outer_ring_mean_rgb, sample_region_mean_rgb
from .types import (
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
)

__all__ = [name for name in globals() if not name.startswith("_")]
