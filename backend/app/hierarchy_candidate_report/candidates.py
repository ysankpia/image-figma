from __future__ import annotations

from typing import Any

from .geometry import bbox_area, containment_ratio, oversize_ratio, padding_imbalance
from .relations import child_in_parent_ratio, edge_between, relation_supports_parent
from .types import PARENT_REPLAY_ACTIONS, VISIBLE_REPLAY_ACTIONS


def build_hierarchy_candidates(
    *,
    source_objects: list[dict[str, Any]],
    plan_items: list[dict[str, Any]],
    edge_lookup: dict[frozenset[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_by_id = {item["sourceObjectId"]: item for item in source_objects}
    plan_by_source = {item["sourceObjectId"]: item for item in plan_items}
    parents = [item for item in source_objects if is_parent_source(item, plan_by_source.get(item["sourceObjectId"]))]
    children = [item for item in plan_items if item["finalReplayAction"] in VISIBLE_REPLAY_ACTIONS]
    parent_candidates: list[dict[str, Any]] = []
    by_parent: dict[str, list[dict[str, Any]]] = {}

    for parent in parents:
        parent_plan = plan_by_source.get(parent["sourceObjectId"])
        for child in children:
            if child["sourceObjectId"] == parent["sourceObjectId"]:
                continue
            child_source = source_by_id.get(child["sourceObjectId"])
            if child_source is None:
                continue
            edge = edge_between(edge_lookup, parent["sourceObjectId"], child["sourceObjectId"])
            if edge is None or not relation_supports_parent(edge, parent_id=parent["sourceObjectId"], child_id=child["sourceObjectId"]):
                continue
            score = parent_score(parent, child, edge)
            candidate = {
                "parentSourceObjectId": parent["sourceObjectId"],
                "parentPlanItemId": parent_plan.get("planItemId") if parent_plan else None,
                "parentFinalReplayAction": parent_plan.get("finalReplayAction") if parent_plan else parent["replayDecision"],
                "parentVisualKind": parent["visualKind"],
                "parentPixelOwner": parent["pixelOwner"],
                "childSourceObjectId": child["sourceObjectId"],
                "childPlanItemId": child["planItemId"],
                "childFinalReplayAction": child["finalReplayAction"],
                "childVisualKind": child_source["visualKind"],
                "edgeId": edge["edgeId"],
                "primarySetRelation": edge["primarySetRelation"],
                "childInParentRatio": round(child_in_parent_ratio(edge, parent_id=parent["sourceObjectId"], child_id=child["sourceObjectId"]), 6),
                "score": score,
                "confidence": confidence_label(score),
                "reasons": candidate_reasons(parent, child, edge),
                "risks": candidate_risks(parent, child, edge),
                "metrics": {
                    "parentArea": bbox_area(parent["bbox"]),
                    "childArea": bbox_area(child["bbox"]),
                    "bboxContainmentRatio": round(containment_ratio(parent["bbox"], child["bbox"]), 6),
                    "oversizeRatio": round(oversize_ratio(parent["bbox"], child["bbox"]), 6),
                    "paddingImbalance": padding_imbalance(parent["bbox"], child["bbox"]),
                },
            }
            parent_candidates.append(candidate)
            by_parent.setdefault(parent["sourceObjectId"], []).append(candidate)

    containers = build_container_candidates(parents, plan_by_source, by_parent)
    return sorted(containers, key=container_sort_key), sorted(parent_candidates, key=parent_candidate_sort_key)


def is_parent_source(source: dict[str, Any], plan: dict[str, Any] | None) -> bool:
    if plan is not None:
        return plan["finalReplayAction"] in PARENT_REPLAY_ACTIONS
    return source["pixelOwner"] == "preserve_raster" and source["replayDecision"] == "image_replay"


def parent_score(parent: dict[str, Any], child: dict[str, Any], edge: dict[str, Any]) -> float:
    relation_ratio = child_in_parent_ratio(edge, parent_id=parent["sourceObjectId"], child_id=child["sourceObjectId"])
    bbox_ratio = containment_ratio(parent["bbox"], child["bbox"])
    oversize = oversize_ratio(parent["bbox"], child["bbox"])
    oversize_penalty = min(0.28, max(0.0, (oversize - 12.0) / 80.0))
    padding_penalty = padding_imbalance(parent["bbox"], child["bbox"]) * 0.12
    confidence = min(confidence_value(parent["confidence"]), confidence_value(child["confidence"]))
    role_bonus = 0.04 if parent["pixelOwner"] == "shape_geometry" else 0.03 if parent["pixelOwner"] == "preserve_raster" else 0.0
    score = relation_ratio * 0.48 + bbox_ratio * 0.24 + confidence * 0.20 + role_bonus - oversize_penalty - padding_penalty
    return round(max(0.0, min(1.0, score)), 3)


def build_container_candidates(
    parents: list[dict[str, Any]],
    plan_by_source: dict[str, dict[str, Any]],
    by_parent: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    for parent in parents:
        children = sorted(by_parent.get(parent["sourceObjectId"], []), key=lambda item: (-item["score"], item["childSourceObjectId"]))
        if not children:
            continue
        parent_plan = plan_by_source.get(parent["sourceObjectId"])
        score = round(sum(item["score"] for item in children) / len(children), 3)
        containers.append(
            {
                "id": "",
                "parentSourceObjectId": parent["sourceObjectId"],
                "parentPlanItemId": parent_plan.get("planItemId") if parent_plan else None,
                "parentFinalReplayAction": parent_plan.get("finalReplayAction") if parent_plan else parent["replayDecision"],
                "parentVisualKind": parent["visualKind"],
                "parentPixelOwner": parent["pixelOwner"],
                "bbox": parent["bbox"],
                "childSourceObjectIds": [item["childSourceObjectId"] for item in children],
                "childPlanItemIds": [item["childPlanItemId"] for item in children],
                "candidateCount": len(children),
                "score": score,
                "confidence": confidence_label(score),
                "reasons": ["contains_visible_replay_children"],
                "risks": container_risks(parent, children),
            }
        )
    containers = sorted(containers, key=container_sort_key)
    for index, item in enumerate(containers, start=1):
        item["id"] = f"m29_hierarchy_container_{index:04d}"
    return containers


def select_best_parent_candidates(parent_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_child: dict[str, list[dict[str, Any]]] = {}
    for candidate in parent_candidates:
        by_child.setdefault(candidate["childSourceObjectId"], []).append(candidate)
    selected: list[dict[str, Any]] = []
    for child_id, candidates in by_child.items():
        best = sorted(candidates, key=lambda item: (-item["score"], item["metrics"]["parentArea"], item["parentSourceObjectId"]))[0]
        selected.append({**best, "id": f"m29_hierarchy_parent_{len(selected) + 1:04d}", "selection": "best_parent_for_child"})
    return sorted(selected, key=lambda item: item["id"])


def confidence_label(score: float) -> str:
    if score >= 0.74:
        return "high"
    if score >= 0.52:
        return "medium"
    return "low"


def confidence_value(value: Any) -> float:
    if value == "high":
        return 1.0
    if value == "medium":
        return 0.75
    if value == "low":
        return 0.4
    return 0.5


def candidate_reasons(parent: dict[str, Any], child: dict[str, Any], edge: dict[str, Any]) -> list[str]:
    reasons = ["m29_relation_supports_hierarchy_candidate"]
    primary = edge["primarySetRelation"]
    if primary in {"contains", "contained_by"}:
        reasons.append("containment_relation")
    elif primary == "overlaps":
        reasons.append("high_child_overlap_with_parent")
    if parent["pixelOwner"] == "shape_geometry":
        reasons.append("shape_geometry_parent_candidate")
    if parent["pixelOwner"] == "preserve_raster":
        reasons.append("preserve_raster_media_parent_candidate")
    if child["finalReplayAction"] == "text_replay":
        reasons.append("visible_text_child")
    return reasons


def candidate_risks(parent: dict[str, Any], child: dict[str, Any], edge: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    if edge["primarySetRelation"] == "overlaps":
        risks.append("overlap_not_strict_containment")
    if parent["confidence"] == "low" or child["confidence"] == "low":
        risks.append("low_confidence_member")
    if oversize_ratio(parent["bbox"], child["bbox"]) > 60:
        risks.append("parent_may_be_page_region")
    return risks


def container_risks(parent: dict[str, Any], children: list[dict[str, Any]]) -> list[str]:
    risks: list[str] = []
    if len(children) == 1:
        risks.append("single_child_container_candidate")
    if parent["confidence"] == "low":
        risks.append("low_confidence_parent")
    if any(item["confidence"] == "low" for item in children):
        risks.append("contains_low_confidence_child")
    return risks


def container_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    bbox = item["bbox"]
    return bbox[1], bbox[0], item["parentSourceObjectId"]


def parent_candidate_sort_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return item["parentSourceObjectId"], item["childSourceObjectId"], item["edgeId"]
