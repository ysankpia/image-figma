from __future__ import annotations

from typing import Any

from .geometry import bbox_union


def build_layout_subjects(
    *,
    plan_items: list[dict[str, Any]],
    sibling_groups: list[dict[str, Any]],
    selected_parents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    visible_by_source = {item["sourceObjectId"]: item for item in plan_items if item["visible"]}
    subjects: list[dict[str, Any]] = []
    subjects.extend(sibling_subjects(sibling_groups, visible_by_source))
    subjects.extend(hierarchy_subjects(selected_parents, visible_by_source))
    subjects = dedupe_subjects(subjects)
    subjects = sorted(subjects, key=subject_sort_key)
    for index, subject in enumerate(subjects, start=1):
        subject["id"] = f"m29_layout_subject_{index:04d}"
    return subjects


def sibling_subjects(groups: list[dict[str, Any]], visible_by_source: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    subjects: list[dict[str, Any]] = []
    for group in groups:
        members = [visible_by_source[source_id] for source_id in group["memberSourceObjectIds"] if source_id in visible_by_source]
        if len(members) < 2:
            continue
        subjects.append(
            {
                "id": "",
                "subjectType": "sibling_group",
                "sourceCandidateId": group["id"],
                "sourcePattern": group["groupPattern"],
                "parentSourceObjectId": None,
                "memberSourceObjectIds": [item["sourceObjectId"] for item in members],
                "memberPlanItemIds": [item["planItemId"] for item in members],
                "memberFinalReplayActions": [item["finalReplayAction"] for item in members],
                "bbox": bbox_union([item["bbox"] for item in members]),
                "_memberItems": members,
            }
        )
    return subjects


def hierarchy_subjects(selected_parents: list[dict[str, Any]], visible_by_source: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    for selected in selected_parents:
        child = visible_by_source.get(selected["childSourceObjectId"])
        if child is not None:
            children_by_parent.setdefault(selected["parentSourceObjectId"], []).append(child)

    subjects: list[dict[str, Any]] = []
    for parent_id, children in sorted(children_by_parent.items()):
        members = sorted(children, key=lambda item: item["sourceObjectId"])
        if len(members) < 2:
            continue
        parent_item = visible_by_source.get(parent_id)
        bboxes = [item["bbox"] for item in members]
        if parent_item is not None:
            bboxes.append(parent_item["bbox"])
        subjects.append(
            {
                "id": "",
                "subjectType": "hierarchy_children",
                "sourceCandidateId": f"hierarchy_children:{parent_id}",
                "sourcePattern": "container_children",
                "parentSourceObjectId": parent_id,
                "memberSourceObjectIds": [item["sourceObjectId"] for item in members],
                "memberPlanItemIds": [item["planItemId"] for item in members],
                "memberFinalReplayActions": [item["finalReplayAction"] for item in members],
                "bbox": bbox_union(bboxes),
                "_memberItems": members,
            }
        )
    return subjects


def dedupe_subjects(subjects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for subject in subjects:
        key = (subject["subjectType"], tuple(subject["memberSourceObjectIds"]))
        current = by_key.get(key)
        if current is None or subject_priority(subject) > subject_priority(current):
            by_key[key] = subject
    return list(by_key.values())


def subject_priority(subject: dict[str, Any]) -> tuple[int, int]:
    type_rank = 1 if subject["subjectType"] == "hierarchy_children" else 0
    return type_rank, len(subject["memberSourceObjectIds"])


def subject_sort_key(subject: dict[str, Any]) -> tuple[int, int, str]:
    bbox = subject["bbox"]
    return bbox[1], bbox[0], subject["sourceCandidateId"]
