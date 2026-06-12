from __future__ import annotations

from pathlib import Path

from app.sibling_group_candidate_report import extract_m29_sibling_group_candidate_report


def test_sibling_group_report_empty_is_report_only(tmp_path: Path) -> None:
    report = sibling_report(tmp_path, plan_items=[], edges=[], clusters=[], selected_parents=[])

    assert report["summary"]["siblingGroupCandidateCount"] == 0
    assert report["summary"]["dslChanged"] is False
    assert report["summary"]["materializationChanged"] is False
    assert report["summary"]["groupMaterializationPermission"] is False
    assert report["meta"]["createdVisibleNodeCount"] == 0


def test_relation_edges_build_row_sibling_group(tmp_path: Path) -> None:
    report = sibling_report(
        tmp_path,
        plan_items=[
            plan_item("plan_icon", "icon", [0, 0, 16, 16], "icon_replay"),
            plan_item("plan_text", "text", [24, 1, 80, 14], "text_replay"),
            plan_item("plan_badge", "badge", [112, 0, 24, 16], "shape_replay"),
        ],
        edges=[
            relation_edge("edge_icon_text", "icon", "text", "disjoint", ["near", "left_of", "aligned_center_y"]),
            relation_edge("edge_text_badge", "text", "badge", "disjoint", ["near", "left_of", "aligned_center_y"]),
        ],
        clusters=[],
        selected_parents=[],
    )

    assert report["summary"]["siblingGroupCandidateCount"] == 1
    group = report["siblingGroupCandidates"][0]
    assert group["source"] == "relation_component"
    assert group["groupPattern"] == "row_like"
    assert group["memberSourceObjectIds"] == ["badge", "icon", "text"]
    assert group["metrics"]["edgeCount"] == 2


def test_relation_edges_build_column_sibling_group(tmp_path: Path) -> None:
    report = sibling_report(
        tmp_path,
        plan_items=[
            plan_item("plan_top", "top", [0, 0, 90, 20], "text_replay"),
            plan_item("plan_bottom", "bottom", [0, 30, 90, 20], "text_replay"),
        ],
        edges=[relation_edge("edge_top_bottom", "top", "bottom", "disjoint", ["near", "above", "aligned_center_x", "same_width"])],
        clusters=[],
        selected_parents=[],
    )

    group = report["siblingGroupCandidates"][0]
    assert group["groupPattern"] == "column_like"
    assert group["memberSourceObjectIds"] == ["bottom", "top"]


def test_m294_cluster_backed_group_is_preferred_over_relation_group(tmp_path: Path) -> None:
    report = sibling_report(
        tmp_path,
        plan_items=[
            plan_item("plan_a", "a", [0, 0, 20, 20], "shape_replay"),
            plan_item("plan_b", "b", [30, 0, 20, 20], "shape_replay"),
        ],
        edges=[relation_edge("edge_a_b", "a", "b", "disjoint", ["near", "left_of", "aligned_center_y"])],
        clusters=[cluster("cluster_ab", ["a", "b"], "row_like")],
        selected_parents=[],
    )

    assert report["summary"]["siblingGroupCandidateCount"] == 1
    group = report["siblingGroupCandidates"][0]
    assert group["source"] == "m29_4_cluster"
    assert group["sourceClusterId"] == "cluster_ab"
    assert "m29_4_cluster_supported" in group["reasons"]


def test_hierarchy_parent_child_edge_is_excluded(tmp_path: Path) -> None:
    report = sibling_report(
        tmp_path,
        plan_items=[
            plan_item("plan_parent", "parent", [0, 0, 120, 60], "shape_replay"),
            plan_item("plan_child", "child", [20, 20, 40, 12], "text_replay"),
        ],
        edges=[relation_edge("edge_parent_child", "parent", "child", "disjoint", ["near", "left_of", "aligned_center_y"])],
        clusters=[],
        selected_parents=[selected_parent("parent", "child")],
    )

    assert report["summary"]["siblingGroupCandidateCount"] == 0
    assert report["siblingGroupCandidates"] == []


def test_non_visible_plan_items_are_not_group_members(tmp_path: Path) -> None:
    report = sibling_report(
        tmp_path,
        plan_items=[
            plan_item("plan_image", "image", [0, 0, 120, 80], "image_replay"),
            plan_item("plan_preserved", "preserved_text", [20, 20, 40, 12], "preserve_in_parent_raster"),
        ],
        edges=[relation_edge("edge_image_text", "image", "preserved_text", "disjoint", ["near", "left_of", "aligned_center_y"])],
        clusters=[cluster("cluster_image_text", ["image", "preserved_text"], "row_like")],
        selected_parents=[],
    )

    assert report["summary"]["visiblePlanItemCount"] == 1
    assert report["summary"]["siblingGroupCandidateCount"] == 0


def sibling_report(
    tmp_path: Path,
    *,
    plan_items: list[dict],
    edges: list[dict],
    clusters: list[dict],
    selected_parents: list[dict],
) -> dict:
    result = extract_m29_sibling_group_candidate_report(
        task_id="task_sibling",
        m2931_report=m2931_report(edges),
        m294_report=m294_report(clusters),
        m295_report=m295_report(plan_items),
        hierarchy_report=hierarchy_report(selected_parents),
        output_dir=tmp_path / "m29_sibling_groups",
    )
    assert (tmp_path / "m29_sibling_groups" / "sibling_group_candidate_report.json").exists()
    return result.report


def m2931_report(edges: list[dict]) -> dict:
    return {"schemaName": "M2931RegionRelationGraphReport", "schemaVersion": "0.1", "edges": edges}


def m294_report(clusters: list[dict]) -> dict:
    return {"schemaName": "M294StableDesignClusterReport", "schemaVersion": "0.1", "clusters": clusters}


def m295_report(plan_items: list[dict]) -> dict:
    return {"schemaName": "M295ReplayPlan", "schemaVersion": "0.1", "planItems": plan_items}


def hierarchy_report(selected_parents: list[dict]) -> dict:
    return {
        "schemaName": "M29HierarchyCandidateReport",
        "schemaVersion": "0.1",
        "selectedParentCandidates": selected_parents,
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


def relation_edge(edge_id: str, left: str, right: str, primary: str, secondary: list[str]) -> dict:
    return {
        "edgeId": edge_id,
        "leftObjectId": left,
        "rightObjectId": right,
        "primarySetRelation": primary,
        "secondaryGeometryRelations": secondary,
        "metrics": {},
    }


def cluster(cluster_id: str, members: list[str], role_hint: str) -> dict:
    return {
        "id": cluster_id,
        "memberNodeIds": members,
        "roleHint": role_hint,
        "clusterPattern": "directed_row_subgraph",
        "stabilityScore": 0.8,
        "repeatabilityScore": 0.6,
    }


def selected_parent(parent: str, child: str) -> dict:
    return {
        "parentSourceObjectId": parent,
        "childSourceObjectId": child,
        "confidence": "high",
    }
