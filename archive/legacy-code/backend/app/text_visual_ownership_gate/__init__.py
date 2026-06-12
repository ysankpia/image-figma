from __future__ import annotations

from .artifacts import (
    build_preview_sheet,
    crop_previews,
    export_examples,
    fill_rect,
    frame_color,
    grid_height,
    overlay_decisions,
    paste_grid,
    paste_scaled,
    write_debug_artifacts,
)
from .decision import (
    build_ownership_decisions,
    decide_text_box,
    decide_visual_item,
    dedupe_strings,
    has_source_support_contract,
    lineage_is_text_owned_rejected,
    make_visual_decision,
    truncate_text,
    valid_text_boxes,
    visual_owned_decision,
)
from .overlap import intersection_area, overlap_with_text_union, overlapping_text_boxes
from .pipeline import extract_text_visual_ownership_gate
from .report import build_markdown_report, write_outputs
from .routing import build_audit, build_routing_views
from .types import (
    M2907DebugArtifacts,
    M2907Document,
    M2907Options,
    OwnershipDecision,
    OwnershipDecisionKind,
    OwnershipKind,
    OwnershipSource,
)
from .validation import assert_readable_relative_png, assert_unique, build_meta, count_by, validate_text_visual_ownership_gate_document

__all__ = [name for name in globals() if not name.startswith("_")]
