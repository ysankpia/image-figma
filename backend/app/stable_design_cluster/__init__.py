from __future__ import annotations

from .candidates import build_candidates, connected_components
from .clusters import build_clusters, dedupe_clusters, dedupe_preserve_order
from .geometry import bbox_iou, bbox_union, cluster_sort_key, member_overlap_ratio, node_sort_key, size_signature, x2, y2
from .motifs import classify_edge_motif, group_edges_by_motif, is_media_text_pair, pattern_reasons_for_pattern, role_hint_for_pattern
from .normalization import normalize_edges, normalize_nodes
from .pipeline import extract_m294_stable_design_cluster_report
from .report import build_summary
from .scoring import cluster_risks, confidence_value, count_values, repeatability_score_for, stability_score_for
from .types import (
    ClusterPattern,
    M294Options,
    M294Result,
    PRIMARY_RELATIONS,
    PrimaryRelation,
    RoleHint,
    SECONDARY_RELATIONS,
)
from .validation import validate_report

__all__ = [
    "ClusterPattern",
    "M294Options",
    "M294Result",
    "PRIMARY_RELATIONS",
    "PrimaryRelation",
    "RoleHint",
    "SECONDARY_RELATIONS",
    "bbox_iou",
    "bbox_union",
    "build_candidates",
    "build_clusters",
    "build_summary",
    "classify_edge_motif",
    "cluster_risks",
    "cluster_sort_key",
    "confidence_value",
    "connected_components",
    "count_values",
    "dedupe_clusters",
    "dedupe_preserve_order",
    "extract_m294_stable_design_cluster_report",
    "group_edges_by_motif",
    "is_media_text_pair",
    "member_overlap_ratio",
    "node_sort_key",
    "normalize_edges",
    "normalize_nodes",
    "pattern_reasons_for_pattern",
    "repeatability_score_for",
    "role_hint_for_pattern",
    "size_signature",
    "stability_score_for",
    "validate_report",
    "x2",
    "y2",
]
