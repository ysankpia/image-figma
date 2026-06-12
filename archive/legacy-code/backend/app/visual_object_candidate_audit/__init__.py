from __future__ import annotations

from .artifacts import (
    bbox_center,
    build_preview_sheet,
    crop_previews_for_objects,
    draw_line,
    edge_color,
    export_object_asset,
    fill_rect,
    grid_height,
    object_color,
    object_sort_key,
    overlay_edges,
    overlay_objects,
    overlay_sets,
    paste_grid,
    paste_scaled,
    write_debug_artifacts,
)
from .candidates import (
    build_object_candidates,
    build_text_clusters,
    dedupe_objects,
    make_object,
    member_from_node,
    object_confidence,
    object_priority,
    object_reasons,
    suggested_action,
)
from .edges import (
    build_evidence_edges,
    candidate_pairs,
    duplicate_source,
    edge_kind_for,
    edge_reasons,
    is_visual_text_pair_nodes,
    object_forming_visual_side,
    score_edge,
    source_compatibility,
    text_side_allowed,
)
from .evidence import (
    build_evidence_nodes,
    build_ownership_routing,
    classify_m2903_node,
    ownership_augmented_reasons,
    ownership_augmented_risks,
)
from .geometry import (
    assert_unique,
    baseline_alignment_score,
    bbox_union,
    center_alignment_score,
    center_x,
    center_y,
    compact_union_score,
    count_by,
    dedupe_strings,
    expand_bbox,
    is_icon_like_text_noise,
    is_wide_bbox,
    out_of_reasonable_bounds,
    same_column_like,
    same_row_like,
    size_compatibility,
    truncate_text,
)
from .pipeline import extract_visual_object_candidate_audit
from .report import build_markdown_report, build_meta, write_outputs
from .sets import build_set_candidates, group_objects_by_row, regular_spacing
from .types import (
    EdgeAuditItem,
    EdgeDecision,
    EvidenceEdgeKind,
    EvidenceNodeKind,
    EvidenceSource,
    M2904DebugArtifacts,
    M2904Document,
    M2904Options,
    M2904SourceExpansionRefs,
    MemberRole,
    ObjectDecision,
    ObjectKind,
    SetDecision,
    SetKind,
    VisualObjectCandidate,
    VisualObjectEvidenceEdge,
    VisualObjectEvidenceNode,
    VisualObjectMember,
    VisualObjectSetCandidate,
)
from .validation import assert_readable_relative_png, validate_visual_object_candidate_audit_document

__all__ = [name for name in globals() if not name.startswith("_")]
