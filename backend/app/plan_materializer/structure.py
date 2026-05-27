from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..m29_materialization_utils import next_unique_id
from .types import PlanMaterializerOptions, ReplayNode


@dataclass(frozen=True)
class StructureGroup:
    id: str
    source_candidate_id: str
    source: str
    subject_type: str
    bbox: list[int]
    member_node_ids: list[str]
    member_source_object_ids: list[str]
    score: float
    confidence: str
    recommended_model: str | None
    risks: list[str]


def materialize_controlled_structure_groups(
    *,
    dsl: dict[str, Any],
    replayed: list[ReplayNode],
    existing_ids: set[str],
    hierarchy_report: dict[str, Any] | None,
    sibling_group_report: dict[str, Any] | None,
    layout_energy_report: dict[str, Any] | None,
    auto_layout_permission_report: dict[str, Any] | None,
    options: PlanMaterializerOptions,
) -> dict[str, Any]:
    if not options.enable_controlled_structure_materialization:
        return build_structure_report([], [], ["controlled_structure_materialization_disabled"])

    children = dsl.get("root", {}).get("children")
    if not isinstance(children, list):
        return build_structure_report([], [], ["root_children_missing"])

    replay_by_source = {item.source_id: item for item in replayed}
    child_by_id = {str(child.get("id") or ""): child for child in children if isinstance(child, dict)}
    candidates, candidate_warnings = build_structure_group_candidates(
        replay_by_source=replay_by_source,
        hierarchy_report=hierarchy_report,
        sibling_group_report=sibling_group_report,
        layout_energy_report=layout_energy_report,
        auto_layout_permission_report=auto_layout_permission_report,
        options=options,
        page_bbox=[
            0,
            0,
            int(dsl.get("page", {}).get("width") or dsl.get("root", {}).get("layout", {}).get("width") or 0),
            int(dsl.get("page", {}).get("height") or dsl.get("root", {}).get("layout", {}).get("height") or 0),
        ],
    )

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    claimed_node_ids: set[str] = set()
    current_children = children
    for candidate in candidates:
        reject_reason = reject_candidate(candidate, current_children, child_by_id, claimed_node_ids)
        if reject_reason is not None:
            rejected.append(rejected_group(candidate, reject_reason))
            continue
        group_id = next_unique_id(existing_ids, f"m29_c_group_{candidate.source_candidate_id.replace(':', '_')}")
        existing_ids.add(group_id)
        claimed_node_ids.update(candidate.member_node_ids)
        accepted.append(asdict(candidate) | {"groupNodeId": group_id, "materializationMode": "report_only"})
        if len(accepted) >= options.max_controlled_groups:
            break
    return build_structure_report(accepted, rejected, candidate_warnings)


def build_structure_group_candidates(
    *,
    replay_by_source: dict[str, ReplayNode],
    hierarchy_report: dict[str, Any] | None,
    sibling_group_report: dict[str, Any] | None,
    layout_energy_report: dict[str, Any] | None,
    auto_layout_permission_report: dict[str, Any] | None,
    options: PlanMaterializerOptions,
    page_bbox: list[int],
) -> tuple[list[StructureGroup], list[str]]:
    warnings: list[str] = []
    permission_by_source = permission_lookup(auto_layout_permission_report)
    layout_by_source = layout_lookup(layout_energy_report)
    candidates: list[StructureGroup] = []
    for group in list_dicts((sibling_group_report or {}).get("siblingGroupCandidates")):
        members = [str(item) for item in group.get("memberSourceObjectIds", []) if isinstance(item, str)]
        candidate = candidate_from_source_ids(
            source_candidate_id=str(group.get("id") or ""),
            source="sibling_group_candidate",
            subject_type="sibling_group",
            source_ids=members,
            bbox=parse_bbox(group.get("bbox")),
            score=float(group.get("score") or 0.0),
            confidence=str(group.get("confidence") or ""),
            risks=[str(item) for item in group.get("risks", []) if isinstance(item, str)],
            replay_by_source=replay_by_source,
            permission_by_source=permission_by_source,
            layout_by_source=layout_by_source,
        )
        if candidate is None:
            continue
        candidates.append(candidate)

    hierarchy_children: dict[str, list[str]] = {}
    hierarchy_scores: dict[str, list[float]] = {}
    hierarchy_risks: dict[str, list[str]] = {}
    for selected in list_dicts((hierarchy_report or {}).get("selectedParentCandidates")):
        parent_id = str(selected.get("parentSourceObjectId") or "")
        child_id = str(selected.get("childSourceObjectId") or "")
        if parent_id and child_id:
            hierarchy_children.setdefault(parent_id, []).append(child_id)
            hierarchy_scores.setdefault(parent_id, []).append(float(selected.get("score") or 0.0))
            hierarchy_risks.setdefault(parent_id, []).extend(str(item) for item in selected.get("risks", []) if isinstance(item, str))
    for parent_id, child_ids in hierarchy_children.items():
        parent = replay_by_source.get(parent_id)
        source_ids = ([parent_id] if parent is not None else []) + child_ids
        bboxes = [replay_by_source[source_id].bbox for source_id in source_ids if source_id in replay_by_source]
        candidate = candidate_from_source_ids(
            source_candidate_id=f"hierarchy_children:{parent_id}",
            source="hierarchy_candidate",
            subject_type="hierarchy_children",
            source_ids=source_ids,
            bbox=bbox_union(bboxes) if bboxes else None,
            score=sum(hierarchy_scores.get(parent_id, [0.0])) / max(1, len(hierarchy_scores.get(parent_id, []))),
            confidence="high" if min(hierarchy_scores.get(parent_id, [0.0])) >= options.controlled_group_min_score else "medium",
            risks=hierarchy_risks.get(parent_id, []),
            replay_by_source=replay_by_source,
            permission_by_source=permission_by_source,
            layout_by_source=layout_by_source,
        )
        if candidate is not None:
            candidates.append(candidate)

    filtered: list[StructureGroup] = []
    page_area = max(1, page_bbox[2] * page_bbox[3])
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        key = tuple(sorted(candidate.member_source_object_ids))
        if key in seen:
            continue
        seen.add(key)
        if len(candidate.member_node_ids) < options.controlled_group_min_members:
            continue
        if len(candidate.member_node_ids) > options.controlled_group_max_members:
            warnings.append(f"candidate_skipped_too_many_members:{candidate.source_candidate_id}")
            continue
        if candidate.score < options.controlled_group_min_score:
            continue
        if bbox_area(candidate.bbox) / page_area > options.controlled_group_max_area_ratio:
            warnings.append(f"candidate_skipped_page_sized:{candidate.source_candidate_id}")
            continue
        if "contains_low_confidence_member" in candidate.risks or "contains_low_confidence_child" in candidate.risks:
            continue
        filtered.append(candidate)
    filtered.sort(key=lambda item: (-item.score, len(item.member_node_ids), item.bbox[1], item.bbox[0], item.source_candidate_id))
    return filtered, warnings


def candidate_from_source_ids(
    *,
    source_candidate_id: str,
    source: str,
    subject_type: str,
    source_ids: list[str],
    bbox: list[int] | None,
    score: float,
    confidence: str,
    risks: list[str],
    replay_by_source: dict[str, ReplayNode],
    permission_by_source: dict[tuple[str, ...], dict[str, Any]],
    layout_by_source: dict[tuple[str, ...], dict[str, Any]],
) -> StructureGroup | None:
    member_nodes = [replay_by_source[source_id] for source_id in source_ids if source_id in replay_by_source]
    if len(member_nodes) < 2 or bbox is None:
        return None
    member_sources = [node.source_id for node in member_nodes]
    key = tuple(sorted(member_sources))
    permission = permission_by_source.get(key, {})
    layout = layout_by_source.get(key, {})
    permission_score = score
    permission_risks = list(risks)
    recommended_model = None
    if permission:
        if permission.get("permission") == "allow_candidate":
            permission_score = max(permission_score, 0.78 if permission.get("confidence") == "high" else 0.72)
        recommended_model = str(permission.get("recommendedModel") or "") or None
        permission_risks.extend(str(item) for item in permission.get("risks", []) if isinstance(item, str))
    if layout and layout.get("confidence") == "high":
        permission_score = max(permission_score, 0.76)
    return StructureGroup(
        id="",
        source_candidate_id=source_candidate_id,
        source=source,
        subject_type=subject_type,
        bbox=bbox,
        member_node_ids=[node.id for node in member_nodes],
        member_source_object_ids=member_sources,
        score=round(min(1.0, permission_score), 3),
        confidence="high" if permission_score >= 0.78 and confidence in {"high", "medium"} else confidence,
        recommended_model=recommended_model,
        risks=ordered_unique(permission_risks),
    )


def reject_candidate(
    candidate: StructureGroup,
    current_children: list[dict[str, Any]],
    child_by_id: dict[str, dict[str, Any]],
    claimed_node_ids: set[str],
) -> str | None:
    if any(node_id in claimed_node_ids for node_id in candidate.member_node_ids):
        return "member_already_grouped"
    if any(node_id not in child_by_id for node_id in candidate.member_node_ids):
        return "member_node_missing"
    positions = [index for index, child in enumerate(current_children) if str(child.get("id") or "") in candidate.member_node_ids]
    if len(positions) != len(candidate.member_node_ids):
        return "member_not_at_root_level"
    positions.sort()
    if positions[-1] - positions[0] + 1 != len(positions):
        return "member_z_order_not_contiguous"
    return None


def build_group_node(
    candidate: StructureGroup,
    existing_ids: set[str],
    child_by_id: dict[str, dict[str, Any]],
    current_children: list[dict[str, Any]],
) -> dict[str, Any]:
    group_id = next_unique_id(existing_ids, f"m29_c_group_{candidate.source_candidate_id.replace(':', '_')}")
    x, y, width, height = candidate.bbox
    children: list[dict[str, Any]] = []
    ordered_node_ids = [
        str(child.get("id") or "")
        for child in current_children
        if str(child.get("id") or "") in set(candidate.member_node_ids)
    ]
    for node_id in ordered_node_ids:
        child = child_by_id[node_id]
        local_child = {**child, "layout": dict(child.get("layout", {}))}
        local_child["layout"]["x"] = local_child["layout"].get("x", 0) - x
        local_child["layout"]["y"] = local_child["layout"].get("y", 0) - y
        children.append(local_child)
    return {
        "id": group_id,
        "type": "group",
        "role": "m29_controlled_structure_group",
        "name": f"M29 C Group / {candidate.source_candidate_id}",
        "layout": {"x": x, "y": y, "width": width, "height": height},
        "style": {"fill": None, "clipContent": False},
        "children": children,
        "meta": {
            "m29ControlledStructureMaterialization": True,
            "sourceCandidateId": candidate.source_candidate_id,
            "source": candidate.source,
            "subjectType": candidate.subject_type,
            "memberSourceObjectIds": candidate.member_source_object_ids,
            "score": candidate.score,
            "confidence": candidate.confidence,
            "recommendedModel": candidate.recommended_model,
            "autoLayoutCreated": False,
            "reasons": ["controlled_transparent_group_materialization"],
            "risks": candidate.risks,
        },
    }


def replace_members_with_group(current_children: list[dict[str, Any]], member_node_ids: list[str], group_node: dict[str, Any]) -> list[dict[str, Any]]:
    member_ids = set(member_node_ids)
    positions = [index for index, child in enumerate(current_children) if str(child.get("id") or "") in member_ids]
    if not positions:
        return current_children
    start = min(positions)
    output: list[dict[str, Any]] = []
    inserted = False
    for index, child in enumerate(current_children):
        node_id = str(child.get("id") or "")
        if index == start and not inserted:
            output.append(group_node)
            inserted = True
        if node_id in member_ids:
            continue
        output.append(child)
    return output


def permission_lookup(report: dict[str, Any] | None) -> dict[tuple[str, ...], dict[str, Any]]:
    result: dict[tuple[str, ...], dict[str, Any]] = {}
    for item in list_dicts((report or {}).get("permissionItems")):
        key = tuple(sorted(str(source_id) for source_id in item.get("memberSourceObjectIds", []) if isinstance(source_id, str)))
        if len(key) >= 2:
            result[key] = item
    return result


def layout_lookup(report: dict[str, Any] | None) -> dict[tuple[str, ...], dict[str, Any]]:
    result: dict[tuple[str, ...], dict[str, Any]] = {}
    for item in list_dicts((report or {}).get("layoutEnergyCandidates")):
        key = tuple(sorted(str(source_id) for source_id in item.get("memberSourceObjectIds", []) if isinstance(source_id, str)))
        if len(key) >= 2:
            result[key] = item
    return result


def build_structure_report(accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    return {
        "schemaName": "M29ControlledStructureMaterialization",
        "schemaVersion": "0.1",
        "summary": {
            "acceptedGroupCount": len(accepted),
            "rejectedGroupCount": len(rejected),
            "materializationChanged": False,
            "autoLayoutCreated": False,
            "componentCreated": False,
            "variantCreated": False,
            "vectorCreated": False,
        },
        "acceptedGroups": accepted,
        "rejectedGroups": rejected,
        "warnings": warnings,
        "meta": {
            "truthSource": "m29_hierarchy_plus_sibling_group_plus_layout_energy_plus_auto_layout_permission",
            "dslChanged": False,
            "createdVisibleNodeCount": 0,
            "transparentGroupsOnly": True,
            "reportOnly": True,
        },
    }


def rejected_group(candidate: StructureGroup, reason: str) -> dict[str, Any]:
    return asdict(candidate) | {"reason": reason}


def parse_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [int(round(float(item))) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def bbox_union(bboxes: list[list[int]]) -> list[int]:
    x1 = min(bbox[0] for bbox in bboxes)
    y1 = min(bbox[1] for bbox in bboxes)
    x2 = max(bbox[0] + bbox[2] for bbox in bboxes)
    y2 = max(bbox[1] + bbox[3] for bbox in bboxes)
    return [x1, y1, x2 - x1, y2 - y1]


def bbox_area(bbox: list[int]) -> int:
    return max(0, bbox[2]) * max(0, bbox[3])


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def list_dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
