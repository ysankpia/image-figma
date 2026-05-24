from __future__ import annotations

from pathlib import Path

from app.hierarchy_candidate_report import extract_m29_hierarchy_candidate_report


def test_hierarchy_candidate_report_empty_is_report_only(tmp_path: Path) -> None:
    report = hierarchy_report(tmp_path, objects=[], plan_items=[], edges=[])

    assert report["summary"]["containerCandidateCount"] == 0
    assert report["summary"]["parentCandidateCount"] == 0
    assert report["summary"]["dslChanged"] is False
    assert report["summary"]["materializationChanged"] is False
    assert report["meta"]["createdVisibleNodeCount"] == 0


def test_shape_container_selects_text_child_parent(tmp_path: Path) -> None:
    report = hierarchy_report(
        tmp_path,
        objects=[
            source_object("shape", [0, 0, 120, 60], "control_background", "shape_geometry", "shape_replay"),
            source_object("text", [20, 20, 40, 12], "editable_ui_text", "editable_text", "text_replay"),
        ],
        plan_items=[
            plan_item("plan_shape", "shape", [0, 0, 120, 60], "shape_replay"),
            plan_item("plan_text", "text", [20, 20, 40, 12], "text_replay"),
        ],
        edges=[relation_edge("edge_shape_text", "shape", "text", "contains", right_in_left=1.0, left_in_right=0.067)],
    )

    assert report["summary"]["containerCandidateCount"] == 1
    assert report["summary"]["selectedParentCandidateCount"] == 1
    selected = report["selectedParentCandidates"][0]
    assert selected["parentSourceObjectId"] == "shape"
    assert selected["childSourceObjectId"] == "text"
    assert selected["confidence"] in {"medium", "high"}


def test_best_parent_prefers_tighter_container(tmp_path: Path) -> None:
    report = hierarchy_report(
        tmp_path,
        objects=[
            source_object("outer", [0, 0, 400, 240], "media_region", "preserve_raster", "image_replay"),
            source_object("inner", [100, 80, 140, 70], "control_background", "shape_geometry", "shape_replay"),
            source_object("text", [120, 100, 50, 16], "editable_ui_text", "editable_text", "text_replay"),
        ],
        plan_items=[
            plan_item("plan_outer", "outer", [0, 0, 400, 240], "image_replay"),
            plan_item("plan_inner", "inner", [100, 80, 140, 70], "shape_replay"),
            plan_item("plan_text", "text", [120, 100, 50, 16], "text_replay"),
        ],
        edges=[
            relation_edge("edge_outer_text", "outer", "text", "contains", right_in_left=1.0, left_in_right=0.008),
            relation_edge("edge_inner_text", "inner", "text", "contains", right_in_left=1.0, left_in_right=0.082),
        ],
    )

    selected = [item for item in report["selectedParentCandidates"] if item["childSourceObjectId"] == "text"]
    assert len(selected) == 1
    assert selected[0]["parentSourceObjectId"] == "inner"


def test_non_visible_plan_items_do_not_become_children(tmp_path: Path) -> None:
    report = hierarchy_report(
        tmp_path,
        objects=[
            source_object("media", [0, 0, 100, 60], "media_region", "preserve_raster", "image_replay"),
            source_object("preserved_text", [20, 20, 40, 12], "preserve_raster_text", "preserve_raster", "preserve_in_parent_raster"),
        ],
        plan_items=[
            plan_item("plan_media", "media", [0, 0, 100, 60], "image_replay"),
            plan_item("plan_preserved", "preserved_text", [20, 20, 40, 12], "preserve_in_parent_raster"),
        ],
        edges=[relation_edge("edge_media_text", "media", "preserved_text", "contains", right_in_left=1.0, left_in_right=0.08)],
    )

    assert report["summary"]["parentCandidateCount"] == 0
    assert report["selectedParentCandidates"] == []


def hierarchy_report(
    tmp_path: Path,
    *,
    objects: list[dict],
    plan_items: list[dict],
    edges: list[dict],
) -> dict:
    result = extract_m29_hierarchy_candidate_report(
        task_id="task_hierarchy",
        m292_document=m292_document(objects),
        m2931_report=m2931_report(edges),
        m295_report=m295_report(plan_items),
        output_dir=tmp_path / "m29_hierarchy_candidates",
    )
    assert (tmp_path / "m29_hierarchy_candidates" / "hierarchy_candidate_report.json").exists()
    return result.report


def m292_document(objects: list[dict]) -> dict:
    return {"schemaName": "M292SourceUiPhysicalGraph", "schemaVersion": "0.1", "sourceObjects": objects}


def m2931_report(edges: list[dict]) -> dict:
    return {"schemaName": "M2931RegionRelationGraphReport", "schemaVersion": "0.1", "edges": edges}


def m295_report(plan_items: list[dict]) -> dict:
    return {"schemaName": "M295ReplayPlan", "schemaVersion": "0.1", "planItems": plan_items}


def source_object(object_id: str, bbox: list[int], visual_kind: str, pixel_owner: str, replay_decision: str) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "sourceEvidence": {},
        "confidence": "high",
        "reasons": ["test"],
        "risks": [],
    }


def plan_item(plan_id: str, source_id: str, bbox: list[int], action: str) -> dict:
    return {
        "id": plan_id,
        "sourceObjectId": source_id,
        "bbox": bbox,
        "finalReplayAction": action,
        "targetRole": "m29_text" if action == "text_replay" else "m29_image" if action == "image_replay" else "m29_shape",
        "pixelOwner": "editable_text",
        "cleanupTargets": [],
        "suppressedSourceObjectIds": [],
        "relationEdgeIds": [],
        "clusterIds": [],
        "confidence": "high",
        "reasons": ["test"],
        "risks": [],
    }


def relation_edge(edge_id: str, left: str, right: str, primary: str, *, left_in_right: float, right_in_left: float) -> dict:
    return {
        "edgeId": edge_id,
        "leftObjectId": left,
        "rightObjectId": right,
        "primarySetRelation": primary,
        "secondaryGeometryRelations": ["near"],
        "metrics": {
            "leftInRightRatio": left_in_right,
            "rightInLeftRatio": right_in_left,
            "intersectionArea": 1,
        },
    }
