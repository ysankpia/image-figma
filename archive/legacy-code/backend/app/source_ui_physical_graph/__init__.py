from __future__ import annotations

from .artifacts import build_summary, local_background_confidence, parse_bbox, render_overlay, union_bbox
from .blocked import classify_blocked_objects, is_recoverable_blocked_foreground
from .dedupe import dedupe_objects, rename_objects
from .icons import cluster_icon_objects
from .media import detect_media_objects
from .pipeline import extract_source_ui_physical_graph
from .shapes import (
    classify_shape_objects,
    is_complex_foreground_metrics,
    is_shape_replay_safe,
    is_small_foreground_bbox,
    is_small_textured_foreground_shape,
    metric_float,
    metric_int,
)
from .text import classify_ocr_text_objects, is_media_display_text
from .types import (
    M292PixelOwner,
    M292ReplayDecision,
    M292SourceObject,
    M292SourcePhysicalOptions,
    M292VisualKind,
    clean_ids,
    make_object,
    unique_strings,
)
from .unknowns import classify_unknown_objects

__all__ = [
    "M292PixelOwner",
    "M292ReplayDecision",
    "M292SourceObject",
    "M292SourcePhysicalOptions",
    "M292VisualKind",
    "build_summary",
    "classify_blocked_objects",
    "classify_ocr_text_objects",
    "classify_shape_objects",
    "classify_unknown_objects",
    "clean_ids",
    "cluster_icon_objects",
    "dedupe_objects",
    "detect_media_objects",
    "extract_source_ui_physical_graph",
    "is_complex_foreground_metrics",
    "is_media_display_text",
    "is_recoverable_blocked_foreground",
    "is_shape_replay_safe",
    "is_small_foreground_bbox",
    "is_small_textured_foreground_shape",
    "local_background_confidence",
    "make_object",
    "metric_float",
    "metric_int",
    "parse_bbox",
    "rename_objects",
    "render_overlay",
    "union_bbox",
    "unique_strings",
]
