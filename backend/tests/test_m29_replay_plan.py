from __future__ import annotations

import json
from pathlib import Path

from app.m29_replay_plan import M295ReplayPlanOptions, build_m295_replay_plan


def test_m295_maps_m292_replay_decisions_to_plan_actions(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_basic",
        m292_document=m292_document(
            [
                m292_object("text", [10, 10, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("image", [0, 30, 80, 40], "media_region", "preserve_raster", "image_replay"),
                m292_object("icon", [90, 10, 10, 10], "raster_icon", "raster_icon", "icon_replay"),
                m292_object("shape", [0, 0, 100, 4], "separator", "shape_geometry", "shape_replay"),
            ]
        ),
        m2931_report=m2931_report([], []),
        m294_report=m294_report([]),
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {
        "text": "text_replay",
        "image": "image_replay",
        "icon": "icon_replay",
        "shape": "shape_replay",
    }
    assert result.report["summary"]["plannedVisibleNodeCount"] == 4
    assert result.report["summary"]["plannedTextReplayCount"] == 1
    assert (tmp_path / "m29_5" / "replay_plan.json").exists()


def test_m295_plan_items_are_sorted_for_replay_layer_order(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_layer_order",
        m292_document=m292_document(
            [
                m292_object("text", [20, 20, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("image", [0, 0, 100, 60], "media_region", "preserve_raster", "image_replay"),
                m292_object("icon", [70, 20, 10, 10], "raster_icon", "raster_icon", "icon_replay"),
                m292_object("shape", [0, 0, 100, 60], "control_background", "shape_geometry", "shape_replay"),
            ]
        ),
        m2931_report=m2931_report([], []),
        m294_report=m294_report([]),
        output_dir=tmp_path / "m29_5",
    )

    assert [item["finalReplayAction"] for item in result.report["planItems"]] == [
        "shape_replay",
        "image_replay",
        "icon_replay",
        "text_replay",
    ]


def test_m295_preserve_raster_text_has_no_cleanup_targets(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_preserve",
        m292_document=m292_document(
            [
                m292_object("art", [10, 10, 50, 20], "preserve_raster_text", "preserve_raster", "preserve_in_parent_raster"),
            ]
        ),
        m2931_report=None,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    item = result.report["planItems"][0]
    assert item["finalReplayAction"] == "preserve_in_parent_raster"
    assert item["targetRole"] is None
    assert item["cleanupTargets"] == []
    assert result.report["summary"]["plannedVisibleNodeCount"] == 0


def test_m295_editable_text_inside_media_declares_fallback_and_asset_cleanup(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_cleanup",
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 100, 60], "media_region", "preserve_raster", "image_replay"),
                m292_object("text", [20, 20, 30, 10], "editable_ui_text", "editable_text", "text_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["media", "text"],
            [edge("media_text", "media", "text", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    text_item = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "text")
    assert text_item["finalReplayAction"] == "text_replay"
    assert {"target": "fallback", "targetSourceObjectId": None, "reason": "replayed_visible_object"} in text_item["cleanupTargets"]
    assert {"target": "copied_image_asset", "targetSourceObjectId": "media", "reason": "editable_text_contained_by_media"} in text_item["cleanupTargets"]
    assert result.report["summary"]["fallbackCleanupTargetCount"] == 2
    assert result.report["summary"]["copiedImageAssetCleanupTargetCount"] == 1


def test_m295_near_equal_duplicate_keeps_one_replay_owner(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_duplicate",
        m292_document=m292_document(
            [
                m292_object("a", [10, 10, 20, 10], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("b", [11, 10, 20, 10], "editable_ui_text", "editable_text", "text_replay"),
            ]
        ),
        m2931_report=m2931_report(["a", "b"], [edge("a_b", "a", "b", "near_equal", ["near"])]),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert sorted(actions.values()) == ["suppress_duplicate", "text_replay"]
    assert result.report["summary"]["suppressedDuplicateCount"] == 1


def test_m295_suppresses_same_icon_contained_visible_overlap(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_icon_overlap",
        m292_document=m292_document(
            [
                m292_object("icon_outer", [10, 10, 34, 22], "raster_icon", "raster_icon", "icon_replay"),
                m292_object("icon_inner", [19, 19, 8, 13], "raster_icon", "raster_icon", "icon_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["icon_outer", "icon_inner"],
            [edge("icon_overlap", "icon_outer", "icon_inner", "contains", [])],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions == {"icon_outer": "icon_replay", "icon_inner": "suppress_duplicate"}
    suppressed = next(item for item in result.report["planItems"] if item["sourceObjectId"] == "icon_inner")
    assert "visible_overlap_duplicate_suppressed" in suppressed["reasons"]
    assert "visible_overlap_duplicate" in suppressed["risks"]
    assert result.report["summary"]["visibleOverlapSuppressedCount"] == 1


def test_m295_suppresses_same_shape_high_overlap_without_suppressing_text_background(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_shape_overlap",
        m292_document=m292_document(
            [
                m292_object("shape_outer", [10, 10, 155, 55], "control_background", "shape_geometry", "shape_replay"),
                m292_object("shape_inner", [17, 10, 110, 55], "control_background", "shape_geometry", "shape_replay"),
                m292_object("label", [24, 24, 40, 12], "editable_ui_text", "editable_text", "text_replay"),
            ]
        ),
        m2931_report=m2931_report(
            ["shape_outer", "shape_inner", "label"],
            [
                edge("shape_overlap", "shape_outer", "shape_inner", "contains", []),
                edge("shape_label", "shape_outer", "label", "contains", []),
            ],
        ),
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions["shape_outer"] == "shape_replay"
    assert actions["shape_inner"] == "suppress_duplicate"
    assert actions["label"] == "text_replay"
    assert result.report["summary"]["visibleOverlapSuppressedCount"] == 1


def test_m295_records_cluster_support_without_semantic_role_promotion(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_cluster",
        m292_document=m292_document(
            [
                m292_object("icon", [10, 10, 12, 12], "raster_icon", "raster_icon", "icon_replay"),
                m292_object("label", [26, 10, 40, 12], "editable_ui_text", "editable_text", "text_replay"),
            ]
        ),
        m2931_report=m2931_report([], []),
        m294_report=m294_report([cluster("cluster_row", ["icon", "label"], "row_like")]),
        output_dir=tmp_path / "m29_5",
    )

    assert result.report["summary"]["clusterSupportedPlanItemCount"] == 2
    for item in result.report["planItems"]:
        assert item["clusterIds"] == ["cluster_row"]
        assert item["targetRole"] in {"m29_text", "m29_symbol"}
        assert "SearchBar" not in json.dumps(item)
        assert "Card" not in json.dumps(item)


def test_m295_keeps_recovered_raster_foreground_as_icon_replay(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_recovered_icon",
        m292_document=m292_document(
            [
                m292_object("blocked_icon", [24, 24, 36, 36], "raster_icon", "raster_icon", "icon_replay"),
                m292_object("diagnostic", [80, 24, 20, 20], "unknown", "diagnostic_only", "skip", confidence="low"),
            ]
        ),
        m2931_report=None,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    )

    actions = {item["sourceObjectId"]: item["finalReplayAction"] for item in result.report["planItems"]}
    assert actions["blocked_icon"] == "icon_replay"
    assert actions["diagnostic"] == "diagnostic_only"
    assert result.report["summary"]["plannedIconReplayCount"] == 1


def test_m295_node_budget_suppresses_low_priority_visible_items(tmp_path: Path) -> None:
    result = build_m295_replay_plan(
        task_id="task_budget",
        m292_document=m292_document(
            [
                m292_object("text1", [0, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("text2", [20, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"),
                m292_object("image1", [0, 20, 30, 20], "media_region", "preserve_raster", "image_replay"),
            ]
        ),
        m2931_report=None,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
        options=M295ReplayPlanOptions(max_visible_nodes=2),
    )

    assert result.report["summary"]["plannedVisibleNodeCount"] == 2
    assert result.report["summary"]["nodeBudgetSuppressedCount"] == 1
    suppressed = [item for item in result.report["planItems"] if "node_budget_suppressed" in item["reasons"]]
    assert len(suppressed) == 1
    assert suppressed[0]["finalReplayAction"] == "suppress_duplicate"


def test_m295_invalid_inputs_are_reported_and_input_is_not_mutated(tmp_path: Path) -> None:
    m292 = m292_document(
        [
            m292_object("z", [30, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"),
            {**m292_object("bad", [0, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"), "bbox": [0, 0, 0, 10]},
            m292_object("a", [0, 0, 10, 10], "editable_ui_text", "editable_text", "text_replay"),
        ]
    )
    before = json.dumps(m292, sort_keys=True)

    result = build_m295_replay_plan(
        task_id="task_invalid",
        m292_document=m292,
        m2931_report=None,
        m294_report=m294_report([{"id": "bad_cluster", "memberNodeIds": "not-list"}]),
        output_dir=tmp_path / "m29_5",
    )

    assert json.dumps(m292, sort_keys=True) == before
    assert result.report["summary"]["skippedInvalidSourceObjectCount"] == 1
    assert result.report["summary"]["warningCount"] == 2
    assert [item["sourceObjectId"] for item in result.report["planItems"]] == ["a", "z"]


def m292_document(objects: list[dict]) -> dict:
    return {
        "schemaName": "M292SourceUiPhysicalGraph",
        "schemaVersion": "0.1",
        "sourceObjects": objects,
    }


def m292_object(
    object_id: str,
    bbox: list[int],
    visual_kind: str,
    pixel_owner: str,
    replay_decision: str,
    *,
    confidence: str = "high",
) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "sourceEvidence": {},
        "confidence": confidence,
        "reasons": ["test"],
        "risks": [],
    }


def m2931_report(node_ids: list[str], edges: list[dict]) -> dict:
    return {
        "schemaName": "M2931RegionRelationGraphReport",
        "schemaVersion": "0.1",
        "nodes": [{"id": node_id, "bbox": [0, 0, 10, 10]} for node_id in node_ids],
        "edges": edges,
    }


def edge(edge_id: str, left: str, right: str, primary: str, secondary: list[str]) -> dict:
    return {
        "edgeId": edge_id,
        "leftObjectId": left,
        "rightObjectId": right,
        "primarySetRelation": primary,
        "secondaryGeometryRelations": secondary,
        "metrics": {},
    }


def m294_report(clusters: list[dict]) -> dict:
    return {
        "schemaName": "M294StableDesignClusterReport",
        "schemaVersion": "0.1",
        "clusters": clusters,
    }


def cluster(cluster_id: str, member_ids: list[str], role_hint: str) -> dict:
    return {
        "id": cluster_id,
        "bbox": [0, 0, 60, 20],
        "memberNodeIds": member_ids,
        "edgeIds": [],
        "clusterPattern": "directed_row_subgraph",
        "roleHint": role_hint,
        "stabilityScore": 0.8,
        "repeatabilityScore": 0.0,
        "reasons": ["test"],
        "risks": [],
    }
