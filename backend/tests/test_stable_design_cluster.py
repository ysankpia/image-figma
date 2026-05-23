from __future__ import annotations

import json
from pathlib import Path

from app.stable_design_cluster import extract_m294_stable_design_cluster_report


def test_m294_empty_report_is_read_only(tmp_path: Path) -> None:
    result = extract_m294_stable_design_cluster_report(
        task_id="task_empty",
        m2931_report=m2931_report([], []),
        output_dir=tmp_path / "m29_4",
    )

    assert result.report["summary"]["clusterCount"] == 0
    assert result.report["summary"]["dslChanged"] is False
    assert result.report["summary"]["assetChanged"] is False
    assert result.report["summary"]["createdVisibleNodeCount"] == 0
    assert (tmp_path / "m29_4" / "stable_design_cluster_report.json").exists()


def test_m294_single_node_produces_no_cluster(tmp_path: Path) -> None:
    result = extract_m294_stable_design_cluster_report(
        task_id="task_single",
        m2931_report=m2931_report([m2931_node("one", [0, 0, 10, 10])], []),
        output_dir=tmp_path / "m29_4",
    )

    assert result.report["clusters"] == []
    assert result.report["summary"]["clusterCount"] == 0


def test_m294_containment_chain_becomes_stable_background_anchor_cluster(tmp_path: Path) -> None:
    result = extract_m294_stable_design_cluster_report(
        task_id="task_containment",
        m2931_report=m2931_report(
            [
                m2931_node("outer", [0, 0, 100, 100], pixel_owner="preserve_raster", replay_decision="image_replay", visual_kind="media_region"),
                m2931_node("inner", [10, 10, 20, 20]),
            ],
            [
                m2931_edge("outer", "inner", "contains", ["near"]),
            ],
        ),
        output_dir=tmp_path / "m29_4",
    )

    assert result.report["summary"]["clusterCount"] == 1
    cluster = result.report["clusters"][0]
    assert cluster["clusterPattern"] == "containment_anchor_subgraph"
    assert cluster["roleHint"] == "background_anchor_like"
    assert cluster["memberNodeIds"] == ["inner", "outer"]
    assert cluster["bbox"] == [0, 0, 100, 100]


def test_m294_row_and_column_clusters_keep_directionality(tmp_path: Path) -> None:
    result = extract_m294_stable_design_cluster_report(
        task_id="task_flow",
        m2931_report=m2931_report(
            [
                m2931_node("icon", [10, 10, 16, 16], pixel_owner="raster_icon", replay_decision="icon_replay", visual_kind="raster_icon"),
                m2931_node("text", [30, 10, 40, 16]),
                m2931_node("below", [10, 40, 16, 16], pixel_owner="shape_geometry", replay_decision="shape_replay", visual_kind="control_background"),
            ],
            [
                m2931_edge("icon", "text", "disjoint", ["near", "left_of", "aligned_center_y"]),
                m2931_edge("icon", "below", "disjoint", ["below", "aligned_center_x"]),
            ],
        ),
        output_dir=tmp_path / "m29_4",
    )

    patterns = {cluster["clusterPattern"] for cluster in result.report["clusters"]}
    assert "directed_row_subgraph" in patterns
    assert "directed_column_subgraph" in patterns
    assert all(cluster["roleHint"] in {"row_like", "column_like"} for cluster in result.report["clusters"])


def test_m294_repeated_local_subgraph_scores_repeatability(tmp_path: Path) -> None:
    result = extract_m294_stable_design_cluster_report(
        task_id="task_repeat",
        m2931_report=m2931_report(
            [
                m2931_node("a", [0, 0, 20, 20], pixel_owner="editable_text"),
                m2931_node("b", [30, 0, 20, 20], pixel_owner="editable_text"),
                m2931_node("c", [60, 0, 20, 20], pixel_owner="editable_text"),
            ],
            [
                m2931_edge("a", "b", "disjoint", ["near", "left_of", "aligned_center_y", "same_width", "same_height", "same_size"]),
                m2931_edge("b", "c", "disjoint", ["near", "left_of", "aligned_center_y", "same_width", "same_height", "same_size"]),
            ],
        ),
        output_dir=tmp_path / "m29_4",
    )

    cluster = result.report["clusters"][0]
    assert cluster["clusterPattern"] == "repeated_size_subgraph"
    assert cluster["roleHint"] == "repeated_item_like"
    assert cluster["repeatabilityScore"] > 0
    assert cluster["stabilityScore"] >= 0.55


def test_m294_invalid_inputs_are_skipped_and_report_stays_deterministic(tmp_path: Path) -> None:
    m2931 = m2931_report(
        [
            m2931_node("b", [30, 0, 10, 10]),
            {**m2931_node("bad", [0, 0, 10, 10]), "bbox": [0, 0, 0, 10]},
            m2931_node("a", [0, 0, 10, 10]),
        ],
        [
            m2931_edge("a", "b", "disjoint", ["near", "left_of"]),
            {"edgeId": "bad_edge", "leftObjectId": "a", "rightObjectId": "missing", "primarySetRelation": "disjoint", "secondaryGeometryRelations": ["near"], "metrics": {}},
        ],
    )
    before = json.dumps(m2931, sort_keys=True)

    result = extract_m294_stable_design_cluster_report(task_id="task_bad", m2931_report=m2931, output_dir=tmp_path / "m29_4")

    assert json.dumps(m2931, sort_keys=True) == before
    assert result.report["summary"]["skippedNodeCount"] == 1
    assert result.report["summary"]["skippedEdgeCount"] == 1
    assert result.report["summary"]["warningCount"] == 2
    assert result.report["summary"]["clusterCount"] == 1
    assert result.report["clusters"][0]["memberNodeIds"] == ["a", "b"]


def m2931_report(nodes: list[dict], edges: list[dict]) -> dict:
    return {
        "schemaName": "M2931RegionRelationGraphReport",
        "schemaVersion": "0.1",
        "nodes": nodes,
        "edges": edges,
    }


def m2931_node(
    node_id: str,
    bbox: list[int],
    *,
    pixel_owner: str = "editable_text",
    replay_decision: str = "text_replay",
    visual_kind: str = "editable_ui_text",
    confidence: str = "high",
) -> dict:
    return {
        "id": node_id,
        "bbox": bbox,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "confidence": confidence,
        "visualKind": visual_kind,
    }


def m2931_edge(left: str, right: str, primary: str, secondary: list[str]) -> dict:
    return {
        "edgeId": f"{left}_{right}",
        "leftObjectId": left,
        "rightObjectId": right,
        "primarySetRelation": primary,
        "secondaryGeometryRelations": secondary,
        "metrics": {},
    }
