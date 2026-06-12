from __future__ import annotations

from pathlib import Path

from app.layout_energy_report import extract_m29_layout_energy_report


def test_layout_energy_report_empty_is_report_only(tmp_path: Path) -> None:
    report = layout_report(tmp_path, plan_items=[], sibling_groups=[], selected_parents=[])

    assert report["summary"]["layoutSubjectCount"] == 0
    assert report["summary"]["layoutEnergyCandidateCount"] == 0
    assert report["summary"]["dslChanged"] is False
    assert report["summary"]["materializationChanged"] is False
    assert report["summary"]["autoLayoutPermission"] is False
    assert report["meta"]["createdVisibleNodeCount"] == 0


def test_row_sibling_group_has_low_row_energy(tmp_path: Path) -> None:
    report = layout_report(
        tmp_path,
        plan_items=[
            plan_item("plan_a", "a", [0, 0, 20, 20], "shape_replay"),
            plan_item("plan_b", "b", [30, 0, 20, 20], "shape_replay"),
            plan_item("plan_c", "c", [60, 0, 20, 20], "shape_replay"),
        ],
        sibling_groups=[sibling_group("group_abc", ["a", "b", "c"], "row_like")],
        selected_parents=[],
    )

    candidate = report["layoutEnergyCandidates"][0]
    assert candidate["bestModel"] == "row"
    assert candidate["confidence"] == "high"
    assert candidate["energy"] <= 0.2
    assert report["summary"]["bestModelCounts"] == {"row": 1}


def test_column_sibling_group_has_low_column_energy(tmp_path: Path) -> None:
    report = layout_report(
        tmp_path,
        plan_items=[
            plan_item("plan_a", "a", [0, 0, 40, 12], "text_replay"),
            plan_item("plan_b", "b", [0, 22, 40, 12], "text_replay"),
            plan_item("plan_c", "c", [0, 44, 40, 12], "text_replay"),
        ],
        sibling_groups=[sibling_group("group_abc", ["a", "b", "c"], "column_like")],
        selected_parents=[],
    )

    candidate = report["layoutEnergyCandidates"][0]
    assert candidate["bestModel"] == "column"
    assert candidate["energy"] <= 0.2


def test_grid_sibling_group_can_win_grid_energy(tmp_path: Path) -> None:
    report = layout_report(
        tmp_path,
        plan_items=[
            plan_item("plan_a", "a", [0, 0, 20, 20], "image_replay"),
            plan_item("plan_b", "b", [30, 0, 20, 20], "image_replay"),
            plan_item("plan_c", "c", [0, 30, 20, 20], "image_replay"),
            plan_item("plan_d", "d", [30, 30, 20, 20], "image_replay"),
        ],
        sibling_groups=[sibling_group("group_grid", ["a", "b", "c", "d"], "repeated_item_like")],
        selected_parents=[],
    )

    candidate = report["layoutEnergyCandidates"][0]
    assert candidate["bestModel"] == "grid"
    assert candidate["energy"] <= 0.2


def test_hierarchy_children_become_container_layout_subject(tmp_path: Path) -> None:
    report = layout_report(
        tmp_path,
        plan_items=[
            plan_item("plan_parent", "parent", [0, 0, 140, 60], "shape_replay"),
            plan_item("plan_left", "left", [10, 20, 30, 12], "text_replay"),
            plan_item("plan_right", "right", [60, 20, 30, 12], "text_replay"),
        ],
        sibling_groups=[],
        selected_parents=[selected_parent("parent", "left"), selected_parent("parent", "right")],
    )

    assert report["summary"]["layoutSubjectCount"] == 1
    subject = report["layoutSubjects"][0]
    assert subject["subjectType"] == "hierarchy_children"
    assert subject["parentSourceObjectId"] == "parent"
    assert subject["memberSourceObjectIds"] == ["left", "right"]
    assert report["layoutEnergyCandidates"][0]["bestModel"] == "row"


def test_non_visible_plan_items_are_not_layout_members(tmp_path: Path) -> None:
    report = layout_report(
        tmp_path,
        plan_items=[
            plan_item("plan_image", "image", [0, 0, 120, 80], "image_replay"),
            plan_item("plan_preserved", "preserved_text", [20, 20, 40, 12], "preserve_in_parent_raster"),
        ],
        sibling_groups=[sibling_group("group_image_text", ["image", "preserved_text"], "row_like")],
        selected_parents=[selected_parent("image", "preserved_text")],
    )

    assert report["summary"]["visiblePlanItemCount"] == 1
    assert report["summary"]["layoutSubjectCount"] == 0
    assert report["summary"]["layoutEnergyCandidateCount"] == 0


def layout_report(
    tmp_path: Path,
    *,
    plan_items: list[dict],
    sibling_groups: list[dict],
    selected_parents: list[dict],
) -> dict:
    result = extract_m29_layout_energy_report(
        task_id="task_layout",
        m295_report=m295_report(plan_items),
        hierarchy_report=hierarchy_report(selected_parents),
        sibling_group_report=sibling_group_report(sibling_groups),
        output_dir=tmp_path / "m29_layout_energy",
    )
    assert (tmp_path / "m29_layout_energy" / "layout_energy_report.json").exists()
    return result.report


def m295_report(plan_items: list[dict]) -> dict:
    return {"schemaName": "M295ReplayPlan", "schemaVersion": "0.1", "planItems": plan_items}


def hierarchy_report(selected_parents: list[dict]) -> dict:
    return {
        "schemaName": "M29HierarchyCandidateReport",
        "schemaVersion": "0.1",
        "selectedParentCandidates": selected_parents,
    }


def sibling_group_report(groups: list[dict]) -> dict:
    return {
        "schemaName": "M29SiblingGroupCandidateReport",
        "schemaVersion": "0.1",
        "siblingGroupCandidates": groups,
    }


def plan_item(plan_id: str, source_id: str, bbox: list[int], action: str, *, confidence: str = "high") -> dict:
    return {
        "id": plan_id,
        "sourceObjectId": source_id,
        "bbox": bbox,
        "finalReplayAction": action,
        "targetRole": "m29_text" if action == "text_replay" else "m29_shape",
        "pixelOwner": "editable_text",
        "cleanupTargets": [],
        "suppressedSourceObjectIds": [],
        "relationEdgeIds": [],
        "clusterIds": [],
        "confidence": confidence,
        "reasons": ["test"],
        "risks": [],
    }


def sibling_group(group_id: str, members: list[str], pattern: str) -> dict:
    return {
        "id": group_id,
        "source": "relation_component",
        "groupPattern": pattern,
        "memberSourceObjectIds": members,
        "score": 0.9,
        "confidence": "high",
    }


def selected_parent(parent: str, child: str) -> dict:
    return {
        "parentSourceObjectId": parent,
        "childSourceObjectId": child,
        "confidence": "high",
    }
