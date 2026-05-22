from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.unit_structure_readiness import M391Options, audit_unit_structure_readiness


def test_m391_normalizes_safe_and_blocked_m37_units(tmp_path: Path) -> None:
    paths = write_m391_inputs(
        tmp_path,
        dsl=m30_dsl(
            [
                text_node("m30_text_1", [10, 10, 80, 24], "Title", "content"),
                text_node("m30_text_2", [100, 10, 90, 24], "Body", "content"),
            ]
        ),
        m37_report={
            "summary": {"safeContainerUnitCount": 1},
            "unitReports": [
                {
                    "unitId": "unit_safe",
                    "unitKind": "row_unit",
                    "visualKind": "text_block",
                    "bbox": [10, 10, 180, 24],
                    "safeContainerCandidate": True,
                    "unsafeReasons": [],
                    "matchCounts": {"direct_match": 2, "geometry_text_match": 0, "geometry_type_match": 0},
                    "matches": [
                        {"m30NodeId": "m30_text_1", "role": "m30_text_member", "boundaryClassification": "content"},
                        {"m30NodeId": "m30_text_2", "role": "m30_text_member", "boundaryClassification": "content"},
                    ],
                },
                {
                    "unitId": "unit_micro",
                    "unitKind": "single_primitive_unit",
                    "visualKind": "unknown",
                    "bbox": [10, 50, 20, 20],
                    "safeContainerCandidate": False,
                    "unsafeReasons": ["single_primitive_unit", "micro_unit", "insufficient_mapped_children"],
                    "matchCounts": {"direct_match": 0, "geometry_text_match": 0, "geometry_type_match": 0},
                    "matches": [],
                },
            ],
        },
        m38_report={"summary": {"createdContainerCount": 1}, "containers": [{"unitId": "unit_safe", "containerId": "m38_container_unit_safe"}]},
    )

    result = audit_unit_structure_readiness(
        task_id="task_m391",
        m30_dsl_path=str(paths["dsl"]),
        m31_tree_path=str(paths["m31_tree"]),
        m31_report_path=str(paths["m31_report"]),
        m37_report_path=str(paths["m37_report"]),
        m38_report_path=str(paths["m38_report"]),
        m39_report_path=None,
        output_dir=tmp_path / "m39_1",
        options=M391Options(onnx_unit_proposer_enabled=False),
    )

    safe = next(item for item in result.report["candidateUnits"] if item["m37UnitIds"] == ["unit_safe"])
    micro = next(item for item in result.report["candidateUnits"] if item["m37UnitIds"] == ["unit_micro"])
    assert safe["readiness"] == "ready_for_existing_m38"
    assert safe["m38ContainerIds"] == ["m38_container_unit_safe"]
    assert micro["readiness"] == "blocked"
    assert "micro_unit_only" in micro["blockerReasons"]
    assert "insufficient_direct_matches" in micro["blockerReasons"]
    assert result.report["summary"]["readyCandidateCount"] == 1
    assert result.report["summary"]["blockedCandidateCount"] == 1
    assert result.report["summary"]["dslChanged"] is False
    assert result.report["summary"]["createdVisibleNodeCount"] == 0
    assert result.report["summary"]["assetChanged"] is False
    assert (tmp_path / "m39_1" / "unit_structure_readiness_report.json").exists()


def test_m391_derives_product_card_candidate_without_mutating_dsl(tmp_path: Path) -> None:
    dsl = m30_dsl(
        [
            image_node("m30_image_1", [20, 100, 180, 180], "content"),
            text_node("m30_text_1", [40, 120, 60, 20], "旅行", "content"),
        ]
    )
    before = json.dumps(dsl, sort_keys=True)
    paths = write_m391_inputs(tmp_path, dsl=dsl)

    result = audit_unit_structure_readiness(
        task_id="task_m391",
        m30_dsl_path=str(paths["dsl"]),
        m31_tree_path=str(paths["m31_tree"]),
        m31_report_path=str(paths["m31_report"]),
        m37_report_path=str(paths["m37_report"]),
        m38_report_path=None,
        m39_report_path=None,
        output_dir=tmp_path / "m39_1",
        options=M391Options(onnx_unit_proposer_enabled=False),
    )

    after = paths["dsl"].read_text(encoding="utf-8")
    assert json.loads(after) == json.loads(before)
    product_cards = [item for item in result.report["candidateUnits"] if item["candidateKind"] == "product_card_candidate"]
    assert product_cards
    assert product_cards[0]["readiness"] == "needs_unit_promotion"
    assert product_cards[0]["childM30NodeIds"] == ["m30_image_1", "m30_text_1"]
    assert result.report["promotionHints"]


def test_m391_boundary_clusters_stay_diagnostic_and_conflicts_block(tmp_path: Path) -> None:
    dsl = m30_dsl(
        [
            text_node("top_1", [0, 10, 180, 30], "Search", "chrome"),
            text_node("top_2", [200, 10, 100, 30], "Cancel", "chrome"),
            image_node("image_1", [20, 100, 180, 180], "content"),
            text_node("mixed_text", [40, 120, 60, 20], "旅行", "chrome"),
        ]
    )
    m39_report = {
        "classifiedNodes": [
            {"nodeId": "top_1", "role": "m30_text_member", "bbox": [0, 10, 180, 30], "classification": "chrome"},
            {"nodeId": "top_2", "role": "m30_text_member", "bbox": [200, 10, 100, 30], "classification": "chrome"},
            {"nodeId": "image_1", "role": "m30_visual_asset", "bbox": [20, 100, 180, 180], "classification": "content"},
            {"nodeId": "mixed_text", "role": "m30_text_member", "bbox": [40, 120, 60, 20], "classification": "chrome"},
        ],
    }
    paths = write_m391_inputs(tmp_path, dsl=dsl, m39_report=m39_report)

    result = audit_unit_structure_readiness(
        task_id="task_m391",
        m30_dsl_path=str(paths["dsl"]),
        m31_tree_path=str(paths["m31_tree"]),
        m31_report_path=str(paths["m31_report"]),
        m37_report_path=str(paths["m37_report"]),
        m38_report_path=None,
        m39_report_path=str(paths["m39_report"]),
        output_dir=tmp_path / "m39_1",
        options=M391Options(onnx_unit_proposer_enabled=False),
    )

    chrome = next(item for item in result.report["candidateUnits"] if item["candidateKind"] == "chrome_shell_candidate")
    assert chrome["readiness"] == "diagnostic_only"
    assert chrome["roleHint"] == "top_chrome"
    product = next(item for item in result.report["candidateUnits"] if item["candidateKind"] == "product_card_candidate")
    assert product["readiness"] == "blocked"
    assert "boundary_classification_conflict" in product["blockerReasons"]


def test_m391_missing_model_falls_back_to_rule_only(tmp_path: Path) -> None:
    paths = write_m391_inputs(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(b"not-used")

    result = audit_unit_structure_readiness(
        task_id="task_m391",
        m30_dsl_path=str(paths["dsl"]),
        m31_tree_path=str(paths["m31_tree"]),
        m31_report_path=str(paths["m31_report"]),
        m37_report_path=str(paths["m37_report"]),
        m38_report_path=None,
        m39_report_path=None,
        output_dir=tmp_path / "m39_1",
        source_image_path=source,
        options=M391Options(onnx_unit_proposer_enabled=True, onnx_model_path=tmp_path / "missing.onnx"),
    )

    assert result.report["modelSkippedReason"] == "missing_model"
    assert result.report["summary"]["onnxModelLoaded"] is False
    assert result.report["summary"]["onnxCandidateCount"] == 0
    assert result.report["warnings"]


def test_m391_model_only_candidate_is_diagnostic_only(tmp_path: Path) -> None:
    paths = write_m391_inputs(tmp_path, dsl=m30_dsl([text_node("inside", [20, 20, 40, 20], "Hi", "content")]))
    source = tmp_path / "source.png"
    source.write_bytes(b"not-used")

    def fake_propose(**_kwargs):
        return [{"bbox": [0, 0, 100, 100], "score": 0.91}], None, True, []

    with patch.dict(audit_unit_structure_readiness.__globals__, {"propose_boxes_with_onnx": fake_propose}):
        result = audit_unit_structure_readiness(
            task_id="task_m391",
            m30_dsl_path=str(paths["dsl"]),
            m31_tree_path=str(paths["m31_tree"]),
            m31_report_path=str(paths["m31_report"]),
            m37_report_path=str(paths["m37_report"]),
            m38_report_path=None,
            m39_report_path=None,
            output_dir=tmp_path / "m39_1",
            source_image_path=source,
        )

    onnx = next(item for item in result.report["candidateUnits"] if item["candidateKind"] == "onnx_box_candidate")
    assert onnx["readiness"] == "diagnostic_only"
    assert onnx["blockerReasons"] == ["model_only_untrusted"]
    assert result.report["summary"]["onnxModelLoaded"] is True
    assert result.report["summary"]["onnxCandidateCount"] == 1


def write_m391_inputs(
    tmp_path: Path,
    *,
    dsl: dict | None = None,
    m37_report: dict | None = None,
    m38_report: dict | None = None,
    m39_report: dict | None = None,
) -> dict[str, Path]:
    paths = {
        "dsl": tmp_path / "m30_materialized_dsl.json",
        "m31_tree": tmp_path / "m31_reconstruction_tree.json",
        "m31_report": tmp_path / "m31_reconstruction_tree_report.json",
        "m37_report": tmp_path / "m37_hierarchy_readiness_report.json",
        "m38_report": tmp_path / "hierarchy_materialization_report.json",
        "m39_report": tmp_path / "m39_boundary_classification_report.json",
    }
    paths["dsl"].write_text(json.dumps(dsl or m30_dsl([])), encoding="utf-8")
    paths["m31_tree"].write_text(json.dumps({"nodes": [], "primitiveRefs": []}), encoding="utf-8")
    paths["m31_report"].write_text(json.dumps({"summary": {"unitCount": 0}, "unitSummaries": []}), encoding="utf-8")
    paths["m37_report"].write_text(json.dumps(m37_report or {"summary": {"safeContainerUnitCount": 0}, "unitReports": []}), encoding="utf-8")
    if m38_report is not None:
        paths["m38_report"].write_text(json.dumps(m38_report), encoding="utf-8")
    if m39_report is not None:
        paths["m39_report"].write_text(json.dumps(m39_report), encoding="utf-8")
    return paths


def m30_dsl(children: list[dict]) -> dict:
    return {
        "version": "0.1",
        "page": {"width": 400, "height": 800},
        "assets": [],
        "root": {"id": "root", "type": "frame", "children": children},
    }


def text_node(node_id: str, bbox: list[int], text: str, classification: str) -> dict:
    return {
        "id": node_id,
        "type": "text",
        "role": "m30_text_member",
        "layout": {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]},
        "content": {"text": text},
        "meta": {"m30Materialized": True, "boundaryClassification": classification},
    }


def image_node(node_id: str, bbox: list[int], classification: str) -> dict:
    return {
        "id": node_id,
        "type": "image",
        "role": "m30_visual_asset",
        "layout": {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]},
        "source": {"assetId": f"asset_{node_id}"},
        "meta": {"m30Materialized": True, "boundaryClassification": classification},
    }
