from __future__ import annotations

from typing import Any

from ..png_tools import PngPixels
from ..visual_primitive_graph import bbox_area, bbox_in_bounds, measure_region
from .geometry import (
    find_container_id,
    find_interactive_shape_id,
    has_near_symbol_or_interactive_shape,
    is_interactive_shape,
    parse_bbox,
    parse_metrics,
)
from .lineage import build_candidate_lineage
from .types import ELIGIBLE_BLOCKED_REASONS, HARD_BLOCKED_REASONS, M291FragmentCandidate, M291Options, M291SourceKind


def require_m29_0_1_document(document: dict[str, Any]) -> None:
    version = document.get("meta", {}).get("blockedEvidenceVersion")
    if version != "0.2":
        raise ValueError("M29.1 requires M29 meta.blockedEvidenceVersion == 0.2. Run M29.0.1 visual primitive graph first.")

def collect_fragment_candidates(
    nodes: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
    pixels: PngPixels,
    m29_options: dict[str, Any],
    options: M291Options,
) -> list[M291FragmentCandidate]:
    candidates: list[M291FragmentCandidate] = []
    for node in nodes:
        if node.get("type") != "symbol":
            continue
        candidate = candidate_from_record(
            id=f"fragment_{len(candidates) + 1:03d}",
            source_kind="symbol",
            record=node,
            nodes=nodes,
            pixels=pixels,
        )
        if candidate is not None:
            candidates.append(candidate)

    symbol_nodes = [node for node in nodes if node.get("type") == "symbol"]
    interactive_shapes = [node for node in nodes if is_interactive_shape(node)]
    for item in blocked:
        if not is_eligible_blocked(item, symbol_nodes, interactive_shapes, pixels, m29_options, options):
            continue
        candidate = candidate_from_record(
            id=f"fragment_{len(candidates) + 1:03d}",
            source_kind="blocked",
            record=item,
            nodes=nodes,
            pixels=pixels,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates

def candidate_from_record(
    *,
    id: str,
    source_kind: M291SourceKind,
    record: dict[str, Any],
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
) -> M291FragmentCandidate | None:
    bbox = parse_bbox(record.get("bbox"))
    if bbox is None or not bbox_in_bounds(bbox, pixels.width, pixels.height):
        return None
    metrics = parse_metrics(record.get("metrics")) or measure_region(pixels, bbox)
    return M291FragmentCandidate(
        id=id,
        source_node_id=str(record.get("id")),
        source_kind=source_kind,
        bbox=bbox,
        metrics=metrics,
        mean_rgb=metrics.mean_rgb,
        container_id=find_container_id(bbox, nodes),
        interactive_shape_id=find_interactive_shape_id(bbox, nodes),
        layer_hint=str(record.get("layerHint") or "unknown"),
        risk_reasons=[str(reason) for reason in record.get("reasons", [])],
        source_lineage=build_candidate_lineage(id, source_kind, str(record.get("id")), [str(reason) for reason in record.get("reasons", [])]),
    )

def is_eligible_blocked(
    item: dict[str, Any],
    symbol_nodes: list[dict[str, Any]],
    interactive_shapes: list[dict[str, Any]],
    pixels: PngPixels,
    m29_options: dict[str, Any],
    options: M291Options,
) -> bool:
    bbox = parse_bbox(item.get("bbox"))
    metrics = parse_metrics(item.get("metrics"))
    context = item.get("context")
    reasons = {str(reason) for reason in item.get("reasons", [])}
    if bbox is None or metrics is None or not isinstance(context, dict):
        return False
    if not bbox_in_bounds(bbox, pixels.width, pixels.height):
        return False
    symbol_min_area = int(m29_options.get("symbol_min_area", m29_options.get("symbolMinArea", 16)))
    symbol_max_area = int(m29_options.get("symbol_max_area", m29_options.get("symbolMaxArea", 12000)))
    if bbox_area(bbox) < symbol_min_area * 0.25 or bbox_area(bbox) > symbol_max_area:
        return False
    if max(bbox[2], bbox[3]) > options.icon_cluster_max_edge:
        return False
    if reasons & HARD_BLOCKED_REASONS:
        return False
    if not reasons & ELIGIBLE_BLOCKED_REASONS:
        return False
    return has_near_symbol_or_interactive_shape(bbox, symbol_nodes, interactive_shapes, options.neighbor_search_radius)
