from __future__ import annotations

import json
from pathlib import Path

from app.hierarchy_readiness import extract_m37_hierarchy_readiness


def test_m37_hierarchy_readiness_reports_safe_and_unsafe_units(tmp_path: Path) -> None:
    m31_tree = {
        "schemaName": "M31ReconstructionUiTree",
        "schemaVersion": "0.1",
        "imageSize": {"width": 300, "height": 200},
        "root": {"id": "page", "kind": "page", "bbox": [0, 0, 300, 200], "children": ["unit_safe", "unit_micro", "unit_dup_a", "unit_dup_b"]},
        "nodes": [
            {
                "id": "unit_safe",
                "kind": "reconstruction_unit",
                "unitKind": "row_unit",
                "visualKind": "text_block",
                "bbox": [20, 20, 160, 40],
                "children": ["prim_text_1", "prim_text_2"],
                "fallback": {"assetId": "fallback_safe"},
            },
            {
                "id": "unit_micro",
                "kind": "reconstruction_unit",
                "unitKind": "single_primitive_unit",
                "visualKind": "unknown",
                "bbox": [220, 20, 8, 8],
                "children": ["prim_symbol"],
                "fallback": {"assetId": "fallback_micro"},
            },
            {
                "id": "unit_dup_a",
                "kind": "reconstruction_unit",
                "unitKind": "row_unit",
                "visualKind": "text_block",
                "bbox": [20, 90, 60, 20],
                "children": ["prim_dup_a"],
                "fallback": {"assetId": "fallback_dup_a"},
            },
            {
                "id": "unit_dup_b",
                "kind": "reconstruction_unit",
                "unitKind": "row_unit",
                "visualKind": "text_block",
                "bbox": [20, 90, 60, 20],
                "children": ["prim_dup_b"],
                "fallback": {"assetId": "fallback_dup_b"},
            },
        ],
        "primitiveRefs": [
            {
                "id": "prim_text_1",
                "sourceId": "text_001",
                "primitiveType": "text",
                "bbox": [30, 28, 50, 16],
                "ownerUnitId": "unit_safe",
                "sourceRefs": {"ocrTextBoxId": "ocr_001"},
                "text": "Alpha",
            },
            {
                "id": "prim_text_2",
                "sourceId": "text_002",
                "primitiveType": "text",
                "bbox": [96, 28, 44, 16],
                "ownerUnitId": "unit_safe",
                "sourceRefs": {"ocrTextBoxId": "ocr_002"},
                "text": "Beta",
            },
            {
                "id": "prim_symbol",
                "sourceId": "symbol_001",
                "primitiveType": "symbol",
                "bbox": [220, 20, 8, 8],
                "ownerUnitId": "unit_micro",
                "sourceRefs": {"m29NodeId": "symbol_001"},
            },
            {
                "id": "prim_dup_a",
                "sourceId": "text_003",
                "primitiveType": "text",
                "bbox": [20, 90, 60, 20],
                "ownerUnitId": "unit_dup_a",
                "sourceRefs": {"ocrTextBoxId": "ocr_003"},
                "text": "Gamma",
            },
            {
                "id": "prim_dup_b",
                "sourceId": "text_004",
                "primitiveType": "text",
                "bbox": [20, 90, 60, 20],
                "ownerUnitId": "unit_dup_b",
                "sourceRefs": {"ocrTextBoxId": "ocr_004"},
                "text": "Delta",
            },
        ],
    }
    m31_report = {"schemaName": "M31ReconstructionUiTreeReport", "summary": {"primitiveOwnershipRate": 1.0}}
    m30_dsl = {
        "version": "0.1",
        "page": {"width": 300, "height": 200},
        "assets": [],
        "root": {
            "id": "root",
            "type": "frame",
            "children": [
                m30_text_node("m30_text_1", [30, 28, 50, 16], "Alpha", "ocr_001"),
                m30_text_node("m30_text_2", [96, 28, 44, 16], "Beta", "ocr_002"),
                m30_text_node("m30_text_3", [20, 90, 60, 20], "Gamma", "ocr_003"),
            ],
        },
    }
    m30_report = {"schemaName": "M30EvidenceGroundedDslMaterializationReport", "summary": {"materializedTextCount": 3}}

    tree_path = write_json(tmp_path / "m31" / "m31_reconstruction_tree.json", m31_tree)
    m31_report_path = write_json(tmp_path / "m31" / "m31_reconstruction_tree_report.json", m31_report)
    dsl_path = write_json(tmp_path / "m30" / "m30_materialized_dsl.json", m30_dsl)
    m30_report_path = write_json(tmp_path / "m30" / "m30_materialization_report.json", m30_report)

    result = extract_m37_hierarchy_readiness(
        m31_tree_path=str(tree_path),
        m31_report_path=str(m31_report_path),
        m30_dsl_path=str(dsl_path),
        m30_report_path=str(m30_report_path),
        output_dir=tmp_path / "m37",
    )

    summary = result.report["summary"]
    assert summary["m30NodeCount"] == 3
    assert summary["m31UnitCount"] == 4
    assert summary["mappableM30NodeCount"] == 3
    assert summary["safeContainerUnitCount"] == 1
    assert summary["unsafeContainerUnitCount"] == 3
    assert summary["duplicateUnitBBoxCount"] == 1
    assert summary["createdVisibleFrameCount"] == 0
    assert summary["dslChanged"] is False
    safe = result.report["safeContainerCandidates"][0]
    assert safe["unitId"] == "unit_safe"
    unit_reports = {item["unitId"]: item for item in result.report["unitReports"]}
    assert unit_reports["unit_safe"]["matchCounts"]["direct_match"] == 2
    assert "single_primitive_unit" in unit_reports["unit_micro"]["unsafeReasons"]
    assert "duplicate_unit_bbox" in unit_reports["unit_dup_a"]["unsafeReasons"]
    assert (tmp_path / "m37" / "m37_hierarchy_readiness_report.json").exists()
    assert json.loads(dsl_path.read_text(encoding="utf-8")) == m30_dsl


def test_m37_geometry_text_match_is_diagnostic_only(tmp_path: Path) -> None:
    m31_tree = {
        "schemaName": "M31ReconstructionUiTree",
        "schemaVersion": "0.1",
        "imageSize": {"width": 200, "height": 120},
        "root": {"id": "page", "kind": "page", "bbox": [0, 0, 200, 120], "children": ["unit_1"]},
        "nodes": [
            {
                "id": "unit_1",
                "kind": "reconstruction_unit",
                "unitKind": "row_unit",
                "visualKind": "text_block",
                "bbox": [20, 20, 120, 30],
                "children": ["prim_1", "prim_2"],
            }
        ],
        "primitiveRefs": [
            {"id": "prim_1", "sourceId": "text_001", "primitiveType": "text", "bbox": [20, 20, 40, 20], "ownerUnitId": "unit_1", "sourceRefs": {}, "text": "Alpha"},
            {"id": "prim_2", "sourceId": "text_002", "primitiveType": "text", "bbox": [80, 20, 40, 20], "ownerUnitId": "unit_1", "sourceRefs": {}, "text": "Beta"},
        ],
    }
    m30_dsl = {
        "version": "0.1",
        "page": {"width": 200, "height": 120},
        "assets": [],
        "root": {
            "id": "root",
            "type": "frame",
            "children": [
                m30_text_node("m30_text_1", [20, 20, 40, 20], "Alpha", "unrelated_1"),
                m30_text_node("m30_text_2", [80, 20, 40, 20], "Beta", "unrelated_2"),
            ],
        },
    }
    tree_path = write_json(tmp_path / "m31_tree.json", m31_tree)
    m31_report_path = write_json(tmp_path / "m31_report.json", {"summary": {}})
    dsl_path = write_json(tmp_path / "m30_dsl.json", m30_dsl)
    m30_report_path = write_json(tmp_path / "m30_report.json", {"summary": {}})

    result = extract_m37_hierarchy_readiness(
        m31_tree_path=str(tree_path),
        m31_report_path=str(m31_report_path),
        m30_dsl_path=str(dsl_path),
        m30_report_path=str(m30_report_path),
        output_dir=tmp_path / "m37",
    )

    unit = result.report["unitReports"][0]
    assert unit["safeContainerCandidate"] is True
    assert unit["matchCounts"]["geometry_text_match"] == 2
    assert result.report["summary"]["createdVisibleFrameCount"] == 0
    assert result.report["summary"]["dslChanged"] is False


def m30_text_node(node_id: str, bbox: list[int], text: str, source_text_box_id: str) -> dict:
    return {
        "id": node_id,
        "type": "text",
        "role": "m30_text_member",
        "layout": {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]},
        "content": {"text": text},
        "meta": {
            "m30Materialized": True,
            "sourceKind": "m2905_text_member",
            "sourceTextMemberId": f"text_member_{node_id}",
            "sourceTextBoxId": source_text_box_id,
            "sourceBBox": bbox,
        },
    }


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
