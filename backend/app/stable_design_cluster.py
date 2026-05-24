from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .region_relation_kernel import normalize_bbox


PrimaryRelation = Literal["near_equal", "contains", "contained_by", "overlaps", "disjoint"]
ClusterPattern = Literal[
    "containment_anchor_subgraph",
    "directed_row_subgraph",
    "directed_column_subgraph",
    "repeated_size_subgraph",
    "stable_local_relation_subgraph",
]
RoleHint = Literal[
    "row_like",
    "column_like",
    "repeated_item_like",
    "background_anchor_like",
    "media_text_group_like",
]

PRIMARY_RELATIONS: set[str] = {"near_equal", "contains", "contained_by", "overlaps", "disjoint"}
SECONDARY_RELATIONS: set[str] = {
    "near",
    "left_of",
    "right_of",
    "above",
    "below",
    "aligned_left",
    "aligned_center_x",
    "aligned_right",
    "aligned_top",
    "aligned_center_y",
    "aligned_bottom",
    "same_width",
    "same_height",
    "same_size",
}


@dataclass(frozen=True)
class M294Options:
    max_cluster_members: int = 12
    min_stability_score: float = 0.55
    duplicate_bbox_iou_threshold: float = 0.92
    duplicate_member_overlap_threshold: float = 0.85

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M294Result:
    report: dict[str, Any]
    output_dir: Path


def extract_m294_stable_design_cluster_report(
    *,
    task_id: str,
    m2931_report: dict[str, Any],
    output_dir: Path,
    options: M294Options | None = None,
) -> M294Result:
    options = options or M294Options()
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes, skipped_nodes = normalize_nodes(m2931_report.get("nodes", []))
    node_by_id = {node["id"]: node for node in nodes}
    edges, skipped_edges = normalize_edges(m2931_report.get("edges", []), set(node_by_id))

    motif_edges = group_edges_by_motif(edges, node_by_id)
    candidates = build_candidates(motif_edges, node_by_id)
    clusters, skipped_clusters = build_clusters(candidates, node_by_id, options)

    warnings: list[str] = []
    if skipped_nodes:
        warnings.append(f"skipped_invalid_node:{len(skipped_nodes)}")
    if skipped_edges:
        warnings.append(f"skipped_invalid_edge:{len(skipped_edges)}")

    report = {
        "schemaName": "M294StableDesignClusterReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m2931_report.get("schemaName"),
        "sourceSchemaVersion": m2931_report.get("schemaVersion"),
        "outputReport": str(output_dir / "stable_design_cluster_report.json"),
        "summary": build_summary(
            source_node_count=len(nodes),
            source_edge_count=len(edges),
            structural_edge_count=sum(len(items) for items in motif_edges.values()),
            clusters=clusters,
            skipped_nodes=skipped_nodes,
            skipped_edges=skipped_edges,
            skipped_clusters=skipped_clusters,
            warnings=warnings,
        ),
        "options": options.to_dict(),
        "clusters": clusters,
        "skippedItems": skipped_nodes + skipped_edges + skipped_clusters,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_3_relation_graph_report_only",
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "componentChanged": False,
            "roleHintsAreWeakStructuralEvidence": True,
        },
    }
    validate_report(report)
    (output_dir / "stable_design_cluster_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return M294Result(report=report, output_dir=output_dir)


def normalize_nodes(raw_nodes: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_nodes if isinstance(raw_nodes, list) else []):
        if not isinstance(item, dict):
            skipped.append({"index": index, "reason": "invalid_node", "message": "node must be an object"})
            continue
        node_id = str(item.get("id") or "").strip()
        if not node_id:
            skipped.append({"index": index, "reason": "missing_node_id", "message": "node id is required"})
            continue
        if node_id in seen_ids:
            skipped.append({"sourceObjectId": node_id, "index": index, "reason": "duplicate_node_id"})
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"nodes[{index}].bbox")
        except ValueError as error:
            skipped.append({"sourceObjectId": node_id, "index": index, "reason": "invalid_bbox", "message": str(error)})
            continue
        seen_ids.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "bbox": bbox,
                "pixelOwner": str(item.get("pixelOwner") or ""),
                "replayDecision": str(item.get("replayDecision") or ""),
                "confidence": str(item.get("confidence") or ""),
                "visualKind": str(item.get("visualKind") or ""),
            }
        )
    return sorted(nodes, key=node_sort_key), skipped


def normalize_edges(raw_edges: Any, valid_node_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    edges: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, item in enumerate(raw_edges if isinstance(raw_edges, list) else []):
        if not isinstance(item, dict):
            skipped.append({"index": index, "reason": "invalid_edge", "message": "edge must be an object"})
            continue
        edge_id = str(item.get("edgeId") or f"m2931_edge_{index + 1:04d}")
        left_id = str(item.get("leftObjectId") or "")
        right_id = str(item.get("rightObjectId") or "")
        if left_id not in valid_node_ids or right_id not in valid_node_ids or left_id == right_id:
            skipped.append({"edgeId": edge_id, "index": index, "reason": "invalid_edge_endpoint"})
            continue
        primary = str(item.get("primarySetRelation") or "")
        if primary not in PRIMARY_RELATIONS:
            skipped.append({"edgeId": edge_id, "index": index, "reason": "invalid_primary_relation"})
            continue
        secondary_raw = item.get("secondaryGeometryRelations")
        if not isinstance(secondary_raw, list):
            skipped.append({"edgeId": edge_id, "index": index, "reason": "invalid_secondary_relations"})
            continue
        secondary = [str(relation) for relation in secondary_raw if str(relation) in SECONDARY_RELATIONS]
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        edges.append(
            {
                "edgeId": edge_id,
                "leftObjectId": left_id,
                "rightObjectId": right_id,
                "primarySetRelation": primary,
                "secondaryGeometryRelations": secondary,
                "metrics": metrics,
            }
        )
    return sorted(edges, key=lambda edge: edge["edgeId"]), skipped


def group_edges_by_motif(edges: list[dict[str, Any]], nodes: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        "containment_anchor_subgraph": [],
        "directed_row_subgraph": [],
        "directed_column_subgraph": [],
        "repeated_size_subgraph": [],
        "stable_local_relation_subgraph": [],
    }
    for edge in edges:
        pattern, _, _ = classify_edge_motif(edge, nodes)
        grouped[pattern].append(edge)
    return grouped


def build_candidates(
    motif_edges: dict[str, list[dict[str, Any]]],
    nodes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    node_ids = list(nodes)
    for pattern, edges in motif_edges.items():
        if not edges:
            continue
        for members, member_edges in connected_components(edges, node_ids):
            if len(members) < 2:
                continue
            candidates.append(
                {
                    "candidateKind": "motif_component",
                    "clusterPattern": pattern,
                    "memberNodeIds": sorted(members),
                    "edgeIds": sorted(edge["edgeId"] for edge in member_edges),
                    "_internalEdges": member_edges,
                    "reasons": [f"{pattern}_connected_component"],
                }
            )
    return candidates


def connected_components(
    edges: list[dict[str, Any]],
    node_ids: list[str],
) -> list[tuple[set[str], list[dict[str, Any]]]]:
    if len(node_ids) < 2 or not edges:
        return []
    index_by_id = {node_id: index for index, node_id in enumerate(node_ids)}
    parent = list(range(len(node_ids)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left_id: str, right_id: str) -> None:
        left_root = find(index_by_id[left_id])
        right_root = find(index_by_id[right_id])
        if left_root != right_root:
            parent[right_root] = left_root

    for edge in edges:
        union(edge["leftObjectId"], edge["rightObjectId"])

    members_by_root: dict[int, set[str]] = {}
    for node_id in node_ids:
        members_by_root.setdefault(find(index_by_id[node_id]), set()).add(node_id)

    member_edges_by_root: dict[int, list[dict[str, Any]]] = {root: [] for root in members_by_root}
    for edge in edges:
        root = find(index_by_id[edge["leftObjectId"]])
        member_edges_by_root[root].append(edge)

    return [
        (members_by_root[root], member_edges_by_root[root])
        for root in sorted(members_by_root)
        if len(members_by_root[root]) > 1
    ]


def build_clusters(
    candidates: list[dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    options: M294Options,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    ordered_candidates = sorted(
        candidates,
        key=lambda item: (
            item["clusterPattern"],
            -len(item["memberNodeIds"]),
            item["memberNodeIds"],
        ),
    )

    for index, candidate in enumerate(ordered_candidates, start=1):
        member_ids = [node_id for node_id in candidate["memberNodeIds"] if node_id in nodes]
        if len(member_ids) < 2:
            skipped.append({"candidateIndex": index, "reason": "too_few_members"})
            continue
        if len(member_ids) > options.max_cluster_members:
            skipped.append({"candidateIndex": index, "reason": "too_many_members", "memberCount": len(member_ids)})
            continue

        internal_edges = candidate.get("_internalEdges") if isinstance(candidate.get("_internalEdges"), list) else []
        internal_edges = [edge for edge in internal_edges if edge["leftObjectId"] in member_ids and edge["rightObjectId"] in member_ids]
        if not internal_edges:
            skipped.append({"candidateIndex": index, "reason": "no_internal_structural_edges", "memberNodeIds": member_ids})
            continue

        pattern = str(candidate["clusterPattern"])
        role_hint = role_hint_for_pattern(pattern)
        reasons = [str(reason) for reason in candidate.get("reasons", [])] + pattern_reasons_for_pattern(pattern)
        stability_score = stability_score_for(pattern, member_ids, nodes, internal_edges)
        repeatability_score = repeatability_score_for(member_ids, nodes, internal_edges)

        if stability_score < options.min_stability_score:
            skipped.append(
                {
                    "candidateIndex": index,
                    "reason": "low_stability_score",
                    "memberNodeIds": member_ids,
                    "stabilityScore": round(stability_score, 3),
                }
            )
            continue

        accepted.append(
            {
                "id": "",
                "bbox": bbox_union([nodes[node_id]["bbox"] for node_id in member_ids]),
                "memberNodeIds": sorted(member_ids),
                "edgeIds": sorted(edge["edgeId"] for edge in internal_edges),
                "clusterPattern": pattern,
                "roleHint": role_hint,
                "stabilityScore": round(stability_score, 3),
                "repeatabilityScore": round(repeatability_score, 3),
                "reasons": dedupe_preserve_order(reasons),
                "risks": cluster_risks(member_ids, nodes, internal_edges),
            }
        )

    accepted, dedupe_skips = dedupe_clusters(accepted, options)
    skipped.extend(dedupe_skips)
    accepted = sorted(accepted, key=cluster_sort_key)
    for index, cluster in enumerate(accepted, start=1):
        cluster["id"] = f"m294_cluster_{index:04d}"
    return accepted, skipped


def classify_edge_motif(
    edge: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
) -> tuple[ClusterPattern, RoleHint | None, list[str]]:
    left = nodes[edge["leftObjectId"]]
    right = nodes[edge["rightObjectId"]]
    primary = str(edge["primarySetRelation"])
    secondary = set(edge.get("secondaryGeometryRelations", []))

    has_row_flow = "left_of" in secondary or "right_of" in secondary
    has_column_flow = "above" in secondary or "below" in secondary
    has_repeat_signal = "same_size" in secondary or ("same_width" in secondary and "same_height" in secondary)
    has_containment = primary in {"contains", "contained_by"}
    has_near_equal = primary == "near_equal"
    has_overlap = primary == "overlaps"
    has_near = "near" in secondary

    if has_repeat_signal and has_near:
        return "repeated_size_subgraph", "repeated_item_like", ["repeated_size_or_dimension_relations"]
    if has_containment:
        return "containment_anchor_subgraph", "background_anchor_like", ["contains_or_contained_by_relations"]
    if has_row_flow and ("aligned_center_y" in secondary or "aligned_top" in secondary or "aligned_bottom" in secondary):
        return "directed_row_subgraph", "row_like", ["directed_horizontal_relation_flow"]
    if has_column_flow and ("aligned_center_x" in secondary or "aligned_left" in secondary or "aligned_right" in secondary):
        return "directed_column_subgraph", "column_like", ["directed_vertical_relation_flow"]
    if has_near_equal or has_overlap or has_near:
        if is_media_text_pair(left, right):
            return "containment_anchor_subgraph", "background_anchor_like", ["media_and_text_members_share_stable_relations"]
        return "stable_local_relation_subgraph", None, ["local_structural_relations"]
    return "stable_local_relation_subgraph", None, ["local_structural_relations"]


def is_media_text_pair(left: dict[str, Any], right: dict[str, Any]) -> bool:
    kinds = {str(left.get("visualKind") or ""), str(right.get("visualKind") or "")}
    return "media_region" in kinds and bool(kinds & {"editable_ui_text", "preserve_raster_text"})


def role_hint_for_pattern(pattern: str) -> RoleHint | None:
    return {
        "containment_anchor_subgraph": "background_anchor_like",
        "directed_row_subgraph": "row_like",
        "directed_column_subgraph": "column_like",
        "repeated_size_subgraph": "repeated_item_like",
        "stable_local_relation_subgraph": None,
    }[pattern]


def pattern_reasons_for_pattern(pattern: str) -> list[str]:
    return {
        "containment_anchor_subgraph": ["contains_or_contained_by_relations"],
        "directed_row_subgraph": ["directed_horizontal_relation_flow"],
        "directed_column_subgraph": ["directed_vertical_relation_flow"],
        "repeated_size_subgraph": ["repeated_size_or_dimension_relations"],
        "stable_local_relation_subgraph": ["local_structural_relations"],
    }[pattern]


def stability_score_for(
    pattern: str,
    member_ids: list[str],
    nodes: dict[str, dict[str, Any]],
    internal_edges: list[dict[str, Any]],
) -> float:
    possible_edge_count = max(1, len(member_ids) * (len(member_ids) - 1) // 2)
    edge_density = min(1.0, len(internal_edges) / possible_edge_count)
    confidence_score = sum(confidence_value(nodes[node_id].get("confidence")) for node_id in member_ids) / len(member_ids)
    primary_signal = sum(1 for edge in internal_edges if edge["primarySetRelation"] != "disjoint") / len(internal_edges)
    repeatability_score = repeatability_score_for(member_ids, nodes, internal_edges)

    if pattern == "repeated_size_subgraph":
        return min(1.0, 0.62 + repeatability_score * 0.22 + edge_density * 0.08 + confidence_score * 0.08)
    if pattern == "containment_anchor_subgraph":
        return min(1.0, 0.68 + primary_signal * 0.15 + confidence_score * 0.12 + edge_density * 0.05)
    if pattern == "directed_row_subgraph" or pattern == "directed_column_subgraph":
        return min(1.0, 0.58 + edge_density * 0.12 + confidence_score * 0.16 + primary_signal * 0.08)
    return min(1.0, 0.8 + confidence_score * 0.08 + primary_signal * 0.06 + edge_density * 0.06)


def repeatability_score_for(member_ids: list[str], nodes: dict[str, dict[str, Any]], internal_edges: list[dict[str, Any]]) -> float:
    if len(member_ids) < 3:
        return 0.0
    secondary_counts = count_values(relation for edge in internal_edges for relation in edge.get("secondaryGeometryRelations", []))
    owner_counts = count_values(nodes[node_id].get("pixelOwner", "") for node_id in member_ids)
    size_counts = count_values(size_signature(nodes[node_id]["bbox"]) for node_id in member_ids)
    owner_repeat = max(owner_counts.values(), default=1) / len(member_ids)
    size_repeat = max(size_counts.values(), default=1) / len(member_ids)
    repeated_edges = secondary_counts.get("same_size", 0) + min(secondary_counts.get("same_width", 0), secondary_counts.get("same_height", 0))
    repeated_edge_ratio = min(1.0, repeated_edges / max(1, len(internal_edges)))
    return min(1.0, owner_repeat * 0.35 + size_repeat * 0.35 + repeated_edge_ratio * 0.30)


def cluster_risks(member_ids: list[str], nodes: dict[str, dict[str, Any]], internal_edges: list[dict[str, Any]]) -> list[str]:
    risks: list[str] = []
    if any(nodes[node_id].get("confidence") == "low" for node_id in member_ids):
        risks.append("contains_low_confidence_member")
    if any(nodes[node_id].get("pixelOwner") == "diagnostic_only" for node_id in member_ids):
        risks.append("contains_diagnostic_member")
    if any(edge.get("primarySetRelation") == "near_equal" for edge in internal_edges):
        risks.append("near_equal_members_may_be_duplicate_evidence")
    return risks


def dedupe_clusters(clusters: list[dict[str, Any]], options: M294Options) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    ordered = sorted(
        clusters,
        key=lambda item: (
            item["clusterPattern"],
            -float(item["stabilityScore"]),
            -len(item["memberNodeIds"]),
            item["memberNodeIds"],
        ),
    )
    seen_signatures: set[tuple[str, tuple[str, ...]]] = set()
    for cluster in ordered:
        signature = (cluster["clusterPattern"], tuple(cluster["memberNodeIds"]))
        if signature in seen_signatures:
            skipped.append({"reason": "duplicate_cluster_signature", "memberNodeIds": cluster["memberNodeIds"]})
            continue
        duplicate_of = next(
            (
                accepted_cluster
                for accepted_cluster in accepted
                if accepted_cluster["clusterPattern"] == cluster["clusterPattern"]
                and bbox_iou(accepted_cluster["bbox"], cluster["bbox"]) >= options.duplicate_bbox_iou_threshold
                and member_overlap_ratio(accepted_cluster["memberNodeIds"], cluster["memberNodeIds"])
                >= options.duplicate_member_overlap_threshold
            ),
            None,
        )
        if duplicate_of is not None:
            skipped.append(
                {
                    "reason": "duplicate_cluster_overlap",
                    "memberNodeIds": cluster["memberNodeIds"],
                    "duplicateOfMemberNodeIds": duplicate_of["memberNodeIds"],
                }
            )
            continue
        seen_signatures.add(signature)
        accepted.append(cluster)
    return accepted, skipped


def build_summary(
    *,
    source_node_count: int,
    source_edge_count: int,
    structural_edge_count: int,
    clusters: list[dict[str, Any]],
    skipped_nodes: list[dict[str, Any]],
    skipped_edges: list[dict[str, Any]],
    skipped_clusters: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    pattern_counts = count_values(cluster.get("clusterPattern", "") for cluster in clusters)
    role_hint_counts = count_values(cluster.get("roleHint", "") for cluster in clusters if cluster.get("roleHint"))
    return {
        "sourceNodeCount": source_node_count,
        "sourceEdgeCount": source_edge_count,
        "structuralEdgeCount": structural_edge_count,
        "clusterCount": len(clusters),
        "skippedNodeCount": len(skipped_nodes),
        "skippedEdgeCount": len(skipped_edges),
        "skippedClusterCount": len(skipped_clusters),
        "warningCount": len(warnings),
        "clusterPatternCounts": dict(sorted(pattern_counts.items())),
        "roleHintCounts": dict(sorted(role_hint_counts.items())),
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "componentChanged": False,
    }


def validate_report(report: dict[str, Any]) -> None:
    if report.get("schemaName") != "M294StableDesignClusterReport":
        raise ValueError("invalid M29.4 schemaName")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("M29.4 summary must be an object")
    if summary.get("dslChanged") is not False:
        raise ValueError("M29.4 must not change DSL")
    if summary.get("assetChanged") is not False:
        raise ValueError("M29.4 must not change assets")
    if summary.get("createdVisibleNodeCount") != 0:
        raise ValueError("M29.4 must not create visible nodes")
    if summary.get("componentChanged") is not False:
        raise ValueError("M29.4 must not create components")
    for cluster in report.get("clusters", []):
        role_hint = cluster.get("roleHint")
        if role_hint is not None and role_hint not in {"row_like", "column_like", "repeated_item_like", "background_anchor_like", "media_text_group_like"}:
            raise ValueError(f"M29.4 roleHint is not structural: {role_hint}")


def node_sort_key(node: dict[str, Any]) -> tuple[int, int, str]:
    bbox = node["bbox"]
    return bbox[1], bbox[0], node["id"]


def cluster_sort_key(cluster: dict[str, Any]) -> tuple[int, int, int, str]:
    bbox = cluster["bbox"]
    return bbox[1], bbox[0], -len(cluster["memberNodeIds"]), str(cluster["clusterPattern"])


def count_values(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def confidence_value(value: Any) -> float:
    if value == "high":
        return 1.0
    if value == "medium":
        return 0.75
    if value == "low":
        return 0.4
    return 0.5


def size_signature(bbox: list[int]) -> str:
    width_bucket = round(bbox[2] / 8) * 8
    height_bucket = round(bbox[3] / 8) * 8
    return f"{width_bucket}x{height_bucket}"


def bbox_union(bboxes: list[list[int]]) -> list[int]:
    min_x = min(bbox[0] for bbox in bboxes)
    min_y = min(bbox[1] for bbox in bboxes)
    max_x = max(x2(bbox) for bbox in bboxes)
    max_y = max(y2(bbox) for bbox in bboxes)
    return [min_x, min_y, max_x - min_x, max_y - min_y]


def bbox_iou(left: list[int], right: list[int]) -> float:
    intersection = max(0, min(x2(left), x2(right)) - max(left[0], right[0])) * max(
        0,
        min(y2(left), y2(right)) - max(left[1], right[1]),
    )
    union = left[2] * left[3] + right[2] * right[3] - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def member_overlap_ratio(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / min(len(left_set), len(right_set))


def x2(bbox: list[int]) -> int:
    return bbox[0] + bbox[2]


def y2(bbox: list[int]) -> int:
    return bbox[1] + bbox[3]


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
