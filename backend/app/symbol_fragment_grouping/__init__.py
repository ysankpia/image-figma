from __future__ import annotations

from .artifacts import (
    bbox_previews,
    build_preview_sheet,
    crop_previews,
    fill_rect,
    grid_height,
    overlay_asset_risks,
    overlay_grouped_vs_original,
    overlay_groups,
    paste_grid,
    paste_scaled,
    render_asset_audit_markdown,
    write_m291_outputs,
    write_m291_overlays,
)
from .assets import build_asset_audit, export_group_assets
from .candidates import candidate_from_record, collect_fragment_candidates, is_eligible_blocked, require_m29_0_1_document
from .edges import build_fragment_edges, edge_metric_values, hard_boundary_reasons, score_fragment_edge
from .geometry import (
    are_horizontally_aligned,
    container_compatibility,
    find_container_id,
    find_interactive_shape_id,
    group_confidence,
    has_near_symbol_or_interactive_shape,
    intersects_node_type,
    is_interactive_shape,
    is_text_like_sequence,
    merge_bboxes,
    merged_bbox_score,
    parse_bbox,
    parse_metrics,
)
from .groups import build_symbol_groups, score_symbol_group
from .icon_button import add_icon_button_groups, make_icon_button_group
from .lineage import build_candidate_lineage, build_group_lineage, build_interactive_shape_lineage
from .pipeline import extract_m291_symbol_fragment_grouping
from .types import (
    ELIGIBLE_BLOCKED_REASONS,
    HARD_BLOCKED_REASONS,
    INTERACTIVE_SHAPE_SUBTYPES,
    PROTECTIVE_CONTAINER_SUBTYPES,
    M291AssetAuditItem,
    M291DebugArtifacts,
    M291Decision,
    M291Document,
    M291EdgeAuditItem,
    M291FragmentCandidate,
    M291FragmentEdge,
    M291GroupMember,
    M291GroupRole,
    M291GroupType,
    M291Options,
    M291SourceKind,
    M291SymbolGroup,
)
from .validation import assert_readable_relative_png, build_m291_meta, validate_m291_document

__all__ = [name for name in globals() if not name.startswith("_")]
