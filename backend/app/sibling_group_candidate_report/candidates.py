from __future__ import annotations

from typing import Any

from .geometry import bbox_union, group_sort_key
from .types import STRUCTURAL_CLUSTER_ROLE_HINTS


def build_sibling_group_candidates(
    *,
    plan_items: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    hierarchy_edges: set[frozenset[str]],
) -> list[dict[str, Any]]:
    visible_by_source = {item["sourceObjectId"]: item for item in plan_items if item["visible"]}
    groups: list[dict[str, Any]] = []
    groups.extend(cluster_backed_groups(clusters, visible_by_source, edges, hierarchy_edges))
    groups.extend(relation_backed_groups(edges, visible_by_source, hierarchy_edges))
    groups = dedupe_groups(groups)
    groups = sorted(groups, key=group_sort_key)
    for index, group in enumerate(groups, start=1):
        group["id"] = f"m29_sibling_group_{index:04d}"
    return groups


def cluster_backed_groups(
    clusters: list[dict[str, Any]],
    visible_by_source: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    hierarchy_edges: set[frozenset[str]],
) -> list[dict[str, Any]]:
    edge_by_key = edge_lookup(edges)
    groups: list[dict[str, Any]] = []
    for cluster in clusters:
        if cluster.get("roleHint") not in STRUCTURAL_CLUSTER_ROLE_HINTS:
            continue
        members = [source_id for source_id in cluster["memberSourceObjectIds"] if source_id in visible_by_source]
        member_edges = [
            edge_by_key[key]
            for key in pair_keys(members)
            if key in edge_by_key and key not in hierarchy_edges and sibling_edge(edge_by_key[key])
        ]
        if len(members) < 2 or not member_edges:
            continue
        groups.append(build_group("m29_4_cluster", members, visible_by_source, member_edges, source_cluster=cluster))
    return groups


def relation_backed_groups(
    edges: list[dict[str, Any]],
    visible_by_source: dict[str, dict[str, Any]],
    hierarchy_edges: set[frozenset[str]],
) -> list[dict[str, Any]]:
    usable_edges = [
        edge
        for edge in edges
        if edge["leftObjectId"] in visible_by_source
        and edge["rightObjectId"] in visible_by_source
        and frozenset({edge["leftObjectId"], edge["rightObjectId"]}) not in hierarchy_edges
        and sibling_edge(edge)
    ]
    groups: list[dict[str, Any]] = []
    for members, member_edges in connected_components(usable_edges, sorted(visible_by_source)):
        if len(members) < 2:
            continue
        groups.append(build_group("relation_component", sorted(members), visible_by_source, member_edges, source_cluster=None))
    return groups


def sibling_edge(edge: dict[str, Any]) -> bool:
    if edge["primarySetRelation"] in {"near_equal", "contains", "contained_by"}:
        return False
    secondary = set(edge.get("secondaryGeometryRelations", []))
    has_flow = bool(secondary & {"left_of", "right_of", "above", "below"})
    has_alignment = bool(
        secondary
        & {
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
    )
    return has_flow and ("near" in secondary or has_alignment)


def build_group(
    source: str,
    members: list[str],
    visible_by_source: dict[str, dict[str, Any]],
    member_edges: list[dict[str, Any]],
    *,
    source_cluster: dict[str, Any] | None,
) -> dict[str, Any]:
    member_items = [visible_by_source[source_id] for source_id in sorted(members)]
    pattern = group_pattern(member_edges, source_cluster)
    score = group_score(member_items, member_edges, source_cluster)
    return {
        "id": "",
        "source": source,
        "sourceClusterId": source_cluster.get("clusterId") if source_cluster else None,
        "clusterRoleHint": source_cluster.get("roleHint") if source_cluster else None,
        "groupPattern": pattern,
        "memberSourceObjectIds": [item["sourceObjectId"] for item in member_items],
        "memberPlanItemIds": [item["planItemId"] for item in member_items],
        "memberFinalReplayActions": [item["finalReplayAction"] for item in member_items],
        "edgeIds": sorted(edge["edgeId"] for edge in member_edges),
        "bbox": bbox_union([item["bbox"] for item in member_items]),
        "score": score,
        "confidence": confidence_label(score),
        "metrics": {
            "memberCount": len(member_items),
            "edgeCount": len(member_edges),
            "relationDensity": relation_density(len(member_items), len(member_edges)),
            "alignmentScore": alignment_score(member_edges),
            "nearScore": near_score(member_edges),
            "confidenceMean": round(sum(confidence_value(item["confidence"]) for item in member_items) / len(member_items), 3),
        },
        "reasons": group_reasons(source, pattern, source_cluster),
        "risks": group_risks(member_items, member_edges),
    }


def group_pattern(edges: list[dict[str, Any]], source_cluster: dict[str, Any] | None) -> str:
    if source_cluster and source_cluster.get("roleHint") == "row_like":
        return "row_like"
    if source_cluster and source_cluster.get("roleHint") == "column_like":
        return "column_like"
    if source_cluster and source_cluster.get("roleHint") == "repeated_item_like":
        return "repeated_item_like"
    secondary = [relation for edge in edges for relation in edge.get("secondaryGeometryRelations", [])]
    row = sum(1 for relation in secondary if relation in {"left_of", "right_of", "aligned_center_y", "aligned_top", "aligned_bottom"})
    column = sum(1 for relation in secondary if relation in {"above", "below", "aligned_center_x", "aligned_left", "aligned_right"})
    repeat = sum(1 for relation in secondary if relation in {"same_width", "same_height", "same_size"})
    if repeat >= max(row, column, 1):
        return "repeated_item_like"
    if column > row:
        return "column_like"
    return "row_like"


def group_score(member_items: list[dict[str, Any]], member_edges: list[dict[str, Any]], source_cluster: dict[str, Any] | None) -> float:
    confidence = sum(confidence_value(item["confidence"]) for item in member_items) / len(member_items)
    score = relation_density(len(member_items), len(member_edges)) * 0.32
    score += alignment_score(member_edges) * 0.24
    score += near_score(member_edges) * 0.14
    score += confidence * 0.20
    if source_cluster:
        score += min(0.10, float(source_cluster.get("stabilityScore") or 0.0) * 0.10)
    return round(max(0.0, min(1.0, score)), 3)


def relation_density(member_count: int, edge_count: int) -> float:
    possible = max(1, member_count * (member_count - 1) // 2)
    return round(min(1.0, edge_count / possible), 3)


def alignment_score(edges: list[dict[str, Any]]) -> float:
    if not edges:
        return 0.0
    aligned = 0
    for edge in edges:
        secondary = set(edge.get("secondaryGeometryRelations", []))
        if secondary & {"aligned_left", "aligned_center_x", "aligned_right", "aligned_top", "aligned_center_y", "aligned_bottom", "same_width", "same_height", "same_size"}:
            aligned += 1
    return round(aligned / len(edges), 3)


def near_score(edges: list[dict[str, Any]]) -> float:
    if not edges:
        return 0.0
    return round(sum(1 for edge in edges if "near" in edge.get("secondaryGeometryRelations", [])) / len(edges), 3)


def confidence_value(value: Any) -> float:
    if value == "high":
        return 1.0
    if value == "medium":
        return 0.75
    if value == "low":
        return 0.4
    return 0.5


def confidence_label(score: float) -> str:
    if score >= 0.74:
        return "high"
    if score >= 0.52:
        return "medium"
    return "low"


def group_reasons(source: str, pattern: str, source_cluster: dict[str, Any] | None) -> list[str]:
    reasons = [f"{source}_sibling_candidate", f"{pattern}_relations"]
    if source_cluster:
        reasons.append("m29_4_cluster_supported")
    return reasons


def group_risks(member_items: list[dict[str, Any]], member_edges: list[dict[str, Any]]) -> list[str]:
    risks: list[str] = []
    if any(item["confidence"] == "low" for item in member_items):
        risks.append("contains_low_confidence_member")
    if len(member_items) == 2:
        risks.append("two_member_group_candidate")
    if any(edge["primarySetRelation"] == "overlaps" for edge in member_edges):
        risks.append("contains_overlap_relation")
    return risks


def dedupe_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_members: dict[tuple[str, ...], dict[str, Any]] = {}
    for group in groups:
        key = tuple(group["memberSourceObjectIds"])
        current = by_members.get(key)
        if current is None or group_priority(group) > group_priority(current):
            by_members[key] = group
    return list(by_members.values())


def group_priority(group: dict[str, Any]) -> tuple[int, float, int]:
    source_rank = 1 if group["source"] == "m29_4_cluster" else 0
    return source_rank, group["score"], len(group["edgeIds"])


def edge_lookup(edges: list[dict[str, Any]]) -> dict[frozenset[str], dict[str, Any]]:
    return {frozenset({edge["leftObjectId"], edge["rightObjectId"]}): edge for edge in edges}


def pair_keys(members: list[str]) -> list[frozenset[str]]:
    keys: list[frozenset[str]] = []
    for index, left in enumerate(members):
        for right in members[index + 1 :]:
            keys.append(frozenset({left, right}))
    return keys


def connected_components(edges: list[dict[str, Any]], node_ids: list[str]) -> list[tuple[set[str], list[dict[str, Any]]]]:
    if len(node_ids) < 2 or not edges:
        return []
    parent = {node_id: node_id for node_id in node_ids}

    def find(node_id: str) -> str:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for edge in edges:
        union(edge["leftObjectId"], edge["rightObjectId"])

    members_by_root: dict[str, set[str]] = {}
    edges_by_root: dict[str, list[dict[str, Any]]] = {}
    for node_id in node_ids:
        members_by_root.setdefault(find(node_id), set()).add(node_id)
    for edge in edges:
        edges_by_root.setdefault(find(edge["leftObjectId"]), []).append(edge)
    return [
        (members_by_root[root], edges_by_root.get(root, []))
        for root in sorted(members_by_root)
        if len(members_by_root[root]) > 1
    ]
