from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from app.hierarchy_materialization import M38Options, materialize_m38_hierarchy
from app.hierarchy_readiness import extract_m37_hierarchy_readiness


def test_classify_content_chrome_rules(tmp_path: Path) -> None:
    import app.content_chrome_classification

    dsl = {
        "version": "0.1",
        "page": {"width": 1000, "height": 1000},
        "root": {
            "id": "root",
            "type": "frame",
            "children": [
                {
                    "id": "node_top_chrome",
                    "role": "m30_text_member",
                    "layout": {"x": 100, "y": 10, "width": 800, "height": 50},
                    "meta": {"m30Materialized": True},
                },
                {
                    "id": "node_bottom_chrome",
                    "role": "m30_shape_candidate",
                    "layout": {"x": 100, "y": 900, "width": 800, "height": 50},
                    "meta": {"m30Materialized": True},
                },
                {
                    "id": "node_right_float_chrome",
                    "role": "m30_visual_asset",
                    "layout": {"x": 850, "y": 200, "width": 50, "height": 50},
                    "meta": {"m30Materialized": True},
                },
                {
                    "id": "node_composite_content",
                    "role": "m30_composite_media_asset",
                    "layout": {"x": 100, "y": 320, "width": 800, "height": 200},
                    "meta": {"m30Materialized": True},
                },
                {
                    "id": "node_center_content",
                    "role": "m30_text_member",
                    "layout": {"x": 400, "y": 400, "width": 200, "height": 100},
                    "meta": {"m30Materialized": True},
                },
                {
                    "id": "node_non_m30",
                    "role": "some_other_role",
                    "layout": {"x": 100, "y": 10, "width": 800, "height": 50},
                    "meta": {"m30Materialized": False},
                },
            ],
        },
    }

    report = app.content_chrome_classification.classify_content_chrome(
        dsl,
        "task_dummy",
        tmp_path,
        options=app.content_chrome_classification.M39Options(onnx_proposer_enabled=False),
    )

    nodes_by_id = {node["id"]: node for node in dsl["root"]["children"]}
    assert nodes_by_id["node_top_chrome"]["meta"]["boundaryClassification"] == "chrome"
    assert nodes_by_id["node_bottom_chrome"]["meta"]["boundaryClassification"] == "chrome"
    assert nodes_by_id["node_right_float_chrome"]["meta"]["boundaryClassification"] == "chrome"
    assert nodes_by_id["node_composite_content"]["meta"]["boundaryClassification"] == "content"
    assert nodes_by_id["node_center_content"]["meta"]["boundaryClassification"] == "content"
    assert nodes_by_id["node_non_m30"]["meta"].get("boundaryClassification") is None
    assert report["summary"] == {
        "totalClassifiedNodeCount": 5,
        "chromeNodeCount": 3,
        "contentNodeCount": 2,
        "onnxProposerEnabled": False,
        "onnxModelLoaded": False,
        "onnxCandidateCount": 0,
        "ruleOnlyClassificationCount": 5,
        "modelAssistedClassificationCount": 0,
    }
    assert report["modelSkippedReason"] is None


def test_classify_content_chrome_model_proposer_and_override(tmp_path: Path) -> None:
    import app.content_chrome_classification

    dsl = {
        "version": "0.1",
        "page": {"width": 1000, "height": 1000},
        "root": {
            "id": "root",
            "type": "frame",
            "children": [
                {
                    "id": "node_overlap_chrome",
                    "role": "m30_text_member",
                    "layout": {"x": 10, "y": 10, "width": 100, "height": 100},
                    "meta": {"m30Materialized": True},
                },
                {
                    "id": "node_overlap_center_protected",
                    "role": "m30_text_member",
                    "layout": {"x": 450, "y": 450, "width": 100, "height": 100},
                    "meta": {"m30Materialized": True},
                },
            ],
        },
    }
    proposed_boxes = [
        {"bbox": [5, 5, 110, 110], "score": 0.9},
        {"bbox": [440, 440, 120, 120], "score": 0.85},
    ]

    with patch("app.content_chrome_classification.propose_chrome_boxes_with_onnx") as mock_propose:
        mock_propose.return_value = (proposed_boxes, None, True, [])
        source_image = tmp_path / "source.png"
        source_image.write_bytes(b"not-used")
        report = app.content_chrome_classification.classify_content_chrome(
            dsl,
            "task_dummy",
            tmp_path,
            source_image_path=source_image,
        )

    nodes_by_id = {node["id"]: node for node in dsl["root"]["children"]}
    assert nodes_by_id["node_overlap_chrome"]["meta"]["boundaryClassification"] == "chrome"
    assert nodes_by_id["node_overlap_center_protected"]["meta"]["boundaryClassification"] == "content"
    assert report["summary"]["onnxProposerEnabled"] is True
    assert report["summary"]["onnxModelLoaded"] is True
    assert report["summary"]["onnxCandidateCount"] == 2
    assert report["summary"]["modelAssistedClassificationCount"] == 1
    protected = next(item for item in report["classifiedNodes"] if item["nodeId"] == "node_overlap_center_protected")
    assert protected["modelAssisted"] is False
    assert "override_safety_center_60_percent" in protected["matchedRules"]


def test_classify_content_chrome_missing_model_falls_back_to_rules(tmp_path: Path) -> None:
    import app.content_chrome_classification

    dsl = dsl_with_single_node(
        role="m30_shape_candidate",
        bbox=[0, 0, 1000, 80],
    )
    source = tmp_path / "source.png"
    source.write_bytes(b"not-used-because-model-is-missing")

    report = app.content_chrome_classification.classify_content_chrome(
        dsl,
        "task_dummy",
        tmp_path / "m39",
        source_image_path=source,
        options=app.content_chrome_classification.M39Options(
            onnx_proposer_enabled=True,
            onnx_model_path=tmp_path / "missing.onnx",
        ),
    )

    assert dsl["root"]["children"][0]["meta"]["boundaryClassification"] == "chrome"
    assert report["modelSkippedReason"] == "missing_model"
    assert report["summary"]["onnxModelLoaded"] is False
    assert report["summary"]["ruleOnlyClassificationCount"] == 1
    assert report["warnings"]


def test_classify_content_chrome_missing_dependency_falls_back_to_rules(tmp_path: Path) -> None:
    import app.content_chrome_classification

    dsl = dsl_with_single_node(
        role="m30_text_member",
        bbox=[0, 900, 1000, 80],
    )
    source = tmp_path / "source.png"
    model = tmp_path / "model.onnx"
    source.write_bytes(b"not-used")
    model.write_bytes(b"not-used")

    def fake_import(_module_name: str, *, reason_name: str) -> tuple[Any | None, str | None]:
        if reason_name == "numpy":
            return None, "missing_dependency:numpy"
        return MagicMock(), None

    with patch("app.onnx_box_proposer.import_optional_module", side_effect=fake_import):
        report = app.content_chrome_classification.classify_content_chrome(
            dsl,
            "task_dummy",
            tmp_path / "m39",
            source_image_path=source,
            options=app.content_chrome_classification.M39Options(
                onnx_proposer_enabled=True,
                onnx_model_path=model,
            ),
        )

    assert dsl["root"]["children"][0]["meta"]["boundaryClassification"] == "chrome"
    assert report["modelSkippedReason"] == "missing_dependency:numpy"
    assert report["summary"]["onnxModelLoaded"] is False
    assert report["summary"]["ruleOnlyClassificationCount"] == 1


def test_classify_content_chrome_unexpected_model_shape_falls_back_to_rules(tmp_path: Path) -> None:
    import app.content_chrome_classification

    dsl = dsl_with_single_node(
        role="m30_text_member",
        bbox=[100, 300, 120, 40],
    )
    source = tmp_path / "source.png"
    model = tmp_path / "model.onnx"
    source.write_bytes(b"not-used")
    model.write_bytes(b"not-used")

    fake_ort = MagicMock()
    fake_ort.InferenceSession.return_value = MagicMock()
    with patch(
        "app.onnx_box_proposer.import_optional_module",
        return_value=(fake_ort, None),
    ), patch(
        "app.onnx_box_proposer.run_model_inference",
        side_effect=app.content_chrome_classification.UnexpectedOnnxOutputShape("bad shape"),
    ):
        report = app.content_chrome_classification.classify_content_chrome(
            dsl,
            "task_dummy",
            tmp_path / "m39",
            source_image_path=source,
            options=app.content_chrome_classification.M39Options(
                onnx_proposer_enabled=True,
                onnx_model_path=model,
            ),
        )

    assert dsl["root"]["children"][0]["meta"]["boundaryClassification"] == "content"
    assert report["modelSkippedReason"] == "unexpected_output_shape"
    assert report["summary"]["onnxModelLoaded"] is True


def test_m37_m38_boundary_enforcement(tmp_path: Path) -> None:
    m30_dsl = {
        "version": "0.1",
        "page": {"width": 1000, "height": 1000},
        "assets": [],
        "root": {
            "id": "root",
            "type": "frame",
            "children": [
                m30_text_node("m30_node_1", [10, 10, 100, 30], "Header Title", "text_member_1", "ocr_1", "chrome"),
                m30_text_node("m30_node_2", [120, 10, 200, 30], "Content Body", "text_member_2", "ocr_2", "content"),
            ],
        },
    }
    m31_tree = {
        "schemaName": "M31ReconstructionUiTree",
        "schemaVersion": "0.1",
        "imageSize": {"width": 1000, "height": 1000},
        "root": {"id": "page", "kind": "page", "bbox": [0, 0, 1000, 1000], "children": ["unit_conflict"]},
        "nodes": [
            {
                "id": "unit_conflict",
                "kind": "reconstruction_unit",
                "unitKind": "row_unit",
                "visualKind": "text_block",
                "bbox": [0, 0, 400, 50],
                "children": ["prim_1", "prim_2"],
            }
        ],
        "primitiveRefs": [
            {"id": "prim_1", "sourceId": "text_member_1", "primitiveType": "text", "bbox": [10, 10, 100, 30], "ownerUnitId": "unit_conflict"},
            {"id": "prim_2", "sourceId": "text_member_2", "primitiveType": "text", "bbox": [120, 10, 200, 30], "ownerUnitId": "unit_conflict"},
        ],
    }

    paths = write_hierarchy_inputs(tmp_path, m30_dsl, m31_tree)
    m37_result = extract_m37_hierarchy_readiness(
        m31_tree_path=str(paths["tree"]),
        m31_report_path=str(paths["m31_report"]),
        m30_dsl_path=str(paths["dsl"]),
        m30_report_path=str(paths["m30_report"]),
        output_dir=tmp_path / "m37",
    )

    assert m37_result.report["summary"]["safeContainerUnitCount"] == 0
    assert m37_result.report["summary"]["unsafeContainerUnitCount"] == 1
    conflict_unit = m37_result.report["unitReports"][0]
    assert "boundary_classification_conflict" in conflict_unit["unsafeReasons"]
    assert conflict_unit["safeContainerCandidate"] is False

    m38_result = materialize_m38_hierarchy(
        m30_dsl_path=str(paths["dsl"]),
        m37_report_path=str(tmp_path / "m37" / "m37_hierarchy_readiness_report.json"),
        output_dir=tmp_path / "m38",
        flat_dsl_output_path=str(tmp_path / "flat_dsl.json"),
        final_dsl_output_path=str(tmp_path / "final_dsl.json"),
        options=M38Options(max_containers=8),
    )
    assert len(m38_result.report["containers"]) == 0
    assert m38_result.report["summary"]["createdContainerCount"] == 0
    assert m38_result.report["summary"]["sourceSafeContainerCount"] == 0


def test_m37_m38_composite_media_direct_match_can_move(tmp_path: Path) -> None:
    m30_dsl = {
        "version": "0.1",
        "page": {"width": 300, "height": 200},
        "assets": [],
        "root": {
            "id": "root",
            "type": "frame",
            "children": [
                {
                    "id": "m30_composite",
                    "type": "image",
                    "role": "m30_composite_media_asset",
                    "layout": {"x": 20, "y": 40, "width": 120, "height": 80},
                    "source": {"assetId": "asset_composite"},
                    "meta": {
                        "m30Materialized": True,
                        "boundaryClassification": "content",
                        "sourceKind": "m2905_composite_media_object",
                        "sourceRefinedObjectId": "refined_object_1",
                    },
                },
                m30_text_node("m30_text", [30, 50, 50, 20], "Title", "text_member_1", "ocr_1", "content"),
            ],
        },
    }
    m31_tree = {
        "schemaName": "M31ReconstructionUiTree",
        "schemaVersion": "0.1",
        "imageSize": {"width": 300, "height": 200},
        "root": {"id": "page", "kind": "page", "bbox": [0, 0, 300, 200], "children": ["unit_card"]},
        "nodes": [
            {
                "id": "unit_card",
                "kind": "reconstruction_unit",
                "unitKind": "row_unit",
                "visualKind": "card_like",
                "bbox": [20, 40, 120, 80],
                "children": ["prim_image", "prim_text"],
            }
        ],
        "primitiveRefs": [
            {"id": "prim_image", "sourceId": "refined_object_1", "primitiveType": "image", "bbox": [20, 40, 120, 80], "ownerUnitId": "unit_card"},
            {"id": "prim_text", "sourceId": "ocr_1", "primitiveType": "text", "bbox": [30, 50, 50, 20], "ownerUnitId": "unit_card", "text": "Title"},
        ],
    }

    paths = write_hierarchy_inputs(tmp_path, m30_dsl, m31_tree)
    m37_result = extract_m37_hierarchy_readiness(
        m31_tree_path=str(paths["tree"]),
        m31_report_path=str(paths["m31_report"]),
        m30_dsl_path=str(paths["dsl"]),
        m30_report_path=str(paths["m30_report"]),
        output_dir=tmp_path / "m37",
    )
    unit = m37_result.report["unitReports"][0]
    assert unit["safeContainerCandidate"] is True
    assert unit["matchCounts"]["direct_match"] == 2

    m38_result = materialize_m38_hierarchy(
        m30_dsl_path=str(paths["dsl"]),
        m37_report_path=str(tmp_path / "m37" / "m37_hierarchy_readiness_report.json"),
        output_dir=tmp_path / "m38",
        options=M38Options(max_containers=8),
    )
    assert m38_result.report["summary"]["createdContainerCount"] == 1
    assert m38_result.report["summary"]["absolutePositionViolationCount"] == 0
    container = m38_result.dsl["root"]["children"][0]
    assert container["role"] == "m38_container"
    assert [child["id"] for child in container["children"]] == ["m30_composite", "m30_text"]


def dsl_with_single_node(*, role: str, bbox: list[int]) -> dict[str, Any]:
    return {
        "version": "0.1",
        "page": {"width": 1000, "height": 1000},
        "root": {
            "id": "root",
            "type": "frame",
            "children": [
                {
                    "id": "node_1",
                    "role": role,
                    "layout": {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]},
                    "meta": {"m30Materialized": True},
                }
            ],
        },
    }


def m30_text_node(node_id: str, bbox: list[int], text: str, source_text_member_id: str, source_text_box_id: str, classification: str) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "text",
        "role": "m30_text_member",
        "layout": {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]},
        "content": {"text": text},
        "meta": {
            "m30Materialized": True,
            "boundaryClassification": classification,
            "sourceKind": "m2905_text_member",
            "sourceTextMemberId": source_text_member_id,
            "sourceTextBoxId": source_text_box_id,
        },
    }


def write_hierarchy_inputs(tmp_path: Path, m30_dsl: dict[str, Any], m31_tree: dict[str, Any]) -> dict[str, Path]:
    paths = {
        "tree": tmp_path / "m31_reconstruction_tree.json",
        "m31_report": tmp_path / "m31_reconstruction_tree_report.json",
        "dsl": tmp_path / "m30_materialized_dsl.json",
        "m30_report": tmp_path / "m30_materialization_report.json",
    }
    paths["tree"].write_text(json.dumps(m31_tree), encoding="utf-8")
    paths["m31_report"].write_text(json.dumps({"schemaName": "M31ReconstructionUiTreeReport", "summary": {}}), encoding="utf-8")
    paths["dsl"].write_text(json.dumps(m30_dsl), encoding="utf-8")
    paths["m30_report"].write_text(json.dumps({"schemaName": "M30EvidenceGroundedDslMaterializationReport", "summary": {}}), encoding="utf-8")
    return paths
