from __future__ import annotations

from .artifacts import (
    build_preview_sheet,
    crop_previews_for_evidence,
    fill_rect,
    grid_height,
    overlay_before_after,
    overlay_evidence,
    paste_grid,
    paste_scaled,
    preview_border_color,
    preview_sort_key,
    write_debug_artifacts,
)
from .evidence import (
    build_evidence_item,
    collect_media_evidence,
    dedupe_strings,
    export_evidence_asset,
    is_media_like_blocked,
    is_media_like_symbol,
    is_source_support_shape,
    next_evidence_id,
    suggested_next_action,
    support_shape_reasons,
)
from .ocr_text import text_boxes_from_ocr_document
from .pipeline import extract_text_masked_media_audit
from .regions import (
    bbox_iou_or_overlap,
    build_text_suppressed_pixels,
    default_media_regions,
    document_to_dict,
    extract_counts,
    local_background_rgb,
    parse_bbox,
    parse_metrics,
    region_for_bbox,
)
from .report import build_markdown_report, build_meta, write_outputs
from .types import (
    M2902Decision,
    M2902Source,
    MediaAuditRegion,
    MediaEvidenceItem,
    TextMaskedDebugArtifacts,
    TextMaskedMediaAuditDocument,
    TextMaskedMediaAuditOptions,
    text_box_to_dict,
)
from .validation import assert_readable_relative_png, validate_text_masked_media_audit

__all__ = [name for name in globals() if not name.startswith("_")]
