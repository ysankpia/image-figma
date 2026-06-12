from __future__ import annotations

import json
from pathlib import Path

from app.region_relation_graph_report import extract_m2931_region_relation_graph_report


def test_m2931_empty_and_single_graphs_are_report_only(tmp_path: Path) -> None:
    empty = extract_m2931_region_relation_graph_report(
        task_id="task_empty",
        m292_document=m292_document([]),
        output_dir=tmp_path / "empty",
    )
    assert empty.report["summary"]["nodeCount"] == 0
    assert empty.report["summary"]["edgeCount"] == 0
    assert empty.report["summary"]["dslChanged"] is False
    assert empty.report["summary"]["assetChanged"] is False
    assert empty.report["summary"]["createdVisibleNodeCount"] == 0

    single = extract_m2931_region_relation_graph_report(
        task_id="task_single",
        m292_document=m292_document([m292_object("one", [0, 0, 10, 10])]),
        output_dir=tmp_path / "single",
    )
    assert single.report["nodes"] == [
        {
            "id": "one",
            "bbox": [0, 0, 10, 10],
            "pixelOwner": "editable_text",
            "replayDecision": "text_replay",
            "confidence": "high",
            "visualKind": "editable_ui_text",
        }
    ]
    assert single.report["edges"] == []
    assert (tmp_path / "single" / "region_relation_graph_report.json").exists()


def test_m2931_primary_relation_counts_cover_core_set_relations(tmp_path: Path) -> None:
    result = extract_m2931_region_relation_graph_report(
        task_id="task_primary",
        m292_document=m292_document(
            [
                m292_object("a_small", [10, 10, 20, 20]),
                m292_object("b_container", [0, 0, 100, 100]),
                m292_object("c_near_equal", [11, 11, 20, 20]),
                m292_object("d_overlap", [25, 25, 30, 30]),
                m292_object("e_disjoint", [200, 200, 20, 20]),
            ]
        ),
        output_dir=tmp_path / "m29_3",
    )

    edges = edge_map(result.report)
    assert edges[("a_small", "b_container")]["primarySetRelation"] == "contained_by"
    assert edges[("b_container", "c_near_equal")]["primarySetRelation"] == "contains"
    assert edges[("a_small", "c_near_equal")]["primarySetRelation"] == "near_equal"
    assert edges[("a_small", "d_overlap")]["primarySetRelation"] == "overlaps"
    assert edges[("a_small", "e_disjoint")]["primarySetRelation"] == "disjoint"
    counts = result.report["summary"]["primarySetRelationCounts"]
    assert counts["contained_by"] >= 1
    assert counts["contains"] >= 1
    assert counts["near_equal"] >= 1
    assert counts["overlaps"] >= 1
    assert counts["disjoint"] >= 1


def test_m2931_secondary_relations_preserve_direction_alignment_and_size(tmp_path: Path) -> None:
    result = extract_m2931_region_relation_graph_report(
        task_id="task_secondary",
        m292_document=m292_document(
            [
                m292_object("icon", [10, 10, 16, 16], pixel_owner="raster_icon", replay_decision="icon_replay", visual_kind="raster_icon"),
                m292_object("text", [30, 10, 40, 16]),
                m292_object("below", [10, 32, 16, 16]),
                m292_object("same", [10, 58, 16, 16]),
            ]
        ),
        output_dir=tmp_path / "m29_3",
    )

    edges = edge_map(result.report)
    icon_text = set(edges[("icon", "text")]["secondaryGeometryRelations"])
    assert {"near", "left_of", "aligned_center_y", "same_height"} <= icon_text
    icon_below = set(edges[("below", "icon")]["secondaryGeometryRelations"])
    assert {"near", "below", "aligned_left", "aligned_center_x", "aligned_right", "same_width", "same_height", "same_size"} <= icon_below
    icon_same = set(edges[("icon", "same")]["secondaryGeometryRelations"])
    assert {"aligned_left", "aligned_center_x", "aligned_right", "same_width", "same_height", "same_size"} <= icon_same
    secondary_counts = result.report["summary"]["secondaryGeometryRelationCounts"]
    assert secondary_counts["left_of"] >= 1
    assert secondary_counts["below"] >= 1
    assert secondary_counts["aligned_center_y"] >= 1
    assert secondary_counts["same_size"] >= 1


def test_m2931_stable_sorting_and_invalid_bbox_skips(tmp_path: Path) -> None:
    m292 = m292_document(
        [
            m292_object("z", [30, 0, 10, 10]),
            {**m292_object("bad", [0, 0, 10, 10]), "bbox": [0, 0, 0, 10]},
            m292_object("a", [0, 0, 10, 10]),
        ]
    )
    before = json.dumps(m292, sort_keys=True)
    result = extract_m2931_region_relation_graph_report(task_id="task_sort", m292_document=m292, output_dir=tmp_path / "m29_3")

    assert json.dumps(m292, sort_keys=True) == before
    assert [node["id"] for node in result.report["nodes"]] == ["a", "z"]
    assert [(edge["leftObjectId"], edge["rightObjectId"]) for edge in result.report["edges"]] == [("a", "z")]
    assert result.report["summary"]["invalidBBoxSkippedCount"] == 1
    assert result.report["summary"]["warningCount"] == 1
    assert result.report["skippedItems"][0]["sourceObjectId"] == "bad"


def edge_map(report: dict) -> dict[tuple[str, str], dict]:
    return {
        (edge["leftObjectId"], edge["rightObjectId"]): edge
        for edge in report["edges"]
    }


def m292_document(objects: list[dict]) -> dict:
    return {
        "schemaName": "M292SourceUiPhysicalGraph",
        "schemaVersion": "0.1",
        "sourceObjects": objects,
        "summary": {"sourceObjectCount": len(objects)},
    }


def m292_object(
    object_id: str,
    bbox: list[int],
    *,
    pixel_owner: str = "editable_text",
    replay_decision: str = "text_replay",
    visual_kind: str = "editable_ui_text",
    confidence: str = "high",
) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "confidence": confidence,
        "sourceEvidence": {},
        "reasons": [],
        "risks": [],
    }
