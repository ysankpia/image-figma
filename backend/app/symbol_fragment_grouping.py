from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_primitive_graph import (
    M29PrimitiveMetrics,
    bbox_area,
    bbox_clamp,
    bbox_contains,
    bbox_gap_distance,
    bbox_in_bounds,
    bbox_intersects,
    bbox_iou,
    bbox_x2,
    bbox_y2,
    color_distance,
    crop_pixels,
    draw_rect,
    measure_region,
    metrics_to_dict,
)


M291Decision = Literal["accepted", "weak", "rejected", "uncertain"]
M291SourceKind = Literal["symbol", "blocked"]
M291GroupType = Literal["grouped_symbol", "icon_button_group", "badge_group", "uncertain_group", "rejected_group"]
M291GroupRole = Literal["foreground_symbol", "symbol_fragment", "button_background", "badge", "unknown"]

ELIGIBLE_BLOCKED_REASONS = {
    "weak_symbol_metrics",
    "symbol_color_too_high",
    "symbol_texture_too_high",
    "symbol_edge_too_high",
    "symbol_area_too_small",
}
HARD_BLOCKED_REASONS = {
    "inside_image_primitive",
    "image_internal_texture",
    "text_overlap",
    "protective_shape_overlap",
    "large_container_fragment",
    "line_like",
    "symbol_area_too_large",
}
INTERACTIVE_SHAPE_SUBTYPES = {"button_background", "badge_background", "small_ellipse", "small_rounded_rect", "icon_button_background"}
PROTECTIVE_CONTAINER_SUBTYPES = {"background", "card_background", "search_field_background", "large_container", "separator"}


@dataclass(frozen=True)
class M291Options:
    neighbor_search_radius: int = 24
    icon_cluster_max_edge: int = 96
    max_group_members: int = 5
    accepted_edge_threshold: float = 0.68
    weak_edge_threshold: float = 0.52
    accepted_group_threshold: float = 0.72
    uncertain_group_threshold: float = 0.55
    max_merged_symbol_area: int = 12000
    max_text_like_aspect_ratio: float = 3.5
    output_preview_max_thumb: int = 160

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M291FragmentCandidate:
    id: str
    source_node_id: str
    source_kind: M291SourceKind
    bbox: list[int]
    metrics: M29PrimitiveMetrics
    mean_rgb: tuple[int, int, int]
    container_id: str | None
    interactive_shape_id: str | None
    layer_hint: str
    risk_reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sourceNodeId": self.source_node_id,
            "sourceKind": self.source_kind,
            "bbox": self.bbox,
            "metrics": metrics_to_dict(self.metrics),
            "meanRgb": list(self.mean_rgb),
            "containerId": self.container_id,
            "interactiveShapeId": self.interactive_shape_id,
            "layerHint": self.layer_hint,
            "riskReasons": self.risk_reasons,
        }


@dataclass(frozen=True)
class M291FragmentEdge:
    id: str
    left_id: str
    right_id: str
    score: float
    decision: Literal["accepted", "weak", "rejected"]
    reasons: list[str]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "leftId": self.left_id,
            "rightId": self.right_id,
            "score": round(self.score, 3),
            "decision": self.decision,
            "reasons": self.reasons,
            "metrics": {key: round(value, 4) for key, value in self.metrics.items()},
        }


@dataclass(frozen=True)
class M291GroupMember:
    candidate_id: str
    source_node_id: str
    role: M291GroupRole

    def to_dict(self) -> dict[str, Any]:
        return {"candidateId": self.candidate_id, "sourceNodeId": self.source_node_id, "role": self.role}


@dataclass(frozen=True)
class M291SymbolGroup:
    id: str
    group_type: M291GroupType
    decision: Literal["accepted", "uncertain", "rejected"]
    member_ids: list[str]
    members: list[M291GroupMember]
    bbox: list[int]
    confidence: float
    reasons: list[str]
    asset_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "groupType": self.group_type,
            "decision": self.decision,
            "memberIds": self.member_ids,
            "members": [member.to_dict() for member in self.members],
            "bbox": self.bbox,
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
        }
        if self.asset_path is not None:
            data["assetPath"] = self.asset_path
        return data


@dataclass(frozen=True)
class M291AssetAuditItem:
    node_id: str
    bbox: list[int]
    risk: Literal["ok", "fragmented", "text_like", "overcropped", "isolated", "unknown"]
    score: float
    reasons: list[str]
    neighbor_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodeId": self.node_id,
            "bbox": self.bbox,
            "risk": self.risk,
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "neighborIds": self.neighbor_ids,
        }


@dataclass(frozen=True)
class M291EdgeAuditItem:
    edge_id: str
    left_id: str
    right_id: str
    decision: Literal["accepted", "weak", "rejected"]
    score: float
    reasons: list[str]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "edgeId": self.edge_id,
            "leftId": self.left_id,
            "rightId": self.right_id,
            "decision": self.decision,
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "metrics": {key: round(value, 4) for key, value in self.metrics.items()},
        }


@dataclass(frozen=True)
class M291DebugArtifacts:
    symbol_fragment_risks: str | None = None
    symbol_groups: str | None = None
    grouped_vs_original: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "symbolFragmentRisks": self.symbol_fragment_risks,
                "symbolGroups": self.symbol_groups,
                "groupedVsOriginal": self.grouped_vs_original,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class M291Document:
    schema_name: str
    schema_version: str
    source_m29_nodes_json: str
    source_image: str
    options: M291Options
    candidates: list[M291FragmentCandidate]
    edges: list[M291FragmentEdge]
    groups: list[M291SymbolGroup]
    asset_audit: list[M291AssetAuditItem]
    edge_audit: list[M291EdgeAuditItem]
    debug: M291DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceM29NodesJson": self.source_m29_nodes_json,
            "sourceImage": self.source_image,
            "options": self.options.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "edges": [edge.to_dict() for edge in self.edges],
            "groups": [group.to_dict() for group in self.groups],
            "assetAudit": [item.to_dict() for item in self.asset_audit],
            "edgeAudit": [item.to_dict() for item in self.edge_audit],
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }


def extract_m291_symbol_fragment_grouping(
    *,
    m29_document: dict[str, Any],
    m29_nodes_json_path: str,
    png_data: bytes,
    source_image: str,
    output_dir: Path,
    options: M291Options | None = None,
) -> M291Document:
    options = options or M291Options()
    require_m29_0_1_document(m29_document)
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes = [item for item in m29_document.get("nodes", []) if isinstance(item, dict)]
    blocked = [item for item in m29_document.get("blocked", []) if isinstance(item, dict)]
    m29_options = dict(m29_document.get("meta", {}).get("options", {}))
    candidates = collect_fragment_candidates(nodes, blocked, pixels, m29_options, options)
    edges = build_fragment_edges(candidates, nodes, pixels, options)
    groups = build_symbol_groups(candidates, edges, nodes, pixels, options)
    groups = add_icon_button_groups(groups, candidates, nodes, pixels, options)
    groups = export_group_assets(groups, pixels, output_dir)
    edge_audit = [M291EdgeAuditItem(edge.id, edge.left_id, edge.right_id, edge.decision, edge.score, edge.reasons, edge.metrics) for edge in edges]
    asset_audit = build_asset_audit(candidates, edges, groups, options)
    debug = write_m291_overlays(pixels, output_dir, candidates, groups, asset_audit)
    preview_path = output_dir / "preview_sheet.png"
    preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug))
    meta = build_m291_meta(candidates, edges, groups, asset_audit)
    document = M291Document(
        schema_name="M291SymbolFragmentGroupingDocument",
        schema_version="0.1",
        source_m29_nodes_json=m29_nodes_json_path,
        source_image=source_image,
        options=options,
        candidates=candidates,
        edges=edges,
        groups=groups,
        asset_audit=asset_audit,
        edge_audit=edge_audit,
        debug=debug,
        warnings=[],
        meta=meta,
    )
    validate_m291_document(document, output_dir, pixels.width, pixels.height)
    write_m291_outputs(document, output_dir)
    return document


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


def build_fragment_edges(
    candidates: list[M291FragmentCandidate],
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
    options: M291Options,
) -> list[M291FragmentEdge]:
    edges: list[M291FragmentEdge] = []
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1 :]:
            gap = bbox_gap_distance(left.bbox, right.bbox)
            same_interactive = left.interactive_shape_id is not None and left.interactive_shape_id == right.interactive_shape_id
            same_container = left.container_id is not None and left.container_id == right.container_id
            if gap > options.neighbor_search_radius and not same_interactive:
                if not same_container or gap > options.neighbor_search_radius * 2:
                    continue
            if gap > options.icon_cluster_max_edge:
                continue
            edge = score_fragment_edge(f"edge_{len(edges) + 1:04d}", left, right, nodes, pixels, options)
            edges.append(edge)
    return edges


def score_fragment_edge(
    id: str,
    left: M291FragmentCandidate,
    right: M291FragmentCandidate,
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
    options: M291Options,
) -> M291FragmentEdge:
    hard_reasons = hard_boundary_reasons(left, right, nodes, pixels, options)
    metrics = edge_metric_values(left, right, pixels, options, boundary_violation=1.0 if hard_reasons else 0.0)
    score = (
        0.30 * metrics["distanceScore"]
        + 0.20 * metrics["colorSimilarityScore"]
        + 0.15 * metrics["sizeCompatibilityScore"]
        + 0.15 * metrics["containerCompatibilityScore"]
        + 0.10 * metrics["mergedBboxScore"]
        + 0.10 * metrics["styleSimilarityScore"]
        - 0.25 * metrics["textLikePenalty"]
        - 0.40 * metrics["boundaryViolationPenalty"]
    )
    score = max(0.0, min(1.0, round(score, 4)))
    if hard_reasons:
        return M291FragmentEdge(id, left.id, right.id, score, "rejected", hard_reasons, metrics)
    if score >= options.accepted_edge_threshold:
        return M291FragmentEdge(id, left.id, right.id, score, "accepted", ["edge_score_accepted"], metrics)
    if score >= options.weak_edge_threshold:
        return M291FragmentEdge(id, left.id, right.id, score, "weak", ["edge_score_weak"], metrics)
    return M291FragmentEdge(id, left.id, right.id, score, "rejected", ["edge_score_below_threshold"], metrics)


def hard_boundary_reasons(
    left: M291FragmentCandidate,
    right: M291FragmentCandidate,
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
    options: M291Options,
) -> list[str]:
    reasons: list[str] = []
    merged = merge_bboxes([left.bbox, right.bbox])
    if left.interactive_shape_id and right.interactive_shape_id and left.interactive_shape_id != right.interactive_shape_id:
        reasons.append("different_interactive_shape")
    if left.container_id and right.container_id and left.container_id != right.container_id:
        reasons.append("different_protective_container")
    if bbox_area(merged) > options.max_merged_symbol_area:
        reasons.append("merged_bbox_too_large")
    if max(merged[2], merged[3]) > options.icon_cluster_max_edge:
        reasons.append("merged_edge_too_large")
    if intersects_node_type(merged, nodes, "text"):
        reasons.append("cross_text_node")
    if intersects_node_type(merged, nodes, "image"):
        reasons.append("cross_image_node")
    if reasons:
        return reasons
    merged_metrics = measure_region(pixels, merged)
    if merged_metrics.color_count >= 48 and merged_metrics.texture_score >= 0.24 and bbox_area(merged) >= 1200:
        reasons.append("image_like_merged_result")
    return reasons


def edge_metric_values(
    left: M291FragmentCandidate,
    right: M291FragmentCandidate,
    pixels: PngPixels,
    options: M291Options,
    *,
    boundary_violation: float,
) -> dict[str, float]:
    gap = bbox_gap_distance(left.bbox, right.bbox)
    merged = merge_bboxes([left.bbox, right.bbox])
    merged_metrics = measure_region(pixels, merged)
    area_ratio = min(bbox_area(left.bbox), bbox_area(right.bbox)) / max(1, max(bbox_area(left.bbox), bbox_area(right.bbox)))
    texture_gap = abs(left.metrics.texture_score - right.metrics.texture_score)
    edge_gap = abs(left.metrics.edge_score - right.metrics.edge_score)
    brightness_gap = abs(left.metrics.brightness - right.metrics.brightness) / 255
    aspect = merged[2] / max(1, merged[3])
    return {
        "distanceScore": max(0.0, 1.0 - gap / max(1, options.neighbor_search_radius)),
        "colorSimilarityScore": max(0.0, 1.0 - color_distance(left.mean_rgb, right.mean_rgb) / 765),
        "sizeCompatibilityScore": max(0.0, min(1.0, area_ratio)),
        "containerCompatibilityScore": container_compatibility(left, right),
        "mergedBboxScore": merged_bbox_score(merged, options),
        "styleSimilarityScore": max(0.0, 1.0 - (texture_gap + edge_gap + brightness_gap) / 3),
        "textLikePenalty": 1.0 if aspect > options.max_text_like_aspect_ratio and are_horizontally_aligned([left, right]) else 0.0,
        "boundaryViolationPenalty": boundary_violation,
        "mergedTextureScore": merged_metrics.texture_score,
    }


def build_symbol_groups(
    candidates: list[M291FragmentCandidate],
    edges: list[M291FragmentEdge],
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
    options: M291Options,
) -> list[M291SymbolGroup]:
    by_id = {candidate.id: candidate for candidate in candidates}
    parent = {candidate.id: candidate.id for candidate in candidates}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for edge in edges:
        if edge.decision == "accepted":
            union(edge.left_id, edge.right_id)

    clusters: dict[str, list[M291FragmentCandidate]] = {}
    for candidate in candidates:
        clusters.setdefault(find(candidate.id), []).append(candidate)

    groups: list[M291SymbolGroup] = []
    accepted_edges = [edge for edge in edges if edge.decision == "accepted"]
    for members in clusters.values():
        if len(members) < 2:
            continue
        group = score_symbol_group(f"group_{len(groups) + 1:03d}", members, accepted_edges, pixels, options)
        groups.append(group)
    return groups


def score_symbol_group(
    id: str,
    candidates: list[M291FragmentCandidate],
    accepted_edges: list[M291FragmentEdge],
    pixels: PngPixels,
    options: M291Options,
) -> M291SymbolGroup:
    bboxes = [candidate.bbox for candidate in candidates]
    bbox = merge_bboxes(bboxes)
    reasons: list[str] = []
    if len(candidates) > options.max_group_members:
        reasons.append("too_many_members")
    if is_text_like_sequence(candidates, bbox, options):
        reasons.append("text_like_sequence")
    merged_metrics = measure_region(pixels, bbox)
    if merged_metrics.color_count >= 48 and merged_metrics.texture_score >= 0.24 and bbox_area(bbox) >= 1200:
        reasons.append("image_like_merged_result")
    edge_scores = [
        edge.score
        for edge in accepted_edges
        if edge.left_id in {candidate.id for candidate in candidates} and edge.right_id in {candidate.id for candidate in candidates}
    ]
    mean_edge = sum(edge_scores) / max(1, len(edge_scores))
    confidence = group_confidence(candidates, bbox, mean_edge, merged_metrics, options)
    decision: Literal["accepted", "uncertain", "rejected"]
    group_type: M291GroupType
    if "text_like_sequence" in reasons or "image_like_merged_result" in reasons:
        decision = "rejected"
        group_type = "rejected_group"
        confidence = min(confidence, 0.35)
    elif len(candidates) > options.max_group_members:
        decision = "uncertain"
        group_type = "uncertain_group"
        confidence = min(confidence, 0.6)
    elif confidence >= options.accepted_group_threshold:
        decision = "accepted"
        group_type = "grouped_symbol"
        reasons.append("group_confidence_accepted")
    elif confidence >= options.uncertain_group_threshold:
        decision = "uncertain"
        group_type = "uncertain_group"
        reasons.append("group_confidence_uncertain")
    else:
        decision = "rejected"
        group_type = "rejected_group"
        reasons.append("group_confidence_rejected")
    members = [
        M291GroupMember(candidate.id, candidate.source_node_id, "foreground_symbol" if candidate.source_kind == "symbol" else "symbol_fragment")
        for candidate in candidates
    ]
    return M291SymbolGroup(
        id=id,
        group_type=group_type,
        decision=decision,
        member_ids=[candidate.id for candidate in candidates],
        members=members,
        bbox=bbox,
        confidence=round(confidence, 4),
        reasons=reasons,
    )


def add_icon_button_groups(
    groups: list[M291SymbolGroup],
    candidates: list[M291FragmentCandidate],
    nodes: list[dict[str, Any]],
    pixels: PngPixels,
    options: M291Options,
) -> list[M291SymbolGroup]:
    output = list(groups)
    accepted_groups = [group for group in groups if group.decision == "accepted"]
    used_pairs: set[tuple[str, str]] = set()
    for shape in [node for node in nodes if is_interactive_shape(node)]:
        shape_bbox = parse_bbox(shape.get("bbox"))
        if shape_bbox is None:
            continue
        foreground_groups = [group for group in accepted_groups if bbox_contains(shape_bbox, group.bbox)]
        foreground_candidates = [candidate for candidate in candidates if bbox_contains(shape_bbox, candidate.bbox)]
        for group in foreground_groups[:1]:
            key = (str(shape.get("id")), group.id)
            if key in used_pairs:
                continue
            used_pairs.add(key)
            output.append(make_icon_button_group(f"group_{len(output) + 1:03d}", shape, group.bbox, group.id, group.id, shape_bbox, pixels, options))
        if foreground_groups:
            continue
        for candidate in foreground_candidates[:1]:
            key = (str(shape.get("id")), candidate.id)
            if key in used_pairs:
                continue
            used_pairs.add(key)
            output.append(make_icon_button_group(f"group_{len(output) + 1:03d}", shape, candidate.bbox, candidate.id, candidate.source_node_id, shape_bbox, pixels, options))
    return output


def make_icon_button_group(
    id: str,
    shape: dict[str, Any],
    foreground_bbox: list[int],
    foreground_candidate_id: str,
    foreground_source_id: str,
    shape_bbox: list[int],
    pixels: PngPixels,
    options: M291Options,
) -> M291SymbolGroup:
    bbox = merge_bboxes([shape_bbox, foreground_bbox])
    confidence = min(0.92, 0.72 + 0.20 * merged_bbox_score(bbox, options))
    return M291SymbolGroup(
        id=id,
        group_type="icon_button_group",
        decision="accepted",
        member_ids=[f"background_{shape.get('id')}", foreground_candidate_id],
        members=[
            M291GroupMember(f"background_{shape.get('id')}", str(shape.get("id")), "button_background"),
            M291GroupMember(foreground_candidate_id, foreground_source_id, "foreground_symbol"),
        ],
        bbox=bbox,
        confidence=confidence,
        reasons=["interactive_shape_contains_symbol", "icon_button_group_relation"],
    )


def export_group_assets(groups: list[M291SymbolGroup], pixels: PngPixels, output_dir: Path) -> list[M291SymbolGroup]:
    group_dir = output_dir / "assets" / "symbol_groups"
    group_dir.mkdir(parents=True, exist_ok=True)
    exported: list[M291SymbolGroup] = []
    group_count = 0
    for group in groups:
        if group.decision != "accepted":
            exported.append(group)
            continue
        group_count += 1
        path = group_dir / f"symbol_group_{group_count:03d}.png"
        path.write_bytes(crop_pixels(pixels, group.bbox))
        exported.append(replace(group, asset_path=str(path.relative_to(output_dir))))
    return exported


def build_asset_audit(
    candidates: list[M291FragmentCandidate],
    edges: list[M291FragmentEdge],
    groups: list[M291SymbolGroup],
    options: M291Options,
) -> list[M291AssetAuditItem]:
    grouped_members = {member_id for group in groups if group.decision == "accepted" for member_id in group.member_ids}
    neighbors: dict[str, list[str]] = {}
    for edge in edges:
        if edge.decision in {"accepted", "weak"}:
            neighbors.setdefault(edge.left_id, []).append(edge.right_id)
            neighbors.setdefault(edge.right_id, []).append(edge.left_id)
    audit: list[M291AssetAuditItem] = []
    for candidate in candidates:
        reasons: list[str] = []
        if candidate.id in grouped_members:
            risk = "fragmented"
            score = 0.82
            reasons.append("member_of_accepted_group")
        elif candidate.id in neighbors:
            risk = "fragmented"
            score = 0.62
            reasons.append("nearby_fragment_candidate")
        elif candidate.metrics.aspect_ratio > options.max_text_like_aspect_ratio:
            risk = "text_like"
            score = 0.74
            reasons.append("wide_text_like_bbox")
        elif bbox_area(candidate.bbox) < 24:
            risk = "overcropped"
            score = 0.68
            reasons.append("very_small_bbox")
        else:
            risk = "isolated"
            score = 0.35
            reasons.append("no_group_neighbor")
        audit.append(M291AssetAuditItem(candidate.id, candidate.bbox, risk, score, reasons, sorted(neighbors.get(candidate.id, []))))
    return audit


def write_m291_outputs(document: M291Document, output_dir: Path) -> None:
    (output_dir / "group_nodes.json").write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "symbol_asset_audit.json").write_text(
        json.dumps([item.to_dict() for item in document.asset_audit], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "edge_audit.json").write_text(
        json.dumps([item.to_dict() for item in document.edge_audit], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "symbol_asset_audit.md").write_text(render_asset_audit_markdown(document.asset_audit), encoding="utf-8")


def render_asset_audit_markdown(items: list[M291AssetAuditItem]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.risk] = counts.get(item.risk, 0) + 1
    lines = ["# M29.1 Symbol Asset Audit", "", "## Summary", ""]
    for risk, count in sorted(counts.items()):
        lines.append(f"- {risk}: {count}")
    lines.extend(["", "## Highest Risk", ""])
    for item in sorted(items, key=lambda entry: entry.score, reverse=True)[:20]:
        lines.append(f"- {item.node_id} `{item.risk}` score={item.score:.3f} bbox={item.bbox} reasons={','.join(item.reasons)}")
    lines.append("")
    return "\n".join(lines)


def write_m291_overlays(
    pixels: PngPixels,
    output_dir: Path,
    candidates: list[M291FragmentCandidate],
    groups: list[M291SymbolGroup],
    asset_audit: list[M291AssetAuditItem],
) -> M291DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    risk_path = overlay_dir / "09_symbol_fragment_risks.png"
    groups_path = overlay_dir / "10_symbol_groups.png"
    compare_path = overlay_dir / "11_grouped_vs_original.png"
    risk_path.write_bytes(overlay_asset_risks(pixels, candidates, asset_audit))
    groups_path.write_bytes(overlay_groups(pixels, groups))
    compare_path.write_bytes(overlay_grouped_vs_original(pixels, candidates, groups))
    return M291DebugArtifacts(
        symbol_fragment_risks=str(risk_path.relative_to(output_dir)),
        symbol_groups=str(groups_path.relative_to(output_dir)),
        grouped_vs_original=str(compare_path.relative_to(output_dir)),
    )


def overlay_asset_risks(pixels: PngPixels, candidates: list[M291FragmentCandidate], audit: list[M291AssetAuditItem]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    risk_by_id = {item.node_id: item.risk for item in audit}
    colors = {
        "ok": (0, 180, 90),
        "fragmented": (235, 64, 52),
        "text_like": (160, 80, 220),
        "overcropped": (238, 190, 40),
        "isolated": (120, 120, 120),
        "unknown": (60, 60, 60),
    }
    for candidate in candidates:
        draw_rect(rows, pixels.width, pixels.height, candidate.bbox, colors.get(risk_by_id.get(candidate.id, "unknown"), (60, 60, 60)), 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_groups(pixels: PngPixels, groups: list[M291SymbolGroup]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {"accepted": (0, 200, 90), "uncertain": (238, 190, 40), "rejected": (235, 64, 52)}
    for group in groups:
        draw_rect(rows, pixels.width, pixels.height, group.bbox, colors[group.decision], 3 if group.decision == "accepted" else 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def overlay_grouped_vs_original(pixels: PngPixels, candidates: list[M291FragmentCandidate], groups: list[M291SymbolGroup]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for candidate in candidates:
        draw_rect(rows, pixels.width, pixels.height, candidate.bbox, (150, 150, 150), 1)
    for group in groups:
        if group.decision == "accepted":
            draw_rect(rows, pixels.width, pixels.height, group.bbox, (0, 200, 90), 3)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def build_preview_sheet(pixels: PngPixels, output_dir: Path, debug: M291DebugArtifacts) -> bytes:
    group_overlay = decode_png_pixels((output_dir / (debug.symbol_groups or "overlays/10_symbol_groups.png")).read_bytes())
    m29_output_dir = output_dir.parent
    retained_image_previews = crop_previews(m29_output_dir / "assets" / "images", 160)
    grouped_symbol_previews = crop_previews(output_dir / "assets" / "symbol_groups", 120)
    sheet_width = 1400
    margin = 24
    gap = 18
    scale = min(0.55, (sheet_width - margin * 2 - gap) / max(1, pixels.width * 2))
    source_w = max(1, round(pixels.width * scale))
    source_h = max(1, round(pixels.height * scale))
    sheet_height = (
        source_h
        + grid_height(retained_image_previews, sheet_width, margin, gap)
        + grid_height(grouped_symbol_previews, sheet_width, margin, gap)
        + margin * 5
    )
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    paste_scaled(canvas, sheet_width, pixels, margin, margin, source_w, source_h)
    paste_scaled(canvas, sheet_width, group_overlay, margin + source_w + gap, margin, source_w, source_h)
    y = margin + source_h + margin
    y = paste_grid(canvas, sheet_width, retained_image_previews, margin, y, gap) + margin
    paste_grid(canvas, sheet_width, grouped_symbol_previews, margin, y, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])


def validate_m291_document(document: M291Document, output_dir: Path, width: int, height: int) -> None:
    if document.schema_name != "M291SymbolFragmentGroupingDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.1 document schema")
    candidate_ids = {candidate.id for candidate in document.candidates}
    if len(candidate_ids) != len(document.candidates):
        raise ValueError("duplicate M29.1 candidate id")
    for candidate in document.candidates:
        if not bbox_in_bounds(candidate.bbox, width, height):
            raise ValueError(f"M29.1 candidate bbox out of bounds: {candidate.id}")
    edge_ids = {edge.id for edge in document.edges}
    if len(edge_ids) != len(document.edges):
        raise ValueError("duplicate M29.1 edge id")
    for edge in document.edges:
        if edge.left_id not in candidate_ids or edge.right_id not in candidate_ids:
            raise ValueError("M29.1 edge references missing candidate")
    group_ids = {group.id for group in document.groups}
    if len(group_ids) != len(document.groups):
        raise ValueError("duplicate M29.1 group id")
    for group in document.groups:
        if not bbox_in_bounds(group.bbox, width, height):
            raise ValueError(f"M29.1 group bbox out of bounds: {group.id}")
        if group.decision == "accepted" and group.asset_path is None:
            raise ValueError(f"M29.1 accepted group missing asset: {group.id}")
        if group.asset_path is not None:
            assert_readable_relative_png(output_dir, group.asset_path)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)


def build_m291_meta(
    candidates: list[M291FragmentCandidate],
    edges: list[M291FragmentEdge],
    groups: list[M291SymbolGroup],
    asset_audit: list[M291AssetAuditItem],
) -> dict[str, Any]:
    return {
        "notes": "m29_1_symbol_fragment_grouping_harness",
        "counts": {
            "candidates": len(candidates),
            "edges": len(edges),
            "groups": len(groups),
            "acceptedGroups": sum(1 for group in groups if group.decision == "accepted"),
            "uncertainGroups": sum(1 for group in groups if group.decision == "uncertain"),
            "rejectedGroups": sum(1 for group in groups if group.decision == "rejected"),
            "assetAudit": len(asset_audit),
        },
    }


def parse_bbox(value: object) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    return [int(item) for item in value]


def parse_metrics(value: object) -> M29PrimitiveMetrics | None:
    if not isinstance(value, dict):
        return None
    mean = value.get("meanRgb", value.get("mean_rgb", [0, 0, 0]))
    if not isinstance(mean, list) or len(mean) != 3:
        return None
    return M29PrimitiveMetrics(
        color_count=int(value.get("colorCount", value.get("color_count", 0))),
        texture_score=float(value.get("textureScore", value.get("texture_score", 0.0))),
        edge_score=float(value.get("edgeScore", value.get("edge_score", 0.0))),
        fill_ratio=float(value.get("fillRatio", value.get("fill_ratio", 0.0))),
        aspect_ratio=float(value.get("aspectRatio", value.get("aspect_ratio", 0.0))),
        brightness=float(value.get("brightness", 0.0)),
        mean_rgb=(int(mean[0]), int(mean[1]), int(mean[2])),
    )


def find_container_id(bbox: list[int], nodes: list[dict[str, Any]]) -> str | None:
    containers = [node for node in nodes if node.get("type") == "shape" and node.get("subtype") in PROTECTIVE_CONTAINER_SUBTYPES]
    containing = [node for node in containers if (shape_bbox := parse_bbox(node.get("bbox"))) is not None and bbox_contains(shape_bbox, bbox)]
    if not containing:
        return None
    return str(min(containing, key=lambda node: bbox_area(parse_bbox(node.get("bbox")) or bbox)).get("id"))


def find_interactive_shape_id(bbox: list[int], nodes: list[dict[str, Any]]) -> str | None:
    shapes = [node for node in nodes if is_interactive_shape(node)]
    containing = [node for node in shapes if (shape_bbox := parse_bbox(node.get("bbox"))) is not None and bbox_contains(shape_bbox, bbox)]
    if not containing:
        return None
    return str(min(containing, key=lambda node: bbox_area(parse_bbox(node.get("bbox")) or bbox)).get("id"))


def is_interactive_shape(node: dict[str, Any]) -> bool:
    return node.get("type") == "shape" and node.get("subtype") in INTERACTIVE_SHAPE_SUBTYPES


def has_near_symbol_or_interactive_shape(
    bbox: list[int],
    symbol_nodes: list[dict[str, Any]],
    interactive_shapes: list[dict[str, Any]],
    radius: int,
) -> bool:
    for node in [*symbol_nodes, *interactive_shapes]:
        other = parse_bbox(node.get("bbox"))
        if other is not None and bbox_gap_distance(bbox, other) <= radius:
            return True
    return False


def merge_bboxes(bboxes: list[list[int]]) -> list[int]:
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox_x2(bbox) for bbox in bboxes)
    y2 = max(bbox_y2(bbox) for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]


def intersects_node_type(bbox: list[int], nodes: list[dict[str, Any]], node_type: str) -> bool:
    for node in nodes:
        if node.get("type") != node_type:
            continue
        other = parse_bbox(node.get("bbox"))
        if other is not None and bbox_intersects(bbox, other):
            return True
    return False


def container_compatibility(left: M291FragmentCandidate, right: M291FragmentCandidate) -> float:
    if left.interactive_shape_id and left.interactive_shape_id == right.interactive_shape_id:
        return 1.0
    if left.container_id and left.container_id == right.container_id:
        return 0.8
    if left.container_id is None and right.container_id is None:
        return 0.55
    return 0.45


def merged_bbox_score(bbox: list[int], options: M291Options) -> float:
    area_score = max(0.0, 1.0 - bbox_area(bbox) / max(1, options.max_merged_symbol_area))
    edge_score = max(0.0, 1.0 - max(bbox[2], bbox[3]) / max(1, options.icon_cluster_max_edge))
    aspect = bbox[2] / max(1, bbox[3])
    aspect_score = 1.0 if 0.25 <= aspect <= 4.0 else 0.25
    return (area_score + edge_score + aspect_score) / 3


def are_horizontally_aligned(candidates: list[M291FragmentCandidate]) -> bool:
    centers = [(candidate.bbox[1] + candidate.bbox[3] / 2, candidate.bbox[3]) for candidate in candidates]
    heights = [height for _center, height in centers]
    return max(center for center, _height in centers) - min(center for center, _height in centers) <= max(3, max(heights) * 0.4)


def is_text_like_sequence(candidates: list[M291FragmentCandidate], bbox: list[int], options: M291Options) -> bool:
    if len(candidates) < 3:
        return False
    aspect = bbox[2] / max(1, bbox[3])
    if aspect <= options.max_text_like_aspect_ratio or not are_horizontally_aligned(candidates):
        return False
    ordered = sorted(candidates, key=lambda item: item.bbox[0])
    gaps = [max(0, ordered[index + 1].bbox[0] - bbox_x2(ordered[index].bbox)) for index in range(len(ordered) - 1)]
    return max(gaps) - min(gaps) <= max(4, bbox[3] * 0.5)


def group_confidence(
    candidates: list[M291FragmentCandidate],
    bbox: list[int],
    mean_edge_score: float,
    merged_metrics: M29PrimitiveMetrics,
    options: M291Options,
) -> float:
    style_values = [candidate.metrics.texture_score for candidate in candidates]
    style_consistency = 1.0 - (max(style_values) - min(style_values) if style_values else 0.0)
    container_ids = {candidate.container_id for candidate in candidates if candidate.container_id is not None}
    container_consistency = 1.0 if len(container_ids) <= 1 else 0.3
    asset_gain = 1.0 if any(candidate.source_kind == "blocked" for candidate in candidates) else 0.7
    text_penalty = 0.30 if is_text_like_sequence(candidates, bbox, options) else 0.0
    boundary_penalty = 0.20 if merged_metrics.color_count >= 48 and merged_metrics.texture_score >= 0.24 else 0.0
    confidence = (
        0.45 * mean_edge_score
        + 0.20 * merged_bbox_score(bbox, options)
        + 0.15 * max(0.0, style_consistency)
        + 0.10 * container_consistency
        + 0.10 * asset_gain
        - text_penalty
        - boundary_penalty
    )
    return max(0.0, min(1.0, confidence))


def crop_previews(path: Path, max_edge: int) -> list[tuple[PngPixels, int, int]]:
    previews: list[tuple[PngPixels, int, int]] = []
    if not path.exists():
        return previews
    for item in sorted(path.glob("*.png")):
        try:
            pixels = decode_png_pixels(item.read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, pixels.width, pixels.height))
        previews.append((pixels, max(1, round(pixels.width * scale)), max(1, round(pixels.height * scale))))
    return previews


def grid_height(previews: list[tuple[PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 60
    x = margin
    row_h = 0
    total = 0
    for _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h


def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[PngPixels, int, int]], margin: int, y: int, gap: int) -> int:
    if not previews:
        fill_rect(canvas, sheet_width, y, margin, sheet_width - margin * 2, 48, (232, 232, 232))
        return y + 48
    x = margin
    row_h = 0
    for preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, y - 3, x - 3, width + 6, height + 6, (232, 232, 232))
        paste_scaled(canvas, sheet_width, preview, x, y, width, height)
        x += width + gap
        row_h = max(row_h, height)
    return y + row_h


def paste_scaled(canvas: list[bytearray], sheet_width: int, source: PngPixels, x: int, y: int, target_width: int, target_height: int) -> None:
    for target_y in range(target_height):
        source_y = min(source.height - 1, round(target_y * source.height / target_height))
        if y + target_y < 0 or y + target_y >= len(canvas):
            continue
        source_row = source.rows[source_y]
        target_row = canvas[y + target_y]
        for target_x in range(target_width):
            source_x = min(source.width - 1, round(target_x * source.width / target_width))
            dst_x = x + target_x
            if 0 <= dst_x < sheet_width:
                target_row[dst_x * 3 : dst_x * 3 + 3] = source_row[source_x * 3 : source_x * 3 + 3]


def fill_rect(canvas: list[bytearray], sheet_width: int, y: int, x: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            row[column * 3 : column * 3 + 3] = color_bytes


def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29.1 PNG output missing or unreadable: {path}")
