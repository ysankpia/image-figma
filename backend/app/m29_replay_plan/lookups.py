from __future__ import annotations

from typing import Any


def build_edge_lookup(report: dict[str, Any]) -> dict[frozenset[str], dict[str, Any]]:
    lookup: dict[frozenset[str], dict[str, Any]] = {}
    for edge in report.get("edges", []) if isinstance(report.get("edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        left = str(edge.get("leftObjectId") or "")
        right = str(edge.get("rightObjectId") or "")
        if not left or not right or left == right:
            continue
        lookup[frozenset({left, right})] = edge
    return lookup


def build_cluster_lookup(report: dict[str, Any]) -> tuple[dict[str, list[str]], int]:
    lookup: dict[str, list[str]] = {}
    malformed = 0
    for cluster in report.get("clusters", []) if isinstance(report.get("clusters"), list) else []:
        if not isinstance(cluster, dict):
            malformed += 1
            continue
        cluster_id = str(cluster.get("id") or "")
        member_ids = cluster.get("memberNodeIds")
        if not cluster_id or not isinstance(member_ids, list):
            malformed += 1
            continue
        for member_id in member_ids:
            if isinstance(member_id, str) and member_id:
                lookup.setdefault(member_id, []).append(cluster_id)
    return {key: sorted(values) for key, values in lookup.items()}, malformed
