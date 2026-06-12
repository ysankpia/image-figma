from __future__ import annotations

from typing import Any

from .geometry import bbox_iou, bbox_union, cluster_sort_key, member_overlap_ratio
from .motifs import pattern_reasons_for_pattern, role_hint_for_pattern
from .scoring import cluster_risks, repeatability_score_for, stability_score_for
from .types import M294Options


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


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
