from __future__ import annotations

from .artifacts import (
    build_preview_sheet,
    crop_previews_for_items,
    export_visual_evidence_asset,
    fill_rect,
    grid_height,
    item_color,
    item_sort_key,
    overlay_items,
    paste_grid,
    paste_scaled,
    write_debug_artifacts,
)
from .classification import classify_evidence, confidence_from_overlap, has_source_support_contract, source_support_subtype
from .groups import build_groups
from .lineage import (
    attach_candidate_bboxes,
    bbox_key,
    build_lineage_lookup,
    lineage_is_rejected_text_like,
    lineage_survives_as_conflict,
    lookup_source_lineage,
    normalized_lineage,
    rejected_lineage,
)
from .parsing import media_candidate_confidence, next_item_id, parse_bbox, parse_metrics, parse_source
from .pipeline import extract_visual_evidence_normalization, normalize_evidence_items
from .report import build_markdown_report, build_meta, write_outputs
from .text_overlap import (
    collect_text_boxes,
    dedupe_strings,
    has_glyph_sequence_risk,
    intersection_area,
    is_single_text_like_token,
    overlapping_text_boxes,
    text_lineage_counter_evidence,
)
from .types import (
    TEXT_REJECTED_LINEAGE_ASPECT_MIN,
    TEXT_REJECTED_LINEAGE_FULL_OCR_COVERAGE_MIN,
    VisualEvidenceDebugArtifacts,
    VisualEvidenceDecision,
    VisualEvidenceDocument,
    VisualEvidenceItem,
    VisualEvidenceKind,
    VisualEvidenceOptions,
    VisualEvidenceSource,
)
from .validation import assert_readable_relative_png, validate_visual_evidence_document

__all__ = [name for name in globals() if not name.startswith("_")]
