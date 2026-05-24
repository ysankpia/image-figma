from __future__ import annotations

from typing import Any

from ..visual_evidence_normalization import parse_metrics
from ..visual_primitive_graph import M29PrimitiveMetrics, bbox_area
from .geometry import dedupe_strings
from .types import M2905Options


def classify_visual_kind(node: dict[str, Any], bbox: list[int], metrics: M29PrimitiveMetrics | None, options: M2905Options) -> str:
    source_kind = str(node.get("sourceVisualKind") or "")
    area = bbox_area(bbox)
    max_edge = max(bbox[2], bbox[3])
    if metrics is not None and metrics.fill_ratio >= 0.70 and metrics.texture_score <= 0.16 and metrics.edge_score <= 0.20:
        if source_kind not in {"icon_candidate", "accepted_image", "media_candidate"}:
            return "shape_like"
    if source_kind == "icon_candidate" or (area <= options.max_icon_asset_area and max_edge <= options.max_icon_asset_edge and source_kind in {"other_candidate", "accepted_image", "media_candidate"}):
        return "icon_like"
    if source_kind in {"accepted_image", "media_candidate"}:
        return "image_like"
    if source_kind == "other_candidate":
        return "shape_like" if metrics is not None and metrics.color_count <= 24 else "unknown_visual"
    return "unknown_visual"

def shape_source_subtype(node: dict[str, Any], lookups: dict[str, Any]) -> str | None:
    source_id = str(node.get("sourceId") or "")
    source = lookups["m2903ById"].get(source_id) or lookups["m2903BySourceEvidenceId"].get(source_id)
    for raw in (source, node):
        if not isinstance(raw, dict):
            continue
        value = str(raw.get("sourceM29Subtype") or raw.get("sourceSubtype") or raw.get("subtype") or "")
        if value:
            return value
        for reason in raw.get("reasons", []):
            if isinstance(reason, str) and reason.startswith("sourceSubtype:"):
                return reason.split(":", 1)[1]
    return None

def shape_source_reasons(node: dict[str, Any], lookups: dict[str, Any]) -> list[str]:
    source_id = str(node.get("sourceId") or "")
    source = lookups["m2903ById"].get(source_id) or lookups["m2903BySourceEvidenceId"].get(source_id)
    reasons: list[str] = []
    for raw in (source, node):
        if not isinstance(raw, dict):
            continue
        reasons.extend(str(reason) for reason in raw.get("sourceReasons", []) if isinstance(reason, str))
        reasons.extend(str(reason) for reason in raw.get("reasons", []) if isinstance(reason, str))
    return dedupe_strings(reasons)

def parse_node_metrics(node: dict[str, Any]) -> M29PrimitiveMetrics | None:
    try:
        return parse_metrics(node.get("metrics"))
    except ValueError:
        return None
