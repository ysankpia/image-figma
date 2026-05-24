from __future__ import annotations

from typing import Any


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
